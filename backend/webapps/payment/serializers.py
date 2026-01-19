from decimal import Decimal
from rest_framework import serializers
from .models import PaymentOrder, PaymentCallback, PaymentConfig, PaymentLog
from django.contrib.auth import get_user_model

User = get_user_model()


class PaymentOrderSerializer(serializers.ModelSerializer):
    """支付订单序列化器"""
    
    user_display_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    can_pay = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PaymentOrder
        fields = [
            'id', 'order_id', 'trade_order_id', 'user', 'user_display_name',
            'payment_method', 'payment_method_display', 'amount', 'currency',
            'title', 'description', 'product_id', 'status', 'status_display',
            'payment_url', 'qrcode_url', 'notify_url', 'return_url',
            'created_at', 'updated_at', 'paid_at', 'expired_at',
            'extra_data', 'can_pay', 'is_expired'
        ]
        read_only_fields = [
            'id', 'order_id', 'trade_order_id', 'payment_url', 'qrcode_url',
            'created_at', 'updated_at', 'paid_at'
        ]


class CreatePaymentOrderSerializer(serializers.Serializer):
    """创建支付订单序列化器"""
    
    payment_method = serializers.ChoiceField(
        choices=['wechat', 'alipay'],
        required=True,
        help_text='支付方式：wechat-微信支付，alipay-支付宝'
    )
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.01'),
        help_text='支付金额'
    )
    title = serializers.CharField(
        max_length=200,
        required=True,
        help_text='商品标题'
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='商品描述'
    )
    product_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text='商品ID'
    )
    frontend_url = serializers.URLField(
        required=True,
        help_text='前端URL地址，用于支付成功/失败后的页面跳转'
    )
    notify_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text='异步通知URL（可选，默认使用后端地址）'
    )
    return_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text='同步返回URL（可选，默认跳转到frontend_url/payment/success）'
    )
    callback_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text='支付失败返回URL（可选，默认跳转到frontend_url/payment/fail）'
    )
    
    def validate_amount(self, value):
        """验证金额"""
        if value <= 0:
            raise serializers.ValidationError("支付金额必须大于0")
        return value


class PaymentCallbackSerializer(serializers.ModelSerializer):
    """支付回调记录序列化器"""
    
    order_info = PaymentOrderSerializer(source='order', read_only=True)
    callback_type_display = serializers.CharField(source='get_callback_type_display', read_only=True)
    
    class Meta:
        model = PaymentCallback
        fields = [
            'id', 'order', 'order_info', 'callback_type', 'callback_type_display',
            'raw_data', 'signature', 'is_verified', 'is_processed',
            'processed_at', 'error_message', 'ip_address', 'user_agent',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PaymentConfigSerializer(serializers.ModelSerializer):
    """支付配置序列化器"""
    
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    
    class Meta:
        model = PaymentConfig
        fields = [
            'id', 'provider', 'provider_display', 'app_id', 'app_secret',
            'api_url', 'is_active', 'is_test_mode', 'extra_config',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'app_secret': {'write_only': True}  # 密钥只写不读
        }


class PaymentLogSerializer(serializers.ModelSerializer):
    """支付日志序列化器"""
    
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    
    class Meta:
        model = PaymentLog
        fields = [
            'id', 'order', 'log_type', 'log_type_display',
            'message', 'data', 'error_code', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PaymentStatusSerializer(serializers.Serializer):
    """支付状态查询序列化器"""
    
    order_id = serializers.CharField(required=True, help_text='订单号')


class PaymentCallbackDataSerializer(serializers.Serializer):
    """支付回调数据序列化器（虎皮椒）"""
    
    trade_order_id = serializers.CharField(required=True, help_text='商户订单号')
    total_fee = serializers.CharField(required=True, help_text='支付金额')
    transaction_id = serializers.CharField(required=True, help_text='平台订单号')
    open_order_id = serializers.CharField(required=False, help_text='第三方订单号')
    order_date = serializers.CharField(required=False, help_text='订单日期')
    plugins = serializers.CharField(required=False, help_text='插件')
    status = serializers.CharField(required=True, help_text='支付状态')
    hash = serializers.CharField(required=True, help_text='签名')
    time = serializers.CharField(required=False, help_text='时间戳')