import logging
from datetime import timedelta
from typing import List, Dict, Any
from django.utils import timezone
from django.db import transaction
from ..models import DownloadTask, Dataset, SystemConfig

logger = logging.getLogger('django')

class HeartbeatService:
    @staticmethod
    @transaction.atomic
    def receive_heartbeat(task_id: str, client_id: str) -> Dict[str, Any]:
        try:
            task = DownloadTask.objects.select_for_update().get(id=task_id)
        except DownloadTask.DoesNotExist:
            return {'ok': False, 'message': '任务不存在', 'code': 404}
        if task.client_id != client_id:
            return {'ok': False, 'message': '客户端ID不匹配', 'code': 403}
        if task.status != DownloadTask.Status.ACTIVE:
            return {'ok': False, 'message': '任务状态不可更新心跳', 'code': 400}
        now = timezone.now()
        task.last_heartbeat = now
        task.save(update_fields=['last_heartbeat', 'updated_at'])
        return {'ok': True, 'last_heartbeat': now}

    @staticmethod
    @transaction.atomic
    def check_timeout() -> List[Dict[str, Any]]:
        timeout_seconds = SystemConfig.get_heartbeat_timeout()
        threshold = timezone.now() - timedelta(seconds=timeout_seconds)
        qs = DownloadTask.objects.select_for_update().filter(status=DownloadTask.Status.ACTIVE, last_heartbeat__lt=threshold)
        timed_out = []
        for t in qs:
            t.status = DownloadTask.Status.TIMEOUT
            t.save(update_fields=['status', 'updated_at'])
            ds = t.dataset
            ds.status = Dataset.Status.PENDING
            ds.save(update_fields=['status', 'updated_at'])
            timed_out.append({
                'task_id': str(t.id),
                'dataset_id': str(ds.id),
                'dataset_url': ds.url,
                'client_id': t.client_id,
                'last_heartbeat': t.last_heartbeat,
                'timeout_seconds': timeout_seconds
            })
        logger.info(f"心跳超时检测: 超时任务 {len(timed_out)}")
        return timed_out