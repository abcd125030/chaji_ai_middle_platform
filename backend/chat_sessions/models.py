from django.db import models
from django.conf import settings
import uuid


class Session(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions',
        verbose_name='用户'
    )
    session_id = models.CharField(max_length=64, unique=True, verbose_name='会话ID')
    state = models.BooleanField(default=True, verbose_name='状态')
    session_length = models.PositiveIntegerField(default=0, verbose_name='会话长度 (Token 总量)')

    class Meta:
        verbose_name = '会话'
        verbose_name_plural = '会话'
        
    def __str__(self):
        """返回session_id，用于在选择框中显示"""
        return self.session_id


class QA(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    source_app = models.CharField(max_length=64, verbose_name='来源应用')
    source_type = models.CharField(max_length=16, verbose_name='来源类型')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='qas',
        verbose_name='用户'
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='qas',
        verbose_name='会话'
    )
    prompt_text = models.TextField(verbose_name='提示文本', blank=True, null=True)
    prompt_images = models.JSONField(default=list, verbose_name='提示图片', blank=True, null=True)
    prompt_files = models.JSONField(default=list, verbose_name='提示文件', blank=True, null=True)
    model = models.CharField(max_length=64, verbose_name='模型名称')
    prompt_params = models.JSONField(default=dict, verbose_name='提示参数', blank=True, null=True)
    origin_response = models.JSONField(default=dict, verbose_name='原始响应')
    response = models.JSONField(default=dict, verbose_name='拼装后响应')

    class Meta:
        verbose_name = '问答记录'
        verbose_name_plural = '问答记录'



class AgenticLog(models.Model):
    """Agent 运行步骤日志模型，用于记录 Agent 的详细运行步骤"""
    
    class LogType(models.TextChoices):
        PLANNER = "PLANNER", "规划器"
        TOOL_CALL = "TOOL_CALL", "工具调用"
        TOOL_RESULT = "TOOL_RESULT", "工具结果"
        REFLECTION = "REFLECTION", "反思"
        FINAL_ANSWER = "FINAL_ANSWER", "最终答案"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        'agentic.AgentTask',
        on_delete=models.CASCADE,
        related_name='logs',
        help_text="关联的 Agent 任务"
    )
    qa_record = models.ForeignKey(
        QA,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_logs',
        help_text="关联的 QA 记录，允许在 QA 记录最终生成前就创建日志"
    )
    step_order = models.PositiveIntegerField(help_text="步骤顺序")
    log_type = models.CharField(
        max_length=50,
        choices=LogType.choices,
        help_text="日志类型"
    )
    details = models.JSONField(
        help_text="每一步的详细数据（如 planner 的思考、工具的输入输出等）"
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")

    def __str__(self):
        return f"Log {self.step_order} - {self.get_log_type_display()} (Task: {self.task.task_id})"

    class Meta:
        verbose_name = "Agent 运行日志"
        verbose_name_plural = "Agent 运行日志"
        ordering = ['task', 'step_order']
        unique_together = ('task', 'step_order')
