from django.contrib import admin
from .models import PDFExtractorTask


@admin.register(PDFExtractorTask)
class PDFExtractorTaskAdmin(admin.ModelAdmin):
    """PDF提取任务管理界面"""

    list_display = [
        'id',
        'user',
        'original_filename',
        'status',
        'total_pages',
        'processed_pages',
        'progress_percentage',
        'created_at',
        'updated_at'
    ]

    list_filter = [
        'status',
        'user',
        'created_at',
        'updated_at'
    ]

    search_fields = [
        'id',
        'original_filename',
        'file_path',
        'user__username',
        'user__user_ai_id'
    ]

    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'progress_percentage'
    ]

    fieldsets = (
        ('基本信息', {
            'fields': ('id', 'user', 'original_filename', 'file_path')
        }),
        ('任务状态', {
            'fields': ('status', 'total_pages', 'processed_pages', 'progress_percentage')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def progress_percentage(self, obj):
        """计算进度百分比"""
        if obj.total_pages == 0:
            return '0%'
        percentage = (obj.processed_pages / obj.total_pages) * 100
        return f'{percentage:.1f}%'

    progress_percentage.short_description = '进度'

    def has_add_permission(self, request):
        """禁止手动添加任务"""
        return False
