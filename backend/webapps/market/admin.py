"""
frago Cloud Market Admin 配置

注册所有 Market 模型到 Django Admin
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Recipe, RecipeVersion, RecipeRating, SyncedSession, DeviceCode,
    ClaudeCodeVersion, ClaudeCodeBinary, ClaudeCodeDownloadLog,
)


class RecipeVersionInline(admin.TabularInline):
    """Recipe 版本内联显示"""
    model = RecipeVersion
    extra = 0
    readonly_fields = ('version', 'file_size', 'is_latest', 'created_at')
    fields = ('version', 'file_size', 'is_latest', 'changelog', 'created_at')
    ordering = ['-created_at']


class RecipeRatingInline(admin.TabularInline):
    """Recipe 评分内联显示"""
    model = RecipeRating
    extra = 0
    readonly_fields = ('user', 'rating', 'comment', 'created_at')
    fields = ('user', 'rating', 'comment', 'created_at')
    ordering = ['-created_at']


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Recipe 管理"""
    list_display = ('name', 'author', 'runtime', 'is_public', 'is_premium',
                    'download_count', 'average_rating', 'created_at')
    list_filter = ('runtime', 'is_public', 'is_premium', 'created_at')
    search_fields = ('name', 'description', 'author__username')
    readonly_fields = ('download_count', 'average_rating', 'created_at', 'updated_at')
    raw_id_fields = ('author',)
    inlines = [RecipeVersionInline, RecipeRatingInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'author', 'description', 'runtime')
        }),
        ('状态', {
            'fields': ('is_public', 'is_premium')
        }),
        ('统计', {
            'fields': ('download_count', 'average_rating'),
            'classes': ('collapse',)
        }),
        ('时间', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RecipeVersion)
class RecipeVersionAdmin(admin.ModelAdmin):
    """Recipe 版本管理"""
    list_display = ('recipe', 'version', 'is_latest', 'file_size_display', 'created_at')
    list_filter = ('is_latest', 'created_at')
    search_fields = ('recipe__name', 'version', 'changelog')
    readonly_fields = ('file_size', 'created_at')
    raw_id_fields = ('recipe',)

    def file_size_display(self, obj):
        """显示文件大小（格式化）"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.2f} MB"
    file_size_display.short_description = '文件大小'


@admin.register(RecipeRating)
class RecipeRatingAdmin(admin.ModelAdmin):
    """Recipe 评分管理"""
    list_display = ('recipe', 'user', 'rating_stars', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('recipe__name', 'user__username', 'comment')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('recipe', 'user')

    def rating_stars(self, obj):
        """显示星级"""
        return '★' * obj.rating + '☆' * (5 - obj.rating)
    rating_stars.short_description = '评分'


@admin.register(SyncedSession)
class SyncedSessionAdmin(admin.ModelAdmin):
    """同步会话管理"""
    list_display = ('session_id', 'user', 'name', 'agent_type',
                    'file_size_display', 'created_at')
    list_filter = ('agent_type', 'created_at')
    search_fields = ('session_id', 'name', 'user__username')
    readonly_fields = ('id', 'storage_key', 'file_size', 'created_at', 'updated_at')
    raw_id_fields = ('user',)

    def file_size_display(self, obj):
        """显示文件大小（格式化）"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.2f} MB"
    file_size_display.short_description = '文件大小'


@admin.register(DeviceCode)
class DeviceCodeAdmin(admin.ModelAdmin):
    """设备认证码管理"""
    list_display = ('user_code', 'client_id', 'user', 'status',
                    'is_expired_display', 'created_at', 'expires_at')
    list_filter = ('status', 'client_id', 'created_at')
    search_fields = ('user_code', 'device_code', 'user__username', 'client_id')
    readonly_fields = ('id', 'device_code', 'user_code', 'created_at',
                       'authorized_at', 'is_expired_display')
    raw_id_fields = ('user',)

    def is_expired_display(self, obj):
        """显示是否已过期"""
        if obj.is_expired:
            return format_html('<span style="color: red;">已过期</span>')
        return format_html('<span style="color: green;">有效</span>')
    is_expired_display.short_description = '过期状态'

    fieldsets = (
        ('认证码', {
            'fields': ('id', 'device_code', 'user_code')
        }),
        ('状态', {
            'fields': ('status', 'user', 'is_expired_display')
        }),
        ('客户端', {
            'fields': ('client_id', 'scope')
        }),
        ('时间', {
            'fields': ('created_at', 'expires_at', 'authorized_at'),
            'classes': ('collapse',)
        }),
    )


# ==================== Claude Code 镜像管理（US6） ====================

class ClaudeCodeBinaryInline(admin.TabularInline):
    """Claude Code 二进制内联显示"""
    model = ClaudeCodeBinary
    extra = 0
    readonly_fields = ('platform_arch', 'file_size_display', 'sha256', 'download_count', 'created_at')
    fields = ('platform_arch', 'file_size_display', 'sha256', 'download_count', 'created_at')

    def file_size_display(self, obj):
        """显示文件大小（格式化）"""
        if obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = '文件大小'


@admin.register(ClaudeCodeVersion)
class ClaudeCodeVersionAdmin(admin.ModelAdmin):
    """Claude Code 版本管理"""
    list_display = ('version', 'released_at', 'deprecated', 'binaries_count', 'created_at')
    list_filter = ('deprecated', 'released_at')
    search_fields = ('version', 'changelog')
    readonly_fields = ('created_at',)
    inlines = [ClaudeCodeBinaryInline]

    fieldsets = (
        ('版本信息', {
            'fields': ('version', 'released_at', 'deprecated')
        }),
        ('更新说明', {
            'fields': ('changelog',),
            'classes': ('collapse',)
        }),
        ('时间', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def binaries_count(self, obj):
        """二进制文件数量"""
        return obj.binaries.count()
    binaries_count.short_description = '二进制数'


@admin.register(ClaudeCodeBinary)
class ClaudeCodeBinaryAdmin(admin.ModelAdmin):
    """Claude Code 二进制管理"""
    list_display = ('version', 'platform_arch', 'file_size_display', 'download_count', 'created_at')
    list_filter = ('platform_arch', 'version__version')
    search_fields = ('version__version', 'sha256')
    readonly_fields = ('download_count', 'created_at')
    raw_id_fields = ('version',)

    def file_size_display(self, obj):
        """显示文件大小（格式化）"""
        if obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = '文件大小'


@admin.register(ClaudeCodeDownloadLog)
class ClaudeCodeDownloadLogAdmin(admin.ModelAdmin):
    """Claude Code 下载日志管理"""
    list_display = ('ip_address', 'binary', 'created_at')
    list_filter = ('created_at', 'binary__platform_arch')
    search_fields = ('ip_address',)
    readonly_fields = ('ip_address', 'binary', 'created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        """禁止手动添加"""
        return False

    def has_change_permission(self, request, obj=None):
        """禁止修改"""
        return False
