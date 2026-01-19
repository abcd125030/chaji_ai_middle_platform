from django.db import models
from django.conf import settings

# Create your models here.
class CustomizedQA(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    source_app = models.CharField(max_length=64, verbose_name='来源应用')
    source_type = models.CharField(max_length=1000, verbose_name='来源类型')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='customizedqas',
        verbose_name='用户'
    )
    task_id = models.TextField(max_length=1000, verbose_name='任务Id', blank=True, null=True)
    input = models.JSONField(default=dict, verbose_name='原始输入')
    prompt_text = models.TextField(verbose_name='提示文本', blank=True, null=True)
    prompt_images = models.JSONField(default=list, verbose_name='提示图片', blank=True, null=True)
    prompt_files = models.JSONField(default=list, verbose_name='提示文件', blank=True, null=True)
    model = models.CharField(max_length=64, verbose_name='模型名称')
    prompt_params = models.JSONField(default=dict, verbose_name='提示参数', blank=True, null=True)
    origin_response = models.JSONField(default=dict, verbose_name='原始响应')
    response = models.JSONField(default=dict, verbose_name='拼装后响应')
    output = models.JSONField(default=dict, verbose_name='输出结果')
    is_final = models.CharField(max_length=10, default="否", verbose_name='是否是最终结果')
    input_session_length = models.PositiveIntegerField(default=0, verbose_name='输入文本长度 (Token)')
    output_session_length = models.PositiveIntegerField(default=0, verbose_name='输出文本长度 (Token)')

    class Meta:
        verbose_name = '定制化记录'
        verbose_name_plural = '定制化记录'
