from django.db import models
from .vendor_models import Vendor


class VendorEndpoint(models.Model):
    """定义供应商端点的数据模型"""
    
    # 关联到动态供应商表
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='endpoints',
        verbose_name='供应商',
        null=True,  # 允许为空以兼容旧数据
        blank=True
    )
    
    # 保留旧字段以兼容
    VENDOR_NAME_CHOICES = [
        ('OpenRouter', 'OpenRouter'),
        ('frago', 'frago'),
        ('茶姬', '茶姬'),
        ('阿里云百炼大模型', '阿里云百炼大模型'),
    ]

    vendor_name = models.CharField(
        max_length=128,
        choices=VENDOR_NAME_CHOICES,
        verbose_name='供应商名称（旧）',
        null=True,
        blank=True
    )

    VENDOR_ID_CHOICES = [
        ('openrouter', 'openrouter'),
        ('frago', 'frago'),
        ('chagee', 'chagee'),
        ('aliyun', 'aliyun'),
    ]

    vendor_id_legacy = models.CharField(
        max_length=64,
        choices=VENDOR_ID_CHOICES,
        verbose_name='供应商标识符（旧）',
        null=True,
        blank=True,
        db_column='vendor_id_old'  # 使用不同的列名避免冲突
    )
    
    endpoint = models.URLField(
        max_length=256,
        verbose_name='API端点地址'
    )
    
    service_type = models.CharField(
        max_length=1000,
        verbose_name='服务类型',
        help_text='如: 文本补全、图像生成、语音识别等'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    def get_vendor_display(self):
        """获取供应商显示名称"""
        if self.vendor:
            return self.vendor.display_name
        return self.vendor_name or '未知供应商'
    
    def get_vendor_identifier(self):
        """获取供应商标识符"""
        if self.vendor:
            return self.vendor.vendor_id
        return self.vendor_id_legacy
    
    def __str__(self):
        vendor_display = self.get_vendor_display()
        vendor_id = self.get_vendor_identifier()
        return f"{vendor_display} - {self.service_type} ({vendor_id})"
    
    class Meta:
        verbose_name = '供应商端点'
        verbose_name_plural = '供应商端点'
        ordering = ['vendor_name', 'service_type']


class VendorAPIKey(models.Model):
    """定义供应商API密钥的数据模型"""
    
    # 关联到动态供应商表
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name='供应商',
        null=True,  # 允许为空以兼容旧数据
        blank=True
    )
    
    # 保留旧字段以兼容
    VENDOR_NAME_CHOICES = [
        ('OpenRouter', 'OpenRouter'),
        ('frago', 'frago'),
        ('茶姬', '茶姬'),
        ('阿里云百炼大模型', '阿里云百炼大模型'),
    ]

    vendor_name = models.CharField(
        max_length=128,
        choices=VENDOR_NAME_CHOICES,
        verbose_name='供应商名称（旧）',
        null=True,
        blank=True
    )

    VENDOR_ID_CHOICES = [
        ('openrouter', 'openrouter'),
        ('frago', 'frago'),
        ('chagee', 'chagee'),
        ('aliyun', 'aliyun'),
    ]

    vendor_id_legacy = models.CharField(
        max_length=64,
        choices=VENDOR_ID_CHOICES,
        verbose_name='供应商标识符（旧）',
        null=True,
        blank=True,
        db_column='vendor_id_old'  # 使用不同的列名避免冲突
    )
    
    api_key = models.CharField(
        max_length=256,
        verbose_name='API密钥'
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='密钥描述',
        help_text='可用于记录密钥的用途、限制或其他相关信息'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    def get_vendor_display(self):
        """获取供应商显示名称"""
        if self.vendor:
            return self.vendor.display_name
        return self.vendor_name or '未知供应商'
    
    def get_vendor_identifier(self):
        """获取供应商标识符"""
        if self.vendor:
            return self.vendor.vendor_id
        return self.vendor_id_legacy
    
    def __str__(self):
        vendor_display = self.get_vendor_display()
        vendor_id = self.get_vendor_identifier()
        return f"{vendor_display} Key ({vendor_id})"
    
    class Meta:
        verbose_name = '供应商API密钥'
        verbose_name_plural = '供应商API密钥'
        ordering = ['vendor_name']


class LLMModel(models.Model):
    """定义大语言模型的数据模型"""

    MODEL_TYPE_CHOICES = [
        ('text', 'Text'),
        ('reasoning', 'Reasoning'),
        ('vision', 'Vision'),
        ('embedding', 'Embedding'),  # 向量嵌入模型
        ('rerank', 'Rerank'),  # 重排序模型
    ]

    API_STANDARD_CHOICES = [
        ('openai', 'OpenAI'),
        ('huggingface', 'HuggingFace'),
        ('custom', 'Custom'),
    ]

    name = models.CharField(
        max_length=128,
        verbose_name='模型名称'
    )
    model_id = models.CharField(
        max_length=128,
        verbose_name='模型标识符',
        help_text='调用 API 时使用的模型标识符，如 gpt-3.5-turbo、llama-7b 等',
        default='default-model'  # 添加默认值
    )
    model_type = models.CharField(
        max_length=32,
        choices=MODEL_TYPE_CHOICES,
        verbose_name='模型类型'
    )
    endpoint = models.ForeignKey(
        VendorEndpoint,
        on_delete=models.CASCADE,
        verbose_name='模型接口',
        related_name='llm_models'
    )
    api_standard = models.CharField(
        max_length=32,
        choices=API_STANDARD_CHOICES,
        verbose_name='模型接口标准'
    )
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='自定义请求头',
        help_text='用于配置额外的API请求头'
    )
    params = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='模型参数'
    )
    adapter_config = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='适配器配置',
        help_text='模型特定的适配器配置，如响应解析规则、请求转换规则等'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='模型描述'
    )
    call_count = models.PositiveIntegerField(
        default=0,
        verbose_name='调用次数'
    )
    success_count = models.PositiveIntegerField(
        default=0,
        verbose_name='调用成功次数'
    )

    def get_adapter(self):
        """获取该模型的适配器实例"""
        from .adapters.factory import AdapterFactory
        
        # 构建模型配置
        model_config = {
            'model_id': self.model_id,
            'model_type': self.model_type,
            'vendor': self.endpoint.get_vendor_identifier() if self.endpoint else None,
            'endpoint': self.endpoint.endpoint if self.endpoint else None,
            'api_standard': self.api_standard,
            'custom_headers': self.custom_headers or {},
            'adapter_config': self.adapter_config or {},
        }
        
        return AdapterFactory.create_adapter(model_config)
    
    def __str__(self):
        """返回模型名称，用于在选择框中显示"""
        return f"{self.name} ({self.model_id})"
    
    class Meta:
        verbose_name = '大语言模型'
        verbose_name_plural = '大语言模型'

