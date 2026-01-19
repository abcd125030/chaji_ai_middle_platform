from django.db import models
from django.conf import settings
import uuid


class PDFExtractorTask(models.Model):
    """PDF文档提取任务模型"""

    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('error', '错误'),
    ]

    LANGUAGE_CHOICES = [
        ('zh', '中文'),
        ('en', '英文'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='任务ID')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pdf_extractor_tasks',
        verbose_name='所属用户',
        null=True,
        blank=True
    )
    original_filename = models.CharField(max_length=255, verbose_name='原始文件名')
    file_path = models.CharField(max_length=500, verbose_name='文件存储路径')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='任务状态')
    total_pages = models.IntegerField(default=0, verbose_name='总页数')
    processed_pages = models.IntegerField(default=0, verbose_name='已处理页数')

    # 翻译相关字段
    translate = models.BooleanField(default=False, verbose_name='是否翻译')
    target_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='zh',
        verbose_name='目标语言'
    )

    # 页码范围字段
    page_range_start = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='起始页码',
        help_text='起始页码（包含），为空表示从第一页开始'
    )
    page_range_end = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='结束页码',
        help_text='结束页码（包含），为空表示到最后一页'
    )

    feishu_doc_url = models.TextField(
        blank=True,
        null=True,
        verbose_name='飞书文档链接',
        help_text='格式: https://feishu.cn/docx/{document_id}'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolkit_pdf_extractor_task'
        verbose_name = 'PDF提取任务'
        verbose_name_plural = 'PDF提取任务'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_filename} ({self.status})"
