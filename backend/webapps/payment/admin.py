from django.contrib import admin
from django.utils.html import format_html
from .models import PaymentOrder, PaymentCallback, PaymentConfig, PaymentLog


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    """支付订单管理"""
    
    list_display = [
        'order_id', 'user', 'payment_method', 'amount_display', 
        'title', 'status_badge', 'created_at', 'paid_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at', 'paid_at']
    search_fields = ['order_id', 'trade_order_id', 'title', 'user__username']
    readonly_fields = [
        'order_id', 'trade_order_id', 'created_at', 'updated_at', 
        'payment_url', 'qrcode_url'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('订单信息', {
            'fields': ('order_id', 'trade_order_id', 'user', 'status')
        }),
        ('支付信息', {
            'fields': ('payment_method', 'amount', 'currency', 'payment_url', 'qrcode_url')
        }),
        ('商品信息', {
            'fields': ('title', 'description', 'product_id')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at', 'paid_at', 'expired_at')
        }),
        ('回调配置', {
            'fields': ('notify_url', 'return_url'),
            'classes': ('collapse',)
        }),
        ('扩展数据', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        })
    )
    
    def amount_display(self, obj):
        """格式化显示金额"""
        return f"¥{obj.amount}"
    amount_display.short_description = '金额'
    
    def status_badge(self, obj):
        """状态标签"""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'success': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'refunded': 'purple'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = '状态'
    
    def has_delete_permission(self, request, obj=None):
        """禁止删除已支付的订单"""
        if obj and obj.status == 'success':
            return False
        return super().has_delete_permission(request, obj)


@admin.register(PaymentCallback)
class PaymentCallbackAdmin(admin.ModelAdmin):
    """支付回调记录管理"""
    
    list_display = [
        'id', 'order_link', 'callback_type', 'is_verified', 
        'is_processed', 'created_at'
    ]
    list_filter = ['callback_type', 'is_verified', 'is_processed', 'created_at']
    search_fields = ['order__order_id', 'signature']
    readonly_fields = [
        'order', 'callback_type', 'raw_data', 'signature', 
        'is_verified', 'ip_address', 'user_agent', 'created_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def order_link(self, obj):
        """订单链接"""
        return format_html(
            '<a href="/admin/webapps/payment/paymentorder/{}/change/">{}</a>',
            obj.order.id, obj.order.order_id
        )
    order_link.short_description = '订单'
    
    def has_add_permission(self, request):
        """禁止手动添加回调记录"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """只允许超级管理员删除回调记录"""
        return request.user.is_superuser


@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    """支付配置管理"""
    
    list_display = [
        'provider', 'app_id', 'is_active_badge', 
        'is_test_mode_badge', 'created_at'
    ]
    list_filter = ['provider', 'is_active', 'is_test_mode']
    search_fields = ['provider', 'app_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本配置', {
            'fields': ('provider', 'app_id', 'app_secret', 'api_url')
        }),
        ('状态设置', {
            'fields': ('is_active', 'is_test_mode')
        }),
        ('扩展配置', {
            'fields': ('extra_config',),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def is_active_badge(self, obj):
        """激活状态标签"""
        if obj.is_active:
            return format_html(
                '<span style="color: green;">✓ 已激活</span>'
            )
        return format_html(
            '<span style="color: gray;">未激活</span>'
        )
    is_active_badge.short_description = '状态'
    
    def is_test_mode_badge(self, obj):
        """测试模式标签"""
        if obj.is_test_mode:
            return format_html(
                '<span style="color: orange;">测试模式</span>'
            )
        return format_html(
            '<span style="color: green;">正式模式</span>'
        )
    is_test_mode_badge.short_description = '模式'


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    """支付日志管理"""
    
    list_display = [
        'id', 'order_link', 'log_type_badge', 
        'message_truncated', 'created_at'
    ]
    list_filter = ['log_type', 'created_at']
    search_fields = ['order__order_id', 'message', 'error_code']
    readonly_fields = ['order', 'log_type', 'message', 'data', 'error_code', 'created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def order_link(self, obj):
        """订单链接"""
        if obj.order:
            return format_html(
                '<a href="/admin/webapps/payment/paymentorder/{}/change/">{}</a>',
                obj.order.id, obj.order.order_id
            )
        return '-'
    order_link.short_description = '订单'
    
    def log_type_badge(self, obj):
        """日志类型标签"""
        colors = {
            'request': 'blue',
            'response': 'green',
            'callback': 'purple',
            'error': 'red'
        }
        color = colors.get(obj.log_type, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_log_type_display()
        )
    log_type_badge.short_description = '类型'
    
    def message_truncated(self, obj):
        """截断的消息"""
        if len(obj.message) > 50:
            return obj.message[:50] + '...'
        return obj.message
    message_truncated.short_description = '消息'
    
    def has_add_permission(self, request):
        """禁止手动添加日志"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """只允许超级管理员删除日志"""
        return request.user.is_superuser
