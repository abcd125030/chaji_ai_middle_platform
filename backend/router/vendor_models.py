"""
供应商动态管理模型
"""
from django.db import models
from django.core.validators import RegexValidator


class Vendor(models.Model):
    """供应商配置表"""
    
    # 供应商标识符，用于代码中引用
    vendor_id = models.CharField(
        max_length=64,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9_]+$',
                message='供应商ID只能包含小写字母、数字和下划线'
            )
        ],
        verbose_name='供应商标识符',
        help_text='用于代码中引用，只能包含小写字母、数字和下划线'
    )
    
    # 供应商显示名称
    display_name = models.CharField(
        max_length=128,
        verbose_name='显示名称',
        help_text='在界面上显示的友好名称'
    )
    
    # 供应商描述
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='描述',
        help_text='供应商的详细描述信息'
    )
    
    # 供应商官网
    website = models.URLField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name='官方网站'
    )
    
    # 支持的服务类型
    supported_services = models.JSONField(
        default=list,
        verbose_name='支持的服务',
        help_text='列表格式，如: ["文本补全", "图像生成", "语音识别"]'
    )
    
    # 配置模板
    config_template = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='配置模板',
        help_text='供应商特定的配置参数模板'
    )
    
    # 是否启用
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )
    
    # 排序权重
    priority = models.IntegerField(
        default=0,
        verbose_name='优先级',
        help_text='数值越大优先级越高'
    )
    
    # 时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    def __str__(self):
        return f"{self.display_name} ({self.vendor_id})"
    
    class Meta:
        verbose_name = '供应商'
        verbose_name_plural = '供应商'
        ordering = ['-priority', 'display_name']
        indexes = [
            models.Index(fields=['vendor_id']),
            models.Index(fields=['is_active', '-priority']),
        ]