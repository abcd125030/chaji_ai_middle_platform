"""
frago Cloud Market 数据模型

包含 Recipe 市场和会话同步所需的所有模型：
- Recipe: Recipe 主表
- RecipeVersion: Recipe 版本表
- RecipeRating: Recipe 评分表
- SyncedSession: 同步会话表
- DeviceCode: 设备认证码表
"""

import re
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone


class Recipe(models.Model):
    """Recipe 主表 - 存储 Recipe 的元信息"""

    class RuntimeType(models.TextChoices):
        """运行时类型"""
        CHROME_JS = 'chrome-js', 'Chrome CDP JavaScript'
        PYTHON = 'python', 'Python 脚本'
        SHELL = 'shell', 'Shell 脚本'

    # Recipe 名称验证器：只允许小写字母、数字和连字符
    name_validator = RegexValidator(
        regex=r'^[a-z0-9-]+$',
        message='Recipe 名称只能包含小写字母、数字和连字符',
        code='invalid_recipe_name'
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        validators=[name_validator],
        verbose_name='名称',
        help_text='Recipe 唯一标识符（如 twitter-login）'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='作者'
    )
    description = models.TextField(
        verbose_name='描述',
        help_text='Recipe 功能描述'
    )
    runtime = models.CharField(
        max_length=20,
        choices=RuntimeType.choices,
        verbose_name='运行时类型'
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name='是否公开',
        help_text='是否在市场中公开可见'
    )
    is_premium = models.BooleanField(
        default=False,
        verbose_name='是否需要订阅',
        help_text='是否需要 VIP/Enterprise 订阅才能下载'
    )
    download_count = models.PositiveIntegerField(
        default=0,
        verbose_name='下载次数'
    )
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        verbose_name='平均评分',
        help_text='冗余字段，异步计算更新'
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
        verbose_name = 'Recipe'
        verbose_name_plural = 'Recipes'
        ordering = ['-download_count', '-created_at']
        indexes = [
            models.Index(fields=['name'], name='idx_recipe_name'),
            models.Index(fields=['author'], name='idx_recipe_author'),
            models.Index(fields=['is_public', 'is_premium'], name='idx_recipe_public_premium'),
        ]

    def __str__(self):
        return f"{self.name} by {self.author.username}"

    def get_latest_version(self):
        """获取最新版本"""
        return self.versions.filter(is_latest=True).first()


class RecipeVersion(models.Model):
    """Recipe 版本表 - 存储 Recipe 的各个版本内容"""

    # 语义版本号验证器
    version_validator = RegexValidator(
        regex=r'^\d+\.\d+\.\d+$',
        message='版本号必须是语义版本格式（如 1.0.0）',
        code='invalid_version'
    )

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='Recipe'
    )
    version = models.CharField(
        max_length=20,
        validators=[version_validator],
        verbose_name='版本号',
        help_text='语义版本号（如 1.0.0）'
    )
    content = models.TextField(
        verbose_name='内容',
        help_text='Recipe 脚本内容'
    )
    changelog = models.TextField(
        blank=True,
        default='',
        verbose_name='更新说明'
    )
    is_latest = models.BooleanField(
        default=False,
        verbose_name='是否最新版本'
    )
    file_size = models.PositiveIntegerField(
        verbose_name='文件大小',
        help_text='字节数'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='发布时间'
    )

    class Meta:
        verbose_name = 'Recipe 版本'
        verbose_name_plural = 'Recipe 版本'
        ordering = ['-created_at']
        unique_together = [['recipe', 'version']]
        indexes = [
            models.Index(fields=['recipe', 'is_latest'], name='idx_version_recipe_latest'),
            models.Index(fields=['recipe', 'version'], name='idx_version_recipe_version'),
        ]

    def __str__(self):
        return f"{self.recipe.name}@{self.version}"

    def save(self, *args, **kwargs):
        # 自动计算文件大小
        if self.content:
            self.file_size = len(self.content.encode('utf-8'))
        super().save(*args, **kwargs)


class RecipeRating(models.Model):
    """Recipe 评分表 - 存储用户对 Recipe 的评分和评论"""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name='Recipe'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recipe_ratings',
        verbose_name='用户'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='评分',
        help_text='1-5 星评分'
    )
    comment = models.TextField(
        blank=True,
        default='',
        verbose_name='评论'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='评分时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = 'Recipe 评分'
        verbose_name_plural = 'Recipe 评分'
        ordering = ['-created_at']
        unique_together = [['recipe', 'user']]
        indexes = [
            models.Index(fields=['recipe'], name='idx_rating_recipe'),
            models.Index(fields=['user'], name='idx_rating_user'),
        ]

    def __str__(self):
        return f"{self.user.username} rated {self.recipe.name}: {self.rating}★"


class SyncedSession(models.Model):
    """同步会话表 - 记录用户同步到云端的会话元信息"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='synced_sessions',
        verbose_name='用户'
    )
    session_id = models.CharField(
        max_length=100,
        verbose_name='本地会话 ID'
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='会话名称',
        help_text='用户自定义名称'
    )
    agent_type = models.CharField(
        max_length=50,
        verbose_name='Agent 类型'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='元信息'
    )
    storage_key = models.CharField(
        max_length=200,
        verbose_name='存储路径',
        help_text='R2 存储路径'
    )
    file_size = models.PositiveIntegerField(
        verbose_name='文件大小',
        help_text='字节数'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='上传时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '同步会话'
        verbose_name_plural = '同步会话'
        ordering = ['-created_at']
        unique_together = [['user', 'session_id']]
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_session_user'),
        ]

    def __str__(self):
        return f"{self.session_id} ({self.user.username})"


class DeviceCode(models.Model):
    """设备认证码表 - 管理 CLI OAuth Device Authorization 流程的状态"""

    class Status(models.TextChoices):
        """认证状态"""
        PENDING = 'pending', '等待授权'
        AUTHORIZED = 'authorized', '已授权'
        USED = 'used', '已使用'
        EXPIRED = 'expired', '已过期'
        DENIED = 'denied', '已拒绝'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID'
    )
    device_code = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='设备码',
        help_text='CLI 轮询用'
    )
    user_code = models.CharField(
        max_length=8,
        unique=True,
        verbose_name='用户码',
        help_text='显示给用户的 8 位代码'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_codes',
        verbose_name='用户',
        help_text='认证成功后关联的用户'
    )
    client_id = models.CharField(
        max_length=100,
        verbose_name='客户端标识'
    )
    scope = models.CharField(
        max_length=200,
        default='market sync',
        verbose_name='授权范围'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='状态'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    expires_at = models.DateTimeField(
        verbose_name='过期时间'
    )
    authorized_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='授权时间'
    )

    class Meta:
        verbose_name = '设备认证码'
        verbose_name_plural = '设备认证码'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device_code'], name='idx_device_code'),
            models.Index(fields=['user_code'], name='idx_user_code'),
            models.Index(fields=['expires_at'], name='idx_expires'),
        ]

    def __str__(self):
        return f"{self.user_code} ({self.status})"

    @property
    def is_expired(self):
        """检查是否已过期"""
        return timezone.now() > self.expires_at

    def authorize(self, user):
        """用户授权"""
        self.user = user
        self.status = self.Status.AUTHORIZED
        self.authorized_at = timezone.now()
        self.save()

    def mark_used(self):
        """标记为已使用"""
        self.status = self.Status.USED
        self.save()

    def deny(self):
        """拒绝授权"""
        self.status = self.Status.DENIED
        self.save()


# ==================== Claude Code 镜像模型（US6） ====================

class ClaudeCodeVersion(models.Model):
    """Claude Code 版本表 - 存储 Claude Code 的版本元信息"""

    # 语义版本号验证器
    version_validator = RegexValidator(
        regex=r'^\d+\.\d+\.\d+$',
        message='版本号必须是语义版本格式（如 1.0.34）',
        code='invalid_version'
    )

    version = models.CharField(
        max_length=20,
        unique=True,
        validators=[version_validator],
        verbose_name='版本号',
        help_text='语义版本号（如 1.0.34）'
    )
    released_at = models.DateTimeField(
        verbose_name='发布时间',
        help_text='官方发布时间'
    )
    changelog = models.TextField(
        blank=True,
        default='',
        verbose_name='更新说明'
    )
    deprecated = models.BooleanField(
        default=False,
        verbose_name='是否已废弃'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='同步时间'
    )

    class Meta:
        verbose_name = 'Claude Code 版本'
        verbose_name_plural = 'Claude Code 版本'
        ordering = ['-released_at']
        indexes = [
            models.Index(fields=['version'], name='idx_claude_version'),
            models.Index(fields=['-released_at'], name='idx_claude_released_at'),
        ]

    def __str__(self):
        return f"Claude Code v{self.version}"


class ClaudeCodeBinary(models.Model):
    """Claude Code 二进制表 - 存储各平台的二进制文件元信息"""

    class PlatformArch(models.TextChoices):
        """平台-架构组合（与 GCS 目录名一致）"""
        LINUX_X64 = 'linux-x64', 'Linux x64'
        LINUX_ARM64 = 'linux-arm64', 'Linux arm64'
        LINUX_X64_MUSL = 'linux-x64-musl', 'Linux x64 (musl)'
        LINUX_ARM64_MUSL = 'linux-arm64-musl', 'Linux arm64 (musl)'
        DARWIN_X64 = 'darwin-x64', 'macOS Intel'
        DARWIN_ARM64 = 'darwin-arm64', 'macOS Apple Silicon'
        WIN32_X64 = 'win32-x64', 'Windows x64'

    version = models.ForeignKey(
        ClaudeCodeVersion,
        on_delete=models.CASCADE,
        related_name='binaries',
        verbose_name='版本'
    )
    platform_arch = models.CharField(
        max_length=30,
        choices=PlatformArch.choices,
        verbose_name='平台架构',
        help_text='与 GCS 目录名一致（如 linux-x64, darwin-arm64）'
    )
    file_size = models.BigIntegerField(
        verbose_name='文件大小',
        help_text='字节数（二进制文件约 200MB）'
    )
    sha256 = models.CharField(
        max_length=64,
        verbose_name='SHA256 校验和'
    )
    storage_key = models.CharField(
        max_length=200,
        verbose_name='存储路径',
        help_text='R2 存储路径'
    )
    download_count = models.PositiveIntegerField(
        default=0,
        verbose_name='下载次数'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='上传时间'
    )

    class Meta:
        verbose_name = 'Claude Code 二进制'
        verbose_name_plural = 'Claude Code 二进制'
        ordering = ['-created_at']
        unique_together = [['version', 'platform_arch']]
        indexes = [
            models.Index(fields=['version'], name='idx_binary_version'),
            models.Index(fields=['platform_arch'], name='idx_binary_platform_arch'),
        ]

    def __str__(self):
        return f"claude-code-{self.platform_arch} v{self.version.version}"

    @property
    def filename(self):
        """生成文件名"""
        if self.platform_arch.startswith('win32'):
            return 'claude.exe'
        return 'claude'

    @property
    def platform(self):
        """获取平台部分"""
        parts = self.platform_arch.split('-')
        return parts[0]

    @property
    def arch(self):
        """获取架构部分"""
        parts = self.platform_arch.split('-')
        return '-'.join(parts[1:]) if len(parts) > 1 else parts[0]


class ClaudeCodeDownloadLog(models.Model):
    """Claude Code 下载日志表 - 用于 IP 限流统计"""

    ip_address = models.GenericIPAddressField(
        verbose_name='请求 IP'
    )
    binary = models.ForeignKey(
        ClaudeCodeBinary,
        on_delete=models.CASCADE,
        related_name='download_logs',
        verbose_name='下载的二进制'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='下载时间'
    )

    class Meta:
        verbose_name = 'Claude Code 下载日志'
        verbose_name_plural = 'Claude Code 下载日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', '-created_at'], name='idx_download_ip_time'),
        ]

    def __str__(self):
        return f"{self.ip_address} downloaded {self.binary.filename}"
