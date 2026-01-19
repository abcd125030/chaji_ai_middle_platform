from django.contrib import admin
from .models import MomentsPost


@admin.register(MomentsPost)
class MomentsPostAdmin(admin.ModelAdmin):
    """公司圈帖子管理"""

    list_display = [
        'post_id',
        'author_user_id',
        'content_preview',
        'feishu_create_time',
        'created_at',
    ]

    list_filter = [
        'feishu_create_time',
        'created_at',
    ]

    search_fields = [
        'post_id',
        'author_open_id',
        'author_user_id',
        'content_text',
    ]

    readonly_fields = [
        'post_id',
        'author_open_id',
        'author_user_id',
        'content_raw',
        'content_text',
        'category_ids',
        'feishu_create_time',
        'event_id',
        'created_at',
        'updated_at',
    ]

    ordering = ['-feishu_create_time']

    fieldsets = [
        ('帖子标识', {
            'fields': ['post_id', 'event_id']
        }),
        ('发帖人', {
            'fields': ['author_open_id', 'author_user_id']
        }),
        ('帖子内容', {
            'fields': ['content_text', 'content_raw']
        }),
        ('元数据', {
            'fields': ['category_ids', 'feishu_create_time']
        }),
        ('系统信息', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """内容预览（截取前50字符）"""
        if obj.content_text:
            return obj.content_text[:50] + '...' if len(obj.content_text) > 50 else obj.content_text
        return '-'
    content_preview.short_description = '内容预览'
