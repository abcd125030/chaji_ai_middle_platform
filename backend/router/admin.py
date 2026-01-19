from django.contrib import admin
from .models import LLMModel, VendorEndpoint, VendorAPIKey
from .vendor_models import Vendor
from django import forms


# 注册 LLMModel 模型到 Admin
@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'model_id', 'model_type', 'get_endpoint', 'api_standard', 'call_count', 'success_count')
    search_fields = ('name', 'model_id')
    list_filter = ('model_type', 'api_standard')
    autocomplete_fields = ['endpoint']  # 启用端点的自动完成搜索功能
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'model_id', 'model_type', 'description')
        }),
        ('接口配置', {
            'fields': ('endpoint', 'api_standard', 'custom_headers')
        }),
        ('模型参数', {
            'fields': ('params',),
            'description': '模型的默认参数，如temperature、max_tokens等'
        }),
        ('适配器配置', {
            'fields': ('adapter_config',),
            'classes': ('collapse',),
            'description': '高级配置：自定义请求/响应处理规则'
        }),
        ('统计信息', {
            'fields': ('call_count', 'success_count'),
            'classes': ('collapse',)
        })
    )
    
    def get_endpoint(self, obj):
        """显示端点信息"""
        if obj.endpoint:
            return f"{obj.endpoint.get_vendor_display()} - {obj.endpoint.service_type}"
        return "-"
    
    get_endpoint.short_description = '模型接口'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # 为JSON字段添加更大的输入框
        if 'params' in form.base_fields:
            form.base_fields['params'].widget = forms.Textarea(attrs={'rows': 4, 'cols': 80})
        if 'custom_headers' in form.base_fields:
            form.base_fields['custom_headers'].widget = forms.Textarea(attrs={'rows': 3, 'cols': 80})
        if 'adapter_config' in form.base_fields:
            form.base_fields['adapter_config'].widget = forms.Textarea(attrs={'rows': 6, 'cols': 80})
        return form


# 注册 VendorEndpoint 模型到 Admin
@admin.register(VendorEndpoint)
class VendorEndpointAdmin(admin.ModelAdmin):
    list_display = ('get_vendor_display', 'service_type', 'endpoint', 'created_at')
    search_fields = ('vendor__display_name', 'vendor__vendor_id', 'service_type', 'endpoint')
    list_filter = ('vendor', 'service_type')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['vendor']  # 使用自动完成搜索
    
    fieldsets = (
        ('供应商信息', {
            'fields': ('vendor',),
            'description': '选择供应商'
        }),
        ('端点设置', {
            'fields': ('service_type', 'endpoint')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_vendor_display(self, obj):
        """显示供应商名称"""
        if obj.vendor:
            return f"{obj.vendor.display_name}"
        elif obj.vendor_name:
            return f"{obj.vendor_name} (旧)"
        return "-"
    
    get_vendor_display.short_description = '供应商'


# 注册 VendorAPIKey 模型到 Admin
@admin.register(VendorAPIKey)
class VendorAPIKeyAdmin(admin.ModelAdmin):
    list_display = ('get_vendor_display', 'masked_key', 'created_at')
    search_fields = ('vendor__display_name', 'vendor__vendor_id', 'description')
    list_filter = ('vendor',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['vendor']  # 使用自动完成搜索
    
    fieldsets = (
        ('供应商信息', {
            'fields': ('vendor',),
            'description': '选择供应商'
        }),
        ('API密钥', {
            'fields': ('api_key', 'description')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_vendor_display(self, obj):
        """显示供应商名称"""
        if obj.vendor:
            return f"{obj.vendor.display_name}"
        elif obj.vendor_name:
            return f"{obj.vendor_name} (旧)"
        return "-"
    
    get_vendor_display.short_description = '供应商'
    
    def masked_key(self, obj):
        """显示部分隐藏的API密钥"""
        if obj.api_key:
            visible_chars = min(4, len(obj.api_key))
            return f"{obj.api_key[:visible_chars]}{'*' * (len(obj.api_key) - visible_chars)}"
        return "-"
        
    masked_key.short_description = 'API密钥(隐藏)'


# 注册 Vendor 模型到 Admin
@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'vendor_id', 'is_active', 'priority', 'created_at')
    search_fields = ('display_name', 'vendor_id', 'description')  # 支持autocomplete
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'priority')
    ordering = ['-priority', 'display_name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('vendor_id', 'display_name', 'description', 'website')
        }),
        ('配置信息', {
            'fields': ('supported_services', 'config_template')
        }),
        ('状态控制', {
            'fields': ('is_active', 'priority')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # 为JSON字段添加更大的输入框
        if 'supported_services' in form.base_fields:
            form.base_fields['supported_services'].widget = forms.Textarea(attrs={'rows': 4, 'cols': 60})
        if 'config_template' in form.base_fields:
            form.base_fields['config_template'].widget = forms.Textarea(attrs={'rows': 6, 'cols': 60})
        return form

