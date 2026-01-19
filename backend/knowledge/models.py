from django.db import models
from django.conf import settings # 用于关联 User 模型
from django.utils.translation import gettext_lazy as _

"""
知识库核心数据模型
定义知识库系统的数据结构，包括集合、条目、交互记录和配置
"""

class KnowledgeCollection(models.Model):
    """
    知识集合模型
    用于管理不同的知识库或记忆集合，每个集合代表一个独立的知识空间
    
    属性:
        name: 集合名称(唯一)
        description: 集合描述
        qdrant_collection_name: Qdrant中的集合名称
        created_by: 创建者
        created_at: 创建时间
        updated_at: 更新时间
    """
    name = models.CharField(
        _("Collection Name"),
        max_length=255,
        unique=True,
        help_text=_("Unique name for the knowledge collection, e.g., 'product_manuals', 'faq_data'.")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        null=True,
        help_text=_("Detailed description of this knowledge collection.")
    )
    qdrant_collection_name = models.CharField(
        _("Qdrant Collection Name"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Specific Qdrant collection name, if explicitly managed.")
    )
    # config = models.JSONField(
    #     _("Configuration"),
    #     blank=True,
    #     null=True,
    #     help_text=_("JSON configuration for this collection, e.g., vectorization settings.")
    # ) # Removed as per plan X/docs/plans/2025-05-30_knowledge_config_admin_plan.md
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='knowledge_collections_created',
        verbose_name=_("Created By")
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Knowledge Collection")
        verbose_name_plural = _("Knowledge Collections")
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class KnowledgeItem(models.Model):
    """
    知识条目模型
    表示存入知识库的具体知识单元的元数据
    
    属性:
        collection: 所属集合
        content: 知识内容
        item_type: 条目类型
        source_identifier: 数据源标识符
        data_hash: 数据内容哈希值
        metadata: 附加元数据
        status: 条目状态(active/archived等)
        added_at: 添加时间
        last_accessed_at: 最后访问时间
    """
    collection = models.ForeignKey(
        KnowledgeCollection,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Collection"),
        help_text=_("The collection this item belongs to.")
    )
    content = models.TextField(
        _("Content"),
        default="",
        help_text=_("The actual content of the knowledge item.")
    )
    item_type = models.CharField(
        _("Item Type"),
        max_length=50,
        choices=[
            ('text', _('Text')),
            ('document', _('Document')),
            ('faq', _('FAQ')),
            ('memory', _('Memory')),
            ('reference', _('Reference')),
        ],
        default='text',
        db_index=True,
        help_text=_("Type of the knowledge item.")
    )
    source_identifier = models.CharField(
        _("Source Identifier"),
        max_length=512,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Unique identifier for the original data source, e.g., filename, URL, DB record ID.")
    )
    data_hash = models.CharField(
        _("Data Hash"),
        max_length=128,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Hash of the original data content to detect changes.")
    )
    metadata = models.JSONField(
        _("Metadata"),
        blank=True,
        null=True,
        help_text=_("Arbitrary metadata related to this item, e.g., creation date, author, tags.")
    )
    status = models.CharField(
        _("Status"),
        max_length=50,
        choices=[
            ('pending', _('Pending')),
            ('processing', _('Processing')),
            ('active', _('Active')),
            ('archived', _('Archived')),
            ('error', _('Error')),
        ],
        default='active',
        db_index=True,
        help_text=_("Status of this knowledge item.")
    )
    added_at = models.DateTimeField(_("Added At"), auto_now_add=True)
    last_accessed_at = models.DateTimeField(
        _("Last Accessed At"),
        blank=True,
        null=True,
        help_text=_("Timestamp of the last access or retrieval.")
    )

    class Meta:
        verbose_name = _("Knowledge Item")
        verbose_name_plural = _("Knowledge Items")
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['collection', 'status']),
        ]

    def __str__(self):
        return f"Item {self.id} in {self.collection.name}"

class KnowledgeInteraction(models.Model):
    """
    知识交互记录模型
    记录用户与知识库系统的所有交互操作
    
    属性:
        user: 操作用户
        collection: 相关集合
        interaction_type: 交互类型(add_data/search_query等)
        request_payload: 请求数据
        response_payload: 响应数据
        llm_prompt_data: LLM提示数据
        duration_ms: 处理时长(毫秒)
        status_code: HTTP状态码
        error_message: 错误信息
        timestamp: 时间戳
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='knowledge_interactions',
        verbose_name=_("User")
    )
    collection = models.ForeignKey(
        KnowledgeCollection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interactions',
        verbose_name=_("Collection")
    )
    interaction_type = models.CharField(
        _("Interaction Type"),
        max_length=50,
        choices=[
            ('add_data', _('Add Data')),
            ('search_query', _('Search Query')),
            ('search_data', _('Search Data')), # 新增纯搜索类型
            ('get_data', _('Get Data')), # 新增获取数据类型
            ('delete_data', _('Delete Data')), # 新增删除数据类型
        ],
        db_index=True,
        help_text=_("Type of interaction, e.g., 'add_data', 'search_query'.")
    )
    request_payload = models.JSONField(
        _("Request Payload"),
        blank=True,
        null=True,
        help_text=_("Sanitized main content of the API request.")
    )
    response_payload = models.JSONField(
        _("Response Payload"),
        blank=True,
        null=True,
        help_text=_("Sanitized main content of the API response.")
    )
    llm_prompt_data = models.JSONField(
        _("LLM Prompt Data"),
        blank=True,
        null=True,
        help_text=_("Prompt and context sent to LLM, if applicable.")
    )
    duration_ms = models.PositiveIntegerField(
        _("Duration (ms)"),
        blank=True,
        null=True,
        help_text=_("Processing time for the interaction in milliseconds.")
    )
    status_code = models.PositiveSmallIntegerField(
        _("Status Code"),
        blank=True,
        null=True,
        help_text=_("HTTP response status code.")
    )
    error_message = models.TextField(
        _("Error Message"),
        blank=True,
        null=True,
        help_text=_("Error message if an error occurred.")
    )
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Knowledge Interaction")
        verbose_name_plural = _("Knowledge Interactions")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_interaction_type_display()} at {self.timestamp} by {self.user or 'System'}"

# Added as per plan X/docs/plans/2025-05-30_knowledge_config_admin_plan.md
class KnowledgeConfig(models.Model):
    name = models.CharField(
        _("配置名称"),
        max_length=255,
        unique=True,
        help_text=_("此配置集的唯一名称，例如 '默认 Groq Llama4 Aliyun V3'")
    )
    is_active = models.BooleanField(
        _("是否激活"),
        default=False,
        help_text=_("一次只能激活一个配置。系统将使用激活的配置。")
    )

    # LLM 配置（从路由器获取）
    llm_model_name = models.CharField(
        _("LLM 模型名称"),
        max_length=255,
        default="meta-llama/llama-4-maverick-17b-128e-instruct",
        help_text=_("具体的模型名称，例如 'gpt-3.5-turbo', 'meta-llama/llama-4-maverick-17b-128e-instruct'。")
    )
    llm_temperature = models.FloatField(
        _("LLM 温度参数"),
        default=0.35,
        help_text=_("LLM 的采样温度，例如 0.7。")
    )

    # Embedder 配置（从路由器获取）
    embedder_model_name = models.CharField(
        _("Embedder 模型名称"),
        max_length=255,
        default="text-embedding-v3",
        help_text=_("Embeddings 的具体模型名称，例如 'text-embedding-ada-002', 'text-embedding-v3'。")
    )
    embedder_dimensions = models.PositiveIntegerField(
        _("Embedder 维度"),
        default=1024,
        help_text=_("Embeddings 的维度，例如 1024。")
    )

    # 向量存储配置
    vector_store_provider = models.CharField(
        _("向量存储提供商"),
        max_length=50,
        choices=[("qdrant", "Qdrant")],
        default="qdrant",
        help_text=_("向量存储的提供商。")
    )
    qdrant_host = models.CharField(
        _("Qdrant 主机"),
        max_length=255,
        default="localhost",
        help_text=_("Qdrant 服务的主机名或 IP 地址。")
    )
    qdrant_port = models.PositiveIntegerField(
        _("Qdrant 端口"),
        default=6333,
        help_text=_("Qdrant 服务的端口号。")
    )
    qdrant_api_key = models.CharField(
        _("Qdrant API 密钥"),
        max_length=512,
        blank=True,
        null=True,
        help_text=_("Qdrant 服务的 API 密钥（如果已配置）。")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("知识库配置")
        verbose_name_plural = _("知识库配置")
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        return f"{self.name} ({_('激活') if self.is_active else _('未激活')})"

    def save(self, *args, **kwargs):
        if self.is_active:
            KnowledgeConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
