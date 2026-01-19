"""
批量回调队列管理工具
用于诊断和修复队列问题
"""
import logging
from django.core.management.base import BaseCommand
from customized.image_editor.callback_batcher_redis import get_redis_batcher

logger = logging.getLogger(__name__)


def force_release_lock():
    """强制释放发送锁（用于死锁恢复）"""
    batcher = get_redis_batcher()
    try:
        batcher.redis_client.delete(batcher.LOCK_KEY)
        logger.info("已强制释放发送锁")
        return True
    except Exception as e:
        logger.error(f"释放锁失败: {str(e)}")
        return False


def clear_processing_queue():
    """清理处理中队列，将任务移回待处理队列"""
    batcher = get_redis_batcher()
    try:
        moved_count = 0
        while True:
            item = batcher.redis_client.lpop(batcher.PROCESSING_KEY)
            if not item:
                break
            batcher.redis_client.rpush(batcher.QUEUE_KEY, item)
            moved_count += 1
        
        logger.info(f"已将 {moved_count} 个任务从处理中队列移回待处理队列")
        return moved_count
    except Exception as e:
        logger.error(f"清理处理队列失败: {str(e)}")
        return 0


def get_queue_status():
    """获取队列状态"""
    batcher = get_redis_batcher()
    try:
        pending = batcher.redis_client.llen(batcher.QUEUE_KEY)
        processing = batcher.redis_client.llen(batcher.PROCESSING_KEY)
        lock = batcher.redis_client.get(batcher.LOCK_KEY)
        last_send = batcher.redis_client.get(batcher.LAST_SEND_KEY)
        
        status = {
            'pending_count': pending,
            'processing_count': processing,
            'lock_status': 'locked' if lock else 'unlocked',
            'lock_value': lock.decode() if lock else None,
            'last_send_time': float(last_send.decode()) if last_send else None
        }
        
        return status
    except Exception as e:
        logger.error(f"获取状态失败: {str(e)}")
        return None


def reset_callback_queue():
    """完全重置回调队列（慎用）"""
    batcher = get_redis_batcher()
    try:
        # 删除所有相关键
        keys_to_delete = [
            batcher.QUEUE_KEY,
            batcher.PROCESSING_KEY,
            batcher.LOCK_KEY,
            batcher.LAST_SEND_KEY
        ]
        
        # 删除统计键
        stats_keys = batcher.redis_client.keys(f"{batcher.STATS_KEY}:*")
        if stats_keys:
            keys_to_delete.extend(stats_keys)
        
        for key in keys_to_delete:
            batcher.redis_client.delete(key)
        
        logger.info(f"已重置回调队列，删除了 {len(keys_to_delete)} 个键")
        return True
    except Exception as e:
        logger.error(f"重置队列失败: {str(e)}")
        return False


# Django管理命令（可选）
class Command(BaseCommand):
    help = '管理批量回调队列'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='显示队列状态'
        )
        parser.add_argument(
            '--unlock',
            action='store_true',
            help='强制释放发送锁'
        )
        parser.add_argument(
            '--recover',
            action='store_true',
            help='恢复处理中的任务'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='完全重置队列（危险）'
        )
    
    def handle(self, *args, **options):
        if options['status']:
            status = get_queue_status()
            if status:
                self.stdout.write(f"待处理: {status['pending_count']}")
                self.stdout.write(f"处理中: {status['processing_count']}")
                self.stdout.write(f"锁状态: {status['lock_status']}")
                if status['lock_value']:
                    self.stdout.write(f"锁持有者: {status['lock_value']}")
                if status['last_send_time']:
                    import time
                    elapsed = time.time() - status['last_send_time']
                    self.stdout.write(f"上次发送: {elapsed:.1f}秒前")
        
        if options['unlock']:
            if force_release_lock():
                self.stdout.write(self.style.SUCCESS('已释放锁'))
            else:
                self.stdout.write(self.style.ERROR('释放锁失败'))
        
        if options['recover']:
            count = clear_processing_queue()
            self.stdout.write(self.style.SUCCESS(f'已恢复 {count} 个任务'))
        
        if options['reset']:
            confirm = input('确定要重置队列吗？这将删除所有待处理的回调！(yes/no): ')
            if confirm.lower() == 'yes':
                if reset_callback_queue():
                    self.stdout.write(self.style.SUCCESS('队列已重置'))
                else:
                    self.stdout.write(self.style.ERROR('重置失败'))