"""
Xiaohongshu sentiment monitoring admin configuration
"""
from django.contrib import admin
from .models import MonitorKeyword, XiaohongshuNote, NoteAnalysisResult


@admin.register(MonitorKeyword)
class MonitorKeywordAdmin(admin.ModelAdmin):
    """Monitor keyword admin"""

    list_display = [
        'keyword',
        'match_type',
        'category',
        'is_active',
        'priority',
        'created_at',
    ]

    list_filter = [
        'is_active',
        'match_type',
        'category',
    ]

    search_fields = [
        'keyword',
        'category',
        'description',
    ]

    list_editable = [
        'is_active',
        'priority',
    ]

    ordering = ['-priority', '-created_at']

    fieldsets = [
        ('关键词配置', {
            'fields': ['keyword', 'match_type', 'is_active', 'priority']
        }),
        ('分类与描述', {
            'fields': ['category', 'description']
        }),
        ('系统信息', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    readonly_fields = ['created_at', 'updated_at']


@admin.register(XiaohongshuNote)
class XiaohongshuNoteAdmin(admin.ModelAdmin):
    """Xiaohongshu note admin"""

    list_display = [
        'note_id',
        'author_name',
        'description_preview',
        'note_type',
        'status',
        'likes_count',
        'collects_count',
        'comments_count',
        'extracted_at',
    ]

    list_filter = [
        'note_type',
        'status',
        'extracted_at',
        'created_at',
    ]

    search_fields = [
        'note_id',
        'author_name',
        'description',
        'tags',
    ]

    readonly_fields = [
        'note_id',
        'author_name',
        'author_avatar',
        'description',
        'note_type',
        'images',
        'tags',
        'likes_count',
        'collects_count',
        'comments_count',
        'publish_time',
        'location',
        'top_comments',
        'extracted_at',
        'card_index',
        'source',
        'raw_data',
        'created_at',
        'updated_at',
    ]

    ordering = ['-extracted_at']

    fieldsets = [
        ('笔记标识', {
            'fields': ['note_id', 'note_type', 'status']
        }),
        ('作者信息', {
            'fields': ['author_name', 'author_avatar']
        }),
        ('笔记内容', {
            'fields': ['description', 'images', 'tags']
        }),
        ('互动数据', {
            'fields': ['likes_count', 'collects_count', 'comments_count', 'top_comments']
        }),
        ('时间与位置', {
            'fields': ['publish_time', 'location', 'extracted_at']
        }),
        ('关键词匹配', {
            'fields': ['matched_keywords']
        }),
        ('采集元数据', {
            'fields': ['source', 'card_index', 'raw_data'],
            'classes': ['collapse']
        }),
        ('系统信息', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    filter_horizontal = ['matched_keywords']

    def description_preview(self, obj):
        """Content preview (first 50 chars)"""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_preview.short_description = '内容预览'


@admin.register(NoteAnalysisResult)
class NoteAnalysisResultAdmin(admin.ModelAdmin):
    """Note analysis result admin"""

    list_display = [
        'note',
        'category',
        'sentiment',
        'risk_score',
        'is_reviewed',
        'analyzed_at',
    ]

    list_filter = [
        'category',
        'sentiment',
        'is_reviewed',
        'analyzed_at',
    ]

    search_fields = [
        'note__note_id',
        'note__description',
        'reason',
    ]

    readonly_fields = [
        'note',
        'category',
        'sentiment',
        'risk_score',
        'reason',
        'image_analysis',
        'llm_response',
        'model_used',
        'input_tokens',
        'output_tokens',
        'analyzed_at',
        'analysis_duration',
    ]

    ordering = ['-analyzed_at']

    fieldsets = [
        ('分析结果', {
            'fields': ['note', 'category', 'sentiment', 'risk_score', 'reason']
        }),
        ('详细分析', {
            'fields': ['image_analysis', 'llm_response'],
            'classes': ['collapse']
        }),
        ('模型信息', {
            'fields': ['model_used', 'input_tokens', 'output_tokens', 'analysis_duration'],
            'classes': ['collapse']
        }),
        ('人工复核', {
            'fields': ['is_reviewed', 'reviewed_by', 'reviewed_at', 'review_notes', 'manual_category']
        }),
        ('系统信息', {
            'fields': ['analyzed_at'],
            'classes': ['collapse']
        }),
    ]
