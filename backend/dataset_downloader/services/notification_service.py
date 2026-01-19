import logging
import json
from typing import List, Dict
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from ..models import Notification, SystemConfig

logger = logging.getLogger('django')

class NotificationService:
    @staticmethod
    def send_timeout_notification(timed_out_tasks: List[Dict]) -> None:
        recipients_raw = SystemConfig.get_value('heartbeat_notification_recipients', '[]')
        try:
            recipients = json.loads(recipients_raw)
        except Exception:
            recipients = [i.strip() for i in recipients_raw.split(',') if i.strip()]
        if not recipients:
            return
        subject = '下载心跳超时告警'
        lines = []
        for t in timed_out_tasks:
            last = t['last_heartbeat'].isoformat() if t.get('last_heartbeat') else ''
            lines.append(f"task_id={t['task_id']} dataset_url={t['dataset_url']} client_id={t['client_id']} last_heartbeat={last} timeout={t['timeout_seconds']}s")
        content = '\n'.join(lines) or '无超时任务'
        n = Notification.objects.create(
            notification_type=Notification.NotificationType.HEARTBEAT_TIMEOUT,
            recipients=recipients,
            subject=subject,
            content=content,
            status=Notification.Status.PENDING
        )
        try:
            send_mail(subject, content, settings.DEFAULT_FROM_EMAIL, recipients)
            n.status = Notification.Status.SENT
            n.sent_at = timezone.now()
            n.save(update_fields=['status', 'sent_at'])
            logger.info(f"超时通知发送成功: {len(recipients)}")
        except Exception as e:
            n.status = Notification.Status.FAILED
            n.error_message = str(e)
            n.save(update_fields=['status', 'error_message'])
            logger.error(f"超时通知发送失败: {e}")