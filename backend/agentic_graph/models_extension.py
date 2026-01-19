"""
Graph 执行框架的扩展模型
补充必要的模型定义
"""
from django.db import models
import uuid
from django.utils import timezone


class GraphTask(models.Model):
    """
    Graph 任务模型
    简化版的任务执行模型，用于新框架
    """
    class TaskStatus(models.TextChoices):
        PENDING = 'PENDING', '待执行'
        RUNNING = 'RUNNING', '执行中'
        COMPLETED = 'COMPLETED', '已完成'
        FAILED = 'FAILED', '失败'
        CANCELLED = 'CANCELLED', '已取消'
    
    task_id = models.CharField(
        max_length=100,
        unique=True,
        primary_key=True,
        verbose_name="任务ID"
    )
    
    graph_definition = models.ForeignKey(
        'GraphDefinition',
        on_delete=models.PROTECT,
        verbose_name="图定义"
    )
    
    user_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="用户ID"
    )
    
    session_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="会话ID"
    )
    
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        verbose_name="任务状态"
    )
    
    input_data = models.JSONField(
        default=dict,
        verbose_name="输入数据"
    )
    
    output_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="输出数据"
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name="错误信息"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )
    
    class Meta:
        verbose_name = "Graph任务"
        verbose_name_plural = "Graph任务"
        ordering = ['-created_at']
        db_table = 'agentic_graph_graphtask'
    
    def __str__(self):
        return f"Task {self.task_id} ({self.status})"


class GraphCheckpoint(models.Model):
    """
    Graph 检查点模型
    用于保存和恢复执行状态
    """
    task_id = models.CharField(
        max_length=100,
        unique=True,
        primary_key=True,
        verbose_name="任务ID"
    )
    
    state_data = models.JSONField(
        verbose_name="状态数据",
        help_text="完整的 RuntimeState 数据"
    )
    
    checkpoint_count = models.IntegerField(
        default=0,
        verbose_name="检查点计数"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )
    
    class Meta:
        verbose_name = "Graph检查点"
        verbose_name_plural = "Graph检查点"
        db_table = 'agentic_graph_graphcheckpoint'
    
    def __str__(self):
        return f"Checkpoint for {self.task_id}"


