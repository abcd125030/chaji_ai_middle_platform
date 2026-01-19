from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class PaymentOrder(models.Model):
    """支付订单模型"""
    
    PAYMENT_METHOD_CHOICES = [
        ('wechat', '微信支付'),
        ('alipay', '支付宝'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待支付'),
        ('processing', '处理中'),
        ('success', '支付成功'),
        ('failed', '支付失败'),
        ('cancelled', '已取消'),
        ('refunded', '已退款'),
    ]
    
    # 订单基本信息
    order_id = models.CharField(
        max_length=64, 
        unique=True, 
        verbose_name='订单号',
        help_text='商户系统内部订单号'
    )
    trade_order_id = models.CharField(
        max_length=128, 
        blank=True, 
        null=True,
        verbose_name='第三方交易号',
        help_text='支付平台返回的交易号'
    )
    
    # 用户关联
    user = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='payment_orders',
        verbose_name='用户'
    )
    
    # 支付信息
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name='支付方式'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name='支付金额'
    )
    currency = models.CharField(
        max_length=10,
        default='CNY',
        verbose_name='货币类型'
    )
    
    # 商品信息
    title = models.CharField(
        max_length=200,
        verbose_name='商品标题'
    )
    description = models.TextField(
        blank=True,
        verbose_name='商品描述'
    )
    product_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='商品ID',
        help_text='关联的商品或服务ID'
    )
    
    # 状态信息
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='订单状态'
    )
    
    # 支付平台信息
    payment_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='支付页面URL'
    )
    qrcode_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='支付二维码URL'
    )
    
    # 回调信息
    notify_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='异步通知URL'
    )
    return_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='同步返回URL'
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
    paid_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='支付时间'
    )
    expired_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='过期时间'
    )
    
    # 附加信息
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='扩展数据',
        help_text='存储额外的支付相关信息'
    )
    
    class Meta:
        db_table = 'payment_orders'
        verbose_name = '支付订单'
        verbose_name_plural = '支付订单'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.order_id} - {self.title} - {self.get_status_display()}"
    
    def is_expired(self):
        """检查订单是否已过期"""
        if self.expired_at:
            return timezone.now() > self.expired_at
        return False
    
    def can_pay(self):
        """检查订单是否可以支付"""
        return self.status == 'pending' and not self.is_expired()


class PaymentCallback(models.Model):
    """支付回调记录"""
    
    CALLBACK_TYPE_CHOICES = [
        ('notify', '异步通知'),
        ('return', '同步返回'),
    ]
    
    order = models.ForeignKey(
        PaymentOrder,
        on_delete=models.CASCADE,
        related_name='callbacks',
        verbose_name='支付订单'
    )
    
    callback_type = models.CharField(
        max_length=20,
        choices=CALLBACK_TYPE_CHOICES,
        verbose_name='回调类型'
    )
    
    # 回调数据
    raw_data = models.JSONField(
        verbose_name='原始数据',
        help_text='支付平台返回的原始数据'
    )
    
    # 签名验证
    signature = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='签名'
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='签名验证通过'
    )
    
    # 处理结果
    is_processed = models.BooleanField(
        default=False,
        verbose_name='是否已处理'
    )
    processed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='处理时间'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='错误信息'
    )
    
    # 请求信息
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name='IP地址'
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='User-Agent'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    class Meta:
        db_table = 'payment_callbacks'
        verbose_name = '支付回调记录'
        verbose_name_plural = '支付回调记录'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_id} - {self.get_callback_type_display()} - {self.created_at}"


class PaymentConfig(models.Model):
    """支付配置"""
    
    PROVIDER_CHOICES = [
        ('hupijiao', '虎皮椒支付'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    ]
    
    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        unique=True,
        verbose_name='支付服务商'
    )
    
    # 基本配置
    app_id = models.CharField(
        max_length=200,
        verbose_name='应用ID'
    )
    app_secret = models.CharField(
        max_length=500,
        verbose_name='应用密钥'
    )
    
    # API配置
    api_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='API地址'
    )
    
    # 状态
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )
    is_test_mode = models.BooleanField(
        default=False,
        verbose_name='测试模式'
    )
    
    # 额外配置
    extra_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='额外配置',
        help_text='其他配置参数'
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
    
    class Meta:
        db_table = 'payment_configs'
        verbose_name = '支付配置'
        verbose_name_plural = '支付配置'
    
    def __str__(self):
        return f"{self.get_provider_display()} - {'测试' if self.is_test_mode else '正式'}"


class PaymentLog(models.Model):
    """支付日志"""
    
    LOG_TYPE_CHOICES = [
        ('request', '请求'),
        ('response', '响应'),
        ('callback', '回调'),
        ('error', '错误'),
    ]
    
    order = models.ForeignKey(
        PaymentOrder,
        on_delete=models.CASCADE,
        related_name='logs',
        blank=True,
        null=True,
        verbose_name='支付订单'
    )
    
    log_type = models.CharField(
        max_length=20,
        choices=LOG_TYPE_CHOICES,
        verbose_name='日志类型'
    )
    
    # 日志内容
    message = models.TextField(
        verbose_name='日志消息'
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='日志数据'
    )
    
    # 错误信息
    error_code = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='错误代码'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    class Meta:
        db_table = 'payment_logs'
        verbose_name = '支付日志'
        verbose_name_plural = '支付日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_log_type_display()} - {self.created_at}"
