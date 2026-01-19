from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Avg
from .models import GraphDefinition, NodeDefinition, EdgeDefinition, TaskExecution, StepRecord


class NodeDefinitionInline(admin.TabularInline):
    """节点定义内联编辑"""
    model = NodeDefinition
    extra = 0
    fields = ('node_id', 'node_type', 'node_name', 'tool_name')
    show_change_link = True
    verbose_name = "图中的节点"
    verbose_name_plural = "图中的节点"


class EdgeDefinitionInline(admin.TabularInline):
    """边定义内联编辑"""
    model = EdgeDefinition
    extra = 0
    fields = ('edge_id', 'source_node_id', 'target_node_id', 'condition', 'priority')
    verbose_name = "节点连接"
    verbose_name_plural = "节点连接"


@admin.register(GraphDefinition)
class GraphDefinitionAdmin(admin.ModelAdmin):
    """图定义管理界面"""
    list_display = ('name', 'version', 'is_active', 'is_default', 'get_node_count', 'get_execution_count', 'creator', 'created_at')
    list_filter = ('is_active', 'is_default', 'created_at')
    search_fields = ('name', 'description', 'version')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [NodeDefinitionInline, EdgeDefinitionInline]
    actions = ['activate_graphs', 'deactivate_graphs', 'set_as_default']

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'version', 'description')
        }),
        ('状态设置', {
            'fields': ('is_active', 'is_default', 'entry_point')
        }),
        ('配置信息', {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
        ('系统信息', {
            'fields': ('id', 'creator', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_node_count(self, obj):
        """获取节点数量"""
        return obj.nodes.count()
    get_node_count.short_description = '节点数'
    get_node_count.admin_order_field = 'nodes__count'

    def get_execution_count(self, obj):
        """获取执行次数"""
        return obj.executions.count()
    get_execution_count.short_description = '执行次数'

    def activate_graphs(self, request, queryset):
        """激活选中的图"""
        queryset.update(is_active=True)
        self.message_user(request, f"已激活 {queryset.count()} 个图定义")
    activate_graphs.short_description = "激活选中的图"

    def deactivate_graphs(self, request, queryset):
        """停用选中的图"""
        queryset.update(is_active=False)
        self.message_user(request, f"已停用 {queryset.count()} 个图定义")
    deactivate_graphs.short_description = "停用选中的图"

    def set_as_default(self, request, queryset):
        """设置为默认图"""
        if queryset.count() != 1:
            self.message_user(request, "只能选择一个图设置为默认", level='ERROR')
            return
        GraphDefinition.objects.update(is_default=False)
        queryset.update(is_default=True)
        self.message_user(request, "已设置默认图")
    set_as_default.short_description = "设置为默认图"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            nodes__count=Count('nodes'),
            edges__count=Count('edges')
        )


@admin.register(NodeDefinition)
class NodeDefinitionAdmin(admin.ModelAdmin):
    """节点定义管理界面"""
    list_display = ('node_name', 'node_id', 'node_type', 'graph', 'tool_name')
    list_filter = ('node_type', 'graph')
    search_fields = ('node_name', 'node_id', 'tool_name')
    autocomplete_fields = ['graph']

    fieldsets = (
        ('基本信息', {
            'fields': ('graph', 'node_id', 'node_name', 'node_type')
        }),
        ('工具配置', {
            'fields': ('tool_name',),
            'description': '仅对 tool_call 和 output 类型节点有效'
        }),
        ('高级配置', {
            'fields': ('config', 'position'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EdgeDefinition)
class EdgeDefinitionAdmin(admin.ModelAdmin):
    """边定义管理界面"""
    list_display = ('edge_id', 'get_connection', 'graph', 'condition', 'priority')
    list_filter = ('graph', 'priority')
    search_fields = ('edge_id', 'source_node_id', 'target_node_id')
    autocomplete_fields = ['graph']

    fieldsets = (
        ('基本信息', {
            'fields': ('graph', 'edge_id')
        }),
        ('连接关系', {
            'fields': ('source_node_id', 'target_node_id')
        }),
        ('路由配置', {
            'fields': ('condition', 'priority'),
            'description': '条件为空表示无条件路由'
        }),
    )

    def get_connection(self, obj):
        """显示连接关系"""
        return f"{obj.source_node_id} → {obj.target_node_id}"
    get_connection.short_description = '连接'


class StepRecordInline(admin.TabularInline):
    """步骤记录内联显示"""
    model = StepRecord
    extra = 0
    fields = ('step_number', 'node_name', 'node_type', 'result', 'duration_ms', 'total_tokens')
    readonly_fields = fields
    ordering = ['step_number']
    can_delete = False
    verbose_name = "执行步骤"
    verbose_name_plural = "执行步骤"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
    """任务执行管理界面"""
    list_display = ('get_short_id', 'graph', 'status', 'current_node', 'get_step_count', 'total_tokens', 'total_cost', 'user', 'created_at')
    list_filter = ('status', 'graph', 'created_at')
    search_fields = ('id', 'session_id', 'turn_id', 'user__username')
    readonly_fields = ('id', 'created_at', 'started_at', 'updated_at', 'completed_at')
    inlines = [StepRecordInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('执行信息', {
            'fields': ('id', 'graph', 'status', 'current_node')
        }),
        ('关联信息', {
            'fields': ('user', 'session_id', 'turn_id')
        }),
        ('执行结果', {
            'fields': ('result', 'error_message'),
            'classes': ('collapse',)
        }),
        ('运行时状态', {
            'fields': ('runtime_state',),
            'classes': ('collapse',),
            'description': '完整的运行时状态数据'
        }),
        ('统计信息', {
            'fields': ('total_tokens', 'total_cost')
        }),
        ('时间信息', {
            'fields': ('created_at', 'started_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('元数据', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )

    def get_short_id(self, obj):
        """显示缩短的ID"""
        return str(obj.id)[:8]
    get_short_id.short_description = '执行ID'
    get_short_id.admin_order_field = 'id'

    def get_step_count(self, obj):
        """获取步骤数量"""
        return obj.steps.count()
    get_step_count.short_description = '步骤数'

    def has_add_permission(self, request):
        # 任务执行由系统创建，不允许手动添加
        return False

    def has_change_permission(self, request, obj=None):
        # 任务执行为只读
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('graph', 'user')


@admin.register(StepRecord)
class StepRecordAdmin(admin.ModelAdmin):
    """步骤记录管理界面"""
    list_display = ('get_task_id', 'step_number', 'node_name', 'node_type', 'result', 'duration_ms', 'total_tokens', 'started_at')
    list_filter = ('result', 'node_type', 'started_at')
    search_fields = ('task_execution__id', 'node_name', 'node_id')
    readonly_fields = ['task_execution', 'step_number', 'node_id', 'node_type', 'node_name',
                      'input_data', 'output_data', 'result', 'error_message',
                      'prompt_tokens', 'completion_tokens', 'total_tokens',
                      'duration_ms', 'started_at', 'completed_at', 'metadata']
    date_hierarchy = 'started_at'

    fieldsets = (
        ('基本信息', {
            'fields': ('task_execution', 'step_number', 'node_id', 'node_name', 'node_type')
        }),
        ('执行结果', {
            'fields': ('result', 'error_message')
        }),
        ('数据', {
            'fields': ('input_data', 'output_data'),
            'classes': ('collapse',)
        }),
        ('Token统计', {
            'fields': ('prompt_tokens', 'completion_tokens', 'total_tokens')
        }),
        ('性能指标', {
            'fields': ('duration_ms', 'started_at', 'completed_at')
        }),
        ('元数据', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )

    def get_task_id(self, obj):
        """显示任务ID"""
        return str(obj.task_execution.id)[:8]
    get_task_id.short_description = '任务ID'
    get_task_id.admin_order_field = 'task_execution'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('task_execution', 'task_execution__graph')
