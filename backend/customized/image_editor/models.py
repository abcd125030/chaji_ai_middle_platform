from django.db import models
from django.conf import settings
import uuid


class ImageEditTask(models.Model):
    """图片编辑任务模型"""
    STATUS_CHOICES = [
        ('processing', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]
    
    task_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='image_edit_tasks')
    prompt = models.TextField(verbose_name='风格描述提示词')
    image_url = models.URLField(max_length=500, verbose_name='原始图片URL')
    callback_url = models.URLField(max_length=500, blank=True, null=True, verbose_name='回调地址')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    result_image = models.TextField(blank=True, null=True, verbose_name='处理后的图片base64')
    result_image_path = models.CharField(max_length=255, blank=True, null=True, verbose_name='处理后的图片文件路径')
    error_code = models.CharField(max_length=20, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    error_details = models.TextField(blank=True, null=True)
    
    # 图片验证信息
    image_format = models.CharField(max_length=10, blank=True, null=True, verbose_name='图片格式')
    image_width = models.IntegerField(null=True, blank=True, verbose_name='图片宽度')
    image_height = models.IntegerField(null=True, blank=True, verbose_name='图片高度')
    image_size_bytes = models.IntegerField(null=True, blank=True, verbose_name='图片大小(字节)')
    image_aspect_ratio = models.FloatField(null=True, blank=True, verbose_name='图片宽高比')
    
    # 宠物检测结果
    pet_detection_result = models.BooleanField(null=True, blank=True, verbose_name='是否为宠物')
    pet_detection_reason = models.CharField(max_length=100, blank=True, null=True, verbose_name='检测失败原因')
    pet_detection_model = models.CharField(max_length=50, blank=True, null=True, default='doubao-1.5-vision-pro-250328', verbose_name='检测模型')
    pet_description = models.TextField(blank=True, null=True, verbose_name='宠物描述')
    
    # AI生成信息
    generation_model = models.CharField(max_length=50, blank=True, null=True, default='doubao-seededit-3-0-i2i-250628', verbose_name='生成模型')
    generation_seed = models.IntegerField(null=True, blank=True, verbose_name='生成seed值')
    generation_guidance_scale = models.FloatField(null=True, blank=True, default=10, verbose_name='引导系数')
    actual_prompt = models.TextField(blank=True, null=True, verbose_name='实际使用的提示词')
    generated_image_url = models.URLField(max_length=500, blank=True, null=True, verbose_name='生成的图片URL')
    
    # 一致性检测结果
    consistency_check = models.BooleanField(null=True, blank=True, verbose_name='一致性检测是否通过')
    consistency_score = models.FloatField(null=True, blank=True, verbose_name='一致性分数')
    consistency_reason = models.CharField(max_length=100, blank=True, null=True, verbose_name='不一致原因')
    
    # 背景移除信息
    bg_removal_attempted = models.BooleanField(default=False, verbose_name='是否尝试背景移除')
    bg_removal_success = models.BooleanField(null=True, blank=True, verbose_name='背景移除是否成功')
    bg_removal_retry_count = models.IntegerField(default=0, verbose_name='背景移除重试次数')
    bg_removal_error = models.TextField(blank=True, null=True, verbose_name='背景移除错误信息')
    bg_removed_source_url = models.URLField(max_length=500, blank=True, null=True, verbose_name='用于背景移除的原图URL')
    
    # 各流程执行时长（秒）
    image_validation_duration = models.FloatField(null=True, blank=True, verbose_name='图片验证时长(秒)')
    pet_detection_duration = models.FloatField(null=True, blank=True, verbose_name='宠物检测时长(秒)')
    text_to_image_duration = models.FloatField(null=True, blank=True, verbose_name='文生图时长(秒)')
    consistency_check_duration = models.FloatField(null=True, blank=True, verbose_name='一致性检测时长(秒)')
    bg_removal_duration = models.FloatField(null=True, blank=True, verbose_name='背景移除时长(秒)')
    callback_duration = models.FloatField(null=True, blank=True, verbose_name='回调发送时长(秒)')
    
    # 回调状态字段
    callback_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '待发送'),
            ('success', '成功'),
            ('failed', '失败'),
            ('not_required', '无需回调'),
        ],
        default='pending',
        verbose_name='回调状态'
    )
    callback_attempts = models.IntegerField(default=0, verbose_name='回调尝试次数')
    callback_occurred_at = models.DateTimeField(null=True, blank=True, verbose_name='回调发生时间')
    callback_response_code = models.IntegerField(null=True, blank=True, verbose_name='回调响应状态码')
    callback_error_message = models.TextField(blank=True, default='', verbose_name='回调错误信息')
    
    processing_time = models.FloatField(null=True, blank=True, verbose_name='处理时长(秒)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始处理时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    class Meta:
        db_table = 'image_edit_task'
        verbose_name = '图片编辑任务'
        verbose_name_plural = '图片编辑任务'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Task {self.task_id} - {self.status}"


class BatchTask(models.Model):
    """批量任务模型"""
    batch_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='batch_tasks')
    callback_url = models.URLField(max_length=500, blank=True, null=True, verbose_name='批量回调地址')
    total_count = models.IntegerField(verbose_name='总任务数')
    completed_count = models.IntegerField(default=0, verbose_name='已完成数')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'image_edit_batch_task'
        verbose_name = '批量任务'
        verbose_name_plural = '批量任务'
    
    def __str__(self):
        return f"Batch {self.batch_id} - {self.completed_count}/{self.total_count}"