from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import LLMCallLog, LLMTokenUsage, LLMModelPrice, LLMRequestCache


@admin.register(LLMCallLog)
class LLMCallLogAdmin(admin.ModelAdmin):
    list_display = [
        'request_id_short', 'model_name', 'vendor_name', 'user', 
        'status_colored', 'call_type', 'total_tokens', 
        'duration_ms', 'request_timestamp'
    ]
    list_filter = [
        'status', 'call_type', 'model_name', 'vendor_name', 
        'source_app', 'is_stream', 'request_timestamp'
    ]
    search_fields = [
        'request_id', 'model_name', 'user__username', 
        'session_id', 'error_message'
    ]
    readonly_fields = [
        'id', 'request_id', 'created_at', 'updated_at',
        'duration_ms', 'total_tokens'
    ]
    date_hierarchy = 'request_timestamp'
    ordering = ['-request_timestamp']
    
    fieldsets = (
        ('基础信息', {
            'fields': ('id', 'request_id', 'user', 'session_id', 'call_type')
        }),
        ('模型信息', {
            'fields': ('model_name', 'model_id', 'vendor_name', 'vendor_id', 'endpoint')
        }),
        ('请求信息', {
            'fields': ('request_timestamp', 'request_messages', 'request_params', 'request_headers', 'is_stream')
        }),
        ('响应信息', {
            'fields': ('response_timestamp', 'response_content', 'response_raw', 'status', 'error_message', 'error_code')
        }),
        ('性能指标', {
            'fields': ('duration_ms', 'retry_count')
        }),
        ('Token统计', {
            'fields': ('prompt_tokens', 'completion_tokens', 'total_tokens', 'estimated_cost')
        }),
        ('追踪信息', {
            'fields': ('source_app', 'source_function', 'ip_address', 'user_agent', 'metadata')
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def request_id_short(self, obj):
        return f"{str(obj.request_id)[:8]}..."
    request_id_short.short_description = '请求ID'
    
    def status_colored(self, obj):
        colors = {
            'success': 'green',
            'failed': 'red',
            'timeout': 'orange',
            'processing': 'blue',
            'pending': 'gray',
            'cancelled': 'darkred'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = '状态'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # 如果不是超级用户，只显示自己的日志
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs


@admin.register(LLMTokenUsage)
class LLMTokenUsageAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'model_name', 'vendor_name', 'date', 'hour_display',
        'period', 'call_count', 'total_tokens', 'total_cost'
    ]
    list_filter = [
        'period', 'model_name', 'vendor_name', 'date'
    ]
    search_fields = [
        'user__username', 'model_name', 'vendor_name'
    ]
    date_hierarchy = 'date'
    ordering = ['-date', '-hour']
    
    fieldsets = (
        ('基础信息', {
            'fields': ('user', 'model_name', 'vendor_name', 'date', 'hour', 'period')
        }),
        ('统计数据', {
            'fields': ('call_count', 'success_count', 'failed_count')
        }),
        ('Token统计', {
            'fields': ('total_prompt_tokens', 'total_completion_tokens', 'total_tokens')
        }),
        ('成本与性能', {
            'fields': ('total_cost', 'avg_duration_ms')
        }),
        ('元数据', {
            'fields': ('metadata', 'created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'total_tokens']
    
    def hour_display(self, obj):
        if obj.period == 'hourly' and obj.hour is not None:
            return f"{obj.hour:02d}:00"
        return '-'
    hour_display.short_description = '小时'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # 如果不是超级用户，只显示自己的统计
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs


@admin.register(LLMModelPrice)
class LLMModelPriceAdmin(admin.ModelAdmin):
    list_display = [
        'model_name', 'vendor_name', 'input_price_per_1k', 
        'output_price_per_1k', 'currency', 'is_active', 
        'effective_date'
    ]
    list_filter = [
        'is_active', 'currency', 'vendor_name', 'effective_date'
    ]
    search_fields = ['model_name', 'vendor_name', 'description']
    ordering = ['model_name', '-effective_date']
    
    fieldsets = (
        ('模型信息', {
            'fields': ('model_name', 'vendor_name')
        }),
        ('定价信息', {
            'fields': ('input_price_per_1k', 'output_price_per_1k', 'currency')
        }),
        ('有效期', {
            'fields': ('is_active', 'effective_date', 'expiry_date')
        }),
        ('其他', {
            'fields': ('description', 'created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        # 如果设置为活跃，将同模型的其他定价设为非活跃
        if obj.is_active:
            LLMModelPrice.objects.filter(
                model_name=obj.model_name,
                is_active=True
            ).exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(LLMRequestCache)
class LLMRequestCacheAdmin(admin.ModelAdmin):
    list_display = [
        'cache_key_short', 'model_name', 'hit_count', 
        'is_expired_display', 'expires_at', 'last_accessed_at'
    ]
    list_filter = ['model_name', 'expires_at']
    search_fields = ['cache_key', 'model_name', 'request_hash']
    ordering = ['-last_accessed_at']
    
    fieldsets = (
        ('缓存信息', {
            'fields': ('cache_key', 'model_name', 'request_hash')
        }),
        ('数据', {
            'fields': ('request_data', 'response_data', 'token_usage')
        }),
        ('统计', {
            'fields': ('hit_count', 'expires_at', 'created_at', 'last_accessed_at')
        }),
    )
    
    readonly_fields = ['created_at', 'last_accessed_at']
    
    def cache_key_short(self, obj):
        return f"{obj.cache_key[:30]}..."
    cache_key_short.short_description = '缓存键'
    
    def is_expired_display(self, obj):
        is_expired = obj.is_expired()
        color = 'red' if is_expired else 'green'
        text = '已过期' if is_expired else '有效'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            text
        )
    is_expired_display.short_description = '状态'
    
    actions = ['clear_expired_cache']
    
    def clear_expired_cache(self, request, queryset):
        now = timezone.now()
        expired_count = LLMRequestCache.objects.filter(expires_at__lt=now).count()
        LLMRequestCache.objects.filter(expires_at__lt=now).delete()
        self.message_user(request, f"已清理 {expired_count} 条过期缓存")
    clear_expired_cache.short_description = "清理所有过期缓存"