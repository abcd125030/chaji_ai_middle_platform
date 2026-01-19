from django.db import models
import uuid

class Dataset(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '未下载'
        DOWNLOADING = 'downloading', '下载中'
        COMPLETED = 'completed', '已完成'
        FAILED = 'failed', '校验失败'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.CharField('下载地址', max_length=2048, unique=True)
    expected_md5 = models.CharField('预期MD5', max_length=32)
    file_size = models.BigIntegerField('文件大小', null=True, blank=True)
    metadata = models.JSONField('元数据', default=dict, blank=True)
    status = models.CharField('状态', max_length=20, choices=Status.choices, default=Status.PENDING)
    storage_path = models.CharField('存储路径', max_length=1024, null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '数据集'
        verbose_name_plural = '数据集'
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_dataset_status_created'),
            models.Index(fields=['url'], name='idx_dataset_url'),
        ]

    def __str__(self):
        return self.url

class DownloadTask(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', '活跃'
        COMPLETED = 'completed', '已完成'
        FAILED = 'failed', '失败'
        TIMEOUT = 'timeout', '超时'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, verbose_name='数据集', related_name='tasks')
    client_id = models.CharField('客户端标识', max_length=100)
    status = models.CharField('状态', max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField('开始时间', auto_now_add=True)
    last_heartbeat = models.DateTimeField('最后心跳', null=True, blank=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    actual_md5 = models.CharField('实际MD5', max_length=32, null=True, blank=True)
    error_message = models.TextField('错误信息', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '下载任务'
        verbose_name_plural = '下载任务'
        indexes = [
            models.Index(fields=['status', 'last_heartbeat'], name='idx_task_status_heartbeat'),
        ]

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        HEARTBEAT_TIMEOUT = 'heartbeat_timeout', '心跳超时'

    class Status(models.TextChoices):
        PENDING = 'pending', '待发送'
        SENT = 'sent', '已发送'
        FAILED = 'failed', '发送失败'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_type = models.CharField('通知类型', max_length=50, choices=NotificationType.choices)
    recipients = models.JSONField('接收者列表')
    subject = models.CharField('邮件主题', max_length=200)
    content = models.TextField('邮件内容')
    status = models.CharField('发送状态', max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField('错误信息', null=True, blank=True)
    sent_at = models.DateTimeField('发送时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '通知记录'
        verbose_name_plural = '通知记录'

class SystemConfig(models.Model):
    key = models.CharField('配置键', max_length=100, unique=True)
    value = models.TextField('配置值')
    description = models.CharField('配置说明', max_length=200, null=True, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'

    def __str__(self):
        return f'{self.key}: {self.value[:50]}'

    @classmethod
    def get_value(cls, key, default=None):
        try:
            config = cls.objects.get(key=key)
            return config.value
        except cls.DoesNotExist:
            return default

    @classmethod
    def get_heartbeat_timeout(cls):
        value = cls.get_value('heartbeat_timeout_seconds', '30')
        return int(value)

    @classmethod
    def set_value(cls, key, value):
        obj, _ = cls.objects.update_or_create(key=key, defaults={'value': value})
        return obj.value
