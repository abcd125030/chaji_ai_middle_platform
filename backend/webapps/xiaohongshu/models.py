"""
Xiaohongshu sentiment monitoring data models
"""
from django.db import models
from django.conf import settings


class MonitorKeyword(models.Model):
    """Monitor keyword configuration"""

    MATCH_TYPE_CHOICES = [
        ('exact', '精确匹配'),
        ('contains', '包含匹配'),
        ('regex', '正则匹配'),
    ]

    # Keyword configuration
    keyword = models.CharField(max_length=100, verbose_name='监控关键词')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    priority = models.IntegerField(default=0, verbose_name='优先级',
                                   help_text='数值越大优先级越高')
    match_type = models.CharField(
        max_length=20,
        choices=MATCH_TYPE_CHOICES,
        default='contains',
        verbose_name='匹配方式'
    )

    # Category for grouping
    category = models.CharField(max_length=50, blank=True, verbose_name='分类标签',
                                help_text='用于对关键词进行分组管理')
    description = models.TextField(blank=True, verbose_name='描述说明')

    # Created by
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='xhs_keywords_created',
        verbose_name='创建人'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'xiaohongshu_monitor_keyword'
        verbose_name = '监控关键词'
        verbose_name_plural = verbose_name
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['keyword', 'is_active']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f'{self.keyword} ({self.get_match_type_display()})'


class XiaohongshuNote(models.Model):
    """Xiaohongshu note storage - fields match actual crawled data structure"""

    NOTE_TYPE_CHOICES = [
        ('image', '图文笔记'),
        ('video', '视频笔记'),
    ]

    STATUS_CHOICES = [
        ('pending', '待分析'),
        ('analyzing', '分析中'),
        ('completed', '已完成'),
        ('failed', '分析失败'),
    ]

    # Note identification (from crawled data: note_id)
    note_id = models.CharField(max_length=64, unique=True, verbose_name='笔记ID',
                               help_text='小红书笔记唯一标识')

    # Author information (from crawled data: author, author_avatar)
    author_name = models.CharField(max_length=100, blank=True, verbose_name='作者昵称')
    author_avatar = models.URLField(max_length=500, blank=True, verbose_name='作者头像')

    # Note content (from crawled data: description, type)
    description = models.TextField(blank=True, verbose_name='笔记正文内容')
    note_type = models.CharField(
        max_length=20,
        choices=NOTE_TYPE_CHOICES,
        default='image',
        verbose_name='笔记类型'
    )

    # Media content (from crawled data: images)
    images = models.JSONField(default=list, verbose_name='图片列表',
                              help_text='图片URL数组')

    # Tags (from crawled data: tags)
    tags = models.JSONField(default=list, verbose_name='标签列表',
                            help_text='标签列表如 #霸王茶姬')

    # Engagement metrics (from crawled data: likes, collects, comments)
    likes_count = models.IntegerField(default=0, verbose_name='点赞数')
    collects_count = models.IntegerField(default=0, verbose_name='收藏数')
    comments_count = models.IntegerField(default=0, verbose_name='评论数')

    # Time and location (from crawled data: publish_time, location)
    publish_time = models.CharField(max_length=50, blank=True, verbose_name='发布时间描述',
                                    help_text='如"编辑于"、"14分钟前"')
    location = models.CharField(max_length=200, blank=True, verbose_name='发布位置')

    # Comments (from crawled data: top_comments)
    top_comments = models.JSONField(default=list, verbose_name='热评列表')

    # Crawl metadata (from crawled data: extracted_at, card_index)
    extracted_at = models.DateTimeField(null=True, blank=True, verbose_name='采集时间')
    card_index = models.IntegerField(default=0, verbose_name='采集卡片索引')

    # Keyword matching
    matched_keywords = models.ManyToManyField(
        MonitorKeyword,
        blank=True,
        related_name='matched_notes',
        verbose_name='命中的关键词'
    )

    # Collection metadata
    source = models.CharField(max_length=50, blank=True, verbose_name='数据来源',
                              help_text='采集客户端标识')
    raw_data = models.JSONField(default=dict, verbose_name='原始数据',
                                help_text='采集到的原始JSON数据')

    # Processing status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='处理状态'
    )

    # Local timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='入库时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'xiaohongshu_note'
        verbose_name = '小红书笔记'
        verbose_name_plural = verbose_name
        ordering = ['-extracted_at', '-created_at']
        indexes = [
            models.Index(fields=['note_id']),
            models.Index(fields=['status']),
            models.Index(fields=['extracted_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        title_preview = self.description[:30] if self.description else '无内容'
        return f'Note({self.note_id}): {title_preview}...'


class NoteAnalysisResult(models.Model):
    """Note analysis result"""

    CATEGORY_CHOICES = [
        ('category_1', '类别1 - 负面舆情客诉'),
        ('category_2', '类别2 - 数据泄露风险'),
        ('category_3', '类别3 - 黑灰产信息'),
        ('category_4', '类别4 - 代下单'),
        ('other', '其他 - 非负面'),
    ]

    SENTIMENT_CHOICES = [
        ('positive', '正向'),
        ('neutral', '中立'),
        ('negative', '负向'),
    ]

    # Relation to note
    note = models.OneToOneField(
        XiaohongshuNote,
        on_delete=models.CASCADE,
        related_name='analysis_result',
        verbose_name='关联笔记'
    )

    # Analysis result category
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name='分析类别'
    )

    # Sentiment analysis
    sentiment = models.CharField(
        max_length=20,
        choices=SENTIMENT_CHOICES,
        default='neutral',
        verbose_name='情感倾向'
    )

    # Risk score (0-100, higher means more risky)
    risk_score = models.IntegerField(default=50, verbose_name='风险评分',
                                     help_text='0-100分，分数越高风险越大')

    # Analysis details
    reason = models.TextField(blank=True, verbose_name='分析原因',
                              help_text='AI给出的分类原因说明')

    # Image analysis results
    image_analysis = models.JSONField(default=list, verbose_name='图片分析结果',
                                      help_text='每张图片的VLM分析结果')

    # Raw LLM response
    llm_response = models.JSONField(default=dict, verbose_name='LLM原始响应')

    # Model information
    model_used = models.CharField(max_length=100, blank=True, verbose_name='使用的模型')

    # Token usage
    input_tokens = models.IntegerField(default=0, verbose_name='输入Token数')
    output_tokens = models.IntegerField(default=0, verbose_name='输出Token数')

    # Processing metadata
    analyzed_at = models.DateTimeField(auto_now_add=True, verbose_name='分析时间')
    analysis_duration = models.FloatField(default=0, verbose_name='分析耗时(秒)')

    # Manual review
    is_reviewed = models.BooleanField(default=False, verbose_name='是否已人工复核')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='xhs_reviews',
        verbose_name='复核人'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='复核时间')
    review_notes = models.TextField(blank=True, verbose_name='复核备注')

    # Override category after review
    manual_category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        blank=True,
        verbose_name='人工修正类别'
    )

    class Meta:
        db_table = 'xiaohongshu_note_analysis'
        verbose_name = '笔记分析结果'
        verbose_name_plural = verbose_name
        ordering = ['-analyzed_at']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['sentiment']),
            models.Index(fields=['risk_score']),
            models.Index(fields=['is_reviewed']),
        ]

    def __str__(self):
        return f'Analysis({self.note.note_id}): {self.get_category_display()}'

    @property
    def final_category(self):
        """Returns the final category (manual override if exists, otherwise AI result)"""
        return self.manual_category if self.manual_category else self.category
