"""
Toolkit应用的Celery异步任务
"""
import logging
from django.conf import settings
from pathlib import Path

# 使用PDF Extractor专用的Celery实例
from backend.celery_pdf_extractor import app

logger = logging.getLogger('django')


@app.task(bind=True, name='toolkit.process_pdf_extraction')
def process_pdf_extraction(self, task_id: str, file_path: str):
    """
    处理PDF文档提取任务

    Args:
        self: Celery任务实例
        task_id: 任务UUID字符串
        file_path: PDF文件路径

    Returns:
        任务处理结果
    """
    from .models import PDFExtractorTask
    from .services.pdf_extractor.processors import PDFProcessor
    from .utils import FileManager

    try:
        logger.info(f"开始处理PDF提取任务: {task_id}")

        # 获取任务记录
        task = PDFExtractorTask.objects.get(id=task_id)

        # 更新任务状态为处理中
        task.status = 'processing'
        task.save()

        # 获取任务目录
        task_dir = FileManager.EXTRACTOR_BASE_DIR / task_id

        # 初始化PDF处理器
        processor = PDFProcessor()

        # 处理PDF文档
        result = processor.process_pdf_document(
            pdf_path=file_path,
            task_id=task_id,
            task_dir=task_dir
        )

        if result['status'] == 'success':
            # 更新任务状态
            task.status = 'completed'
            task.total_pages = result['total_pages']
            task.processed_pages = result['processed_pages']
            task.save()

            logger.info(f"PDF提取任务完成: {task_id}, 共 {result['total_pages']} 页")

            # 4. 调用飞书转换（仅对已关联飞书账号的用户）
            try:
                from .services.feishu_document import FeishuDocumentService
                feishu_service = FeishuDocumentService()
                feishu_url = feishu_service.convert_markdown_to_feishu(
                    task=task,
                    markdown_path=result['final_markdown']
                )
                if feishu_url:
                    task.feishu_doc_url = feishu_url
                    task.save()
                    logger.info(f"飞书文档创建成功: {task_id}, URL: {feishu_url}")
            except Exception as e:
                logger.warning(f"飞书文档转换失败，不影响PDF提取结果: {str(e)}", exc_info=True)

            return {
                'status': 'success',
                'task_id': task_id,
                'total_pages': result['total_pages'],
                'processed_pages': result['processed_pages'],
                'final_markdown': result['final_markdown']
            }
        else:
            # 处理失败
            task.status = 'error'
            task.save()

            logger.error(f"PDF提取任务失败: {task_id}, 错误: {result.get('error')}")

            return {
                'status': 'error',
                'task_id': task_id,
                'message': result.get('error', '未知错误')
            }

    except PDFExtractorTask.DoesNotExist:
        logger.error(f"任务不存在: {task_id}")
        return {
            'status': 'error',
            'task_id': task_id,
            'message': '任务不存在'
        }

    except Exception as e:
        logger.error(f"处理PDF提取任务失败: {task_id}, 错误: {str(e)}", exc_info=True)

        # 更新任务状态为错误
        try:
            task = PDFExtractorTask.objects.get(id=task_id)
            task.status = 'error'
            task.save()
        except Exception:
            pass

        return {
            'status': 'error',
            'task_id': task_id,
            'message': str(e)
        }


@app.task(bind=True, name='toolkit.cleanup_old_tasks')
def cleanup_old_tasks(self):
    """
    清理超过24小时仍在pending状态的任务

    注意:
    - 不删除任务记录,只标记为失败状态
    - 这些任务通常是因为异常原因未能正常处理

    Args:
        self: Celery任务实例

    Returns:
        清理结果
    """
    from .models import PDFExtractorTask
    from datetime import timedelta
    from django.utils import timezone

    try:
        logger.info("开始清理超过24小时的pending任务")

        # 找出超过24小时仍在pending状态的任务
        cutoff_time = timezone.now() - timedelta(hours=24)
        stuck_tasks = PDFExtractorTask.objects.filter(
            status='pending',
            created_at__lt=cutoff_time
        )

        count = stuck_tasks.count()

        if count > 0:
            # 将这些任务标记为error状态
            stuck_tasks.update(
                status='error',
                updated_at=timezone.now()
            )
            logger.info(f"清理完成，将{count}个超时pending任务标记为失败")
        else:
            logger.info("没有需要清理的超时pending任务")

        return {
            'status': 'success',
            'cleaned_count': count,
            'message': f'将{count}个超时pending任务标记为失败'
        }

    except Exception as e:
        logger.error(f"清理任务失败: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e)
        }
