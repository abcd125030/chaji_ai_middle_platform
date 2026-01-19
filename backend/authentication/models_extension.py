"""
用户扩展模型 - 遵循单一职责原则，扩展用户信息而不修改核心User模型
"""

from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
import uuid


class UserProfile(models.Model):
    """用户配置文件 - 存储扩展的用户信息"""
    
    # 订阅类型选择
    class SubscriptionType(models.TextChoices):
        FREE = 'free_user', '免费用户'
        VIP = 'vip_user', 'VIP用户'
        ENTERPRISE = 'enterprise_user', '企业用户'
        MAX = 'max_user', 'Max用户'
    
    # 行业类型选择
    class IndustryType(models.TextChoices):
        TECHNOLOGY = 'technology', 'Technology'
        FINANCE = 'finance', 'Finance'
        HEALTHCARE = 'healthcare', 'Healthcare'
        EDUCATION = 'education', 'Education'
        RETAIL = 'retail', 'Retail'
        MANUFACTURING = 'manufacturing', 'Manufacturing'
        REAL_ESTATE = 'real_estate', 'Real Estate'
        HOSPITALITY = 'hospitality', 'Hospitality'
        TRANSPORTATION = 'transportation', 'Transportation'
        ENERGY = 'energy', 'Energy'
        MEDIA = 'media', 'Media & Entertainment'
        TELECOMMUNICATIONS = 'telecommunications', 'Telecommunications'
        AGRICULTURE = 'agriculture', 'Agriculture'
        CONSTRUCTION = 'construction', 'Construction'
        GOVERNMENT = 'government', 'Government'
        NON_PROFIT = 'non_profit', 'Non-Profit'
        CONSULTING = 'consulting', 'Consulting'
        LEGAL = 'legal', 'Legal'
        INSURANCE = 'insurance', 'Insurance'
        PHARMACEUTICAL = 'pharmaceutical', 'Pharmaceutical'
        AUTOMOTIVE = 'automotive', 'Automotive'
        AEROSPACE = 'aerospace', 'Aerospace & Defense'
        LOGISTICS = 'logistics', 'Logistics & Supply Chain'
        E_COMMERCE = 'e_commerce', 'E-Commerce'
        OTHER = 'other', 'Other'
    
    # 主键和关联
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='配置文件ID'
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='用户'
    )
    
    # 订阅类型字段
    subscription_type = models.CharField(
        max_length=20,
        choices=SubscriptionType.choices,
        default=SubscriptionType.FREE,
        verbose_name='订阅类型',
        help_text='用户的订阅等级，决定配额和功能权限'
    )
    
    # 行业字段
    industry = models.CharField(
        max_length=30,
        choices=IndustryType.choices,
        blank=True,
        null=True,
        verbose_name='所属行业',
        help_text='用户或组织所在的行业领域'
    )

    # 用户上下文信息
    context_data = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name='上下文数据',
        help_text='存储用户的背景信息、专业领域等'
    )
    
    # 用户标签和分类
    tags = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        verbose_name='用户标签',
        help_text='用于分类和个性化的标签列表'
    )
    
    # 用户偏好设置
    preferences = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name='用户偏好',
        help_text='存储用户的各种偏好设置'
    )
    
    # 能力和权限配置
    capabilities = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name='能力配置',
        help_text='定义用户可以访问的工具、模型等资源'
    )
    
    # 配额和限制
    """
    配额标准（quotas）：
    
    1. 命名规范：
       - AI模型：{model}_calls_{period}（如 gpt4_calls_monthly）
       - Token：{type}_tokens_{period}（如 input_tokens_daily）
       - 存储：storage_{unit}（如 storage_mb）
       - 并发：concurrent_{resource}（如 concurrent_tasks）
       - 速率：{resource}_per_{time}（如 requests_per_minute）
    
    2. 时间周期后缀：
       - _daily：每日限制（24小时重置）
       - _monthly：每月限制（月初重置）
       - _total：总量限制（不重置）
       - 无后缀：永久限制或实时限制
    
    3. 特殊值约定：
       - 0：禁用该功能
       - -1：无限制
       - 正整数：具体配额数量
    
    4. 标准配额键（嵌套结构）：
       {
           "llm_calls": {
               "gpt4_monthly": 1000,         # GPT-4月度调用次数
               "gpt35_daily": 100,           # GPT-3.5每日调用次数  
               "claude_total": 5000          # Claude总调用次数
           },
           
           "tokens": {
               "max_per_request": 4000,      # 单次请求最大token
               "input_monthly": 500000,      # 月度输入token上限
               "output_monthly": 500000      # 月度输出token上限
           },
           
           "storage": {
               "max_documents": 100,         # 最大文档数
               "space_mb": 500,              # 存储空间(MB)
               "max_file_mb": 10             # 单文件大小上限(MB)
           },
           
           "rate_limits": {
               "concurrent_tasks": 3,        # 最大并发任务数
               "requests_per_minute": 20,    # 每分钟请求数
               "requests_per_hour": 500      # 每小时请求数
           },
           
           "features": {
               "knowledge_base": 1,          # 知识库权限(0=禁用,1=启用,-1=无限)
               "advanced_tools": 0,          # 高级工具权限
               "workflow_creation": -1       # 工作流创建权限
           }
       }
    """
    quotas = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name='使用配额',
        help_text='各种资源的使用配额限制'
    )
    
    # 使用统计
    """
    使用统计标准（usage_stats）：
    
    1. 与配额对应关系：
       - 每个quotas中的限制项，在usage_stats中应有对应的统计项
       - 键名保持一致，便于配额检查
       - 示例：quotas["gpt4_calls_monthly"] 对应 usage_stats["gpt4_calls_monthly"]
    
    2. 统计项分类：
       
       a) 需要重置的统计（与quotas周期对应）：
          - {resource}_daily：每日统计，每天0点重置
          - {resource}_monthly：月度统计，每月1日重置
          - {resource}_per_minute：分钟级统计，每分钟重置
          - {resource}_per_hour：小时级统计，每小时重置
       
       b) 累计统计（不重置）：
          - {resource}_total：历史总量
          - 不带周期后缀的项：永久累计
    
    3. 标准统计键（嵌套结构，与quotas对应）：
       {
           "llm_calls": {
               "gpt4_monthly": 150,          # 本月已调用GPT-4次数
               "gpt35_daily": 23,            # 今日已调用GPT-3.5次数
               "claude_total": 892           # 历史总调用Claude次数
           },
           
           "tokens": {
               "input_monthly": 125000,      # 本月输入token使用量
               "output_monthly": 98000,      # 本月输出token使用量
               "total": 450000              # 历史总token使用量
           },
           
           "storage": {
               "documents": 45,              # 当前文档数量
               "space_mb": 125.5            # 当前存储使用量(MB)
           },
           
           "rate_limits": {
               "requests_per_minute": 5,     # 当前分钟内请求数
               "requests_per_hour": 120,     # 当前小时内请求数
               "concurrent_tasks": 2         # 当前并发任务数
           },
           
           "activity": {
               "knowledge_queries": 320,     # 知识库查询次数（仅统计）
               "workflows_created": 15,      # 创建的工作流数量
               "tools_called": 89,          # 工具调用次数
               "tasks_completed": 28,        # 完成的任务数
               "tasks_failed": 3            # 失败的任务数
           },
           
           "timestamps": {
               "last_gpt4_call": "2024-01-15T10:30:00Z",
               "last_reset_daily": "2024-01-15T00:00:00Z",
               "last_reset_monthly": "2024-01-01T00:00:00Z"
           }
       }
    
    4. 更新规则：
       - 成功的操作才更新统计
       - 失败或取消的操作不计入
       - 并发统计需要在任务开始时+1，结束时-1
       - 使用事务保证数据一致性
    
    5. 重置规则：
       - daily项：每天UTC 0点或本地时间0点重置
       - monthly项：每月1日0点重置
       - per_minute/per_hour：滑动窗口或固定窗口重置
       - total项和无后缀项：永不重置
    """
    usage_stats = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name='使用统计',
        help_text='累计的使用统计数据'
    )
    
    
    # 时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        verbose_name = '用户配置文件'
        verbose_name_plural = '用户配置文件'
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Profile ({self.get_subscription_type_display()})"
    
    def get_collection_name(self, base_name: str) -> str:
        """生成用户专属的collection名称"""
        return f"user_{self.user.id}_{base_name}"
    
    def has_capability(self, capability: str) -> bool:
        """检查用户是否有某个能力"""
        if not self.capabilities:
            return False
        return capability in self.capabilities.get('allowed', [])
    
    def is_free_user(self) -> bool:
        """检查是否为免费用户"""
        return self.subscription_type == self.SubscriptionType.FREE
    
    def is_vip_user(self) -> bool:
        """检查是否为VIP用户"""
        return self.subscription_type == self.SubscriptionType.VIP
    
    def is_enterprise_user(self) -> bool:
        """检查是否为企业用户"""
        return self.subscription_type == self.SubscriptionType.ENTERPRISE
    
    def is_max_user(self) -> bool:
        """检查是否为Max用户"""
        return self.subscription_type == self.SubscriptionType.MAX
    
    def is_premium_user(self) -> bool:
        """检查是否为付费用户（非免费用户）"""
        return self.subscription_type != self.SubscriptionType.FREE
    
    def get_quota(self, resource: str) -> int:
        """获取某个资源的配额"""
        if not self.quotas:
            return 0
        return self.quotas.get(resource, 0)
    
    def update_usage(self, resource: str, amount: int = 1):
        """更新使用统计"""
        if not self.usage_stats:
            self.usage_stats = {}
        
        current = self.usage_stats.get(resource, 0)
        self.usage_stats[resource] = current + amount
        self.save(update_fields=['usage_stats', 'updated_at'])
    


