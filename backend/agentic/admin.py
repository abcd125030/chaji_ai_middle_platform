from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
import json
from .models import Graph, Node, Edge, AgentTask, ActionSteps


# Inlines for GraphAdmin
class NodeInline(admin.TabularInline):
    model = Node
    extra = 1
    fields = ('name', 'display_name', 'node_type', 'python_callable')
    show_change_link = True
    verbose_name = "图中的节点"
    verbose_name_plural = "图中的节点"


class EdgeInlineForGraph(admin.TabularInline):
    model = Edge
    extra = 1
    fields = ('source', 'target', 'condition_key')
    autocomplete_fields = ['source', 'target']
    verbose_name = "图中的边"
    verbose_name_plural = "图中的边"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ["source", "target"]:
            if hasattr(request, '_obj_') and request._obj_:
                kwargs["queryset"] = Node.objects.filter(graph=request._obj_)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Graph)
class GraphAdmin(admin.ModelAdmin):
    """图的管理界面"""
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [NodeInline, EdgeInlineForGraph]
    actions = ['delete_selected']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        # Pass the graph object to the inlines
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)


# Inlines for NodeAdmin
class OutgoingEdgeInline(admin.TabularInline):
    """出边的内联编辑 (从某个节点出发的边)"""
    model = Edge
    fk_name = 'source'
    extra = 1
    verbose_name = "出边"
    verbose_name_plural = "出边"
    fields = ('target', 'condition_key')
    autocomplete_fields = ['target']

class IncomingEdgeInline(admin.TabularInline):
    """入边的内联编辑 (指向某个节点的边)"""
    model = Edge
    fk_name = 'target'
    extra = 0
    verbose_name = "入边"
    verbose_name_plural = "入边"
    fields = ('source', 'condition_key')
    readonly_fields = ('source', 'condition_key')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class NodeAdminForm(forms.ModelForm):
    """自定义节点表单，提供更好的模型配置界面"""
    model_name = forms.CharField(
        required=False,
        label='模型配置',
        help_text='选择节点使用的LLM模型（留空使用默认模型）',
        widget=forms.Select(attrs={'class': 'vTextField'})
    )
    
    class Meta:
        model = Node
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 动态加载可用的模型选项
        from router.models import LLMModel
        model_choices = [('', '-- 使用默认模型 --')]
        model_choices.extend([
            (model.model_id, f"{model.name} ({model.model_id})")
            for model in LLMModel.objects.all().order_by('name')
        ])
        self.fields['model_name'].widget.choices = model_choices
        
        # 如果节点已有模型配置，设置初始值
        if self.instance and self.instance.pk and self.instance.config:
            self.fields['model_name'].initial = self.instance.config.get('model_name', '')
        
        # 为config字段添加更详细的帮助文本
        if self.instance and self.instance.pk:
            node_type = self.instance.node_type
            if node_type in ['llm', 'tool']:
                help_text = "节点配置（JSON格式）。"
                if node_type == 'llm':
                    help_text += "\n示例：{'model_name': 'gemini-2.5-flash', 'temperature': 0.7}"
                elif node_type == 'tool':
                    help_text += "\n示例：{'model_name': 'gemini-2.5-flash', 'timeout': 30}"
                self.fields['config'].help_text = help_text
        else:
            self.fields['config'].help_text = "节点配置（JSON格式）。保存后会根据节点类型显示示例。"
    
    def clean(self):
        cleaned_data = super().clean()
        model_id = cleaned_data.get('model_name')
        config = cleaned_data.get('config') or {}
        node_type = cleaned_data.get('node_type')
        
        # 如果选择了模型，更新config
        if model_id:
            config['model_name'] = model_id
            cleaned_data['config'] = config
        
        # 验证模型配置
        if node_type in ['llm', 'tool'] and config.get('model_name'):
            from router.models import LLMModel
            model_id = config['model_name']
            if not LLMModel.objects.filter(model_id=model_id).exists():
                raise ValidationError(f"模型 '{model_id}' 不存在。请在 LLMModel 中配置该模型。")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        model_name = self.cleaned_data.get('model_name')
        
        if model_name:
            if not instance.config:
                instance.config = {}
            instance.config['model_name'] = model_name
        elif instance.config and 'model_name' in instance.config and not model_name:
            # 如果清空了模型选择，从config中移除
            del instance.config['model_name']
        
        if commit:
            instance.save()
        return instance


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    """节点的管理界面"""
    form = NodeAdminForm
    list_display = ('name', 'display_name', 'graph', 'get_node_type_display_cn', 'get_model_name', 'python_callable')
    list_filter = ('node_type', 'graph')
    search_fields = ('name', 'display_name', 'python_callable', 'graph__name')
    ordering = ('graph', 'name')
    autocomplete_fields = ['graph']
    inlines = [OutgoingEdgeInline, IncomingEdgeInline]
    actions = ['delete_selected']

    fieldsets = (
        ('基本信息', {
            'fields': ('graph', 'name', 'display_name', 'node_type')
        }),
        ('模型配置', {
            'fields': ('model_name',),
            'description': '为LLM节点和工具节点配置使用的模型'
        }),
        ('执行配置', {
            'fields': ('python_callable', 'config'),
            'description': '配置节点的执行逻辑和其他参数'
        }),
    )
    
    def get_model_name(self, obj):
        """显示节点配置的模型名称"""
        if obj.config and 'model_name' in obj.config:
            return obj.config['model_name']
        return '默认'
    get_model_name.short_description = '配置模型'
    
    def get_node_type_display_cn(self, obj):
        """显示节点类型的中文"""
        return obj.get_node_type_display()
    get_node_type_display_cn.short_description = '节点类型'
    
    def get_node_category(self, obj):
        """显示节点类别"""
        # finalizer节点是特殊的虚拟配置节点
        if obj.name == 'finalizer':
            return '配置节点'
        
        # 检查是否有边连接（没有入边也没有出边的节点）
        has_edges = obj.incoming_edges.exists() or obj.outgoing_edges.exists()
        
        if not has_edges:
            return '配置节点'
        return '执行节点'
    get_node_category.short_description = '节点类别'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('graph')

    def get_form(self, request, obj=None, **kwargs):
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    """边的管理界面"""
    list_display = ('__str__', 'graph', 'condition_key')
    list_filter = ('graph',)
    search_fields = ('source__name', 'target__name', 'condition_key')
    ordering = ('graph', 'source')
    autocomplete_fields = ['graph', 'source', 'target']
    actions = ['delete_selected']

    fieldsets = (
        ('基本信息', {
            'fields': ('graph', 'source', 'target')
        }),
        ('路由条件', {
            'fields': ('condition_key',),
            'description': '留空表示无条件边，否则只有当源节点返回匹配的condition_key时该边才被激活'
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('graph', 'source', 'target')


# Inline for ActionSteps in AgentTaskAdmin
class ActionStepsInline(admin.TabularInline):
    """任务执行步骤的内联显示"""
    model = ActionSteps
    extra = 0
    fields = ('step_order', 'log_type', 'details', 'created_at')
    readonly_fields = ('step_order', 'log_type', 'details', 'created_at')
    ordering = ['step_order']
    verbose_name = "执行步骤"
    verbose_name_plural = "执行步骤"
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    """Agent 任务的管理界面"""
    list_display = ('task_id', 'graph', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'graph')
    search_fields = ('task_id',)
    readonly_fields = ('task_id', 'graph', 'status', 'input_data', 'output_data', 'state_snapshot', 'created_at', 'updated_at')
    actions = ['delete_selected']
    inlines = [ActionStepsInline]  # 添加执行步骤的内联显示
    
    fieldsets = (
        ('任务信息', {
            'fields': ('task_id', 'graph', 'status')
        }),
        ('数据', {
            'fields': ('input_data', 'output_data', 'state_snapshot'),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ActionSteps)
class ActionStepsAdmin(admin.ModelAdmin):
    """执行步骤的管理界面"""
    list_display = ('task', 'step_order', 'log_type', 'created_at')
    list_filter = ('log_type', 'created_at')
    search_fields = ('task__task_id', 'details')
    readonly_fields = ('task', 'step_order', 'log_type', 'details', 'created_at')
    ordering = ['-created_at', 'step_order']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('task', 'step_order', 'log_type')
        }),
        ('详细信息', {
            'fields': ('details',),
            'classes': ('wide',)
        }),
        ('时间信息', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        # 执行步骤由系统自动创建，不允许手动添加
        return False
    
    def has_change_permission(self, request, obj=None):
        # 执行步骤为只读，不允许修改
        return False
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('task')


# 自定义管理站点标题
admin.site.site_header = "Agentic 应用管理"
admin.site.site_title = "Agentic 管理"
admin.site.index_title = "欢迎使用 Agentic 应用管理系统"
