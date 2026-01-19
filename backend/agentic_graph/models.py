"""
agentic_graph 应用的数据模型
基于新的 Graph 处理引擎设计，与原 agentic 应用隔离
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json
import uuid

User = get_user_model()


class GraphDefinition(models.Model):
    """
    图定义模型
    存储图的结构定义，包含节点和边的配置
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="图ID"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="图名称"
    )
    version = models.CharField(
        max_length=50,
        default="1.0.0",
        verbose_name="版本号"
    )
    description = models.TextField(
        blank=True,
        verbose_name="描述"
    )
    
    # 创建信息
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_graphs",
        verbose_name="创建者"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )
    
    # 状态
    is_active = models.BooleanField(
        default=True,
        verbose_name="是否激活"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="是否为默认图"
    )
    
    # 配置
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="图配置",
        help_text="存储图的全局配置信息"
    )
    
    # 入口节点
    entry_point = models.CharField(
        max_length=100,
        default="START",
        verbose_name="入口节点",
        help_text="图的起始节点ID"
    )
    
    class Meta:
        verbose_name = "图定义"
        verbose_name_plural = "图定义"
        ordering = ["-created_at"]
        unique_together = [["name", "version"]]
        indexes = [
            models.Index(fields=["is_active", "-created_at"]),
            models.Index(fields=["name", "version"]),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version}"
    
    def clone(self, new_version=None):
        """克隆图定义，用于创建新版本"""
        new_graph = GraphDefinition.objects.create(
            name=self.name,
            version=new_version or f"{self.version}.1",
            description=self.description,
            creator=self.creator,
            config=self.config,
            is_active=False  # 新版本默认不激活
        )
        
        # 克隆节点
        for node in self.nodes.all():
            NodeDefinition.objects.create(
                graph=new_graph,
                node_id=node.node_id,
                node_type=node.node_type,
                node_name=node.node_name,
                tool_name=node.tool_name,
                config=node.config,
                position=node.position
            )
        
        # 克隆边
        for edge in self.edges.all():
            EdgeDefinition.objects.create(
                graph=new_graph,
                edge_id=edge.edge_id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                condition=edge.condition,
                priority=edge.priority
            )
        
        return new_graph


class NodeDefinition(models.Model):
    """
    节点定义模型
    定义图中的节点及其配置
    """
    NODE_TYPE_CHOICES = [
        ('planner', 'Planner - 规划节点'),
        ('tool_call', 'Tool Call - 工具调用节点'),
        ('reflection', 'Reflection - 反思节点'),
        ('output_selector', 'Output Selector - 输出选择节点'),
        ('output', 'Output - 输出节点'),
        ('end', 'End - 结束节点'),
        ('start', 'Start - 开始节点'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    graph = models.ForeignKey(
        GraphDefinition,
        on_delete=models.CASCADE,
        related_name="nodes",
        verbose_name="所属图"
    )
    
    # 节点标识
    node_id = models.CharField(
        max_length=100,
        verbose_name="节点ID",
        help_text="图内唯一的节点标识"
    )
    node_type = models.CharField(
        max_length=20,
        choices=NODE_TYPE_CHOICES,
        verbose_name="节点类型"
    )
    node_name = models.CharField(
        max_length=200,
        verbose_name="节点名称",
        help_text="节点的显示名称"
    )
    
    # 工具配置（仅对 tool_call 和 output 类型节点）
    tool_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="工具名称",
        help_text="关联的工具名称"
    )
    
    # 节点配置
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="节点配置",
        help_text="节点的具体配置参数"
    )
    
    # 位置信息（用于可视化）
    position = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="位置信息",
        help_text="节点在图中的位置坐标"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    
    class Meta:
        verbose_name = "节点定义"
        verbose_name_plural = "节点定义"
        unique_together = [["graph", "node_id"]]
        ordering = ["graph", "node_id"]
        indexes = [
            models.Index(fields=["graph", "node_type"]),
            models.Index(fields=["tool_name"]),
        ]
    
    def __str__(self):
        return f"{self.node_name} ({self.node_type})"


class EdgeDefinition(models.Model):
    """
    边定义模型
    定义节点之间的连接关系
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    graph = models.ForeignKey(
        GraphDefinition,
        on_delete=models.CASCADE,
        related_name="edges",
        verbose_name="所属图"
    )
    
    # 边标识
    edge_id = models.CharField(
        max_length=100,
        verbose_name="边ID",
        help_text="图内唯一的边标识"
    )
    
    # 连接关系
    source_node_id = models.CharField(
        max_length=100,
        verbose_name="源节点ID"
    )
    target_node_id = models.CharField(
        max_length=100,
        verbose_name="目标节点ID"
    )
    
    # 条件路由
    condition = models.TextField(
        blank=True,
        verbose_name="条件表达式",
        help_text="用于条件路由的表达式，为空表示无条件"
    )
    
    # 优先级（数字越小优先级越高）
    priority = models.IntegerField(
        default=0,
        verbose_name="优先级",
        help_text="多条边时的执行优先级，数字越小优先级越高"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    
    class Meta:
        verbose_name = "边定义"
        verbose_name_plural = "边定义"
        unique_together = [["graph", "edge_id"]]
        ordering = ["graph", "priority", "edge_id"]
        indexes = [
            models.Index(fields=["graph", "source_node_id"]),
            models.Index(fields=["graph", "target_node_id"]),
        ]
    
    def __str__(self):
        return f"{self.source_node_id} -> {self.target_node_id}"


class TaskExecution(models.Model):
    """
    任务执行模型
    存储完整的 RuntimeState，覆盖更新
    """
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="执行ID"
    )
    
    # 关联信息
    graph = models.ForeignKey(
        GraphDefinition,
        on_delete=models.PROTECT,
        related_name="executions",
        verbose_name="使用的图定义"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graph_executions",
        verbose_name="执行用户"
    )
    session_id = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="会话ID",
        help_text="关联的会话标识"
    )
    turn_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="轮次ID",
        help_text="多轮对话中的轮次标识"
    )
    
    # 执行状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name="执行状态"
    )
    current_node = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="当前节点",
        help_text="当前执行到的节点ID，为空表示已完成"
    )
    
    # RuntimeState 存储（核心数据）
    runtime_state = models.JSONField(
        default=dict,
        verbose_name="运行时状态",
        help_text="完整的 RuntimeState 数据，覆盖更新"
    )
    
    # 执行结果
    result = models.JSONField(
        null=True,
        blank=True,
        verbose_name="执行结果",
        help_text="最终的执行结果"
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="错误信息",
        help_text="执行失败时的错误信息"
    )
    
    # 统计信息
    total_tokens = models.IntegerField(
        default=0,
        verbose_name="总Token数"
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="总成本"
    )
    
    # 时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="开始时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="完成时间"
    )
    
    # 元数据
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="元数据",
        help_text="额外的元数据信息"
    )
    
    class Meta:
        verbose_name = "任务执行"
        verbose_name_plural = "任务执行"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session_id", "-created_at"]),
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["graph", "status"]),
            models.Index(fields=["status", "-updated_at"]),
        ]
    
    def __str__(self):
        return f"Task {self.id} ({self.status})"
    
    def update_runtime_state(self, new_state):
        """更新 RuntimeState（覆盖）"""
        self.runtime_state = new_state
        self.updated_at = timezone.now()
        self.save(update_fields=['runtime_state', 'updated_at'])
    
    def set_current_node(self, node_id):
        """设置当前节点"""
        self.current_node = node_id
        self.save(update_fields=['current_node', 'updated_at'])
    
    def mark_completed(self, result=None):
        """标记执行完成"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.current_node = ''
        if result:
            self.result = result
        self.save(update_fields=['status', 'completed_at', 'current_node', 'result', 'updated_at'])
    
    def mark_failed(self, error_message):
        """标记执行失败"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'completed_at', 'error_message', 'updated_at'])


class StepRecord(models.Model):
    """
    步骤记录模型
    每个节点生成自己的数据原子记录
    """
    RESULT_CHOICES = [
        ('success', '成功'),
        ('failed', '失败'),
        ('skipped', '跳过'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="记录ID"
    )
    
    # 关联信息
    task_execution = models.ForeignKey(
        TaskExecution,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name="所属任务执行"
    )
    
    # 节点信息
    node_id = models.CharField(
        max_length=100,
        verbose_name="节点ID"
    )
    node_type = models.CharField(
        max_length=20,
        verbose_name="节点类型"
    )
    node_name = models.CharField(
        max_length=200,
        verbose_name="节点名称"
    )
    
    # 执行顺序
    step_number = models.IntegerField(
        verbose_name="步骤序号",
        help_text="执行的顺序编号"
    )
    
    # 输入输出数据
    input_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="输入数据",
        help_text="节点接收的输入数据快照"
    )
    output_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="输出数据",
        help_text="节点产生的输出数据"
    )
    
    # 执行结果
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='success',
        verbose_name="执行结果"
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="错误信息",
        help_text="执行失败时的错误信息"
    )
    
    # Token 使用量
    prompt_tokens = models.IntegerField(
        default=0,
        verbose_name="提示Token数"
    )
    completion_tokens = models.IntegerField(
        default=0,
        verbose_name="完成Token数"
    )
    total_tokens = models.IntegerField(
        default=0,
        verbose_name="总Token数"
    )
    
    # 执行耗时（毫秒）
    duration_ms = models.IntegerField(
        default=0,
        verbose_name="执行耗时(ms)"
    )
    
    # 时间戳
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="开始时间"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="完成时间"
    )
    
    # 元数据
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="元数据",
        help_text="节点特定的额外信息"
    )
    
    class Meta:
        verbose_name = "步骤记录"
        verbose_name_plural = "步骤记录"
        ordering = ["task_execution", "step_number"]
        indexes = [
            models.Index(fields=["task_execution", "step_number"]),
            models.Index(fields=["task_execution", "node_type"]),
            models.Index(fields=["result", "-started_at"]),
        ]
    
    def __str__(self):
        return f"Step {self.step_number}: {self.node_name}"
    
    def calculate_duration(self):
        """计算执行耗时"""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
            self.save(update_fields=['duration_ms'])
    
    def update_tokens(self, prompt_tokens=0, completion_tokens=0):
        """更新 Token 使用量"""
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.save(update_fields=['prompt_tokens', 'completion_tokens', 'total_tokens'])
    
    @classmethod
    def create_from_node(cls, task_execution, node_id, node_type, node_name, input_data=None):
        """从节点创建步骤记录"""
        # 获取下一个步骤序号
        last_step = cls.objects.filter(task_execution=task_execution).order_by('-step_number').first()
        step_number = (last_step.step_number + 1) if last_step else 1
        
        return cls.objects.create(
            task_execution=task_execution,
            node_id=node_id,
            node_type=node_type,
            node_name=node_name,
            step_number=step_number,
            input_data=input_data or {}
        )
