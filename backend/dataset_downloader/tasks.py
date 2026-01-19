import logging
from backend.celery import app
from backend.utils.db_connection import ensure_db_connection_safe
from .services.heartbeat_service import HeartbeatService
from .services.notification_service import NotificationService

logger = logging.getLogger('django')

@app.task(bind=True, ignore_result=True, name='dataset_downloader.tasks.check_heartbeat_timeout')
def check_heartbeat_timeout(self):
    ensure_db_connection_safe()
    timed_out = HeartbeatService.check_timeout()
    if timed_out:
        NotificationService.send_timeout_notification(timed_out)
    return {'timed_out_count': len(timed_out)}