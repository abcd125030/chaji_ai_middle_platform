import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from celery import shared_task
from django.utils import timezone
from django.conf import settings

from .models import PDFParseTask, ParseResult
from .services.optimized_service import OptimizedMinerUService

logger = logging.getLogger('django')


@shared_task(bind=True, max_retries=3)
def process_document_task(self, task_id: str):
    """异步处理文档解析任务"""
    try:
        logger.info(f"开始处理文档任务: {task_id}")
        
        # 获取任务
        task = PDFParseTask.objects.get(task_id=task_id)
        
        # 更新状态为处理中
        task.status = 'processing'
        task.save()
        
        # 读取文件字节
        file_bytes = None
        use_oss = settings.MINERU_SETTINGS.get('USE_OSS', False)
        
        logger.info(f"文件路径: {task.file_path}, USE_OSS: {use_oss}")
        
        if task.file_path:
            # 从本地读取文件
            file_path = Path(task.file_path)
            if not file_path.is_absolute():
                file_path = Path(settings.MEDIA_ROOT) / file_path
            
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            logger.info(f"从本地读取文件: {file_path}")
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
        else:
            # 如果没有文件路径，检查是否有原始文件名，可能需要重新上传
            raise ValueError(f"任务 {task_id} 没有有效的文件路径")
        
        if not file_bytes:
            raise ValueError(f"无法读取任务 {task_id} 的文件内容")
        
        logger.info(f"成功读取文件，大小: {len(file_bytes)} 字节")
        
        # 使用优化的服务处理文档
        service = OptimizedMinerUService()
        result = service.process_document(task, file_bytes)
        
        logger.info(f"文档任务处理完成: {task_id}")
        return {
            'task_id': str(task_id),
            'status': 'completed',
            'result': result
        }
        
    except PDFParseTask.DoesNotExist:
        logger.error(f"任务不存在: {task_id}")
        raise
    
    except Exception as e:
        logger.error(f"文档处理失败，任务ID: {task_id}, 错误: {str(e)}", exc_info=True)
        
        # 更新任务状态
        try:
            task = PDFParseTask.objects.get(task_id=task_id)
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
        except:
            pass
        
        # 重试任务
        if self.request.retries < self.max_retries:
            logger.info(f"重试任务 {task_id}, 第 {self.request.retries + 1} 次")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        raise


@shared_task
def cleanup_old_files_task():
    """定期清理旧文件任务"""
    try:
        logger.info("开始清理旧文件")
        
        # 清理超过30天的文件
        cutoff_date = timezone.now() - timedelta(days=30)
        old_tasks = PDFParseTask.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed']
        )
        
        cleaned_count = 0
        
        for task in old_tasks:
            try:
                # 删除上传的文件
                if task.file_path and Path(task.file_path).exists():
                    Path(task.file_path).unlink()
                
                # 删除输出目录
                if task.output_dir and Path(task.output_dir).exists():
                    shutil.rmtree(task.output_dir)
                
                # 删除任务记录
                task.delete()
                cleaned_count += 1
                
            except Exception as e:
                logger.warning(f"清理任务 {task.task_id} 失败: {str(e)}")
        
        logger.info(f"清理完成，共清理 {cleaned_count} 个任务")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"清理任务失败: {str(e)}")
        raise


@shared_task
def check_stuck_tasks():
    """检查并重置卡住的任务"""
    try:
        logger.info("检查卡住的任务")
        
        # 查找超过1小时仍在处理中的任务
        cutoff_time = timezone.now() - timedelta(hours=1)
        stuck_tasks = PDFParseTask.objects.filter(
            status='processing',
            updated_at__lt=cutoff_time
        )
        
        reset_count = 0
        
        for task in stuck_tasks:
            logger.warning(f"发现卡住的任务: {task.task_id}")
            
            # 重置为待处理状态
            task.status = 'pending'
            task.error_message = "任务处理超时，已重置"
            task.save()
            
            # 重新提交任务
            process_document_task.delay(str(task.task_id))
            reset_count += 1
        
        logger.info(f"重置了 {reset_count} 个卡住的任务")
        return reset_count
        
    except Exception as e:
        logger.error(f"检查卡住任务失败: {str(e)}")
        raise