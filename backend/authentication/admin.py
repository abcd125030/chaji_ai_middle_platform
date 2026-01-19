from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, OAuthState, UserAccount, EmailVerification
from .models_extension import UserProfile


class UserAccountInline(admin.TabularInline):
    """用户账号内联显示"""
    model = UserAccount
    extra = 0
    can_delete = True
    verbose_name = '登录账号'
    verbose_name_plural = '登录账号'
    fields = ('provider', 'provider_account_id', 'is_primary', 'is_verified', 'last_used_at')
    readonly_fields = ('provider_account_id', 'last_used_at')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # 让字段更友好
        if 'is_primary' in formset.form.base_fields:
            formset.form.base_fields['is_primary'].help_text = '一个用户只能有一个主账号'
        return formset



@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """用户管理"""
    list_display = ('username', 'email', 'get_providers', 'get_primary_provider', 'status', 'role', 'is_staff', 'date_joined')
    list_filter = ('status', 'role', 'is_staff', 'is_superuser', 'is_active', 'auth_type')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'external_id')
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('认证信息', {
            'fields': ('auth_type', 'external_id', 'avatar_url'),
            'description': '注意：auth_type 和 external_id 已废弃，请使用下方的"登录账号"管理多种登录方式'
        }),
        ('扩展信息', {
            'fields': ('status', 'role', 'phone', 'twitter_url', 'linkedin_url')
        }),
        ('协议与安全', {
            'fields': ('agreed_agreement_version', 'agreed_at', 'reset_token', 'reset_token_expires_at')
        }),
        ('统计信息', {
            'fields': ('login_count', 'last_login_ip'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('login_count', 'last_login_ip', 'agreed_at')
    inlines = [UserAccountInline]
    
    def get_providers(self, obj):
        """显示用户的所有登录方式"""
        accounts = obj.accounts.all()
        if not accounts:
            return format_html('<span style="color: #999;">无</span>')
        
        providers = []
        for acc in accounts:
            color = '#28a745' if acc.is_verified else '#ffc107'
            primary = '⭐' if acc.is_primary else ''
            providers.append(
                format_html('<span style="color: {};">{}{}</span>', 
                           color, acc.get_provider_display(), primary)
            )
        return format_html(' | '.join(providers))
    
    get_providers.short_description = '登录方式'
    
    def get_primary_provider(self, obj):
        """显示主要登录方式"""
        primary = obj.get_primary_account()
        if primary:
            return format_html('<strong>{}</strong>', primary.get_provider_display())
        return '-'
    
    get_primary_provider.short_description = '主账号'


@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    """用户账号管理"""
    list_display = ('user', 'provider', 'provider_account_id', 'is_primary', 'is_verified', 'created_at', 'last_used_at')
    list_filter = ('provider', 'type', 'is_primary', 'is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'provider_account_id', 'nickname')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'provider', 'type', 'provider_account_id')
        }),
        ('账号状态', {
            'fields': ('is_primary', 'is_verified', 'last_used_at')
        }),
        ('OAuth 信息', {
            'fields': ('access_token', 'refresh_token', 'expires_at', 'scope'),
            'classes': ('collapse',)
        }),
        ('用户信息', {
            'fields': ('nickname', 'avatar_url', 'provider_profile'),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['set_as_primary', 'verify_accounts']
    
    def set_as_primary(self, request, queryset):
        """设置为主账号"""
        for account in queryset:
            account.is_primary = True
            account.save()
        self.message_user(request, f'已将 {queryset.count()} 个账号设置为主账号')
    
    set_as_primary.short_description = '设置为主账号'
    
    def verify_accounts(self, request, queryset):
        """标记为已验证"""
        queryset.update(is_verified=True)
        self.message_user(request, f'已验证 {queryset.count()} 个账号')
    
    verify_accounts.short_description = '标记为已验证'


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    """邮箱验证管理"""
    list_display = ('user', 'email', 'token', 'is_used', 'created_at', 'expires_at', 'is_expired_display')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__username', 'email', 'token')
    raw_id_fields = ('user',)
    readonly_fields = ('token', 'created_at')
    
    def is_expired_display(self, obj):
        """显示是否过期"""
        if obj.is_expired():
            return format_html('<span style="color: red;">已过期</span>')
        return format_html('<span style="color: green;">有效</span>')
    
    is_expired_display.short_description = '状态'


@admin.register(OAuthState)
class OAuthStateAdmin(admin.ModelAdmin):
    """OAuth 状态管理"""
    list_display = ('state', 'provider', 'redirect_url', 'created_at', 'is_expired_display')
    search_fields = ('state', 'provider', 'redirect_url')
    list_filter = ('provider', 'created_at')
    readonly_fields = ('state', 'created_at')
    date_hierarchy = 'created_at'
    
    def is_expired_display(self, obj):
        """显示是否过期"""
        if obj.is_expired():
            return format_html('<span style="color: red;">已过期</span>')
        return format_html('<span style="color: green;">有效</span>')
    
    is_expired_display.short_description = '状态'
    
    actions = ['delete_expired']
    
    def delete_expired(self, request, queryset):
        """删除过期的状态"""
        from django.utils import timezone
        from datetime import timedelta
        
        expired_time = timezone.now() - timedelta(minutes=10)
        expired = queryset.filter(created_at__lt=expired_time)
        count = expired.count()
        expired.delete()
        self.message_user(request, f'已删除 {count} 个过期状态')
    
    delete_expired.short_description = '删除过期状态'



@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """用户配置文件管理"""
    list_display = ('user', 'subscription_type', 'industry', 'created_at', 'updated_at')
    list_filter = ('subscription_type', 'industry', 'created_at')
    search_fields = ('user__username', 'user__email', 'tags')
    raw_id_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'subscription_type', 'industry')
        }),
        ('标签和偏好', {
            'fields': ('tags', 'preferences', 'context_data'),
            'classes': ('collapse',)
        }),
        ('配额和使用统计', {
            'fields': ('quotas', 'usage_stats', 'capabilities'),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# 自定义 Admin 站点标题
admin.site.site_header = '用户认证管理系统'
admin.site.site_title = '认证管理'
admin.site.index_title = '欢迎使用多账号认证系统'