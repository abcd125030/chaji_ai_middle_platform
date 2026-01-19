from django.contrib import admin
from django.utils.html import format_html
from .models import ImageEditTask, BatchTask
from .config_models import ImageEditorConfig


class GenerationStatusFilter(admin.SimpleListFilter):
    """生图成功失败筛选器"""
    title = '生图状态'
    parameter_name = 'generation_status'
    
    def lookups(self, request, model_admin):
        return (
            ('success', '生图成功'),
            ('failed', '生图失败'),
            ('not_executed', '未执行生图'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'success':
            # 生图成功：有生成的图片URL
            return queryset.filter(generated_image_url__isnull=False).exclude(generated_image_url='')
        elif self.value() == 'failed':
            # 生图失败：任务失败且宠物检测通过（说明到达了生图阶段）但没有生成图片URL
            return queryset.filter(
                status='failed',
                pet_detection_result=True,
                generated_image_url__isnull=True
            ) | queryset.filter(
                status='failed',
                pet_detection_result=True,
                generated_image_url=''
            )
        elif self.value() == 'not_executed':
            # 未执行生图：宠物检测失败或任务还在处理中
            return queryset.filter(pet_detection_result=False) | queryset.filter(status='processing')


@admin.register(ImageEditTask)
class ImageEditTaskAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'user', 'colored_status', 'callback_status_display', 'callback_time_display',
                   'pet_detection_display', 'generation_status', 'consistency_display', 'bg_removal_display', 
                   'error_code', 'created_at_display', 'processing_time', 
                   'pet_detection_time', 'text_to_image_time', 'bg_removal_time']
    list_filter = ['status', 'callback_status', GenerationStatusFilter, 'pet_detection_result', 'consistency_check', 'bg_removal_success', 'created_at', 'error_code']
    search_fields = ['task_id', 'user__username', 'prompt', 'error_code']
    readonly_fields = ['task_id', 'created_at', 'completed_at', 'processing_time', 
                      'image_format', 'image_width', 'image_height', 'image_size_bytes', 'image_aspect_ratio',
                      'generation_seed', 'consistency_score', 'bg_removal_retry_count', 'bg_removed_source_url', 'result_image_path',
                      'image_validation_duration', 'pet_detection_duration', 'text_to_image_duration', 
                      'consistency_check_duration', 'bg_removal_duration', 'callback_duration',
                      'callback_status', 'callback_attempts', 'callback_occurred_at_display', 'callback_response_code', 'callback_error_message']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('task_id', 'user', 'status')
        }),
        ('任务参数', {
            'fields': ('prompt', 'actual_prompt', 'image_url', 'callback_url'),
            'description': '用户提交的参数和实际使用的参数'
        }),
        ('图片验证信息', {
            'fields': ('image_format', 'image_width', 'image_height', 'image_size_bytes', 'image_aspect_ratio'),
            'classes': ('collapse',),
            'description': '原始图片的验证信息'
        }),
        ('宠物检测结果', {
            'fields': ('pet_detection_result', 'pet_detection_reason', 'pet_detection_model', 'pet_description'),
            'classes': ('collapse',),
            'description': '使用AI模型检测图片是否为宠物'
        }),
        ('AI生成信息', {
            'fields': ('generation_model', 'generation_seed', 'generation_guidance_scale', 'generated_image_url'),
            'classes': ('collapse',),
            'description': '图片生成的参数和结果'
        }),
        ('一致性检测结果', {
            'fields': ('consistency_check', 'consistency_score', 'consistency_reason'),
            'classes': ('collapse',),
            'description': '生成图片与原图的一致性检测'
        }),
        ('背景移除信息', {
            'fields': ('bg_removal_attempted', 'bg_removal_success', 'bg_removal_retry_count', 'bg_removed_source_url', 'bg_removal_error'),
            'classes': ('collapse',),
            'description': '背景移除（抠图）处理信息'
        }),
        ('最终结果', {
            'fields': ('result_image_path', 'result_image', 'error_code', 'error_message', 'error_details'),
            'classes': ('collapse',),
            'description': '图片文件路径和结果信息'
        }),
        ('时间信息', {
            'fields': ('created_at', 'completed_at', 'processing_time'),
            'classes': ('collapse',)
        }),
        ('各流程执行时长', {
            'fields': ('image_validation_duration', 'pet_detection_duration', 'text_to_image_duration', 
                      'consistency_check_duration', 'bg_removal_duration', 'callback_duration'),
            'classes': ('collapse',),
            'description': '各个处理流程的执行时间（秒）'
        }),
        ('回调信息', {
            'fields': ('callback_status', 'callback_attempts', 'callback_occurred_at_display', 
                      'callback_response_code', 'callback_error_message'),
            'classes': ('collapse',),
            'description': '回调发送状态和响应信息'
        }),
    )
    
    def has_add_permission(self, request):
        # 禁止通过admin界面添加任务
        return False
    
    def colored_status(self, obj):
        """显示带颜色的任务状态"""
        colors = {
            'processing': 'orange',
            'success': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    colored_status.short_description = '任务状态'
    colored_status.admin_order_field = 'status'
    
    def pet_detection_display(self, obj):
        """显示宠物检测结果"""
        if obj.pet_detection_result is None:
            return format_html('<span style="color: gray;">-</span>')
        elif obj.pet_detection_result:
            return format_html('<span style="color: green;">✓ 通过</span>')
        else:
            reason = obj.pet_detection_reason or '未知'
            return format_html('<span style="color: red;">✗ 失败({})</span>', reason)
    pet_detection_display.short_description = '宠物检测'
    pet_detection_display.admin_order_field = 'pet_detection_result'
    
    def generation_status(self, obj):
        """显示图片生成状态"""
        if obj.generated_image_url:
            if obj.generation_seed:
                return format_html(
                    '<span style="color: green;">✓ 成功<br><small>Seed: {}</small></span>',
                    obj.generation_seed
                )
            else:
                return format_html('<span style="color: green;">✓ 成功</span>')
        elif obj.status == 'processing':
            return format_html('<span style="color: orange;">处理中...</span>')
        elif obj.status == 'failed':
            # 如果失败了但是在宠物检测阶段就失败了，说明还没到生成阶段
            if obj.pet_detection_result == False:
                return format_html('<span style="color: gray;">未执行</span>')
            else:
                return format_html('<span style="color: red;">✗ 失败</span>')
        else:
            return format_html('<span style="color: gray;">-</span>')
    generation_status.short_description = '图片生成'
    generation_status.admin_order_field = 'generated_image_url'
    
    def consistency_display(self, obj):
        """显示一致性检测结果"""
        if obj.consistency_check is None:
            return format_html('<span style="color: gray;">-</span>')
        elif obj.consistency_check:
            if obj.consistency_score:
                return format_html(
                    '<span style="color: green;">✓ 通过<br><small>分数: {}</small></span>',
                    f'{obj.consistency_score:.2f}'
                )
            else:
                return format_html('<span style="color: green;">✓ 通过</span>')
        else:
            reason = obj.consistency_reason or '未知'
            return format_html('<span style="color: red;">✗ 失败({})</span>', reason)
    consistency_display.short_description = '一致性检测'
    consistency_display.admin_order_field = 'consistency_check'
    
    def bg_removal_display(self, obj):
        """显示背景移除状态"""
        if not obj.bg_removal_attempted:
            return format_html('<span style="color: gray;">未尝试</span>')
        elif obj.bg_removal_success:
            if obj.bg_removal_retry_count > 0:
                return format_html(
                    '<span style="color: green;">✓ 成功<br><small>重试{}次</small></span>',
                    obj.bg_removal_retry_count
                )
            else:
                return format_html('<span style="color: green;">✓ 成功</span>')
        else:
            return format_html(
                '<span style="color: red;">✗ 失败<br><small>重试{}次</small></span>',
                obj.bg_removal_retry_count
            )
    bg_removal_display.short_description = '背景移除'
    bg_removal_display.admin_order_field = 'bg_removal_success'
    
    def pet_detection_time(self, obj):
        """显示宠物检测时长"""
        if obj.pet_detection_duration:
            return format_html('{}s', f'{obj.pet_detection_duration:.2f}')
        else:
            return format_html('<span style="color: gray;">-</span>')
    pet_detection_time.short_description = '宠物检测'
    pet_detection_time.admin_order_field = 'pet_detection_duration'
    
    def text_to_image_time(self, obj):
        """显示文生图时长"""
        if obj.text_to_image_duration:
            return format_html('{}s', f'{obj.text_to_image_duration:.2f}')
        else:
            return format_html('<span style="color: gray;">-</span>')
    text_to_image_time.short_description = '文生图'
    text_to_image_time.admin_order_field = 'text_to_image_duration'
    
    def bg_removal_time(self, obj):
        """显示抠图时长"""
        if obj.bg_removal_duration:
            return format_html('{}s', f'{obj.bg_removal_duration:.2f}')
        else:
            return format_html('<span style="color: gray;">-</span>')
    bg_removal_time.short_description = '抠图'
    bg_removal_time.admin_order_field = 'bg_removal_duration'
    
    def callback_status_display(self, obj):
        """显示回调状态"""
        if not obj.callback_url:
            return format_html('<span style="color: gray;">无需回调</span>')
        
        status_colors = {
            'pending': ('orange', '⏳ 待发送'),
            'success': ('green', '✓ 成功'),
            'failed': ('red', '✗ 失败'),
            'not_required': ('gray', '- 无需回调')
        }
        
        color, text = status_colors.get(obj.callback_status, ('black', obj.callback_status))
        
        # 添加额外信息
        extra_info = []
        if obj.callback_attempts > 0:
            extra_info.append(f'尝试{obj.callback_attempts}次')
        if obj.callback_response_code:
            extra_info.append(f'响应:{obj.callback_response_code}')
        
        if extra_info:
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span><br><small>{}</small>',
                color, text, ', '.join(extra_info)
            )
        else:
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, text
            )
    callback_status_display.short_description = '回调状态'
    callback_status_display.admin_order_field = 'callback_status'
    
    def callback_time_display(self, obj):
        """显示回调时间"""
        if not obj.callback_occurred_at:
            return format_html('<span style="color: gray;">-</span>')
        
        # 格式化时间显示
        from django.utils import timezone
        import datetime
        import pytz
        
        # 转换为本地时间（北京时间）
        local_tz = pytz.timezone('Asia/Shanghai')
        local_time = obj.callback_occurred_at.astimezone(local_tz)
        now = timezone.now().astimezone(local_tz)
        
        time_diff = now - local_time
        
        # 如果是今天，只显示时间
        if local_time.date() == now.date():
            time_str = local_time.strftime('%H:%M:%S')
        # 如果是昨天
        elif local_time.date() == (now - datetime.timedelta(days=1)).date():
            time_str = '昨天 ' + local_time.strftime('%H:%M')
        # 其他情况显示完整日期
        else:
            time_str = local_time.strftime('%m-%d %H:%M')
        
        # 根据回调状态显示不同颜色
        if obj.callback_status == 'success':
            color = 'green'
        elif obj.callback_status == 'failed':
            color = 'red'
        else:
            color = 'gray'
        
        return format_html(
            '<span style="color: {};">{}</span>',
            color, time_str
        )
    callback_time_display.short_description = '回调时间'
    callback_time_display.admin_order_field = 'callback_occurred_at'
    
    def callback_occurred_at_display(self, obj):
        """详情页显示回调时间（本地时间）"""
        if not obj.callback_occurred_at:
            return '-'
        
        import pytz
        # 转换为本地时间（北京时间）
        local_tz = pytz.timezone('Asia/Shanghai')
        local_time = obj.callback_occurred_at.astimezone(local_tz)
        
        # 返回格式化的本地时间
        return local_time.strftime('%Y-%m-%d %H:%M:%S')
    
    callback_occurred_at_display.short_description = '回调时间'
    
    def created_at_display(self, obj):
        """显示创建时间（本地时间，包含秒）"""
        if not obj.created_at:
            return '-'
        
        import pytz
        from django.utils import timezone
        import datetime
        
        # 转换为本地时间（北京时间）
        local_tz = pytz.timezone('Asia/Shanghai')
        local_time = obj.created_at.astimezone(local_tz)
        now = timezone.now().astimezone(local_tz)
        
        # 如果是今天，显示时间包含秒
        if local_time.date() == now.date():
            time_str = local_time.strftime('%H:%M:%S')
        # 如果是昨天
        elif local_time.date() == (now - datetime.timedelta(days=1)).date():
            time_str = '昨天 ' + local_time.strftime('%H:%M:%S')
        # 如果是今年
        elif local_time.year == now.year:
            time_str = local_time.strftime('%m-%d %H:%M:%S')
        # 其他情况显示完整日期
        else:
            time_str = local_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return time_str
    
    created_at_display.short_description = '创建时间'
    created_at_display.admin_order_field = 'created_at'


@admin.register(BatchTask)
class BatchTaskAdmin(admin.ModelAdmin):
    list_display = ['batch_id', 'user', 'total_count', 'completed_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['batch_id', 'user__username']
    readonly_fields = ['batch_id', 'created_at']


@admin.register(ImageEditorConfig)
class ImageEditorConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 't2i_model', 't2i_guidance_scale', 'use_random_seed', 'updated_at']
    list_filter = ['is_active', 'use_random_seed', 'add_watermark', 'enable_bg_removal']
    search_fields = ['name', 'generation_model', 'detection_model']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本配置', {
            'fields': ('name', 'is_active'),
            'description': '配置名称和激活状态，默认使用 name="default" 的激活配置'
        }),
        ('提示词配置', {
            'fields': ('default_prompt', 'style_prompt'),
            'description': '默认提示词和风格化提示词配置'
        }),
        ('Seed 配置', {
            'fields': ('use_random_seed', 'fixed_seed', 'seed_min', 'seed_max'),
            'description': '控制生成的随机性，use_random_seed=False 时使用 fixed_seed'
        }),
        ('图生图参数（已弃用）', {
            'fields': ('guidance_scale', 'generation_model', 'image_size'),
            'classes': ('collapse',),
            'description': '原图生图模型参数（当前流程已改为文生图）'
        }),
        ('文生图参数', {
            'fields': ('t2i_model', 't2i_size', 't2i_guidance_scale'),
            'description': '文生图模型参数配置'
        }),
        ('检测参数', {
            'fields': ('detection_model', 'detection_prompt'),
            'description': '宠物检测模型参数配置'
        }),
        ('其他生成参数', {
            'fields': ('add_watermark', 'response_format'),
            'description': '通用生成参数配置'
        }),
        ('性能配置', {
            'fields': ('api_timeout', 'max_retries'),
            'classes': ('collapse',),
            'description': 'API 调用超时和重试配置'
        }),
        ('背景移除配置', {
            'fields': ('enable_bg_removal', 'bg_removal_max_retries'),
            'classes': ('collapse',),
            'description': '背景移除功能配置'
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': '配置创建和更新时间'
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # 如果设置为激活，确保其他配置都设为非激活（同一时间只能有一个激活配置）
        if obj.is_active:
            ImageEditorConfig.objects.filter(is_active=True).exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        # 移除批量删除操作，避免误删配置
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions