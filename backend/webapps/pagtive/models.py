from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
import uuid


class Project(models.Model):
    """项目模型 - 对应原 projects 表"""
    
    id = models.CharField(
        max_length=36,
        primary_key=True,
        default=uuid.uuid4,
        verbose_name='项目ID'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects',
        verbose_name='用户'
    )
    
    project_name = models.CharField(
        max_length=255,
        verbose_name='项目名称'
    )
    
    project_description = models.TextField(
        blank=True,
        null=True,
        verbose_name='项目描述'
    )
    
    project_style = models.TextField(
        blank=True,
        null=True,
        verbose_name='项目风格'
    )
    
    global_style_code = models.TextField(
        blank=True,
        null=True,
        verbose_name='全局样式代码'
    )
    
    pages = models.JSONField(
        blank=True,
        null=True,
        verbose_name='页面配置'
    )
    
    is_public = models.BooleanField(
        default=False,
        verbose_name='是否公开'
    )
    
    style_tags = ArrayField(
        models.JSONField(),
        default=list,
        blank=True,
        verbose_name='风格标签'
    )
    
    batch_id = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        verbose_name='批次ID'
    )
    
    batch_index = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='批次索引'
    )
    
    is_featured = models.BooleanField(
        default=False,
        verbose_name='是否精选'
    )
    
    is_published = models.BooleanField(
        default=False,
        verbose_name='是否发布'
    )
    
    reference_files = models.JSONField(
        default=list,
        blank=True,
        verbose_name='参考文件',
        help_text='存储上传文件的OSS路径和元信息'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        db_table = 'webapps_pagtive_projects'
        verbose_name = '项目'
        verbose_name_plural = '项目'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_public']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['is_published']),
        ]
    
    def __str__(self):
        return f"{self.project_name} ({self.id})"


class ProjectDetail(models.Model):
    """项目详情模型 - 对应原 project_details 表"""
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='details',
        verbose_name='项目'
    )
    
    page_id = models.IntegerField(
        verbose_name='页面ID'
    )
    
    script = models.TextField(
        blank=True,
        null=True,
        verbose_name='脚本'
    )
    
    styles = models.TextField(
        blank=True,
        null=True,
        verbose_name='样式'
    )
    
    html = models.TextField(
        blank=True,
        null=True,
        verbose_name='HTML内容'
    )
    
    images = models.JSONField(
        blank=True,
        null=True,
        verbose_name='图片'
    )
    
    mermaid_content = models.TextField(
        blank=True,
        null=True,
        verbose_name='Mermaid内容'
    )
    
    version_id = models.UUIDField(
        blank=True,
        null=True,
        verbose_name='版本ID'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        db_table = 'webapps_pagtive_project_details'
        verbose_name = '项目详情'
        verbose_name_plural = '项目详情'
        unique_together = [['project', 'page_id']]
    
    def __str__(self):
        return f"{self.project.project_name} - Page {self.page_id}"


class ProjectLLMLog(models.Model):
    """项目LLM日志模型 - 对应原 llmlog 表"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='日志ID'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_llm_logs',
        verbose_name='用户'
    )
    
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='llm_logs',
        verbose_name='项目'
    )
    
    page_id = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='页面ID'
    )
    
    provider = models.CharField(
        max_length=50,
        verbose_name='提供商'
    )
    
    model = models.CharField(
        max_length=100,
        verbose_name='模型'
    )
    
    scenario = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='场景'
    )
    
    request_timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='请求时间'
    )
    
    request_prompts = models.JSONField(
        verbose_name='请求提示词'
    )
    
    request_config = models.JSONField(
        verbose_name='请求配置'
    )
    
    response_timestamp = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='响应时间'
    )
    
    response_content = models.TextField(
        blank=True,
        null=True,
        verbose_name='响应内容'
    )
    
    response_error = models.TextField(
        blank=True,
        null=True,
        verbose_name='响应错误'
    )
    
    usage_prompt_tokens = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='提示词令牌数'
    )
    
    usage_completion_tokens = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='完成令牌数'
    )
    
    usage_total_tokens = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='总令牌数'
    )
    
    duration_ms = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='耗时(毫秒)'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name='状态'
    )
    
    temporary_page_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='临时页面ID'
    )
    
    version_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name='关联版本ID',
        help_text='关联的页面版本ID'
    )
    
    class Meta:
        db_table = 'webapps_pagtive_llmlog'
        verbose_name = '项目LLM日志'
        verbose_name_plural = '项目LLM日志'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['project']),
            models.Index(fields=['temporary_page_id']),
            models.Index(fields=['provider', 'model']),
            models.Index(fields=['-request_timestamp']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"LLMLog {self.id} - {self.status}"


class InvitationCode(models.Model):
    """邀请码模型 - 对应原 invitation_codes 表"""
    
    STATUS_CHOICES = [
        ('available', '可用'),
        ('used', '已使用'),
        ('expired', '已过期'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='邀请码ID'
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='邀请码'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available',
        verbose_name='状态'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='过期时间'
    )
    
    used_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='使用时间'
    )
    
    used_by_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitation_code',
        verbose_name='使用者'
    )
    
    class Meta:
        db_table = 'webapps_pagtive_invitation_codes'
        verbose_name = '邀请码'
        verbose_name_plural = '邀请码'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"InvitationCode {self.code} - {self.status}"


class UserAgreement(models.Model):
    """用户协议模型 - 对应原 user_agreements 表"""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='协议ID'
    )
    
    version = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='版本号'
    )
    
    content = models.TextField(
        verbose_name='协议内容'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    class Meta:
        db_table = 'webapps_pagtive_user_agreements'
        verbose_name = '用户协议'
        verbose_name_plural = '用户协议'
        indexes = [
            models.Index(fields=['version']),
        ]
    
    def __str__(self):
        return f"UserAgreement v{self.version}"


class PagtiveConfig(models.Model):
    """Pagtive配置模型 - 支持多套配置，可激活其中一套"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='配置名称',
        help_text='配置集的唯一名称'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='配置描述',
        help_text='描述该配置集的用途'
    )
    
    is_active = models.BooleanField(
        default=False,
        verbose_name='是否激活',
        help_text='当前是否为激活配置（系统只能有一套激活配置）'
    )
    
    # LLM相关配置
    llm_model = models.ForeignKey(
        'router.LLMModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagtive_configs',
        verbose_name='默认LLM模型',
        help_text='用于页面生成的默认LLM模型'
    )
    
    llm_model_for_edit = models.ForeignKey(
        'router.LLMModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagtive_edit_configs',
        verbose_name='编辑模式LLM模型',
        help_text='用于页面编辑的LLM模型（可选，不设置则使用默认模型）'
    )
    
    # 提示词配置
    system_prompt = models.TextField(
        blank=True,
        verbose_name='系统提示词',
        help_text='覆盖默认系统提示词（可选）'
    )
    
    generate_template = models.TextField(
        blank=True,
        verbose_name='生成页面模板',
        help_text='覆盖默认生成页面提示词模板（可选）'
    )
    
    edit_template = models.TextField(
        blank=True,
        verbose_name='编辑页面模板',
        help_text='覆盖默认编辑页面提示词模板（可选）'
    )
    
    # 参数配置
    temperature = models.FloatField(
        default=0.7,
        verbose_name='Temperature参数',
        help_text='控制生成的随机性（0-2）'
    )
    
    max_tokens = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='最大令牌数',
        help_text='生成内容的最大令牌数（留空表示无限制）'
    )
    
    enable_stream = models.BooleanField(
        default=False,
        verbose_name='启用流式输出',
        help_text='是否启用流式响应'
    )
    
    # 附加配置
    extra_config = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='额外配置',
        help_text='其他JSON格式的配置参数'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        db_table = 'webapps_pagtive_config'
        verbose_name = 'Pagtive配置'
        verbose_name_plural = 'Pagtive配置'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['name']),
        ]
    
    def save(self, *args, **kwargs):
        """确保只有一个激活的配置"""
        if self.is_active:
            # 将其他配置设为非激活
            PagtiveConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} {'(激活)' if self.is_active else ''}"


class PagtivePromptTemplate(models.Model):
    """Pagtive提示词模板 - 可以为每个配置定义多个提示词模板"""
    
    TEMPLATE_TYPE_CHOICES = [
        ('system', '系统提示词'),
        ('generate', '生成页面'),
        ('edit', '编辑页面'),
        ('metadata', '元数据生成'),
        ('style', '样式生成'),
        ('custom', '自定义'),
    ]
    
    config = models.ForeignKey(
        PagtiveConfig,
        on_delete=models.CASCADE,
        related_name='prompt_templates',
        verbose_name='所属配置'
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name='模板名称'
    )
    
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        verbose_name='模板类型'
    )
    
    template_content = models.TextField(
        verbose_name='模板内容',
        help_text='提示词模板内容，支持变量替换如 {{variable}}'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )
    
    order = models.IntegerField(
        default=0,
        verbose_name='排序',
        help_text='数字越小越靠前'
    )
    
    variables = models.JSONField(
        default=list,
        blank=True,
        null=True,
        verbose_name='变量列表',
        help_text='模板中使用的变量名列表'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        db_table = 'webapps_pagtive_prompt_templates'
        verbose_name = 'Pagtive提示词模板'
        verbose_name_plural = 'Pagtive提示词模板'
        ordering = ['config', 'template_type', 'order']
        unique_together = [['config', 'name']]
    
    def __str__(self):
        return f"{self.config.name} - {self.name} ({self.get_template_type_display()})"
