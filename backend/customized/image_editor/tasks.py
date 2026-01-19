import logging
import time
import requests
import os
import base64
import json
from pathlib import Path
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from celery import shared_task
from .models import ImageEditTask
from .aiCallback import AICallback
from .cache_manager import TaskCacheManager
from .db_batch_manager import db_optimizer
from .config_manager import config_manager
# 导入批量回调任务，确保它们被Celery发现
from .tasks_batch import trigger_batch_send, send_single_callback, cleanup_stuck_callbacks, check_and_flush_callbacks
# dotenv load
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)


@shared_task(bind=True, name='image_editor.reload_worker_config')
def reload_worker_config(self, config_name=None):
    """
    重新加载worker中的配置
    这个任务会在每个worker中执行，确保配置更新
    """
    try:
        # 清除并重新加载配置
        config_manager.reload()
        logger.info(f"Worker {self.request.hostname} 已重新加载配置: {config_name}")
        return f"配置重载成功: {config_name}"
    except Exception as e:
        logger.error(f"Worker {self.request.hostname} 重载配置失败: {e}")
        return f"配置重载失败: {str(e)}"

def save_image_to_file(task_id, image_base64, image_format='png'):
    """保存base64图片到文件，并调整尺寸
    
    Args:
        task_id: 任务ID
        image_base64: base64编码的图片数据
        image_format: 图片格式，默认png
    
    Returns:
        tuple: (相对路径, 调整后的base64数据) 如 ('image_editor/task_id.png', 'base64_string')
    """
    try:
        from PIL import Image
        import io
        
        # 创建媒体目录路径
        media_root = getattr(settings, 'MEDIA_ROOT')
        image_dir = Path(media_root) / 'image_editor'
        image_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名和路径
        filename = f"{task_id}.{image_format}"
        file_path = image_dir / filename
        
        # 解码图片数据
        image_data = base64.b64decode(image_base64)
        
        # 使用PIL打开图片并调整尺寸
        img = Image.open(io.BytesIO(image_data))
        
        # 如果是PNG格式，保持RGBA模式；否则转换为RGB
        if img.mode == 'RGBA' and image_format.lower() == 'png':
            # 保持透明通道
            pass
        elif img.mode == 'RGBA':
            # 非PNG格式，创建白色背景并合成
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 计算调整后的尺寸（以350为基准，按较小边等比例缩放）
        width, height = img.size
        base_size = 350
        
        # 以较小的边为基准进行缩放
        if width == height:
            # 宽高相等，直接缩放到350x350
            new_width = base_size
            new_height = base_size
        elif width < height:
            # 宽度较小，以宽度为基准
            new_width = base_size
            new_height = int(height * base_size / width)
        else:
            # 高度较小，以高度为基准
            new_height = base_size
            new_width = int(width * base_size / height)
        
        # 调整图片尺寸
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.info(f"图片尺寸调整 - 任务ID: {task_id}, 原始: {width}x{height}, 调整后: {new_width}x{new_height}")
        
        # 保存调整后的图片到文件
        if image_format.lower() == 'png':
            img_resized.save(file_path, 'PNG', optimize=True)
        else:
            img_resized.save(file_path, image_format.upper(), quality=95, optimize=True)
        
        # 将调整后的图片转换为base64
        buffer = io.BytesIO()
        if image_format.lower() == 'png':
            img_resized.save(buffer, 'PNG', optimize=True)
        else:
            img_resized.save(buffer, image_format.upper(), quality=95, optimize=True)
        buffer.seek(0)
        resized_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        # 返回相对路径和调整后的base64
        relative_path = f"image_editor/{filename}"
        logger.info(f"图片已保存到文件 - 任务ID: {task_id}, 路径: {relative_path}")
        return relative_path, resized_base64
    except Exception as e:
        logger.error(f"保存图片文件失败 - 任务ID: {task_id}, 错误: {str(e)}")
        return None, None

def load_image_from_file(image_path):
    """从文件加载图片为base64
    
    Args:
        image_path: 图片相对路径
    
    Returns:
        str: base64编码的图片数据，失败返回None
    """
    try:
        media_root = getattr(settings, 'MEDIA_ROOT', '/Users/chagee/Repos/X/backend/media')
        file_path = Path(media_root) / image_path
        
        if not file_path.exists():
            logger.error(f"图片文件不存在 - 路径: {image_path}")
            return None
        
        with open(file_path, 'rb') as f:
            image_data = f.read()
        
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        logger.debug(f"从文件加载图片成功 - 路径: {image_path}")
        return image_base64
    except Exception as e:
        logger.error(f"加载图片文件失败 - 路径: {image_path}, 错误: {str(e)}")
        return None

def execute_callback(task, prompt="", use_batch=None):
    """执行回调函数
    
    Args:
        task: ImageEditTask 对象
        prompt: 提示词
        use_batch: 是否使用批量回调（None=自动判断，True=强制批量，False=强制立即）
    """
    if not task.callback_url:
        logger.debug(f"无需执行回调 - 任务ID: {task.task_id}")
        # 标记为无需回调
        from .db_batch_manager import db_optimizer
        db_optimizer.update_task_status(
            str(task.task_id),
            None,  # 不更新主状态
            {
                'callback_status': 'not_required'
            }
        )
        db_optimizer.flush()  # 立即刷新无需回调状态
        return
    
    # 判断是否使用批量回调
    from .performance_settings import BATCH_CALLBACK_CONFIG
    
    if use_batch is None:
        use_batch = BATCH_CALLBACK_CONFIG.get('ENABLED', False)
    
    # 失败的任务优先立即回调
    if task.status == 'failed' and use_batch:
        # 失败任务也可以批量，但优先级更高
        use_batch = True  # 可以根据业务需求调整
    
    logger.info(f"准备执行回调 - 任务ID: {task.task_id}, 批量模式: {use_batch}, URL: {task.callback_url}")
    
    callback_start = time.time()  # 记录回调开始时间
    try:
        # 准备回调数据
        if task.status == 'success':
            # 如果有文件路径，从文件加载base64；否则使用数据库中的base64
            result_image_base64 = task.result_image
            if task.result_image_path:
                loaded_image = load_image_from_file(task.result_image_path)
                if loaded_image:
                    result_image_base64 = loaded_image
                    logger.debug(f"从文件加载图片用于回调 - 任务ID: {task.task_id}")
            
            callback_data = {
                "task_id": str(task.task_id),
                "status": task.status,
                "result_image": result_image_base64,
                "processing_time": task.processing_time
            }
        elif task.status == 'failed':
            callback_data = {
                "task_id": str(task.task_id),
                "status": task.status,
                "error_code": task.error_code,
                "error_message": task.error_message,
                "error_details": task.error_details,
                "completed_at": (task.completed_at if isinstance(task.completed_at, str) else task.completed_at.isoformat()) if hasattr(task, 'completed_at') and task.completed_at else None
            }
        else:
            logger.warning(f"未知的任务状态 - 任务ID: {task.task_id}, 状态: {task.status}")
            return
        
        # 根据配置选择回调方式
        if use_batch:
            # 使用基于Redis的全局批量回调
            from .callback_batcher_redis import get_redis_batcher
            batcher = get_redis_batcher()
            
            # 处理 created_at，可能是字符串或 datetime 对象
            created_at_value = None
            if hasattr(task, 'created_at') and task.created_at:
                if isinstance(task.created_at, str):
                    created_at_value = task.created_at
                else:
                    try:
                        created_at_value = task.created_at.isoformat()
                    except:
                        created_at_value = str(task.created_at)
            
            batch_data = {
                'url': task.callback_url,
                'task_id': str(task.task_id),
                'status': task.status,
                'data': callback_data,
                'prompt': prompt,
                'created_at': created_at_value
            }
            
            success = batcher.add_callback(batch_data)
            if success:
                logger.info(f"回调已加入Redis全局队列 - 任务ID: {task.task_id}")
                
                # 获取并记录队列状态
                stats = batcher.get_queue_stats()
                logger.debug(f"全局回调队列状态 - 待处理: {stats.get('pending', 0)}, "
                           f"处理中: {stats.get('processing', 0)}")
            else:
                logger.error(f"加入Redis队列失败，尝试立即发送 - 任务ID: {task.task_id}")
                # 如果加入批量队列失败，降级为立即发送
                _send_immediate_callback(task, callback_data, prompt)
        else:
            # 立即发送回调
            _send_immediate_callback(task, callback_data, prompt)
            
    except Exception as e:
        logger.error(f"回调处理失败 - 任务ID: {task.task_id}, 错误: {str(e)}")
        # 记录回调异常状态
        if hasattr(task, 'callback_status'):
            task.callback_status = 'failed'
            task.callback_error_message = f"回调处理异常: {str(e)[:500]}"
            task.save(update_fields=['callback_status', 'callback_error_message'])
    finally:
        # 记录回调耗时
        if hasattr(task, 'callback_duration'):
            task.callback_duration = time.time() - callback_start
            logger.debug(f"回调耗时 - 任务ID: {task.task_id}, 耗时: {task.callback_duration:.2f}秒")

def _send_immediate_callback(task, callback_data, prompt):
    """立即发送回调（内部函数）"""
    from django.utils import timezone
    from .db_batch_manager import db_optimizer
    
    # 更新回调尝试次数
    if hasattr(task, 'callback_attempts'):
        task.callback_attempts += 1
    
    # 记录回调发生时间（无论成功还是失败）
    callback_occurred_at = timezone.now()
    if hasattr(task, 'callback_occurred_at'):
        task.callback_occurred_at = callback_occurred_at
    
    try:
        # 使用任务的callback_url初始化AICallback，这样会自动推断环境并使用正确的密钥
        ai_callback = AICallback(callback_url=task.callback_url)
        
        response = None
        if task.status == 'success':
            success_data = ai_callback.create_success_callback_data(callback_data, prompt=prompt)
            # 不需要再传递callback_url，因为已经在初始化时设置了
            response = ai_callback.send_callback(success_data)
            logger.info(f"成功回调已立即发送 - 任务ID: {task.task_id}")
        elif task.status == 'failed':
            failed_data = ai_callback.create_failed_callback_data(callback_data, prompt=prompt)
            # 不需要再传递callback_url，因为已经在初始化时设置了
            response = ai_callback.send_callback(failed_data)
            logger.info(f"失败回调已立即发送 - 任务ID: {task.task_id}")
        
        # 记录回调成功状态
        callback_status = 'success'
        callback_response_code = response.status_code if response and hasattr(response, 'status_code') else None
        callback_error_message = ''
        
        # 更新任务对象属性（如果有）
        if hasattr(task, 'callback_status'):
            task.callback_status = callback_status
            task.callback_response_code = callback_response_code
            task.callback_error_message = callback_error_message
        
        # 使用批量写入优化器更新数据库
        db_optimizer.update_task_status(
            str(task.task_id),
            None,  # 不更新主状态
            {
                'callback_status': callback_status,
                'callback_attempts': task.callback_attempts if hasattr(task, 'callback_attempts') else 1,
                'callback_occurred_at': callback_occurred_at,
                'callback_response_code': callback_response_code,
                'callback_error_message': callback_error_message
            }
        )
        db_optimizer.flush()  # 立即刷新回调状态
            
    except Exception as e:
        logger.error(f"立即回调失败 - 任务ID: {task.task_id}, 错误: {str(e)}")
        
        # 记录回调失败状态
        callback_status = 'failed'
        callback_error_message = str(e)[:500]  # 限制错误信息长度
        
        # 更新任务对象属性（如果有）
        if hasattr(task, 'callback_status'):
            task.callback_status = callback_status
            task.callback_error_message = callback_error_message
        
        # 使用批量写入优化器更新数据库
        db_optimizer.update_task_status(
            str(task.task_id),
            None,  # 不更新主状态
            {
                'callback_status': callback_status,
                'callback_attempts': task.callback_attempts if hasattr(task, 'callback_attempts') else 1,
                'callback_occurred_at': callback_occurred_at if 'callback_occurred_at' in locals() else timezone.now(),
                'callback_error_message': callback_error_message
            }
        )
        db_optimizer.flush()  # 立即刷新回调失败状态

@shared_task(bind=True, max_retries=0)
def process_image_edit_task(self, task_data):
    """处理图片编辑任务
    
    Args:
        task_data: 任务数据，可以是字符串(task_id)或字典(包含完整任务信息)
    """
    # 兼容旧版本：如果传入的是字符串，则认为是task_id
    if isinstance(task_data, str):
        task_id = task_data
        logger.info(f"开始处理图片编辑任务（兼容模式） - 任务ID: {task_id}")
        # 从数据库获取任务
        task = ImageEditTask.objects.get(task_id=task_id)
        # 添加 username 属性以保持兼容性
        task.username = task.user.username if hasattr(task, 'user') else 'unknown'
        logger.info(f"任务获取成功 - 用户: {task.username}, Prompt: {task.prompt if task.prompt else 'None'}")
    else:
        # 新版本：从传入的数据中获取任务信息
        task_id = task_data['task_id']
        logger.info(f"开始处理图片编辑任务（优化模式） - 任务ID: {task_id}")
        
        # 不再查询数据库！直接使用 Redis 中的数据创建一个任务对象
        # 创建一个简单的对象来存储任务数据，避免数据库查询
        class TaskData:
            def __init__(self, data):
                self.task_id = data['task_id']
                self.image_url = data['image_url']
                self.prompt = data['prompt']
                self.callback_url = data.get('callback_url')
                self.username = data.get('username', 'unknown')
                self.started_at = data.get('started_at')
                self.created_at = data.get('created_at')  # 添加 created_at 属性
                # 初始化其他需要的属性
                self.status = 'processing'
                self.result_image = None
                self.result_image_path = None
                self.error_code = None
                self.error_message = None
                self.error_details = None
                self.processing_time = None
                self.completed_at = None
                self.actual_prompt = None
                self.generation_model = None
                self.generation_guidance_scale = None
                self.pet_detection_result = None
                self.pet_detection_model = None
                self.pet_description = None
                self.consistency_check = None
                self.consistency_score = None
                self.generated_image_url = None
                self.generation_seed = None
                self.bg_removal_attempted = None
                self.bg_removal_retry_count = 0  # 设置默认值为 0，而不是 None
                self.bg_removal_success = None
                self.bg_removed_source_url = None
                self.bg_removal_error = None
                # 各流程执行时长
                self.image_validation_duration = None
                self.pet_detection_duration = None
                self.text_to_image_duration = None
                self.consistency_check_duration = None
                self.bg_removal_duration = None
                self.callback_duration = None
                # 初始化 _update_fields 用于批量数据库更新
                self._update_fields = {}
        
        task = TaskData(task_data)
        
        # 记录从消息中获取的用户信息，避免额外查询
        logger.info(f"任务数据加载成功（优化模式） - 用户: {task.username}, Prompt: {task.prompt if task.prompt else 'None'}")
    
    try:
        # 使用 started_at 作为计时起点
        if hasattr(task, 'started_at') and task.started_at:
            if isinstance(task.started_at, str):
                from dateutil import parser
                start_time = parser.parse(task.started_at).timestamp()
            else:
                start_time = task.started_at.timestamp()
        elif isinstance(task_data, dict) and task_data.get('started_at'):
            from dateutil import parser
            start_time = parser.parse(task_data['started_at']).timestamp()
        else:
            start_time = time.time()
            task.started_at = timezone.now()
            # 注释掉中间状态的数据库更新，只在最终成功/失败时写入
            # db_optimizer.update_task_status(
            #     str(task_id),
            #     'processing',
            #     {'started_at': task.started_at}
            # )
        

        ################## 这一步在真实业务中完全不需要 ##################
        # # 1. 下载图片并验证格式、尺寸、宽高比
        # try:
        #     logger.debug(f"开始下载图片 - URL: {task.image_url}")
        #     response = requests.get(task.image_url, timeout=10)
        #     if response.status_code != 200:
        #         raise Exception(f"图片下载失败，状态码: {response.status_code}")
        #     logger.debug(f"图片下载成功 - 大小: {len(response.content)} bytes")
            
        #     # 验证图片格式、尺寸、宽高比
        #     import io
        #     from PIL import Image
            
        #     # 检查文件大小（不超过 10MB）
        #     content_length = len(response.content)
        #     if content_length > 10 * 1024 * 1024:  # 10MB
        #         logger.warning(f"图片文件过大 - 任务ID: {task_id}, 大小: {content_length / 1024 / 1024:.2f}MB")
        #         raise Exception(f"图片文件过大：{content_length / 1024 / 1024:.2f}MB，超过 10MB 限制")
            
        #     # 使用 PIL 打开图片
        #     try:
        #         img = Image.open(io.BytesIO(response.content))
                
        #         # 检查图片格式
        #         if img.format not in ['JPEG', 'PNG']:
        #             logger.warning(f"不支持的图片格式 - 任务ID: {task_id}, 格式: {img.format}")
        #             raise Exception(f"不支持的图片格式：{img.format}，仅支持 JPG、PNG")
                
        #         # 检查图片尺寸
        #         width, height = img.size
        #         logger.debug(f"图片尺寸验证 - 任务ID: {task_id}, 尺寸: {width}x{height}")
        #         if width <= 14 or height <= 14:
        #             logger.warning(f"图片尺寸过小 - 任务ID: {task_id}, 尺寸: {width}x{height}")
        #             raise Exception(f"图片尺寸过小：{width}x{height}，宽高必须大于 14 像素")
                
        #         # 检查宽高比
        #         aspect_ratio = width / height
        #         if aspect_ratio <= 1/3 or aspect_ratio >= 3:
        #             logger.warning(f"图片宽高比不符合要求 - 任务ID: {task_id}, 宽高比: {aspect_ratio:.2f}")
        #             raise Exception(f"图片宽高比不符合要求：{aspect_ratio:.2f}，必须在 (1/3, 3) 范围内")
                
        #         # 保存图片验证信息到数据库 - 使用批量写入优化
        #         db_optimizer.update_task_status(
        #             str(task.task_id),
        #             task.status,
        #             {
        #                 'image_format': img.format,
        #                 'image_width': width,
        #                 'image_height': height,
        #                 'image_size_bytes': content_length,
        #                 'image_aspect_ratio': aspect_ratio
        #             }
        #         )
                
        #         logger.info(f"图片验证通过 - 任务ID: {task_id}, 格式: {img.format}, 尺寸: {width}x{height}")
                    
        #     except Exception as e:
        #         if "cannot identify image file" in str(e):
        #             logger.error(f"图片文件损坏或编码异常 - 任务ID: {task_id}")
        #             raise Exception("图片文件损坏或编码异常")
        #         raise
        # except Exception as e:
        #     logger.error(f"图片下载或验证失败 - 任务ID: {task_id}, 错误: {str(e)}")
        #     # 根据错误类型设置不同的错误码
        #     if "状态码" in str(e):
        #         error_code = 'E3002'  # 图片下载失败
        #     elif "文件过大" in str(e):
        #         error_code = 'E3008'  # 图片文件过大
        #     elif "不支持的图片格式" in str(e):
        #         error_code = 'E3003'  # 图片格式不支持
        #     elif "尺寸过小" in str(e) or "宽高比" in str(e):
        #         error_code = 'E3004'  # 图片尺寸不符合要求
        #     elif "损坏或编码异常" in str(e):
        #         error_code = 'E3017'  # 图片解码失败
        #     else:
        #         error_code = 'E3002'  # 默认为下载失败
            
        #     # 使用批量写入优化
        #     processing_time = time.time() - start_time
        #     db_optimizer.update_task_status(
        #         str(task_id),
        #         'failed',
        #         {
        #             'error_code': error_code,
        #             'error_message': "图片处理失败",
        #             'error_details': str(e),
        #             'processing_time': processing_time,
        #             'completed_at': timezone.now()
        #         }
        #     )
        #     db_optimizer.flush()  # 立即刷新失败状态
            
        #     # 更新本地task对象以供后续使用
        #     task.status = 'failed'
        #     task.error_code = error_code
        #     task.error_message = "图片处理失败"
        #     task.error_details = str(e)
        #     task.processing_time = processing_time
        #     task.completed_at = timezone.now()
        #     logger.error(f"任务标记为失败 - 任务ID: {task_id}, 错误码: {task.error_code}")
            
        #     # 更新缓存
        #     TaskCacheManager.update_task_status(
        #         str(task_id), 
        #         'failed',
        #         {
        #             'error_code': task.error_code,
        #             'error_message': task.error_message,
        #             'error_details': task.error_details,
        #             'completed_at': task.completed_at.isoformat()
        #         }
        #     )
            
        #     # 执行回调
        #     execute_callback(task)
        #     return
        
        # 2. 调用AI模型生成图片
        try:
            # 从.env环境变量获取API密钥，如果没有则使用默认值
            api_key = os.getenv("DOUBAO_API_KEY")
            if not api_key:
                logger.warning(f"未找到API密钥 - 任务ID: {task_id}")
                return
            
            # 日志中掩码API密钥中间段，仅显示前3和后3位
            masked_key = api_key
            if api_key and len(api_key) > 6:
                masked_key = f"{api_key[:3]}{'*' * (len(api_key) - 6)}{api_key[-3:]}"
            logger.info(f"使用API密钥: {masked_key} (来源: {'环境变量' if os.getenv('DOUBAO_API_KEY') else '默认值'})")
            
            # 初始化图像生成器
            from .doubao_seededit_3_0_i2_seed import DoubaoImageGenerator
            # 获取火山引擎CV服务的密钥（用于抠图）
            volc_access_key = os.getenv("VOLC_ACCESS_KEY")
            volc_secret_key = os.getenv("VOLC_SECRET_KEY")
            generator = DoubaoImageGenerator(api_key, volc_access_key, volc_secret_key)
            logger.info(f"图像生成器初始化成功 - 任务ID: {task_id}")
            
            # 根据要求，要对图片做一个预检测，看看图片的内容是否合规，是否存在暴力，色情这种不合规内容以及图片内容的主体是不是动物, 且不能包括人类
            logger.info(f"开始进行图片内容检测 - 任务ID: {task_id}, 模型: doubao-1.5-vision-pro-250328")
            pet_detection_start = time.time()  # 记录宠物检测开始时间
            try:
                check_result = generator.check_object_is_only_animal(task.image_url)
                task.pet_detection_duration = time.time() - pet_detection_start  # 记录宠物检测耗时
                if check_result is None or (isinstance(check_result, dict) and check_result.get("error")):
                    # 检测服务异常
                    logger.error(f"图片内容检测服务异常 - 任务ID: {task_id}")
                    
                    # 构建完整的错误详情
                    if isinstance(check_result, dict) and "error_details" in check_result:
                        error_details_obj = check_result["error_details"]
                        error_details_str = json.dumps(error_details_obj, ensure_ascii=False)
                    else:
                        error_details_str = "宠物检测模型服务不可用"
                    
                    # 只更新本地task对象，不写数据库
                    processing_time = time.time() - start_time
                    task.status = 'failed'
                    task.error_code = 'E4005'
                    task.error_message = "宠物检测服务异常"
                    task.error_details = error_details_str
                    task.processing_time = processing_time
                    task.completed_at = timezone.now()
                    
                    # 保存要更新的字段，稍后写入
                    task._update_fields = {
                        'error_code': 'E4005',  # 宠物检测模型服务不可用
                        'error_message': "宠物检测服务异常",
                        'error_details': error_details_str,
                        'processing_time': processing_time,
                        'completed_at': timezone.now()
                    }
                    logger.error(f"任务标记为失败 - 任务ID: {task_id}, 错误码: E4005")
                    
                    # 更新缓存
                    TaskCacheManager.update_task_status(
                        str(task_id),
                        'failed',
                        {
                            'error_code': task.error_code,
                            'error_message': task.error_message,
                            'error_details': task.error_details,
                            'completed_at': task.completed_at.isoformat()
                        }
                    )
                    
                    # 执行回调
                    execute_callback(task, prompt="")
                    
                    # 回调完成后写入数据库
                    if hasattr(task, '_update_fields'):
                        db_optimizer.update_task_status(
                            str(task_id),
                            'failed',
                            task._update_fields
                        )
                        # 依赖批量管理器自动刷新（100ms）
                        logger.debug(f"数据库更新已加入队列（宠物检测异常） - 任务ID: {task_id}")
                    return
                elif check_result and not check_result.get("error") and check_result.get("object_is_only_animal"):
                    logger.info(f"图片内容符合要求 - 任务ID: {task_id}")
                    # 获取宠物描述
                    pet_description = check_result.get("pet_description")
                    if pet_description:
                        logger.info(f"宠物描述 - 任务ID: {task_id}, 描述: {pet_description}")
                    # 只更新本地对象，不写数据库（等最终成功/失败时一次性写入）
                    task.pet_detection_result = True
                    task.pet_detection_model = 'doubao-1.5-vision-pro-250328'
                    task.pet_description = pet_description
                else:
                    logger.info(f"图片内容不符合要求 - 任务ID: {task_id}, 原因: {check_result['reason_for_false']}")
                    # 保存宠物检测失败信息 - 使用批量写入优化
                    # 因为check_result['reason_for_false']的结果是'A','B','C','D','E','F'等，所以要根据不同的结果，设置不同的错误码
                    if check_result['reason_for_false'] == 'A':
                        # 暴力内容 - 使用4002无法识别图片内容
                        task.error_code = 'E4002'
                        task.error_message = "无法识别图片内容"
                        task.error_details = "图片内容模糊或无法识别"
                    elif check_result['reason_for_false'] == 'B':
                        # 色情内容 - 使用4002无法识别图片内容
                        task.error_code = 'E4002'
                        task.error_message = "无法识别图片内容"
                        task.error_details = "图片内容模糊或无法识别"
                    elif check_result['reason_for_false'] == 'C':
                        # 主体不是动物
                        task.error_code = 'E4001'
                        task.error_message = "非宠物图片"
                        task.error_details = "检测到图片主体不是宠物"
                    elif check_result['reason_for_false'] == 'D':
                        # 包含人类
                        task.error_code = 'E4007'
                        task.error_message = "图中存在人类"
                        task.error_details = "不允许处理该图片"
                    elif check_result['reason_for_false'] == 'E':
                        # 图片质量过低
                        task.error_code = 'E4003'
                        task.error_message = "图片质量过低"
                        task.error_details = "图片分辨率或清晰度不足以进行检测"
                    elif check_result['reason_for_false'] == 'F':
                        # 多个主体
                        task.error_code = 'E4004'
                        task.error_message = "多个主体检测"
                        task.error_details = "图片中包含多个主体，无法确定主要宠物"
                    else:
                        # 未知原因
                        task.error_code = 'E4002'
                        task.error_message = "无法识别图片内容"
                        task.error_details = "图片内容模糊或无法识别"
                    
                    # 使用批量写入优化
                    processing_time = time.time() - start_time
                    db_optimizer.update_task_status(
                        str(task_id),
                        'failed',
                        {
                            'pet_detection_result': False,
                            'pet_detection_reason': check_result['reason_for_false'],
                            'pet_detection_model': 'doubao-1.5-vision-pro-250328',
                            'error_code': task.error_code,
                            'error_message': task.error_message,
                            'error_details': task.error_details,
                            'processing_time': processing_time,
                            'completed_at': timezone.now()
                        }
                    )
                    # 依赖批量管理器自动刷新（100ms）
                    
                    # 更新本地task对象的状态（重要：必须设置status为failed，否则回调无法正确识别失败状态）
                    task.status = 'failed'
                    task.processing_time = processing_time
                    task.completed_at = timezone.now()
                    logger.error(f"任务标记为失败 - 任务ID: {task_id}, 错误码: {task.error_code}")
                    
                    # 更新缓存
                    TaskCacheManager.update_task_status(
                        str(task_id),
                        'failed',
                        {
                            'error_code': task.error_code,
                            'error_message': task.error_message,
                            'error_details': task.error_details,
                            'completed_at': task.completed_at.isoformat()
                        }
                    )
                    
                    # 执行回调
                    execute_callback(task, prompt="")
                    
                    # 回调完成后写入数据库
                    if hasattr(task, '_update_fields'):
                        db_optimizer.update_task_status(
                            str(task_id),
                            'failed',
                            task._update_fields
                        )
                        # 依赖批量管理器自动刷新（100ms）
                        logger.debug(f"数据库更新已加入队列（宠物检测失败） - 任务ID: {task_id}")
                    return
            except Exception as check_error:
                # 如果异常已经在上面处理过了，直接重新抛出
                if "图片内容不符合要求" in str(check_error) or "宠物检测服务异常" in str(check_error):
                    raise check_error
                else:
                    # 未预期的异常，当作服务异常处理
                    logger.error(f"图片内容检测发生未预期异常 - 任务ID: {task_id}, 错误: {str(check_error)}")
                    
                    # 构建完整的错误详情
                    error_details_obj = {
                        "error_type": "UnexpectedError",
                        "error_message": f"图片内容检测发生未预期异常: {str(check_error)}",
                        "exception_type": type(check_error).__name__,
                        "exception_details": str(check_error)
                    }
                    error_details_str = json.dumps(error_details_obj, ensure_ascii=False)
                    
                    # 只更新本地task对象，不写数据库
                    processing_time = time.time() - start_time
                    task.status = 'failed'
                    task.error_code = 'E4005'
                    task.error_message = "宠物检测服务异常"
                    task.error_details = error_details_str
                    task.processing_time = processing_time
                    task.completed_at = timezone.now()
                    
                    # 保存要更新的字段，稍后写入
                    task._update_fields = {
                        'error_code': 'E4005',  # 宠物检测模型服务不可用
                        'error_message': "宠物检测服务异常",
                        'error_details': error_details_str,
                        'processing_time': processing_time,
                        'completed_at': timezone.now()
                    }
                    logger.error(f"任务标记为失败 - 任务ID: {task_id}, 错误码: E4005")
                    
                    # 更新缓存
                    TaskCacheManager.update_task_status(
                        str(task_id),
                        'failed',
                        {
                            'error_code': task.error_code,
                            'error_message': task.error_message,
                            'error_details': task.error_details,
                            'completed_at': task.completed_at.isoformat()
                        }
                    )
                    
                    # 执行回调
                    execute_callback(task, prompt="")
                    
                    # 回调完成后写入数据库
                    if hasattr(task, '_update_fields'):
                        db_optimizer.update_task_status(
                            str(task_id),
                            'failed',
                            task._update_fields
                        )
                        # 依赖批量管理器自动刷新（100ms）
                        logger.debug(f"数据库更新已加入队列（宠物检测服务异常） - 任务ID: {task_id}")
                    return


            # 2. 构建文生图的提示词
            # 结合宠物描述和风格化要求
            if hasattr(task, 'pet_description') and task.pet_description:
                # 获取风格化提示词
                style_prompt = config_manager.get_style_prompt()
                
                # 检查环境变量，决定风格提示词的拼接顺序
                style_prompt_first = os.getenv('STYLE_PROMPT_FIRST', 'false').lower() in ['true', '1', 'yes']
                
                # 根据环境变量组合宠物描述和风格化要求
                if style_prompt_first:
                    combined_prompt = f"{style_prompt}\n{task.pet_description}"
                    logger.info(f"使用组合提示词（风格在前） - 任务ID: {task_id}")
                else:
                    combined_prompt = f"{task.pet_description}\n{style_prompt}"
                    logger.info(f"使用组合提示词（描述在前） - 任务ID: {task_id}")
                    
                logger.info(f"宠物描述部分: {task.pet_description}")
                logger.info(f"风格化要求: {style_prompt}")
            else:
                # 如果没有宠物描述（不应该发生），使用用户原始提示词或默认提示词
                if not task.prompt or task.prompt.strip() == "":
                    combined_prompt = config_manager.get_default_prompt()
                    logger.warning(f"未找到宠物描述，使用默认提示词 - 任务ID: {task_id}")
                else:
                    combined_prompt = task.prompt
                    logger.warning(f"未找到宠物描述，使用用户提示词 - 任务ID: {task_id}")
            
            # 只更新本地对象，不写数据库（等最终成功/失败时一次性写入）
            task.actual_prompt = combined_prompt
            task.generation_model = config_manager.get_t2i_model()  # 使用文生图模型
            task.generation_guidance_scale = config_manager.get_t2i_guidance_scale()  # 使用文生图引导系数
            
            # 调用文生图API生成图片
            logger.info(f"开始调用文生图模型 - 任务ID: {task_id}, 模型: {task.generation_model}")
            text_to_image_start = time.time()  # 记录文生图开始时间
            api_result, used_seed = generator.generate_image_from_text(
                prompt=task.actual_prompt,
                model=task.generation_model,
                size=config_manager.get_t2i_size(),
                guidance_scale=task.generation_guidance_scale
                # 其他参数在generator内部从配置获取
            )
            task.text_to_image_duration = time.time() - text_to_image_start  # 记录文生图耗时
            
            # 处理API响应
            if api_result and "data" in api_result and len(api_result["data"]) > 0:
                generated_url = api_result["data"][0]["url"]
                logger.debug(f"获取生成图片URL成功 - 任务ID: {task_id}")
                
                # 只更新本地对象，不写数据库（等最终成功/失败时一次性写入）
                task.generated_image_url = generated_url
                task.generation_seed = used_seed
                
                # 3. 跳过一致性检查（文生图不需要与原图比较）
                logger.info(f"文生图模式，跳过一致性检测 - 任务ID: {task_id}")
                # 设置一致性检查为通过（因为没有原图参考）
                task.consistency_check = True
                task.consistency_score = 100.0  # 默认满分
                
                # 注释掉原有的一致性检查代码
                '''
                if consistency_result is None or (isinstance(consistency_result, dict) and consistency_result.get("error")):
                    # 一致性检测服务异常
                    logger.error(f"一致性检测服务异常 - 任务ID: {task_id}")
                    
                    # 构建完整的错误详情
                    if isinstance(consistency_result, dict) and "error_details" in consistency_result:
                        error_details_obj = consistency_result["error_details"]
                        error_details_str = json.dumps(error_details_obj, ensure_ascii=False)
                    else:
                        error_details_str = "一致性检测服务暂时不可用"
                    
                    # 只更新本地task对象，不写数据库
                    processing_time = time.time() - start_time
                    task.status = 'failed'
                    task.error_code = 'E2002'
                    task.error_message = "生成结果质量不符合预期"
                    task.error_details = error_details_str
                    task.processing_time = processing_time
                    task.completed_at = timezone.now()
                    
                    # 保存要更新的字段，稍后写入
                    task._update_fields = {
                        'error_code': 'E2002',  # 生成结果质量不符合预期
                        'error_message': "生成结果质量不符合预期",
                        'error_details': error_details_str,
                        'processing_time': processing_time,
                        'completed_at': timezone.now()
                    }
                    
                    # 更新缓存
                    TaskCacheManager.update_task_status(
                        str(task_id),
                        'failed',
                        {
                            'error_code': task.error_code,
                            'error_message': task.error_message,
                            'error_details': task.error_details,
                            'completed_at': task.completed_at.isoformat()
                        }
                    )
                    
                    execute_callback(task, prompt=task.actual_prompt if hasattr(task, 'actual_prompt') else task.prompt)
                    
                    # 回调完成后写入数据库
                    if hasattr(task, '_update_fields'):
                        db_optimizer.update_task_status(
                            str(task_id),
                            'failed',
                            task._update_fields
                        )
                        # 依赖批量管理器自动刷新（100ms）
                        logger.debug(f"数据库更新已加入队列（生成失败） - 任务ID: {task_id}")
                    return
                
                # 检查一致性结果
                if consistency_result and not consistency_result.get("error") and not consistency_result.get("is_consistent", False):
                    # 一致性检测未通过
                    inconsistent_reason = consistency_result.get("inconsistent_reason", "F")
                    score = consistency_result.get("score", 0)
                    logger.warning(f"一致性检测未通过 - 任务ID: {task_id}, 原因: {inconsistent_reason}, 分数: {score}")
                    
                    # 保存一致性检测结果 - 使用批量写入优化
                    
                    task.status = 'failed'
                    # 根据不同的原因设置错误码
                    if inconsistent_reason == "A":
                        task.error_code = 'E2001'  # 生成结果与原图偏差过大
                        task.error_message = "生成结果与原图偏差过大"
                        task.error_details = "图像相似度评分低于阈值"
                    elif inconsistent_reason == "B":
                        task.error_code = 'E2002'  # 生成结果质量不符合预期
                        task.error_message = "生成结果质量不符合预期"
                        task.error_details = "图像质量评分过低"
                    elif inconsistent_reason == "C":
                        task.error_code = 'E2002'  # 生成结果质量不符合预期
                        task.error_message = "生成结果质量不符合预期"
                        task.error_details = "存在严重畸形或错位"
                    elif inconsistent_reason == "D":
                        task.error_code = 'E2002'  # 生成结果质量不符合预期
                        task.error_message = "生成结果质量不符合预期"
                        task.error_details = "生成不完整或有缺失部分"
                    elif inconsistent_reason == "E":
                        task.error_code = 'E2002'  # 生成结果质量不符合预期
                        task.error_message = "生成结果质量不符合预期"
                        task.error_details = "其他严重问题"
                    else:
                        task.error_code = 'E2002'  # 生成结果质量不符合预期
                        task.error_message = "生成结果质量不符合预期"
                        task.error_details = f"一致性分数: {score}/100"
                    
                    # 只更新本地task对象，不写数据库
                    processing_time = time.time() - start_time
                    task.processing_time = processing_time
                    task.completed_at = timezone.now()
                    
                    # 保存要更新的字段，稍后写入
                    task._update_fields = {
                        'consistency_check': False,
                        'consistency_score': score,
                        'consistency_reason': inconsistent_reason,
                        'error_code': task.error_code,
                        'error_message': task.error_message,
                        'error_details': task.error_details,
                        'processing_time': processing_time,
                        'completed_at': timezone.now()
                    }
                    
                    # 更新缓存
                    TaskCacheManager.update_task_status(
                        str(task_id),
                        'failed',
                        {
                            'error_code': task.error_code,
                            'error_message': task.error_message,
                            'error_details': task.error_details,
                            'completed_at': task.completed_at.isoformat()
                        }
                    )
                    
                    execute_callback(task, prompt=task.actual_prompt if hasattr(task, 'actual_prompt') else task.prompt)
                    
                    # 回调完成后写入数据库
                    if hasattr(task, '_update_fields'):
                        db_optimizer.update_task_status(
                            str(task_id),
                            'failed',
                            task._update_fields
                        )
                        # 依赖批量管理器自动刷新（100ms）
                        logger.debug(f"数据库更新已加入队列（一致性检测失败） - 任务ID: {task_id}")
                    return
                '''  # 结束注释块
                
                # 4. 进行背景移除（抠图）
                logger.info(f"开始背景移除处理 - 任务ID: {task_id}")
                bg_removal_start = time.time()  # 记录抠图开始时间
                if volc_access_key and volc_secret_key:
                    # 只更新本地对象，不写数据库
                    task.bg_removal_attempted = True
                    
                    # 背景移除重试机制：最多尝试2次（首次+重试1次）
                    bg_removal_success = False
                    bg_removal_result = None
                    
                    for attempt in range(2):
                        if attempt > 0:
                            logger.info(f"重试背景移除 - 任务ID: {task_id}, 第{attempt}次重试")
                            # 只更新本地对象，不写数据库
                            task.bg_removal_retry_count = attempt
                        
                        bg_removal_result = generator.remove_background(generated_url)
                        
                        if bg_removal_result.get("success", False):
                            # 背景移除成功
                            result_image = bg_removal_result.get("image_base64", "")
                            logger.info(f"背景移除成功 - 任务ID: {task_id}, 结果大小: {len(result_image)}字符")
                            bg_removal_success = True
                            
                            # # 保存背景抠图结果到文件并获取URL   多余的保存，不再保存
                            # bg_removed_image_path = save_image_to_file(f"{task.task_id}_bg_removed", result_image, image_format='png')
                            # # 构建完整的URL路径
                            # media_url = getattr(settings, 'MEDIA_URL', '/media/')
                            # if not media_url.endswith('/'):
                            #     media_url += '/'
                            # bg_removed_result_url = f"{media_url}{bg_removed_image_path}"
                            bg_removed_result_url = None
                            
                            # 只更新本地对象，不写数据库（等最终成功/失败时一次性写入）
                            task.bg_removal_success = True
                            task.bg_removed_source_url = bg_removed_result_url     # 不存在source url，api返回的仅为 base64
                            break
                        else:
                            # 背景移除失败
                            error_msg = bg_removal_result.get("error", "未知错误")
                            logger.error(f"背景移除失败 - 任务ID: {task_id}, 尝试{attempt+1}/2, 错误: {error_msg}")
                            
                            # 记录详细的错误信息
                            logger.error(f"Error details - 完整响应: {json.dumps(bg_removal_result, ensure_ascii=False)}")
                            logger.error(f"Error details - 生成图片URL: {generated_url}")
                            logger.error(f"Error details - 错误类型: {bg_removal_result.get('error_type', 'unknown')}")
                            if bg_removal_result.get("details"):
                                logger.error(f"Error details - 详细信息: {bg_removal_result.get('details')}")
                            
                            # 如果是"未检测到主体"错误，不重试
                            if "未检测到可分割的主体" in error_msg:
                                logger.info(f"检测到不可恢复错误，停止重试 - 任务ID: {task_id}")
                                break
                    
                    # 处理背景移除结果
                    if not bg_removal_success:
                        # 记录抠图耗时
                        task.bg_removal_duration = time.time() - bg_removal_start
                        # 背景移除失败，按API文档返回错误
                        error_msg = bg_removal_result.get("error", "未知错误")
                        error_details = bg_removal_result.get("details", error_msg)
                        
                        # 判断错误类型
                        if bg_removal_result.get("error_type") == "timeout" or "超时" in error_msg:
                            error_code = 'E3016'  # 背景移除超时
                            error_message = "背景移除超时"
                        else:
                            error_code = 'E3015'  # 背景移除失败
                            error_message = "背景移除失败"
                        
                        # 只更新本地task对象，不写数据库
                        processing_time = time.time() - start_time
                        task.bg_removal_success = False
                        task.bg_removal_error = f"{error_msg}. 详细信息: {error_details}"
                        task.status = 'failed'
                        task.error_code = error_code
                        task.error_message = error_message
                        task.error_details = f"{error_msg}. 详细信息: {error_details}"
                        task.processing_time = processing_time
                        task.completed_at = timezone.now()
                        
                        # 保存要更新的字段，稍后写入
                        task._update_fields = {
                            'bg_removal_success': False,
                            'bg_removal_error': f"{error_msg}. 详细信息: {error_details}",
                            'generated_image_url': generated_url,  # 保存已生成的图片URL，避免数据丢失
                            'error_code': error_code,
                            'error_message': error_message,
                            'error_details': f"{error_msg}. 详细信息: {error_details}",
                            'processing_time': processing_time,
                            'completed_at': timezone.now()
                        }
                        logger.error(f"任务标记为失败 - 任务ID: {task_id}, 错误码: {error_code}")
                        
                        # 更新缓存
                        TaskCacheManager.update_task_status(
                            str(task_id),
                            'failed',
                            {
                                'error_code': task.error_code,
                                'error_message': task.error_message,
                                'error_details': task.error_details,
                                'completed_at': task.completed_at.isoformat()
                            }
                        )
                        
                        execute_callback(task, prompt=task.actual_prompt if hasattr(task, 'actual_prompt') else task.prompt)
                        
                        # 回调完成后写入数据库
                        if hasattr(task, '_update_fields'):
                            db_optimizer.update_task_status(
                                str(task_id),
                                'failed',
                                task._update_fields
                            )
                            # 依赖批量管理器自动刷新（100ms）
                            logger.debug(f"数据库更新已加入队列（背景移除失败） - 任务ID: {task_id}")
                        return
                    else:
                        # 背景移除成功，记录抠图耗时
                        task.bg_removal_duration = time.time() - bg_removal_start
                else:
                    # 没有配置抠图服务，直接使用生成的图片
                    task.bg_removal_duration = time.time() - bg_removal_start
                    logger.warning(f"未配置背景移除服务，使用原始生成图片 - 任务ID: {task_id}")
                    import base64
                    response = requests.get(generated_url, timeout=10)
                    if response.status_code == 200:
                        result_image = base64.b64encode(response.content).decode('utf-8')
                    else:
                        raise Exception(f"下载生成图片失败，状态码: {response.status_code}")
                
                # 5. 保存最终结果
                logger.info(f"保存最终结果 - 任务ID: {task_id}, 结果大小: {len(result_image)}字符")
                
                # 保存图片到文件，并获取调整后的base64
                image_path, resized_image_base64 = save_image_to_file(task.task_id, result_image, image_format='png')
                
                # 如果保存失败，使用原始图片
                if not image_path:
                    resized_image_base64 = result_image
                    logger.warning(f"图片保存失败，使用原始图片 - 任务ID: {task_id}")
                
                # 保存调整后的base64到task对象，用于回调
                task.result_image = resized_image_base64
                
                # 使用批量写入优化 - 成功状态，一次性写入所有字段
                processing_time = time.time() - start_time
                completed_at = timezone.now()
                
                # 构建所有需要更新的字段
                update_fields = {
                    'result_image': None,  # 不再存储base64到数据库
                    'result_image_path': image_path,
                    'processing_time': processing_time,
                    'completed_at': completed_at,
                    'started_at': task.started_at if hasattr(task, 'started_at') else None
                }
                
                # 添加过程中收集的其他字段
                if hasattr(task, 'actual_prompt') and task.actual_prompt:
                    update_fields['actual_prompt'] = task.actual_prompt
                if hasattr(task, 'generation_model') and task.generation_model:
                    update_fields['generation_model'] = task.generation_model
                if hasattr(task, 'generation_guidance_scale') and task.generation_guidance_scale:
                    update_fields['generation_guidance_scale'] = task.generation_guidance_scale
                if hasattr(task, 'pet_detection_result'):
                    update_fields['pet_detection_result'] = task.pet_detection_result
                if hasattr(task, 'pet_detection_model'):
                    update_fields['pet_detection_model'] = task.pet_detection_model
                if hasattr(task, 'pet_description') and task.pet_description:
                    update_fields['pet_description'] = task.pet_description
                if hasattr(task, 'generated_image_url'):
                    update_fields['generated_image_url'] = task.generated_image_url
                if hasattr(task, 'generation_seed'):
                    update_fields['generation_seed'] = task.generation_seed
                if hasattr(task, 'consistency_check'):
                    update_fields['consistency_check'] = task.consistency_check
                if hasattr(task, 'consistency_score'):
                    update_fields['consistency_score'] = task.consistency_score
                if hasattr(task, 'bg_removal_attempted'):
                    update_fields['bg_removal_attempted'] = task.bg_removal_attempted
                if hasattr(task, 'bg_removal_success'):
                    update_fields['bg_removal_success'] = task.bg_removal_success
                if hasattr(task, 'bg_removed_source_url'):
                    update_fields['bg_removed_source_url'] = task.bg_removed_source_url
                if hasattr(task, 'bg_removal_retry_count') and task.bg_removal_retry_count is not None:
                    update_fields['bg_removal_retry_count'] = task.bg_removal_retry_count
                else:
                    update_fields['bg_removal_retry_count'] = 0  # 设置默认值
                
                # 添加各流程执行时长
                if hasattr(task, 'image_validation_duration') and task.image_validation_duration:
                    update_fields['image_validation_duration'] = task.image_validation_duration
                if hasattr(task, 'pet_detection_duration') and task.pet_detection_duration:
                    update_fields['pet_detection_duration'] = task.pet_detection_duration
                if hasattr(task, 'text_to_image_duration') and task.text_to_image_duration:
                    update_fields['text_to_image_duration'] = task.text_to_image_duration
                if hasattr(task, 'consistency_check_duration') and task.consistency_check_duration:
                    update_fields['consistency_check_duration'] = task.consistency_check_duration
                if hasattr(task, 'bg_removal_duration') and task.bg_removal_duration:
                    update_fields['bg_removal_duration'] = task.bg_removal_duration
                if hasattr(task, 'callback_duration') and task.callback_duration:
                    update_fields['callback_duration'] = task.callback_duration
                
                # 只更新本地task对象，不写数据库
                task.status = 'success'
                # task.result_image 已经在上面设置为resized_image_base64
                task.result_image_path = image_path
                task.processing_time = processing_time
                task.completed_at = completed_at
                
                # 将所有需要更新的字段保存到task对象中，稍后一次性写入
                task._update_fields = update_fields
                
                logger.info(f"任务处理成功 - 任务ID: {task_id}, 处理时间: {processing_time:.2f}秒, 图片路径: {image_path}")
                
                # 更新缓存 - 成功状态
                cache_update_data = {
                    'result_image': None,  # 不在缓存中存储大的base64数据
                    'result_image_path': image_path,
                    'processing_time': task.processing_time,
                    'completed_at': task.completed_at.isoformat()
                }
                # 添加宠物描述到缓存（如果存在）
                if hasattr(task, 'pet_description') and task.pet_description:
                    cache_update_data['pet_description'] = task.pet_description
                
                TaskCacheManager.update_task_status(
                    str(task_id),
                    'success',
                    cache_update_data
                )
            else:
                # 记录详细的错误信息（不截断）
                logger.error(f"AI模型生成失败 - 任务ID: {task_id}")
                logger.error(f"Error details - API响应: {json.dumps(api_result, ensure_ascii=False) if api_result else 'None'}")
                logger.error(f"Error details - 使用的prompt: {task.actual_prompt if hasattr(task, 'actual_prompt') else task.prompt}")
                logger.error(f"Error details - 输入图片URL: {task.image_url}")
                
                # 构建详细的错误信息（保存完整内容）
                error_details = {
                    "api_response": api_result,
                    "prompt": task.actual_prompt if hasattr(task, 'actual_prompt') else task.prompt,
                    "image_url": task.image_url,
                    "model": task.generation_model
                }
                raise Exception(f"AI模型生成失败，详细信息: {json.dumps(error_details, ensure_ascii=False)}")
                
        except Exception as e:
            logger.error(f"AI模型生成失败 - 任务ID: {task_id}, 错误: {str(e)}")
            
            # 只更新本地task对象，不写数据库
            processing_time = time.time() - start_time
            task.status = 'failed'
            task.error_code = 'E3001'
            task.error_message = "AI模型生成失败"
            task.error_details = str(e)
            task.processing_time = processing_time
            task.completed_at = timezone.now()
            
            # 保存要更新的字段，稍后写入
            task._update_fields = {
                'error_code': 'E3001',  # 模型调用失败
                'error_message': "AI模型生成失败",
                'error_details': str(e),
                'processing_time': processing_time,
                'completed_at': timezone.now()
            }
            logger.error(f"任务标记为失败 - 任务ID: {task_id}, 错误码: E3001")
            
            # 更新缓存
            TaskCacheManager.update_task_status(
                str(task_id),
                'failed',
                {
                    'error_code': task.error_code,
                    'error_message': task.error_message,
                    'error_details': task.error_details,
                    'completed_at': task.completed_at.isoformat()
                }
            )
            
            # 执行回调
            execute_callback(task, prompt=task.prompt if hasattr(task, 'prompt') else '')
            
            # 回调完成后写入数据库
            if hasattr(task, '_update_fields'):
                db_optimizer.update_task_status(
                    str(task_id),
                    'failed',
                    task._update_fields
                )
                # 依赖批量管理器自动刷新（100ms）
                logger.debug(f"数据库更新已加入队列（模型调用失败） - 任务ID: {task_id}")
            return
        
        # 6. 如果有callback_url，执行回调
        execute_callback(task, prompt=task.actual_prompt if hasattr(task, 'actual_prompt') else task.prompt)
        
        # 7. 回调完成后，再写入数据库（避免阻塞回调）
        if hasattr(task, '_update_fields'):
            if task.status == 'success':
                db_optimizer.update_task_status(
                    str(task_id),
                    'success',
                    task._update_fields
                )
                # 成功任务立即刷新，确保用户及时看到结果
                db_optimizer.flush()
                logger.debug(f"数据库更新完成（成功） - 任务ID: {task_id}")
            elif task.status == 'failed':
                db_optimizer.update_task_status(
                    str(task_id),
                    'failed',
                    task._update_fields
                )
                # 依赖批量管理器自动刷新（100ms）
                logger.debug(f"数据库更新已加入队列（失败） - 任务ID: {task_id}")
        
    except ImageEditTask.DoesNotExist:
        logger.error(f"任务不存在 - 任务ID: {task_id}")
    
    except Exception as e:
        logger.error(f"任务处理异常 - 任务ID: {task_id}, 错误: {str(e)}", exc_info=True)
        try:
            # 计算处理时长
            if 'start_time' in locals():
                processing_time = time.time() - start_time
            else:
                processing_time = None
            
            # 获取task对象以供后续使用
            task = ImageEditTask.objects.get(task_id=task_id)
            task.status = 'failed'
            task.error_code = 'E1006'
            task.error_message = "任务处理失败"
            task.error_details = str(e)
            task.processing_time = processing_time
            task.completed_at = timezone.now()
            
            # 保存要更新的字段，稍后写入
            task._update_fields = {
                'error_code': 'E1006',  # 服务器内部错误
                'error_message': "任务处理失败",
                'error_details': str(e),
                'processing_time': processing_time,
                'completed_at': timezone.now()
            }
            logger.error(f"任务标记为失败 - 任务ID: {task_id}, 错误码: E1006")
            
            # 更新缓存
            TaskCacheManager.update_task_status(
                str(task_id),
                'failed',
                {
                    'error_code': task.error_code,
                    'error_message': task.error_message,
                    'error_details': task.error_details,
                    'completed_at': task.completed_at.isoformat()
                }
            )
        except Exception as save_error:
            logger.error(f"保存失败状态时出错 - 任务ID: {task_id}, 错误: {str(save_error)}")
        
        # 不再重试任务，直接处理失败
        logger.error(f"任务处理失败，不进行重试 - 任务ID: {task_id}")
        # 执行失败回调
        try:
            # 如果task对象存在，直接使用；否则不执行回调
            if 'task' in locals() and task and task.status == 'failed':
                execute_callback(task, prompt=task.prompt if hasattr(task, 'prompt') and task.prompt else '')
                
                # 回调完成后写入数据库
                if hasattr(task, '_update_fields'):
                    db_optimizer.update_task_status(
                        str(task_id),
                        'failed',
                        task._update_fields
                    )
                    # 依赖批量管理器自动刷新（100ms）
                    logger.debug(f"数据库更新已加入队列（异常失败） - 任务ID: {task_id}")
            else:
                logger.warning(f"无法执行失败回调，任务对象不存在 - 任务ID: {task_id}")
        except Exception as callback_error:
            logger.error(f"执行失败回调时出错 - 任务ID: {task_id}, 错误: {str(callback_error)}")


@shared_task(bind=True, max_retries=2)
def send_batch_callback(self, batch_callbacks):
    """批量发送回调任务
    
    Args:
        batch_callbacks: 批量回调数据列表，每个元素包含:
            - url: 回调URL
            - task_id: 任务ID
            - status: 任务状态
            - data: 回调数据
            - prompt: 提示词
    """
    import time
    from .aiCallback import AICallback
    
    logger.info(f"开始批量发送回调 - 数量: {len(batch_callbacks)}")
    
    success_count = 0
    failed_count = 0
    failed_items = []
    
    # 为不同的callback_url创建对应的AICallback实例缓存
    ai_callback_cache = {}
    
    for idx, callback_item in enumerate(batch_callbacks, 1):
        try:
            task_id = callback_item.get('task_id')
            status = callback_item.get('status')
            url = callback_item.get('url')
            data = callback_item.get('data')
            prompt = callback_item.get('prompt', '')
            
            logger.debug(f"发送批量回调 {idx}/{len(batch_callbacks)} - 任务ID: {task_id}")
            
            # 获取或创建对应URL的AICallback实例
            if url not in ai_callback_cache:
                ai_callback_cache[url] = AICallback(callback_url=url)
            ai_callback = ai_callback_cache[url]
            
            # 根据状态构造回调数据
            if status == 'success':
                callback_payload = ai_callback.create_success_callback_data(data, prompt=prompt)
            elif status == 'failed':
                callback_payload = ai_callback.create_failed_callback_data(data, prompt=prompt)
            else:
                logger.warning(f"未知的任务状态 - 任务ID: {task_id}, 状态: {status}")
                failed_count += 1
                continue
            
            # 发送回调，不需要再传递callback_url
            response = ai_callback.send_callback(callback_payload)
            
            if response and response.status_code == 200:
                success_count += 1
                logger.info(f"批量回调成功 - 任务ID: {task_id}, 序号: {idx}/{len(batch_callbacks)}")
            else:
                failed_count += 1
                failed_items.append(callback_item)
                logger.warning(f"批量回调失败 - 任务ID: {task_id}, 响应: {response.status_code if response else 'None'}")
            
            # 添加小延迟，避免对目标服务器造成过大压力
            if idx < len(batch_callbacks):
                time.sleep(0.1)  # 100ms延迟
                
        except Exception as e:
            failed_count += 1
            failed_items.append(callback_item)
            logger.error(f"批量回调异常 - 任务ID: {callback_item.get('task_id')}, 错误: {str(e)}")
    
    # 记录批量发送结果
    logger.info(f"批量回调完成 - 总数: {len(batch_callbacks)}, 成功: {success_count}, 失败: {failed_count}")
    
    # 如果有失败的回调，考虑重试
    if failed_items and self.request.retries < self.max_retries:
        retry_count = self.request.retries + 1
        countdown = 30 * retry_count  # 30秒、60秒递增
        logger.info(f"准备重试失败的批量回调 - 数量: {len(failed_items)}, "
                   f"第 {retry_count} 次重试, {countdown}秒后执行")
        raise self.retry(exc=Exception(f"批量回调部分失败: {failed_count}/{len(batch_callbacks)}"),
                        countdown=countdown,
                        args=[failed_items])
    elif failed_items:
        # 达到最大重试次数，记录失败的回调
        logger.error(f"批量回调最终失败 - 失败数量: {len(failed_items)}")
        
        # 可以将失败的回调记录到数据库或缓存中，以便后续处理
        from django.core.cache import cache
        for item in failed_items:
            failed_key = f"failed_batch_callback:{item.get('task_id')}"
            cache.set(failed_key, json.dumps(item), 86400)  # 保留24小时
    
    return {
        'total': len(batch_callbacks),
        'success': success_count,
        'failed': failed_count
    }