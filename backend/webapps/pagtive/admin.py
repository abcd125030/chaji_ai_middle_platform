from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
import json
from .models import (
    Project, ProjectDetail, ProjectLLMLog, InvitationCode, UserAgreement,
    PagtiveConfig, PagtivePromptTemplate
)


class ProjectDetailInline(admin.TabularInline):
    """项目详情内联显示"""
    model = ProjectDetail
    extra = 0
    fields = ('page_id', 'has_content', 'has_mermaid', 'version_id', 'updated_at')
    readonly_fields = ('has_content', 'has_mermaid', 'updated_at')
    can_delete = True
    
    def has_content(self, obj):
        """检查是否有内容"""
        has_items = []
        if obj.script:
            has_items.append('JS')
        if obj.styles:
            has_items.append('CSS')
        if obj.html:
            has_items.append('HTML')
        if obj.images:
            has_items.append('图片')
        return ' | '.join(has_items) if has_items else '-'
    
    has_content.short_description = '包含内容'
    
    def has_mermaid(self, obj):
        """是否有 Mermaid 图表"""
        if obj.mermaid_content:
            return '✓'
        return '-'
    
    has_mermaid.short_description = 'Mermaid'


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """项目管理"""
    list_display = (
        'project_name', 'user', 'get_pages_count', 'get_files_count', 'get_visibility',
        'get_tags_display', 'batch_info', 'created_at'
    )
    list_filter = (
        'is_public', 'is_featured', 'is_published',
        'created_at', 'updated_at'
    )
    search_fields = ('project_name', 'project_description', 'user__username', 'user__email', 'batch_id')
    raw_id_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'get_pages_preview', 'get_style_preview', 'get_files_detail')
    inlines = [ProjectDetailInline]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('id', 'user', 'project_name', 'project_description')
        }),
        ('样式配置', {
            'fields': ('project_style', 'global_style_code', 'get_style_preview'),
            'classes': ('collapse',)
        }),
        ('页面配置', {
            'fields': ('pages', 'get_pages_preview'),
            'classes': ('collapse',)
        }),
        ('发布设置', {
            'fields': ('is_public', 'is_featured', 'is_published')
        }),
        ('标签和批次', {
            'fields': ('style_tags', 'batch_id', 'batch_index')
        }),
        ('参考文件', {
            'fields': ('reference_files', 'get_files_detail'),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 20
    
    def get_pages_count(self, obj):
        """获取页面数量"""
        if obj.pages and isinstance(obj.pages, list):
            return len(obj.pages)
        return 0
    
    get_pages_count.short_description = '页面数'
    get_pages_count.admin_order_field = 'pages'
    
    def get_files_count(self, obj):
        """获取文件数量"""
        if obj.reference_files and isinstance(obj.reference_files, list):
            count = len(obj.reference_files)
            if count > 0:
                # 计算总文件大小
                total_size = sum(f.get('size', 0) for f in obj.reference_files)
                # 格式化文件大小
                if total_size < 1024:
                    size_str = f'{total_size}B'
                elif total_size < 1024 * 1024:
                    size_str = f'{total_size/1024:.1f}KB'
                else:
                    size_str = f'{total_size/(1024*1024):.1f}MB'
                
                return format_html(
                    '<span title="总大小: {}">{}</span>',
                    size_str, count
                )
            return 0
        return '-'
    
    get_files_count.short_description = '文件数'
    
    def get_visibility(self, obj):
        """显示可见性状态"""
        statuses = []
        if obj.is_public:
            statuses.append(format_html('<span style="color: green;">公开</span>'))
        else:
            statuses.append(format_html('<span style="color: gray;">私有</span>'))
        
        if obj.is_featured:
            statuses.append(format_html('<span style="color: gold;">⭐精选</span>'))
        
        if obj.is_published:
            statuses.append(format_html('<span style="color: blue;">✓已发布</span>'))
        
        return format_html(' '.join(statuses))
    
    get_visibility.short_description = '状态'
    
    def get_tags_display(self, obj):
        """显示样式标签"""
        if obj.style_tags:
            tags_html = []
            for tag in obj.style_tags[:3]:  # 只显示前3个
                if isinstance(tag, dict):
                    tag_text = tag.get('name', str(tag))
                else:
                    tag_text = str(tag)
                tags_html.append(
                    format_html('<span style="background: #e1e4e8; padding: 2px 6px; border-radius: 3px; margin-right: 4px;">{}</span>', tag_text)
                )
            
            if len(obj.style_tags) > 3:
                tags_html.append(format_html('<span style="color: #666;">+{}</span>', len(obj.style_tags) - 3))
            
            return format_html(''.join(tags_html))
        return '-'
    
    get_tags_display.short_description = '标签'
    
    def batch_info(self, obj):
        """批次信息"""
        if obj.batch_id:
            return format_html('{}<br><small>序号: {}</small>', obj.batch_id[:8], obj.batch_index or '-')
        return '-'
    
    batch_info.short_description = '批次'
    
    def get_pages_preview(self, obj):
        """页面配置预览"""
        if obj.pages:
            try:
                pages_json = json.dumps(obj.pages, indent=2, ensure_ascii=False)
                return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', pages_json)
            except:
                return str(obj.pages)
        return '-'
    
    get_pages_preview.short_description = '页面配置预览'
    
    def get_style_preview(self, obj):
        """样式预览"""
        if obj.global_style_code:
            return format_html(
                '<pre style="max-height: 200px; overflow: auto; background: #f6f8fa; padding: 10px;">{}</pre>',
                obj.global_style_code[:500] + ('...' if len(obj.global_style_code) > 500 else '')
            )
        return '-'
    
    get_style_preview.short_description = '样式代码预览'
    
    def get_files_detail(self, obj):
        """文件详细信息"""
        if obj.reference_files and isinstance(obj.reference_files, list):
            files_html = ['<div style="background: #f6f8fa; padding: 10px; border-radius: 5px;">']
            files_html.append('<table style="width: 100%; border-collapse: collapse;">')
            files_html.append('<thead><tr style="border-bottom: 1px solid #ddd;">')
            files_html.append('<th style="text-align: left; padding: 5px;">文件名</th>')
            files_html.append('<th style="text-align: left; padding: 5px;">大小</th>')
            files_html.append('<th style="text-align: left; padding: 5px;">类型</th>')
            files_html.append('<th style="text-align: left; padding: 5px;">上传时间</th>')
            files_html.append('<th style="text-align: left; padding: 5px;">操作</th>')
            files_html.append('</tr></thead><tbody>')
            
            for file_info in obj.reference_files:
                filename = file_info.get('filename', '未知文件')
                size = file_info.get('size', 0)
                content_type = file_info.get('content_type', 'unknown')
                uploaded_at = file_info.get('uploaded_at', '-')
                oss_url = file_info.get('oss_url', '')
                
                # 格式化文件大小
                if size < 1024:
                    size_str = f'{size}B'
                elif size < 1024 * 1024:
                    size_str = f'{size/1024:.1f}KB'
                else:
                    size_str = f'{size/(1024*1024):.2f}MB'
                
                # 格式化时间
                if uploaded_at != '-':
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(uploaded_at.replace('Z', '+00:00'))
                        uploaded_at = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                
                files_html.append('<tr style="border-bottom: 1px solid #eee;">')
                files_html.append(f'<td style="padding: 5px;">{filename}</td>')
                files_html.append(f'<td style="padding: 5px;">{size_str}</td>')
                files_html.append(f'<td style="padding: 5px;"><small>{content_type}</small></td>')
                files_html.append(f'<td style="padding: 5px;"><small>{uploaded_at}</small></td>')
                if oss_url:
                    files_html.append(f'<td style="padding: 5px;"><a href="{oss_url}" target="_blank" style="color: #0366d6;">查看</a></td>')
                else:
                    files_html.append('<td style="padding: 5px;">-</td>')
                files_html.append('</tr>')
            
            files_html.append('</tbody></table>')
            files_html.append('</div>')
            
            # 显示总计信息
            total_size = sum(f.get('size', 0) for f in obj.reference_files)
            if total_size < 1024 * 1024:
                total_size_str = f'{total_size/1024:.1f}KB'
            else:
                total_size_str = f'{total_size/(1024*1024):.2f}MB'
            
            files_html.append(f'<p style="margin-top: 10px; color: #666;">共 {len(obj.reference_files)} 个文件，总大小: {total_size_str}</p>')
            
            return mark_safe(''.join(files_html))
        return '-'
    
    get_files_detail.short_description = '文件详情'
    
    actions = ['make_public', 'make_private', 'mark_featured', 'mark_published']
    
    def make_public(self, request, queryset):
        """设为公开"""
        queryset.update(is_public=True)
        self.message_user(request, f'已将 {queryset.count()} 个项目设为公开')
    
    make_public.short_description = '设为公开'
    
    def make_private(self, request, queryset):
        """设为私有"""
        queryset.update(is_public=False)
        self.message_user(request, f'已将 {queryset.count()} 个项目设为私有')
    
    make_private.short_description = '设为私有'
    
    def mark_featured(self, request, queryset):
        """标记为精选"""
        queryset.update(is_featured=True)
        self.message_user(request, f'已将 {queryset.count()} 个项目标记为精选')
    
    mark_featured.short_description = '标记为精选'
    
    def mark_published(self, request, queryset):
        """标记为已发布"""
        queryset.update(is_published=True)
        self.message_user(request, f'已将 {queryset.count()} 个项目标记为已发布')
    
    mark_published.short_description = '标记为已发布'


@admin.register(ProjectDetail)
class ProjectDetailAdmin(admin.ModelAdmin):
    """项目详情管理"""
    list_display = ('get_project_name', 'page_id', 'get_content_types', 'version_id', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('project__project_name', 'page_id', 'version_id')
    raw_id_fields = ('project',)
    readonly_fields = ('created_at', 'updated_at', 'get_content_preview')
    
    fieldsets = (
        ('基本信息', {
            'fields': ('project', 'page_id', 'version_id')
        }),
        ('页面内容', {
            'fields': ('script', 'styles', 'html'),
            'classes': ('collapse',)
        }),
        ('资源', {
            'fields': ('images', 'mermaid_content'),
            'classes': ('collapse',)
        }),
        ('内容预览', {
            'fields': ('get_content_preview',),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_project_name(self, obj):
        """获取项目名称"""
        return obj.project.project_name
    
    get_project_name.short_description = '项目'
    get_project_name.admin_order_field = 'project__project_name'
    
    def get_content_types(self, obj):
        """显示包含的内容类型"""
        types = []
        if obj.script:
            types.append(format_html('<span style="color: #f1e05a;">JS</span>'))
        if obj.styles:
            types.append(format_html('<span style="color: #563d7c;">CSS</span>'))
        if obj.html:
            types.append(format_html('<span style="color: #e34c26;">HTML</span>'))
        if obj.images:
            types.append(format_html('<span style="color: #21b978;">图片({})</span>', len(obj.images) if isinstance(obj.images, list) else 1))
        if obj.mermaid_content:
            types.append(format_html('<span style="color: #40a9ff;">Mermaid</span>'))
        
        return format_html(' | '.join(types)) if types else '-'
    
    get_content_types.short_description = '内容类型'
    
    def get_content_preview(self, obj):
        """内容预览"""
        preview_parts = []
        
        if obj.html:
            preview_parts.append(format_html(
                '<h4>HTML:</h4><pre style="max-height: 200px; overflow: auto;">{}</pre>',
                obj.html[:500] + ('...' if len(obj.html) > 500 else '')
            ))
        
        if obj.script:
            preview_parts.append(format_html(
                '<h4>JavaScript:</h4><pre style="max-height: 200px; overflow: auto;">{}</pre>',
                obj.script[:500] + ('...' if len(obj.script) > 500 else '')
            ))
        
        if obj.mermaid_content:
            preview_parts.append(format_html(
                '<h4>Mermaid:</h4><pre style="max-height: 200px; overflow: auto;">{}</pre>',
                obj.mermaid_content[:500] + ('...' if len(obj.mermaid_content) > 500 else '')
            ))
        
        return mark_safe(''.join(preview_parts)) if preview_parts else '-'
    
    get_content_preview.short_description = '内容预览'


@admin.register(ProjectLLMLog)
class ProjectLLMLogAdmin(admin.ModelAdmin):
    """LLM 日志管理"""
    list_display = (
        'get_short_id', 'user', 'get_project_name', 'model',
        'scenario', 'status', 'get_tokens', 'duration_ms', 'request_timestamp'
    )
    list_filter = (
        'status', 'provider', 'model', 'scenario',
        'request_timestamp'
    )
    search_fields = (
        'user__username', 'project__project_name',
        'model', 'scenario', 'response_error'
    )
    raw_id_fields = ('user', 'project')
    readonly_fields = (
        'id', 'request_timestamp', 'response_timestamp',
        'get_duration', 'get_request_preview', 'get_response_preview'
    )
    date_hierarchy = 'request_timestamp'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('id', 'user', 'project', 'page_id', 'temporary_page_id')
        }),
        ('模型配置', {
            'fields': ('provider', 'model', 'scenario')
        }),
        ('请求信息', {
            'fields': ('request_timestamp', 'request_prompts', 'request_config', 'get_request_preview'),
            'classes': ('collapse',)
        }),
        ('响应信息', {
            'fields': ('response_timestamp', 'response_content', 'response_error', 'get_response_preview'),
            'classes': ('collapse',)
        }),
        ('使用统计', {
            'fields': (
                'usage_prompt_tokens', 'usage_completion_tokens',
                'usage_total_tokens', 'duration_ms', 'get_duration', 'status'
            )
        }),
    )
    
    list_per_page = 50
    
    def get_short_id(self, obj):
        """显示短ID"""
        return str(obj.id)[:8] + '...'
    
    get_short_id.short_description = 'ID'
    
    def get_project_name(self, obj):
        """获取项目名称"""
        if obj.project:
            return obj.project.project_name
        return '-'
    
    get_project_name.short_description = '项目'
    get_project_name.admin_order_field = 'project__project_name'
    
    def get_tokens(self, obj):
        """显示 Token 使用"""
        if obj.usage_total_tokens:
            return format_html(
                '<span title="提示词: {} | 完成: {}">总计: {}</span>',
                obj.usage_prompt_tokens or 0,
                obj.usage_completion_tokens or 0,
                obj.usage_total_tokens
            )
        return '-'
    
    get_tokens.short_description = 'Tokens'
    get_tokens.admin_order_field = 'usage_total_tokens'
    
    def get_duration(self, obj):
        """计算持续时间"""
        if obj.duration_ms:
            if obj.duration_ms < 1000:
                return f'{obj.duration_ms}ms'
            else:
                return f'{obj.duration_ms/1000:.2f}s'
        elif obj.request_timestamp and obj.response_timestamp:
            delta = obj.response_timestamp - obj.request_timestamp
            return f'{delta.total_seconds():.2f}s'
        return '-'
    
    get_duration.short_description = '耗时'
    
    def get_request_preview(self, obj):
        """请求预览"""
        if obj.request_prompts:
            try:
                prompts = json.dumps(obj.request_prompts, indent=2, ensure_ascii=False)
                return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', prompts)
            except:
                return str(obj.request_prompts)
        return '-'
    
    get_request_preview.short_description = '请求预览'
    
    def get_response_preview(self, obj):
        """响应预览"""
        if obj.response_error:
            return format_html(
                '<div style="color: red;"><strong>错误:</strong><pre>{}</pre></div>',
                obj.response_error
            )
        elif obj.response_content:
            try:
                content = json.dumps(obj.response_content, indent=2, ensure_ascii=False)
                return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', content[:1000])
            except:
                return str(obj.response_content)[:1000]
        return '-'
    
    get_response_preview.short_description = '响应预览'
    
    actions = ['export_logs']
    
    def export_logs(self, request, queryset):
        """导出日志（可扩展为CSV下载）"""
        self.message_user(request, f'选中了 {queryset.count()} 条日志')
    
    export_logs.short_description = '导出选中的日志'


@admin.register(InvitationCode)
class InvitationCodeAdmin(admin.ModelAdmin):
    """邀请码管理"""
    list_display = (
        'code', 'get_status_display', 'get_used_by',
        'created_at', 'expires_at', 'get_is_valid'
    )
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = ('code', 'used_by_user__username', 'used_by_user__email')
    raw_id_fields = ('used_by_user',)
    readonly_fields = ('id', 'created_at', 'get_validity_info')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('id', 'code', 'status')
        }),
        ('使用信息', {
            'fields': ('used_by_user', 'used_at')
        }),
        ('有效期', {
            'fields': ('expires_at', 'get_validity_info')
        }),
        ('时间戳', {
            'fields': ('created_at',)
        }),
    )
    
    def get_status_display(self, obj):
        """状态显示"""
        status_map = {
            'available': ('可用', 'green'),
            'unused': ('未使用', 'green'),
            'used': ('已使用', 'gray'),
            'expired': ('已过期', 'red'),
            'cancelled': ('已取消', 'orange'),
        }
        
        label, color = status_map.get(obj.status, (obj.status, 'black'))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, label
        )
    
    get_status_display.short_description = '状态'
    
    def get_used_by(self, obj):
        """使用者"""
        if obj.used_by_user:
            return format_html(
                '{}<br><small>{}</small>',
                obj.used_by_user.username,
                obj.used_by_user.email or '-'
            )
        return '-'
    
    get_used_by.short_description = '使用者'
    
    def get_is_valid(self, obj):
        """是否有效"""
        if obj.status == 'used':
            return format_html('<span style="color: gray;">已使用</span>')
        elif obj.status == 'cancelled':
            return format_html('<span style="color: orange;">已取消</span>')
        elif obj.status == 'expired':
            return format_html('<span style="color: red;">已过期</span>')
        elif obj.expires_at and obj.expires_at < timezone.now():
            return format_html('<span style="color: red;">已过期</span>')
        elif obj.status == 'available' or obj.status == 'unused':
            return format_html('<span style="color: green;">✓ 有效</span>')
        else:
            return format_html('<span style="color: green;">✓ 有效</span>')
    
    get_is_valid.short_description = '有效性'
    
    def get_validity_info(self, obj):
        """有效期信息"""
        if obj.expires_at:
            now = timezone.now()
            if obj.expires_at > now:
                delta = obj.expires_at - now
                days = delta.days
                hours = delta.seconds // 3600
                
                if days > 0:
                    return format_html(
                        '<span style="color: green;">还有 {} 天 {} 小时</span>',
                        days, hours
                    )
                elif hours > 0:
                    return format_html(
                        '<span style="color: orange;">还有 {} 小时</span>',
                        hours
                    )
                else:
                    minutes = delta.seconds // 60
                    return format_html(
                        '<span style="color: red;">还有 {} 分钟</span>',
                        minutes
                    )
            else:
                return format_html('<span style="color: red;">已过期</span>')
        return '永久有效'
    
    get_validity_info.short_description = '剩余有效期'
    
    actions = ['mark_as_cancelled', 'extend_expiry']
    
    def mark_as_cancelled(self, request, queryset):
        """取消邀请码"""
        queryset.filter(status='unused').update(status='cancelled')
        self.message_user(request, f'已取消 {queryset.count()} 个邀请码')
    
    mark_as_cancelled.short_description = '取消选中的邀请码'
    
    def extend_expiry(self, request, queryset):
        """延长有效期30天"""
        from datetime import timedelta
        for code in queryset:
            if code.expires_at:
                code.expires_at += timedelta(days=30)
                code.save()
        self.message_user(request, f'已延长 {queryset.count()} 个邀请码的有效期')
    
    extend_expiry.short_description = '延长有效期30天'


@admin.register(UserAgreement)
class UserAgreementAdmin(admin.ModelAdmin):
    """用户协议管理"""
    list_display = ('version', 'get_content_preview', 'created_at', 'get_users_count')
    list_filter = ('created_at',)
    search_fields = ('version', 'content')
    readonly_fields = ('id', 'created_at', 'get_formatted_content')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('id', 'version')
        }),
        ('协议内容', {
            'fields': ('content', 'get_formatted_content')
        }),
        ('时间戳', {
            'fields': ('created_at',)
        }),
    )
    
    def get_content_preview(self, obj):
        """内容预览"""
        if obj.content:
            preview = obj.content[:100]
            if len(obj.content) > 100:
                preview += '...'
            return preview
        return '-'
    
    get_content_preview.short_description = '内容预览'
    
    def get_formatted_content(self, obj):
        """格式化内容显示"""
        if obj.content:
            # 假设内容是 Markdown 或纯文本
            return format_html(
                '<div style="background: #f6f8fa; padding: 15px; border-radius: 5px; max-height: 500px; overflow: auto;">'
                '<pre style="white-space: pre-wrap;">{}</pre></div>',
                obj.content
            )
        return '-'
    
    get_formatted_content.short_description = '协议内容（格式化）'
    
    def get_users_count(self, obj):
        """统计同意该版本的用户数"""
        from authentication.models import User
        count = User.objects.filter(agreed_agreement_version=obj.version).count()
        return format_html(
            '<a href="{}?agreed_agreement_version={}">{} 位用户</a>',
            reverse('admin:authentication_user_changelist'),
            obj.version,
            count
        )
    
    get_users_count.short_description = '同意用户数'
    
    actions = ['duplicate_version']
    
    def duplicate_version(self, request, queryset):
        """复制为新版本"""
        for agreement in queryset:
            # 生成新版本号
            import re
            match = re.search(r'(\d+\.\d+)', agreement.version)
            if match:
                current = float(match.group(1))
                new_version = f'{current + 0.1:.1f}'
            else:
                new_version = agreement.version + '_new'
            
            UserAgreement.objects.create(
                version=new_version,
                content=agreement.content
            )
            self.message_user(request, f'已创建新版本: {new_version}')
    
    duplicate_version.short_description = '复制为新版本'


# Pagtive配置管理
class PagtivePromptTemplateInline(admin.TabularInline):
    """提示词模板内联显示"""
    model = PagtivePromptTemplate
    extra = 1
    fields = ('name', 'template_type', 'order', 'is_active')
    ordering = ['template_type', 'order']


@admin.register(PagtiveConfig)
class PagtiveConfigAdmin(admin.ModelAdmin):
    """Pagtive配置管理"""
    list_display = (
        'name', 'get_active_status', 'llm_model', 'get_template_count',
        'temperature', 'get_max_tokens_display', 'enable_stream', 'updated_at'
    )
    list_filter = ('is_active', 'enable_stream', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at', 'get_config_preview')
    inlines = [PagtivePromptTemplateInline]
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('LLM模型配置', {
            'fields': ('llm_model', 'llm_model_for_edit'),
            'description': '选择用于生成和编辑的LLM模型'
        }),
        ('参数设置', {
            'fields': ('temperature', 'max_tokens', 'enable_stream'),
            'description': '调整生成参数'
        }),
        ('提示词覆盖（可选）', {
            'fields': ('system_prompt', 'generate_template', 'edit_template'),
            'classes': ('collapse',),
            'description': '留空则使用默认提示词'
        }),
        ('额外配置', {
            'fields': ('extra_config', 'get_config_preview'),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_active_status(self, obj):
        """显示激活状态"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ 激活中</span>'
            )
        return format_html('<span style="color: gray;">未激活</span>')
    
    get_active_status.short_description = '状态'
    
    def get_template_count(self, obj):
        """获取模板数量"""
        count = obj.prompt_templates.filter(is_active=True).count()
        total = obj.prompt_templates.count()
        if total > 0:
            return format_html(
                '{}/{} <small>模板</small>',
                count, total
            )
        return '-'
    
    get_template_count.short_description = '提示词模板'
    
    def get_max_tokens_display(self, obj):
        """显示最大令牌数"""
        if obj.max_tokens is None:
            return format_html('<span style="color: gray;">无限制</span>')
        return format_html('<span>{}</span>', obj.max_tokens)
    
    get_max_tokens_display.short_description = '最大令牌数'
    
    def get_config_preview(self, obj):
        """配置预览"""
        config = {
            'LLM模型': str(obj.llm_model) if obj.llm_model else '未设置',
            '编辑模型': str(obj.llm_model_for_edit) if obj.llm_model_for_edit else '同上',
            'Temperature': obj.temperature,
            '最大令牌': obj.max_tokens if obj.max_tokens is not None else '无限制',
            '流式输出': '是' if obj.enable_stream else '否',
        }
        if obj.extra_config:
            config['额外配置'] = obj.extra_config
        
        return format_html(
            '<pre style="background: #f6f8fa; padding: 10px; border-radius: 5px;">{}</pre>',
            json.dumps(config, indent=2, ensure_ascii=False)
        )
    
    get_config_preview.short_description = '配置预览'
    
    actions = ['activate_config', 'duplicate_config']
    
    def activate_config(self, request, queryset):
        """激活选中的配置"""
        if queryset.count() > 1:
            self.message_user(request, '只能激活一个配置', level='warning')
            return
        
        config = queryset.first()
        if config:
            config.is_active = True
            config.save()
            self.message_user(request, f'已激活配置: {config.name}')
    
    activate_config.short_description = '激活选中的配置'
    
    def duplicate_config(self, request, queryset):
        """复制配置"""
        for config in queryset:
            # 复制主配置
            new_config = PagtiveConfig.objects.create(
                name=f"{config.name} (副本)",
                description=config.description,
                is_active=False,
                llm_model=config.llm_model,
                llm_model_for_edit=config.llm_model_for_edit,
                system_prompt=config.system_prompt,
                generate_template=config.generate_template,
                edit_template=config.edit_template,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                enable_stream=config.enable_stream,
                extra_config=config.extra_config
            )
            
            # 复制关联的提示词模板
            for template in config.prompt_templates.all():
                PagtivePromptTemplate.objects.create(
                    config=new_config,
                    name=template.name,
                    template_type=template.template_type,
                    template_content=template.template_content,
                    is_active=template.is_active,
                    order=template.order,
                    variables=template.variables
                )
            
            self.message_user(request, f'已创建配置副本: {new_config.name}')
    
    duplicate_config.short_description = '复制选中的配置'


@admin.register(PagtivePromptTemplate)
class PagtivePromptTemplateAdmin(admin.ModelAdmin):
    """Pagtive提示词模板管理"""
    list_display = (
        'name', 'config', 'template_type', 'order',
        'is_active', 'updated_at'
    )
    list_filter = ('config', 'template_type', 'is_active')
    search_fields = ('name', 'template_content')
    readonly_fields = ('created_at', 'updated_at', 'get_template_preview')
    list_editable = ('order', 'is_active')
    
    fieldsets = (
        ('基本信息', {
            'fields': ('config', 'name', 'template_type')
        }),
        ('模板配置', {
            'fields': ('template_content', 'get_template_preview')
        }),
        ('设置', {
            'fields': ('is_active', 'order', 'variables')
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_variables(self, obj):
        """显示变量列表"""
        if obj.variables:
            vars_html = []
            for var in obj.variables[:5]:  # 只显示前5个
                vars_html.append(
                    format_html(
                        '<span style="background: #e1e4e8; padding: 2px 6px; '
                        'border-radius: 3px; margin-right: 4px;">{}</span>',
                        var
                    )
                )
            
            if len(obj.variables) > 5:
                vars_html.append(
                    format_html('<span style="color: #666;">+{}</span>',
                               len(obj.variables) - 5)
                )
            
            return format_html(''.join(vars_html))
        return '-'
    
    get_variables.short_description = '变量'
    
    def get_template_preview(self, obj):
        """模板内容预览"""
        if obj.template_content:
            # 高亮显示变量
            content = obj.template_content
            import re
            # 查找 {{variable}} 格式的变量
            variables = re.findall(r'\{\{(\w+)\}\}', content)
            
            # 预览内容
            preview = content[:500]
            if len(content) > 500:
                preview += '\n...'
            
            # 替换变量为高亮显示
            for var in set(variables):
                preview = preview.replace(
                    f'{{{{{var}}}}}',
                    f'<span style="background: yellow; padding: 2px;">{{{{{var}}}}}</span>'
                )
            
            return format_html(
                '<pre style="background: #f6f8fa; padding: 10px; '
                'border-radius: 5px; max-height: 300px; overflow: auto;">{}</pre>',
                preview
            )
        return '-'
    
    get_template_preview.short_description = '模板预览'


# 自定义管理站点标题
admin.site.site_header = 'Pagtive 项目管理系统'
admin.site.site_title = 'Pagtive Admin'
admin.site.index_title = '项目数据管理'