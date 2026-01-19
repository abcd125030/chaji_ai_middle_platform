import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
import time
import json

logger = logging.getLogger(__name__)

from .serializers import (
    SubmitTaskSerializer,
    QueryTaskSerializer,
    BatchSubmitSerializer,
    BatchQuerySerializer
)
from .models import ImageEditTask, BatchTask
from .tasks import process_image_edit_task, load_image_from_file
from .cache_manager import TaskCacheManager, UserRateLimiter


class SubmitTaskView(APIView):
    """提交图片编辑任务"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        处理流程：
        1. 检查用户请求限流
        2. 验证请求参数（prompt, image, callback_url）
        3. 创建任务记录到数据库
        4. 写入Redis缓存
        5. 将任务提交到Celery异步队列
        6. 返回任务ID和预估时间
        """
        # 检查用户请求限流（按秒限流）
        user_id = str(request.user.id)
        # 从性能配置中获取限流设置
        from .performance_settings import RATE_LIMIT_CONFIG
        user_limit = RATE_LIMIT_CONFIG['USER']['DEFAULT']['LIMIT']
        user_window = RATE_LIMIT_CONFIG['USER']['DEFAULT']['WINDOW']
        allowed, current_count = UserRateLimiter.check_rate_limit(
            user_id=user_id,
            limit=user_limit,  # 每秒请求限制
            window=user_window  # 时间窗口（1秒）
        )
        
        if not allowed:
            logger.warning(f"用户请求被限流 - 用户: {request.user.username}, 当前QPS: {current_count}/{user_limit}")
            return Response({
                "code": 1005,
                "data": {},
                "message": f"请求过于频繁，当前QPS已达{current_count}，限制为{user_limit} QPS，请稍后再试",
                "timestamp": int(time.time())
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        logger.info(f"收到图片编辑任务提交请求 - 用户: {request.user.username}, IP: {request.META.get('REMOTE_ADDR')}, QPS: {current_count}/{user_limit}")
        
        serializer = SubmitTaskSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"任务提交参数验证失败 - 用户: {request.user.username}, 错误: {serializer.errors}")
            return Response({
                "code": 1003,
                "data": {},
                "message": "请求参数无效",
                "timestamp": int(time.time())
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 使用事务创建任务
        with transaction.atomic():
            # 创建ImageEditTask记录
            task = ImageEditTask.objects.create(
                user=request.user,
                prompt=serializer.validated_data['prompt'],
                image_url=serializer.validated_data['image'],
                callback_url=serializer.validated_data.get('callback_url', ''),
                status='processing',
                started_at=timezone.now()  # 记录任务开始处理时间
            )
            logger.info(f"创建任务成功 - 任务ID: {task.task_id}, 用户: {request.user.username}")
            
            # 写入Redis缓存
            cache_data = {
                'task_id': str(task.task_id),
                'status': 'processing',
                'user_id': str(request.user.id),
                'prompt': task.prompt,
                'image_url': task.image_url,
                'created_at': task.created_at.isoformat()
            }
            TaskCacheManager.set_task(str(task.task_id), cache_data, status='processing')
        
        # 提交到Celery队列 - 优化：传递必要的任务数据，减少Worker查询数据库
        task_data = {
            'task_id': str(task.task_id),
            'image_url': task.image_url,
            'prompt': task.prompt,
            'callback_url': task.callback_url,
            'user_id': task.user.id,
            'username': task.user.username,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'created_at': task.created_at.isoformat() if task.created_at else None
        }
        process_image_edit_task.delay(task_data)
        logger.info(f"任务已提交到Celery队列（优化版） - 任务ID: {task.task_id}")
        
        # 3. 返回响应
        return Response({
            "code": 0,
            "data": {
                "task_id": str(task.task_id),
                "status": "processing",
                "estimated_time": 30,  # 预估处理时间，单位秒
                "created_at": task.created_at.isoformat()
            },
            "message": "success",
            "timestamp": int(time.time())
        })


class QueryTaskResultView(APIView):
    """查询任务结果"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        处理流程：
        1. 验证task_id参数
        2. 优先从Redis缓存查询
        3. 缓存未命中则查询数据库
        4. 更新缓存并返回结果
        """
        logger.debug(f"收到任务查询请求 - 用户: {request.user.username}")
        
        serializer = QueryTaskSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"查询参数验证失败 - 用户: {request.user.username}, 错误: {serializer.errors}")
            return Response({
                "code": 1003,
                "data": {},
                "message": "请求参数无效",
                "timestamp": int(time.time())
            }, status=status.HTTP_400_BAD_REQUEST)
        
        task_id = serializer.validated_data['task_id']
        
        # 1. 优先从缓存获取
        cached_task = TaskCacheManager.get_task(task_id)
        
        if cached_task:
            # 缓存命中
            logger.debug(f"缓存命中 - 任务ID: {task_id}")
            
            # 检查权限
            if cached_task.get('user_id') != str(request.user.id):
                logger.warning(f"权限验证失败 - 任务ID: {task_id}, 请求用户: {request.user.username}")
                return Response({
                    "code": 1002,
                    "data": {},
                    "message": "权限不足",
                    "timestamp": int(time.time())
                }, status=status.HTTP_403_FORBIDDEN)
            
            # 构建响应
            response_data = {
                "task_id": cached_task.get('task_id'),
                "status": cached_task.get('status'),
                "created_at": cached_task.get('created_at')
            }
            
            # 根据状态添加不同的数据
            if cached_task.get('status') == 'success':
                data_content = {
                    "image": cached_task.get('result_image', ''),
                    "original_prompt": cached_task.get('prompt')
                }
                
                # 如果有抠图原图URL，添加到响应中
                if cached_task.get('bg_removed_source_url'):
                    data_content["bg_removed_source_url"] = cached_task.get('bg_removed_source_url')
                
                # 如果有宠物描述，添加到响应中
                if cached_task.get('pet_description'):
                    data_content["pet_description"] = cached_task.get('pet_description')
                
                response_data.update({
                    "data": data_content,
                    "processing_time": cached_task.get('processing_time'),
                    "completed_at": cached_task.get('completed_at')
                })
                response_code = 0
                message = "success"
            elif cached_task.get('status') == 'failed':
                response_data.update({
                    "error": {
                        "code": cached_task.get('error_code'),
                        "message": cached_task.get('error_message'),
                        "details": cached_task.get('error_details')
                    },
                    "completed_at": cached_task.get('completed_at')
                })
                response_code = int(cached_task.get('error_code', 'E1006')[1:])
                message = cached_task.get('error_message')
            else:
                response_code = 0
                message = "任务处理中"
            
            return Response({
                "code": response_code,
                "data": response_data,
                "message": message,
                "timestamp": int(time.time())
            })
        
        # 2. 缓存未命中，查询数据库
        try:
            task = ImageEditTask.objects.select_related('user').get(task_id=task_id)
            logger.debug(f"从数据库查询任务 - 任务ID: {task_id}, 状态: {task.status}")
            
            # 检查权限
            if task.user != request.user:
                logger.warning(f"权限验证失败 - 任务ID: {task_id}, 请求用户: {request.user.username}, 任务所有者: {task.user.username}")
                return Response({
                    "code": 1002,
                    "data": {},
                    "message": "权限不足",
                    "timestamp": int(time.time())
                }, status=status.HTTP_403_FORBIDDEN)
            
            # 3. 准备缓存数据
            cache_data = {
                'task_id': str(task.task_id),
                'status': task.status,
                'user_id': str(task.user.id),
                'prompt': task.prompt,
                'image_url': task.image_url,
                'created_at': task.created_at.isoformat()
            }
            
            # 根据任务状态返回相应数据
            response_data = {
                "task_id": str(task.task_id),
                "status": task.status,
                "created_at": task.created_at.isoformat()
            }
            
            # 根据不同状态添加不同的响应数据
            if task.status == 'success':
                # 从文件加载图片base64，如果失败则使用数据库中的base64
                result_image_base64 = task.result_image
                if task.result_image_path:
                    loaded_image = load_image_from_file(task.result_image_path)
                    if loaded_image:
                        result_image_base64 = loaded_image
                        logger.debug(f"从文件加载图片成功 - 任务ID: {task.task_id}")
                
                # 按照API文档要求，成功时需要嵌套的data对象
                data_content = {
                    "image": result_image_base64,
                    "original_prompt": task.prompt
                }
                
                # 如果有抠图原图URL，添加到响应中
                if task.bg_removed_source_url:
                    data_content["bg_removed_source_url"] = task.bg_removed_source_url
                    logger.info(f"返回抠图原图URL - 任务ID: {task.task_id}, URL: {task.bg_removed_source_url}")
                
                # 如果有宠物描述，添加到响应中
                if task.pet_description:
                    data_content["pet_description"] = task.pet_description
                    logger.debug(f"返回宠物描述 - 任务ID: {task.task_id}")
                
                response_data.update({
                    "data": data_content,
                    "processing_time": task.processing_time,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                })
                
                # 更新缓存数据
                cache_data.update({
                    'result_image': result_image_base64,
                    'bg_removed_source_url': task.bg_removed_source_url,
                    'pet_description': task.pet_description,
                    'processing_time': task.processing_time,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None
                })
                
                response_code = 0
                message = "success"
                logger.info(f"返回成功结果 - 任务ID: {task.task_id}, 处理时间: {task.processing_time}秒")
            elif task.status == 'failed':
                # 按照API文档要求，失败时需要error对象
                response_data.update({
                    "error": {
                        "code": task.error_code,
                        "message": task.error_message,
                        "details": task.error_details
                    },
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                })
                
                # 更新缓存数据
                cache_data.update({
                    'error_code': task.error_code,
                    'error_message': task.error_message,
                    'error_details': task.error_details,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None
                })
                
                # 从错误码中提取数字部分作为顶层 code
                response_code = int(task.error_code[1:]) if task.error_code and task.error_code.startswith('E') else 1006
                message = task.error_message
                logger.info(f"返回失败结果 - 任务ID: {task.task_id}, 错误码: {task.error_code}")
            else:  # processing
                response_code = 0
                message = "任务处理中"
                logger.debug(f"任务仍在处理中 - 任务ID: {task.task_id}")
            
            # 写入缓存
            TaskCacheManager.set_task(str(task.task_id), cache_data, status=task.status)
            
            return Response({
                "code": response_code,
                "data": response_data,
                "message": message,
                "timestamp": int(time.time())
            })
            
        except ImageEditTask.DoesNotExist:
            logger.warning(f"任务不存在 - 任务ID: {serializer.validated_data['task_id']}, 请求用户: {request.user.username}")
            return Response({
                "code": 1004,
                "data": {},
                "message": "任务不存在",
                "timestamp": int(time.time())
            }, status=status.HTTP_404_NOT_FOUND)


class BatchSubmitTaskView(APIView):
    """批量提交任务"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        处理流程：
        1. 检查用户请求限流（批量接口特殊限流）
        2. 验证批量请求参数
        3. 创建BatchTask记录
        4. 为每个子任务创建ImageEditTask记录
        5. 批量提交任务到Celery队列
        6. 返回批量任务ID和各个子任务ID
        
        注意：返回的任务顺序必须与请求中的顺序一致
        """
        # 检查批量接口限流（按秒限流）
        user_id = str(request.user.id)
        from .performance_settings import RATE_LIMIT_CONFIG
        batch_limit = RATE_LIMIT_CONFIG['USER']['BATCH']['LIMIT']
        batch_window = RATE_LIMIT_CONFIG['USER']['BATCH']['WINDOW']
        allowed, current_count = UserRateLimiter.check_rate_limit(
            user_id=f"batch_{user_id}",  # 使用不同的key前缀区分批量接口
            limit=batch_limit,  # 批量接口限制为 1 QPS
            window=batch_window  # 时间窗口（1秒）
        )
        
        if not allowed:
            logger.warning(f"批量接口请求被限流 - 用户: {request.user.username}, 当前QPS: {current_count}/{batch_limit}")
            return Response({
                "code": 1005,
                "data": {},
                "message": f"批量接口请求过于频繁，当前QPS已达{current_count}，限制为{batch_limit} QPS，请稍后再试",
                "timestamp": int(time.time())
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        logger.info(f"收到批量任务提交请求 - 用户: {request.user.username}, IP: {request.META.get('REMOTE_ADDR')}, 批量QPS: {current_count}/{batch_limit}")
        
        serializer = BatchSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"批量任务参数验证失败 - 用户: {request.user.username}, 错误: {serializer.errors}")
            return Response({
                "code": 1003,
                "data": {},
                "message": "请求参数无效",
                "timestamp": int(time.time())
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 1. 创建BatchTask记录
        batch_task = BatchTask.objects.create(
            user=request.user,
            callback_url=serializer.validated_data.get('callback_url', ''),
            total_count=len(serializer.validated_data['tasks'])
        )
        logger.info(f"创建批量任务成功 - 批次ID: {batch_task.batch_id}, 任务数: {batch_task.total_count}, 用户: {request.user.username}")
        
        # 2. 批量创建ImageEditTask记录并提交到Celery队列
        tasks = []
        for task_data in serializer.validated_data['tasks']:
            # 创建单个任务
            task = ImageEditTask.objects.create(
                user=request.user,
                prompt=task_data['prompt'],
                image_url=task_data['image'],
                callback_url=serializer.validated_data.get('callback_url', ''),  # 使用批量回调地址
                status='processing',
                started_at=timezone.now()  # 记录任务开始处理时间
            )
            
            # 3. 提交到Celery队列 - 优化：传递必要的任务数据
            celery_task_data = {
                'task_id': str(task.task_id),
                'image_url': task.image_url,
                'prompt': task.prompt,
                'callback_url': task.callback_url,
                'user_id': task.user.id,
                'username': task.user.username,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'created_at': task.created_at.isoformat() if task.created_at else None
            }
            process_image_edit_task.delay(celery_task_data)
            logger.debug(f"子任务已提交（优化版） - 任务ID: {task.task_id}, 批次ID: {batch_task.batch_id}")
            
            # 添加到返回列表
            tasks.append({
                "task_id": str(task.task_id),
                "status": "processing"
            })
        
        # 4. 返回响应
        logger.info(f"批量任务提交完成 - 批次ID: {batch_task.batch_id}, 成功提交: {len(tasks)}个任务")
        return Response({
            "code": 0,
            "data": {
                "batch_id": str(batch_task.batch_id),
                "tasks": tasks,
                "total_count": batch_task.total_count
            },
            "message": "success",
            "timestamp": int(time.time())
        })


class BatchQueryTaskResultView(APIView):
    """批量查询任务结果"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        处理流程：
        1. 验证task_ids参数
        2. 批量查询数据库获取任务状态
        3. 返回每个任务的当前状态和结果
        """
        logger.debug(f"收到批量查询请求 - 用户: {request.user.username}")
        
        serializer = BatchQuerySerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"批量查询参数验证失败 - 用户: {request.user.username}, 错误: {serializer.errors}")
            return Response({
                "code": 1003,
                "data": {},
                "message": "请求参数无效",
                "timestamp": int(time.time())
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 1. 批量查询ImageEditTask
        task_ids = serializer.validated_data['task_ids']
        logger.info(f"批量查询任务 - 查询数量: {len(task_ids)}, 用户: {request.user.username}")
        tasks = ImageEditTask.objects.filter(task_id__in=task_ids)
        
        # 2. 检查权限并组装响应数据
        results = []
        for task_id in task_ids:
            try:
                task = next((t for t in tasks if str(t.task_id) == str(task_id)), None)
                if not task:
                    # 任务不存在
                    logger.debug(f"批量查询 - 任务不存在: {task_id}")
                    results.append({
                        "task_id": str(task_id),
                        "status": "not_found",
                        "error": {
                            "code": "1004",
                            "message": "任务不存在"
                        }
                    })
                    continue
                    
                # 检查权限
                if task.user != request.user:
                    logger.debug(f"批量查询 - 权限不足: 任务ID {task_id}, 请求用户: {request.user.username}")
                    results.append({
                        "task_id": str(task_id),
                        "status": "forbidden",
                        "error": {
                            "code": "1002",
                            "message": "权限不足"
                        }
                    })
                    continue
                
                # 构建响应数据
                result_data = {
                    "task_id": str(task.task_id),
                    "status": task.status,
                    "created_at": task.created_at.isoformat()
                }
                
                if task.status == 'success':
                    # 从文件加载图片base64，如果失败则使用数据库中的base64
                    result_image_base64 = task.result_image
                    if task.result_image_path:
                        loaded_image = load_image_from_file(task.result_image_path)
                        if loaded_image:
                            result_image_base64 = loaded_image
                    
                    result_data.update({
                        "data": {
                            "image": result_image_base64,
                            "original_prompt": task.prompt
                        },
                        "processing_time": task.processing_time,
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None
                    })
                elif task.status == 'failed':
                    result_data.update({
                        "error": {
                            "code": task.error_code,
                            "message": task.error_message,
                            "details": task.error_details
                        },
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None
                    })
                    
                results.append(result_data)
                
            except Exception as e:
                logger.error(f"批量查询处理异常 - 任务ID: {task_id}, 错误: {str(e)}")
                results.append({
                    "task_id": str(task_id),
                    "status": "error",
                    "error": {
                        "code": "1006",
                        "message": "服务器内部错误",
                        "details": str(e)
                    }
                })
        
        logger.info(f"批量查询完成 - 查询数: {len(task_ids)}, 返回结果数: {len(results)}")
        return Response({
            "code": 0,
            "data": {
                "results": results
            },
            "message": "success",
            "timestamp": int(time.time())
        })


class TaskStatusView(APIView):
    """API状态查询"""
    permission_classes = []  # 公开访问
    
    def get(self, request):
        """
        返回API服务状态信息
        """
        logger.debug(f"API状态查询 - IP: {request.META.get('REMOTE_ADDR')}")
        return Response({
            "status": "healthy",
            "service": "Image Editor API",
            "version": "1.0.2",
            "timestamp": int(time.time())
        })


from django.shortcuts import render
from django.http import Http404
from django.conf import settings


def task_viewer(request):
    """图片编辑任务查看器视图（仅在DEBUG模式下可用，无需登录）"""
    from backend.utils.db_connection import ensure_db_connection_safe
    
    # 检查是否处于DEBUG模式
    if not settings.DEBUG:
        # 获取访问者信息（可能是匿名用户）
        user_info = f"用户: {request.user.id if request.user.is_authenticated else '匿名'}"
        logger.warning(f"尝试在非DEBUG模式下访问task_viewer - {user_info}, IP: {request.META.get('REMOTE_ADDR')}")
        raise Http404("This page is only available in DEBUG mode")
    
    # 刷新数据库连接，确保获取最新数据
    ensure_db_connection_safe()
    
    # 获取所有任务（不限用户），按创建时间倒序排列，只取最新的30个
    # 注意：这里移除了 user 过滤，会显示所有用户的任务
    tasks = ImageEditTask.objects.all().order_by('-created_at')[:30]
    
    # 立即执行查询并转换为列表，避免延迟加载
    tasks_list = list(tasks)
    total_count = len(tasks_list)
    
    # 记录访问信息
    visitor_info = f"用户ID: {request.user.id}" if request.user.is_authenticated else "匿名访问"
    logger.info(f"查询所有用户的最新30个任务 - {visitor_info}, IP: {request.META.get('REMOTE_ADDR')}")
    
    # 获取请求的索引参数
    index_param = request.GET.get('index')
    
    if index_param is None:
        # 如果没有提供index参数，默认显示最新的任务（第1个）
        index = 1
        logger.info(f"未提供index参数，默认显示最新任务")
    else:
        # 如果提供了index参数，尝试转换为整数
        try:
            index = int(index_param)
        except ValueError:
            index = 1
            logger.warning(f"无效的index参数: {index_param}，使用默认值1")
    
    # 记录调试信息
    if tasks_list:
        logger.info(f"查询到 {total_count} 个任务（最多30个）")
        logger.info(f"最新任务: {tasks_list[0].task_id}, 用户: {tasks_list[0].user_id}, 创建时间: {tasks_list[0].created_at}")
        if total_count > 1:
            logger.info(f"本批最早任务: {tasks_list[-1].task_id}, 用户: {tasks_list[-1].user_id}, 创建时间: {tasks_list[-1].created_at}")
    
    # 确保索引在有效范围内
    if index < 1:
        index = 1
    elif index > total_count:
        index = total_count if total_count > 0 else 1
    
    # 获取指定索引的任务
    task = None
    if total_count > 0 and 1 <= index <= total_count:
        task = tasks_list[index - 1]
        # 如果任务处于处理中状态，再次刷新获取最新状态
        if task and task.status == 'processing':
            try:
                # 重新从数据库获取该任务的最新状态
                task = ImageEditTask.objects.get(task_id=task.task_id)
            except ImageEditTask.DoesNotExist:
                pass
        
        # 如果任务成功且有文件路径，从文件加载图片base64用于展示
        if task and task.status == 'success' and task.result_image_path:
            from .tasks import load_image_from_file
            loaded_image = load_image_from_file(task.result_image_path)
            if loaded_image:
                # 构建用于展示的data URL
                task.result_image_data_url = f"data:image/png;base64,{loaded_image}"
                logger.debug(f"从文件加载图片 - 任务ID: {task.task_id}, 路径: {task.result_image_path}")
    
    # 判断是否有前一个和后一个任务
    has_prev = index > 1
    has_next = index < total_count
    
    # 记录调试信息
    if task:
        logger.info(f"展示任务 - 索引: {index}/{total_count}, ID: {task.task_id}, "
                   f"状态: {task.status}, 创建时间: {task.created_at}, "
                   f"完成时间: {task.completed_at if task.completed_at else '未完成'}")
    
    # 获取当前配置中的检测提示词
    from .config_manager import config_manager
    detection_prompt = config_manager.get_detection_prompt()
    
    context = {
        'task': task,
        'current_index': index,
        'total_count': total_count,
        'has_prev': has_prev,
        'has_next': has_next,
        'detection_prompt': detection_prompt,
    }
    
    return render(request, 'image_editor/task_viewer.html', context)