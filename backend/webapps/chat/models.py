from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class ChatSession(models.Model):
    """聊天会话模型"""
    
    # 使用 UUID 作为主键
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='会话ID'
    )
    
    # 关联的用户
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
        verbose_name='用户'
    )
    
    # AI 中台的会话 ID
    ai_conversation_id = models.CharField(
        max_length=255,
        verbose_name='AI会话ID'
    )
    
    # 会话标题
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='会话标题'
    )
    
    # 最后一条消息预览
    last_message_preview = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='最后消息预览'
    )
    
    # 最后交互时间
    last_interacted_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='最后交互时间'
    )
    
    # 是否置顶
    is_pinned = models.BooleanField(
        default=False,
        verbose_name='是否置顶'
    )
    
    # 是否归档
    is_archived = models.BooleanField(
        default=False,
        verbose_name='是否归档'
    )
    
    # 标签（JSON字段）
    tags = models.JSONField(
        blank=True,
        null=True,
        verbose_name='标签'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        verbose_name = '聊天会话'
        verbose_name_plural = '聊天会话'
        unique_together = [['user', 'ai_conversation_id']]
        indexes = [
            models.Index(fields=['user', '-last_interacted_at']),
            models.Index(fields=['last_interacted_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title or self.ai_conversation_id}"


class ChatMessage(models.Model):
    """聊天消息模型"""
    
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    
    # 关联的会话
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='会话',
        db_column='session_id'  # 保持数据库列名不变
    )
    
    # 消息角色
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        verbose_name='角色'
    )
    
    # 消息内容
    content = models.TextField(
        verbose_name='内容'
    )
    
    # 文件信息（JSON）
    files_info = models.JSONField(
        blank=True,
        null=True,
        verbose_name='文件信息'
    )
    
    # 任务ID
    task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='任务ID'
    )
    
    # 任务步骤（JSON）
    task_steps = models.JSONField(
        blank=True,
        null=True,
        verbose_name='任务步骤'
    )
    
    # 最终的网页搜索结果（JSON）
    final_web_search_results = models.JSONField(
        blank=True,
        null=True,
        verbose_name='网页搜索结果'
    )
    
    # 是否完成
    is_complete = models.BooleanField(
        default=False,
        verbose_name='是否完成'
    )
    
    # 压缩存储字段
    task_steps_compressed = models.TextField(
        blank=True,
        null=True,
        verbose_name='压缩的任务步骤',
        help_text='Base64编码的gzip压缩数据'
    )
    
    use_compression = models.BooleanField(
        default=False,
        verbose_name='是否使用压缩存储'
    )
    
    # 软删除标记
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='是否已删除',
        help_text='软删除标记，已删除的消息不会显示给用户但数据仍保留'
    )
    
    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='删除时间'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    class Meta:
        verbose_name = '聊天消息'
        verbose_name_plural = '聊天消息'
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.session} - {self.role}: {self.content[:50]}..."
    
    def save_task_steps(self, steps, use_compression=True):
        """
        保存任务步骤，根据大小决定是否压缩
        
        参数:
            steps: 任务步骤列表
            use_compression: 是否使用压缩（对于大数据自动启用）
        """
        from .utils import compress_data
        import json
        
        if not steps:
            self.task_steps = None
            self.task_steps_compressed = None
            self.use_compression = False
            return
        
        # 计算数据大小
        json_str = json.dumps(steps, ensure_ascii=False)
        size = len(json_str.encode('utf-8'))
        
        # 超过 10KB 自动启用压缩
        if size > 10240 or use_compression:
            self.task_steps_compressed = compress_data(steps)
            self.task_steps = None  # 不存储原始数据
            self.use_compression = True
        else:
            self.task_steps = steps
            self.task_steps_compressed = None
            self.use_compression = False
    
    def get_task_steps(self):
        """
        获取任务步骤，自动处理压缩/非压缩数据
        
        返回:
            任务步骤列表，如果没有则返回 None
        """
        from .utils import decompress_data
        
        if self.use_compression and self.task_steps_compressed:
            return decompress_data(self.task_steps_compressed)
        return self.task_steps