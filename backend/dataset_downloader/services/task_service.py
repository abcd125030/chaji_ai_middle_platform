import logging
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
from ..models import Dataset, DownloadTask, SystemConfig

logger = logging.getLogger('django')

class TaskService:
    @staticmethod
    @transaction.atomic
    def request_task(client_id: str) -> Optional[Dict[str, Any]]:
        dataset = (
            Dataset.objects
            .select_for_update(skip_locked=True)
            .filter(status=Dataset.Status.PENDING)
            .order_by('created_at')
            .first()
        )
        if not dataset:
            return None

        task = DownloadTask.objects.create(
            dataset=dataset,
            client_id=client_id,
            status=DownloadTask.Status.ACTIVE
        )

        dataset.status = Dataset.Status.DOWNLOADING
        dataset.save(update_fields=['status', 'updated_at'])

        heartbeat_interval = int(SystemConfig.get_value('heartbeat_interval_seconds', '15'))
        heartbeat_timeout = SystemConfig.get_heartbeat_timeout()

        logger.info(f"分发任务: task_id={task.id} dataset_url={dataset.url} client_id={client_id}")

        return {
            'task_id': str(task.id),
            'dataset': {
                'id': str(dataset.id),
                'url': dataset.url,
                'expected_md5': dataset.expected_md5,
                'file_size': dataset.file_size,
                'metadata': dataset.metadata
            },
            'heartbeat_interval_seconds': heartbeat_interval,
            'heartbeat_timeout_seconds': heartbeat_timeout
        }

    @staticmethod
    @transaction.atomic
    def complete_task(task_id: str, client_id: str, actual_md5: str, storage_path: Optional[str] = None) -> Dict[str, Any]:
        try:
            task = DownloadTask.objects.select_for_update().get(id=task_id)
        except DownloadTask.DoesNotExist:
            return {'ok': False, 'message': '任务不存在', 'code': 404}
        if task.client_id != client_id:
            return {'ok': False, 'message': '客户端ID不匹配', 'code': 403}
        if task.status != DownloadTask.Status.ACTIVE:
            return {'ok': False, 'message': '任务状态不可完成', 'code': 400}
        ds = task.dataset
        md5_match = (actual_md5.lower() == (ds.expected_md5 or '').lower())
        now = timezone.now()
        task.actual_md5 = actual_md5
        task.completed_at = now
        if md5_match:
            task.status = DownloadTask.Status.COMPLETED
            ds.status = Dataset.Status.COMPLETED
            if storage_path:
                ds.storage_path = storage_path
            ds.save(update_fields=['status', 'storage_path', 'updated_at'] if storage_path else ['status', 'updated_at'])
            task.error_message = None
            task.save(update_fields=['status', 'actual_md5', 'completed_at', 'error_message', 'updated_at'])
            logger.info(f"任务完成: task_id={task.id} dataset_id={ds.id} client_id={client_id} md5_match=True storage_path={storage_path or ''}")
        else:
            task.status = DownloadTask.Status.FAILED
            ds.status = Dataset.Status.FAILED
            task.error_message = 'MD5不匹配'
            ds.save(update_fields=['status', 'updated_at'])
            task.save(update_fields=['status', 'actual_md5', 'completed_at', 'error_message', 'updated_at'])
            logger.warning(f"任务校验失败: task_id={task.id} dataset_id={ds.id} client_id={client_id} expected_md5={ds.expected_md5} actual_md5={actual_md5}")
        return {
            'ok': True,
            'result': {
                'task_id': str(task.id),
                'dataset_id': str(ds.id),
                'task_status': task.status,
                'dataset_status': ds.status,
                'storage_path': ds.storage_path
            }
        }