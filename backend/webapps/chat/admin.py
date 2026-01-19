from django.contrib import admin
from .models import ChatSession, ChatMessage


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'ai_conversation_id', 'last_interacted_at', 'is_pinned', 'is_archived']
    list_filter = ['is_pinned', 'is_archived', 'last_interacted_at', 'created_at']
    search_fields = ['title', 'ai_conversation_id', 'user__username', 'user__email']
    date_hierarchy = 'last_interacted_at'
    ordering = ['-last_interacted_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'ai_conversation_id', 'title', 'last_message_preview')
        }),
        ('状态', {
            'fields': ('is_pinned', 'is_archived', 'tags')
        }),
        ('时间信息', {
            'fields': ('last_interacted_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'role', 'content_preview', 'task_id', 'is_complete', 'created_at']
    list_filter = ['role', 'is_complete', 'created_at']
    search_fields = ['content', 'task_id', 'session__title']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('session', 'role', 'content')
        }),
        ('任务信息', {
            'fields': ('task_id', 'task_steps', 'is_complete'),
            'classes': ('collapse',)
        }),
        ('附加信息', {
            'fields': ('files_info', 'final_web_search_results'),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = '内容预览'