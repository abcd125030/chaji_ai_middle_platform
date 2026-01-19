from django.contrib import admin
from django.utils.html import format_html
from .models import PDFParseTask, ParseResult


@admin.register(PDFParseTask)
class PDFParseTaskAdmin(admin.ModelAdmin):
    """PDF解析任务管理"""
    list_display = [
        'task_id_short', 'user', 'original_filename', 'file_type',
        'status_colored', 'processing_time', 'created_at'
    ]
    list_filter = ['status', 'file_type', 'parse_method', 'created_at']
    search_fields = ['task_id', 'original_filename', 'user__username']
    readonly_fields = [
        'task_id', 'file_path', 'output_dir', 'processing_time',
        'created_at', 'updated_at', 'completed_at'
    ]
    
    fieldsets = (
        ('基本信息', {
            'fields': ('task_id', 'user', 'original_filename', 'file_type', 'file_size')
        }),
        ('解析配置', {
            'fields': ('parse_method', 'debug_enabled')
        }),
        ('任务状态', {
            'fields': ('status', 'output_dir', 'processing_time', 'error_message')
        }),
        ('文件路径', {
            'fields': ('file_path',),
            'classes': ('collapse',)
        }),
        ('内容预览', {
            'fields': ('text_preview',),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        })
    )
    
    def task_id_short(self, obj):
        """显示简短的任务ID"""
        return str(obj.task_id)[:8] + '...'
    task_id_short.short_description = '任务ID'
    
    def status_colored(self, obj):
        """带颜色的状态显示"""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = '状态'
    
    actions = ['reprocess_tasks']
    
    def reprocess_tasks(self, request, queryset):
        """重新处理选中的任务"""
        from .tasks import process_document_task
        
        count = 0
        for task in queryset:
            if task.status != 'processing':
                task.status = 'pending'
                task.error_message = None
                task.save()
                process_document_task.delay(str(task.task_id))
                count += 1
        
        self.message_user(request, f'已重新提交 {count} 个任务')
    reprocess_tasks.short_description = '重新处理选中的任务'


@admin.register(ParseResult)
class ParseResultAdmin(admin.ModelAdmin):
    """解析结果管理"""
    list_display = [
        'task_filename', 'total_text_blocks', 'total_images',
        'total_tables', 'total_formulas', 'created_at'
    ]
    list_filter = ['created_at']
    search_fields = ['task__original_filename', 'task__task_id']
    readonly_fields = [
        'task', 'markdown_path', 'json_path',
        'total_text_blocks', 'total_images', 'total_tables',
        'total_formulas', 'metadata', 'created_at'
    ]
    
    def task_filename(self, obj):
        """显示任务文件名"""
        return obj.task.original_filename
    task_filename.short_description = '文件名'
    
    def has_add_permission(self, request):
        """禁止手动添加"""
        return False
