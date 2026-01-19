from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class LLMCallLog(models.Model):
    """LLM 调用日志 - 记录每次 LLM 调用的详细信息"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('timeout', '超时'),
        ('cancelled', '已取消'),
    ]
    
    CALL_TYPE_CHOICES = [
        ('chat', '对话'),
        ('completion', '补全'),
        ('embedding', '嵌入'),
        ('structured', '结构化输出'),
        ('function', '函数调用'),
        ('tool', '工具调用'),
    ]
    
    # 基础信息
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='日志ID'
    )
    
    request_id = models.CharField(
        max_length=100,
        unique=True,
        default=uuid.uuid4,
        verbose_name='请求ID',
        help_text='用于追踪和去重'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='llm_call_logs',
        verbose_name='用户'
    )
    
    session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='会话ID',
        db_index=True
    )
    
    call_type = models.CharField(
        max_length=20,
        choices=CALL_TYPE_CHOICES,
        default='chat',
        verbose_name='调用类型'
    )
    
    # 模型信息 - 与 router.LLMModel 数据关联
    model_name = models.CharField(
        max_length=128,
        verbose_name='模型名称',
        db_index=True,
        help_text='对应 router.LLMModel.name'
    )
    
    model_id = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='模型标识符',
        help_text='对应 router.LLMModel.model_id'
    )
    
    # 供应商信息 - 与 router.VendorEndpoint 数据关联
    vendor_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='供应商名称',
        help_text='对应 router.VendorEndpoint.vendor_name'
    )
    
    vendor_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='供应商标识符',
        help_text='对应 router.VendorEndpoint.vendor_id'
    )
    
    endpoint = models.URLField(
        max_length=500,
        verbose_name='调用端点',
        help_text='实际调用的API端点'
    )
    
    # 请求信息
    request_messages = models.JSONField(
        default=list,
        verbose_name='请求消息',
        help_text='发送给LLM的消息列表'
    )
    
    request_params = models.JSONField(
        default=dict,
        verbose_name='请求参数',
        help_text='temperature、max_tokens等参数'
    )
    
    request_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='请求头'
    )
    
    request_timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name='请求时间',
        db_index=True
    )
    
    # 响应信息
    response_content = models.TextField(
        blank=True,
        verbose_name='响应内容',
        help_text='LLM返回的内容'
    )
    
    response_raw = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='原始响应',
        help_text='完整的原始响应数据'
    )
    
    response_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='响应时间'
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name='错误信息'
    )
    
    error_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='错误代码'
    )
    
    # 性能指标
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='状态',
        db_index=True
    )
    
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='耗时(毫秒)'
    )
    
    retry_count = models.IntegerField(
        default=0,
        verbose_name='重试次数'
    )
    
    is_stream = models.BooleanField(
        default=False,
        verbose_name='是否流式'
    )
    
    # Token 统计
    prompt_tokens = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='输入Token数'
    )
    
    completion_tokens = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='输出Token数'
    )
    
    total_tokens = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='总Token数'
    )
    
    # 成本核算
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name='预估成本(USD)',
        help_text='基于模型定价的预估成本'
    )
    
    # 元数据
    source_app = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='来源应用',
        help_text='调用来源，如chat、agentic、knowledge等'
    )
    
    source_function = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='来源函数',
        help_text='具体的调用函数或模块'
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='元数据',
        help_text='额外的自定义数据'
    )
    
    # 追踪信息
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP地址'
    )
    
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='用户代理'
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
        db_table = 'llm_call_log'
        verbose_name = 'LLM调用日志'
        verbose_name_plural = 'LLM调用日志'
        ordering = ['-request_timestamp']
        indexes = [
            models.Index(fields=['user', '-request_timestamp']),
            models.Index(fields=['model_name', '-request_timestamp']),
            models.Index(fields=['session_id']),
            models.Index(fields=['status']),
            models.Index(fields=['source_app']),
            models.Index(fields=['vendor_name']),
        ]
    
    def __str__(self):
        return f"{self.model_name} - {self.status} - {self.request_timestamp}"
    
    def save(self, *args, **kwargs):
        # 计算总Token数
        if self.prompt_tokens and self.completion_tokens:
            self.total_tokens = self.prompt_tokens + self.completion_tokens
        
        # 计算耗时
        if self.response_timestamp and self.request_timestamp:
            delta = self.response_timestamp - self.request_timestamp
            self.duration_ms = int(delta.total_seconds() * 1000)
        
        super().save(*args, **kwargs)


class LLMTokenUsage(models.Model):
    """Token 使用统计 - 按用户、模型、日期维度聚合"""
    
    PERIOD_CHOICES = [
        ('hourly', '每小时'),
        ('daily', '每日'),
        ('weekly', '每周'),
        ('monthly', '每月'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='token_usage_stats',
        verbose_name='用户'
    )
    
    model_name = models.CharField(
        max_length=128,
        verbose_name='模型名称',
        db_index=True,
        help_text='对应 router.LLMModel.name'
    )
    
    vendor_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='供应商名称'
    )
    
    date = models.DateField(
        verbose_name='日期',
        db_index=True
    )
    
    hour = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='小时',
        help_text='0-23，用于小时级统计'
    )
    
    period = models.CharField(
        max_length=10,
        choices=PERIOD_CHOICES,
        default='daily',
        verbose_name='统计周期'
    )
    
    # 统计数据
    call_count = models.IntegerField(
        default=0,
        verbose_name='调用次数'
    )
    
    success_count = models.IntegerField(
        default=0,
        verbose_name='成功次数'
    )
    
    failed_count = models.IntegerField(
        default=0,
        verbose_name='失败次数'
    )
    
    total_prompt_tokens = models.BigIntegerField(
        default=0,
        verbose_name='总输入Token'
    )
    
    total_completion_tokens = models.BigIntegerField(
        default=0,
        verbose_name='总输出Token'
    )
    
    total_tokens = models.BigIntegerField(
        default=0,
        verbose_name='总Token数'
    )
    
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name='总成本(USD)'
    )
    
    avg_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='平均耗时(毫秒)'
    )
    
    # 元数据
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='元数据'
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
        db_table = 'llm_token_usage'
        verbose_name = 'Token使用统计'
        verbose_name_plural = 'Token使用统计'
        unique_together = [
            ['user', 'model_name', 'date', 'hour', 'period'],
        ]
        ordering = ['-date', '-hour', 'user', 'model_name']
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['model_name', '-date']),
            models.Index(fields=['vendor_name', '-date']),
            models.Index(fields=['date', 'period']),
        ]
    
    def __str__(self):
        if self.period == 'hourly' and self.hour is not None:
            return f"{self.user.username} - {self.model_name} - {self.date} {self.hour:02d}:00"
        return f"{self.user.username} - {self.model_name} - {self.date} ({self.period})"


class LLMModelPrice(models.Model):
    """LLM 模型定价配置"""
    
    CURRENCY_CHOICES = [
        ('USD', '美元'),
        ('CNY', '人民币'),
        ('EUR', '欧元'),
    ]
    
    model_name = models.CharField(
        max_length=128,
        verbose_name='模型名称',
        db_index=True,
        help_text='对应 router.LLMModel.name'
    )
    
    vendor_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='供应商名称'
    )
    
    input_price_per_1k = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name='输入价格(每1K Token)',
        help_text='每1000个输入Token的价格'
    )
    
    output_price_per_1k = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name='输出价格(每1K Token)',
        help_text='每1000个输出Token的价格'
    )
    
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        verbose_name='货币单位'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )
    
    effective_date = models.DateField(
        default=timezone.now,
        verbose_name='生效日期'
    )
    
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='失效日期'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='描述'
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
        db_table = 'llm_model_price'
        verbose_name = 'LLM模型定价'
        verbose_name_plural = 'LLM模型定价'
        ordering = ['model_name', '-effective_date']
        indexes = [
            models.Index(fields=['model_name', 'is_active']),
            models.Index(fields=['vendor_name', 'model_name']),
        ]
    
    def __str__(self):
        return f"{self.model_name} - {self.currency} {self.input_price_per_1k}/{self.output_price_per_1k}"


class LLMRequestCache(models.Model):
    """LLM 请求缓存 - 用于避免重复请求"""
    
    cache_key = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='缓存键',
        help_text='基于请求参数生成的唯一键'
    )
    
    model_name = models.CharField(
        max_length=128,
        verbose_name='模型名称',
        db_index=True
    )
    
    request_hash = models.CharField(
        max_length=64,
        verbose_name='请求哈希',
        db_index=True,
        help_text='请求内容的哈希值'
    )
    
    request_data = models.JSONField(
        verbose_name='请求数据'
    )
    
    response_data = models.JSONField(
        verbose_name='响应数据'
    )
    
    token_usage = models.JSONField(
        default=dict,
        verbose_name='Token使用情况'
    )
    
    hit_count = models.IntegerField(
        default=0,
        verbose_name='命中次数'
    )
    
    expires_at = models.DateTimeField(
        verbose_name='过期时间',
        db_index=True
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    last_accessed_at = models.DateTimeField(
        auto_now=True,
        verbose_name='最后访问时间'
    )
    
    class Meta:
        db_table = 'llm_request_cache'
        verbose_name = 'LLM请求缓存'
        verbose_name_plural = 'LLM请求缓存'
        ordering = ['-last_accessed_at']
        indexes = [
            models.Index(fields=['model_name', 'request_hash']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.model_name} - {self.cache_key[:20]}..."
    
    def is_expired(self):
        """检查缓存是否过期"""
        return timezone.now() > self.expires_at