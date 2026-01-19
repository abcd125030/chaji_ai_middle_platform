from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import uuid


class Graph(models.Model):
    """图模型，用于管理节点和边的集合"""
    name = models.CharField(max_length=255, unique=True, help_text="图的唯一名称")
    description = models.TextField(blank=True, help_text="图的功能描述")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "图"
        verbose_name_plural = "图"


class Node(models.Model):
    """节点模型，支持多种类型的节点，如LLM、工具、路由节点等"""
    class NodeType(models.TextChoices):
        LLM = 'llm', '语言模型节点'
        TOOL = 'tool', '工具节点'
        ROUTER = 'router', '路由/判断节点'

    graph = models.ForeignKey(Graph, on_delete=models.CASCADE, related_name='nodes', verbose_name='所属图')
    name = models.CharField(max_length=255, verbose_name='节点名称', help_text="节点名称")
    display_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='显示名称', help_text="对用户展示的节点别名")
    node_type = models.CharField(max_length=50, choices=NodeType.choices, verbose_name='节点类型', help_text="节点的类型")
    python_callable = models.CharField(
        max_length=255,
        verbose_name='Python可调用路径',
        help_text="节点对应的Python可调用对象路径，例如 'myapp.tools.my_tool_func'"
    )
    config = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="初始化Python可调用对象时所需的参数"
    )

    def __str__(self):
        display = self.display_name or self.name
        return f"{display} ({self.get_node_type_display()})"
    
    def clean(self):
        """验证节点配置，特别是模型配置"""
        super().clean()
        
        # 验证LLM和TOOL节点的模型配置
        if self.node_type in ['llm', 'tool'] and self.config and 'model_name' in self.config:
            model_name = self.config['model_name']
            
            # 延迟导入避免循环依赖
            from router.models import LLMModel
            
            # 检查模型是否存在
            if not LLMModel.objects.filter(model_id=model_name).exists():
                available_models = list(LLMModel.objects.values_list('model_id', flat=True))
                raise ValidationError({
                    'config': f"模型 '{model_name}' 不存在。可用的模型有: {', '.join(available_models) if available_models else '无'}"
                })

    class Meta:
        verbose_name = "节点"
        verbose_name_plural = "节点"
        unique_together = ('graph', 'name')


class Edge(models.Model):
    """边模型，支持条件路由"""
    graph = models.ForeignKey(Graph, on_delete=models.CASCADE, related_name='edges')
    source = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name='outgoing_edges',
        help_text="边的起始节点"
    )
    target = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name='incoming_edges',
        help_text="边的目标节点"
    )
    condition_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="条件路由的键。如果为空，则为无条件边。否则，只有当源节点返回此键时，该边才被激活。"
    )

    def __str__(self):
        source_display = self.source.display_name or self.source.name
        target_display = self.target.display_name or self.target.name
        if self.condition_key:
            return f"{source_display} --[{self.condition_key}]--> {target_display}"
        return f"{source_display} --> {target_display}"

    class Meta:
        verbose_name = "边"
        verbose_name_plural = "边"
        unique_together = ('source', 'condition_key')


class AgentTask(models.Model):
    """
    Agent 任务模型，用于记录 Agent 的执行状态、输入和输出。
    """
    class TaskStatus(models.TextChoices):
        PENDING = 'PENDING', '待处理'
        RUNNING = 'RUNNING', '运行中'
        COMPLETED = 'COMPLETED', '已完成'
        FAILED = 'FAILED', '失败'
        CANCELLED = 'CANCELLED', '已取消'

    task_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, help_text="任务的唯一ID")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agent_tasks', help_text="任务创建者", null=True, blank=True)
    graph = models.ForeignKey(Graph, on_delete=models.SET_NULL, null=True, blank=True, help_text="关联的Agentic Graph")
    status = models.CharField(max_length=50, choices=TaskStatus.choices, default=TaskStatus.PENDING, help_text="任务状态")
    session_id = models.UUIDField(db_index=True, null=True, blank=True, help_text="会话ID（UUID），用于标识同一会话中的任务")
    session_task_history = models.JSONField(default=list, blank=True, help_text="同一会话中历史任务的task_id集合")
    input_data = models.JSONField(default=dict, blank=True, help_text="任务的输入数据，JSON格式")
    output_data = models.JSONField(default=dict, blank=True, help_text="任务的输出数据，JSON格式")
    state_snapshot = models.JSONField(null=True, blank=True, help_text="The serialized snapshot of the agent's RuntimeState.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="任务创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="任务最后更新时间")

    def __str__(self):
        return f"Task {self.task_id} - {self.get_status_display()}"

    class Meta:
        verbose_name = "Agent 任务"
        verbose_name_plural = "Agent 任务"
        ordering = ['-created_at']


class ActionSteps(models.Model):
    """
    Agent 执行步骤记录（替代 AgenticLog）
    用于记录 Agent 执行过程中的各个步骤和结果
    """
    class LogType(models.TextChoices):
        PLANNER = 'planner', '规划器'
        TOOL_CALL = 'tool_call', '工具调用'
        TOOL_RESULT = 'tool_result', '工具结果'
        REFLECTION = 'reflection', '反思'
        FINAL_ANSWER = 'final_answer', '最终答案'
        TODO_UPDATE = 'todo_update', 'TODO更新'
    
    task = models.ForeignKey(
        AgentTask, 
        on_delete=models.CASCADE, 
        related_name='action_steps',
        help_text="关联的Agent任务"
    )
    step_order = models.IntegerField(
        default=0,
        help_text="步骤顺序号"
    )
    log_type = models.CharField(
        max_length=50, 
        choices=LogType.choices,
        help_text="日志类型"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="步骤详细信息，JSON格式"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="创建时间"
    )
    
    def __str__(self):
        return f"Step {self.step_order} - {self.get_log_type_display()} for Task {self.task.task_id}"
    
    class Meta:
        verbose_name = "执行步骤"
        verbose_name_plural = "执行步骤"
        ordering = ['task', 'step_order']
        indexes = [
            models.Index(fields=['task', 'step_order']),
            models.Index(fields=['log_type']),
        ]
