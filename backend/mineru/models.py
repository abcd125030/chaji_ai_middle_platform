import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class PDFParseTask(models.Model):
    """PDF解析任务模型"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败')
    ]
    
    PARSE_METHOD_CHOICES = [
        ('auto', '自动'),
        ('ocr', 'OCR'),
        ('txt', '文本')
    ]
    
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('jpg', 'JPG'),
        ('png', 'PNG'),
        ('doc', 'DOC'),
        ('docx', 'DOCX'),
        ('ppt', 'PPT'),
        ('pptx', 'PPTX')
    ]
    
    task_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='用户')
    
    # 文件信息
    original_filename = models.CharField(max_length=255, verbose_name='原始文件名')
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, verbose_name='文件类型')
    file_size = models.BigIntegerField(verbose_name='文件大小（字节）')
    file_path = models.CharField(max_length=500, verbose_name='文件存储路径', null=True, blank=True)
    
    # 解析配置
    parse_method = models.CharField(max_length=10, choices=PARSE_METHOD_CHOICES, default='auto', verbose_name='解析方法')
    debug_enabled = models.BooleanField(default=False, verbose_name='调试模式')
    # MinerU v2.2 新特性
    enable_table_merge = models.BooleanField(default=True, verbose_name='启用跨页表格合并')
    use_new_table_model = models.BooleanField(default=True, verbose_name='使用新表格识别模型')
    
    # 任务状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='任务状态')
    output_dir = models.CharField(max_length=500, verbose_name='输出目录', null=True, blank=True)
    
    # 解析结果
    page_count = models.IntegerField(null=True, blank=True, verbose_name='页数')
    processing_time = models.FloatField(null=True, blank=True, verbose_name='处理时间（秒）')
    error_message = models.TextField(null=True, blank=True, verbose_name='错误信息')
    
    # 提取的内容预览
    text_preview = models.TextField(null=True, blank=True, verbose_name='文本预览')
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    class Meta:
        db_table = 'mineru_pdf_parse_task'
        verbose_name = 'PDF解析任务'
        verbose_name_plural = 'PDF解析任务'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.original_filename} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)


class ParseResult(models.Model):
    """解析结果详情模型"""
    
    task = models.OneToOneField(PDFParseTask, on_delete=models.CASCADE, related_name='result', verbose_name='解析任务')
    
    # 解析结果文件路径
    markdown_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='Markdown文件路径')
    json_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='JSON文件路径')
    
    # 统计信息
    total_text_blocks = models.IntegerField(default=0, verbose_name='文本块总数')
    total_images = models.IntegerField(default=0, verbose_name='图片总数')
    total_tables = models.IntegerField(default=0, verbose_name='表格总数')
    total_formulas = models.IntegerField(default=0, verbose_name='公式总数')
    # MinerU v2.2 新增统计
    cross_page_tables = models.IntegerField(default=0, verbose_name='跨页表格数')
    
    # 其他元数据
    metadata = models.JSONField(default=dict, verbose_name='其他元数据')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'mineru_parse_result'
        verbose_name = '解析结果'
        verbose_name_plural = '解析结果'
    
    def __str__(self):
        return f"Result for {self.task.original_filename}"
