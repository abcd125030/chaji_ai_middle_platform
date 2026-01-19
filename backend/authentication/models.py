"""
用户认证模型 - 支持多种登录方式
合并版本：保留原有字段用于兼容，新增 UserAccount 支持多账号
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid


class User(AbstractUser):
    """扩展Django默认用户模型"""
    
    # 用户类型选项（保留用于兼容）
    class AuthType(models.TextChoices):
        EMAIL = 'email', '邮箱注册'
        FEISHU = 'feishu', '飞书登录'
    
    # 用户状态
    class Status(models.IntegerChoices):
        INACTIVE = 0, '未激活'
        ACTIVE = 1, '正常'
        BANNED = 2, '封禁'
    
    # 用户角色
    class Role(models.TextChoices):
        USER = 'user', '普通用户'
        ADMIN = 'admin', '管理员'
        SUPER_ADMIN = 'super_admin', '超级管理员'
    
    # 保留原有字段用于兼容（后续可废弃）
    auth_type = models.CharField(
        max_length=20,
        choices=AuthType.choices,
        default=AuthType.EMAIL,
        verbose_name='认证类型（已废弃）',
        help_text='请使用 UserAccount 管理多种登录方式'
    )
    
    external_id = models.CharField(
        max_length=64, 
        blank=True, 
        null=True,
        unique=True,
        verbose_name='外部平台ID（已废弃）',
        help_text='请使用 UserAccount.provider_account_id'
    )
    
    # 用户状态和角色
    status = models.SmallIntegerField(
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name='用户状态'
    )
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        verbose_name='用户角色'
    )
    
    # 用户基本信息
    avatar_url = models.URLField(
        blank=True, 
        null=True,
        verbose_name='头像URL'
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='手机号'
    )
    
    # 社交媒体
    twitter_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='Twitter链接'
    )
    
    linkedin_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='LinkedIn链接'
    )
    
    # 协议和政策
    agreed_agreement_version = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='同意的协议版本'
    )
    
    agreed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='同意协议时间'
    )
    
    # 密码重置
    reset_token = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        verbose_name='重置令牌'
    )
    
    reset_token_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='重置令牌过期时间'
    )
    
    # 元数据
    last_login_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name='最后登录IP'
    )
    
    login_count = models.IntegerField(
        default=0,
        verbose_name='登录次数'
    )
    
    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['role']),
        ]
    
    def get_primary_account(self):
        """获取主账号"""
        return self.accounts.filter(is_primary=True).first()
    
    def get_account_by_provider(self, provider):
        """根据提供商获取账号"""
        return self.accounts.filter(provider=provider).first()
    
    def has_provider(self, provider):
        """检查是否绑定了某个提供商"""
        return self.accounts.filter(provider=provider).exists()
    
    # 兼容方法
    @property
    def is_feishu_user(self):
        """检查是否为飞书用户（兼容旧代码）"""
        return self.has_provider('feishu') or self.auth_type == 'feishu'


class UserAccount(models.Model):
    """用户账号关联表 - 管理多种登录方式"""
    
    # 支持的登录提供商
    class Provider(models.TextChoices):
        EMAIL = 'email', '邮箱'
        FEISHU = 'feishu', '飞书'
        GOOGLE = 'google', 'Google'
        GITHUB = 'github', 'GitHub'
        WECHAT = 'wechat', '微信'
    
    # 账号类型
    class AccountType(models.TextChoices):
        OAUTH = 'oauth', 'OAuth认证'
        EMAIL = 'email', '邮箱密码'
        CREDENTIALS = 'credentials', '用户名密码'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='账号ID'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name='用户'
    )
    
    type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        verbose_name='账号类型'
    )
    
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        verbose_name='提供商'
    )
    
    provider_account_id = models.CharField(
        max_length=128,
        verbose_name='提供商账号ID',
        help_text='如飞书的open_id、Google的sub等'
    )
    
    # OAuth 相关字段
    access_token = models.TextField(
        blank=True,
        null=True,
        verbose_name='访问令牌'
    )
    
    refresh_token = models.TextField(
        blank=True,
        null=True,
        verbose_name='刷新令牌'
    )
    
    token_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='令牌类型'
    )
    
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='令牌过期时间'
    )
    
    scope = models.TextField(
        blank=True,
        null=True,
        verbose_name='授权范围'
    )
    
    id_token = models.TextField(
        blank=True,
        null=True,
        verbose_name='ID令牌'
    )
    
    # 账号状态
    is_primary = models.BooleanField(
        default=False,
        verbose_name='是否主账号',
        help_text='用户的主要登录方式'
    )
    
    is_verified = models.BooleanField(
        default=False,
        verbose_name='是否已验证'
    )
    
    # 提供商特定信息
    provider_profile = models.JSONField(
        blank=True,
        null=True,
        verbose_name='提供商用户信息',
        help_text='存储提供商返回的完整用户信息'
    )
    
    # 额外信息
    nickname = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='昵称'
    )
    
    avatar_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='头像URL'
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
    
    last_used_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='最后使用时间'
    )
    
    class Meta:
        verbose_name = '用户账号'
        verbose_name_plural = '用户账号'
        unique_together = [
            ('provider', 'provider_account_id'),
            ('user', 'provider'),
        ]
        indexes = [
            models.Index(fields=['user', 'is_primary']),
            models.Index(fields=['provider', 'provider_account_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.provider}"
    
    def is_token_expired(self):
        """检查令牌是否过期"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        # 确保每个用户只有一个主账号
        if self.is_primary:
            UserAccount.objects.filter(
                user=self.user,
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        
        # 如果是用户的第一个账号，自动设为主账号
        if not self.pk and not UserAccount.objects.filter(user=self.user).exists():
            self.is_primary = True
        
        super().save(*args, **kwargs)


class OAuthState(models.Model):
    """OAuth认证状态管理"""
    
    state = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='状态值'
    )
    
    provider = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='提供商'
    )
    
    redirect_url = models.URLField(
        verbose_name='回调URL'
    )
    
    code_verifier = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name='PKCE验证码'
    )
    
    extra_data = models.TextField(
        blank=True,
        null=True,
        help_text="存储额外的回调信息"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    class Meta:
        verbose_name = 'OAuth状态'
        verbose_name_plural = 'OAuth状态'
        indexes = [
            models.Index(fields=['-created_at'])
        ]
    
    def is_expired(self, minutes=10):
        """检查是否过期（默认10分钟）"""
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(minutes=minutes)


class EmailVerification(models.Model):
    """邮箱验证"""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_verifications',
        verbose_name='用户'
    )
    
    email = models.EmailField(
        verbose_name='待验证邮箱'
    )
    
    token = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='验证令牌'
    )
    
    is_used = models.BooleanField(
        default=False,
        verbose_name='是否已使用'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    expires_at = models.DateTimeField(
        verbose_name='过期时间'
    )
    
    class Meta:
        verbose_name = '邮箱验证'
        verbose_name_plural = '邮箱验证'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def is_expired(self):
        """检查是否过期"""
        return timezone.now() > self.expires_at

