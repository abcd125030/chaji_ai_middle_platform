"""
frago Cloud Market 序列化器

包含设备认证、Recipe 市场、会话同步相关的序列化器
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Recipe, RecipeVersion, RecipeRating, SyncedSession, DeviceCode

User = get_user_model()


# ==================== 设备认证序列化器 ====================

class DeviceCodeRequestSerializer(serializers.Serializer):
    """设备码请求序列化器"""
    client_id = serializers.CharField(
        max_length=100,
        help_text='客户端标识（如 frago-cli）'
    )
    scope = serializers.CharField(
        max_length=200,
        default='market sync',
        required=False,
        help_text='授权范围'
    )


class DeviceCodeResponseSerializer(serializers.Serializer):
    """设备码响应序列化器"""
    device_code = serializers.CharField(help_text='设备码（CLI 轮询用）')
    user_code = serializers.CharField(help_text='用户码（显示给用户）')
    verification_uri = serializers.URLField(help_text='用户授权页面地址')
    expires_in = serializers.IntegerField(help_text='过期时间（秒）')
    interval = serializers.IntegerField(help_text='建议轮询间隔（秒）')


class TokenPollRequestSerializer(serializers.Serializer):
    """Token 轮询请求序列化器"""
    device_code = serializers.CharField(
        max_length=64,
        help_text='设备码'
    )
    client_id = serializers.CharField(
        max_length=100,
        help_text='客户端标识'
    )
    grant_type = serializers.CharField(
        default='urn:ietf:params:oauth:grant-type:device_code',
        required=False,
        help_text='授权类型'
    )


class TokenResponseSerializer(serializers.Serializer):
    """Token 响应序列化器"""
    access_token = serializers.CharField(help_text='访问令牌')
    refresh_token = serializers.CharField(help_text='刷新令牌')
    token_type = serializers.CharField(default='Bearer', help_text='令牌类型')
    expires_in = serializers.IntegerField(help_text='过期时间（秒）')
    scope = serializers.CharField(required=False, help_text='授权范围')


class DeviceAuthErrorSerializer(serializers.Serializer):
    """设备认证错误响应序列化器"""
    error = serializers.ChoiceField(
        choices=[
            ('authorization_pending', '等待用户授权'),
            ('slow_down', '轮询过快'),
            ('expired_token', '设备码已过期'),
            ('access_denied', '用户拒绝授权'),
            ('invalid_grant', '设备码无效'),
            ('invalid_client', '客户端无效'),
            ('server_error', '服务器错误'),
        ],
        help_text='错误代码'
    )
    error_description = serializers.CharField(help_text='错误描述')


class DeviceAuthorizeRequestSerializer(serializers.Serializer):
    """用户授权请求序列化器"""
    user_code = serializers.CharField(
        max_length=10,
        help_text='用户码（如 ABCD-1234）'
    )


class UserInfoSerializer(serializers.ModelSerializer):
    """用户信息序列化器"""
    subscription_type = serializers.SerializerMethodField()
    avatar_url = serializers.CharField(source='avatar_url', read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'avatar_url', 'subscription_type', 'date_joined')
        read_only_fields = fields

    def get_subscription_type(self, obj):
        """获取订阅类型"""
        try:
            return obj.profile.subscription_type
        except Exception:
            return 'free_user'


class TokenRefreshRequestSerializer(serializers.Serializer):
    """Token 刷新请求序列化器"""
    refresh_token = serializers.CharField(help_text='刷新令牌')


# ==================== Recipe 序列化器 ====================

class RecipeAuthorSerializer(serializers.ModelSerializer):
    """Recipe 作者序列化器（简化版）"""
    class Meta:
        model = User
        fields = ('id', 'username')
        read_only_fields = fields


class RecipeVersionSerializer(serializers.ModelSerializer):
    """Recipe 版本序列化器"""
    class Meta:
        model = RecipeVersion
        fields = ('version', 'changelog', 'file_size', 'is_latest', 'created_at')
        read_only_fields = fields


class RecipeSummarySerializer(serializers.ModelSerializer):
    """Recipe 列表序列化器（摘要）"""
    author = serializers.CharField(source='author.username', read_only=True)
    latest_version = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'name', 'description', 'author', 'runtime',
            'is_premium', 'download_count', 'average_rating',
            'latest_version', 'created_at'
        )
        read_only_fields = fields

    def get_latest_version(self, obj):
        """获取最新版本号"""
        latest = obj.get_latest_version()
        return latest.version if latest else None


class RecipeDetailSerializer(serializers.ModelSerializer):
    """Recipe 详情序列化器"""
    author = RecipeAuthorSerializer(read_only=True)
    versions = RecipeVersionSerializer(many=True, read_only=True)
    ratings_count = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    latest_version = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'name', 'description', 'author', 'runtime',
            'is_public', 'is_premium', 'download_count', 'average_rating',
            'latest_version', 'versions', 'ratings_count', 'user_rating',
            'created_at', 'updated_at'
        )
        read_only_fields = fields

    def get_latest_version(self, obj):
        """获取最新版本号"""
        latest = obj.get_latest_version()
        return latest.version if latest else None

    def get_ratings_count(self, obj):
        """获取评分数量"""
        return obj.ratings.count()

    def get_user_rating(self, obj):
        """获取当前用户的评分"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            rating = obj.ratings.filter(user=request.user).first()
            return rating.rating if rating else None
        return None


class RecipeDownloadResponseSerializer(serializers.Serializer):
    """Recipe 下载响应序列化器"""
    name = serializers.CharField()
    version = serializers.CharField()
    runtime = serializers.CharField()
    content = serializers.CharField()


class RecipePublishRequestSerializer(serializers.Serializer):
    """Recipe 发布请求序列化器"""
    name = serializers.RegexField(
        regex=r'^[a-z0-9-]+$',
        min_length=3,
        max_length=100,
        help_text='Recipe 名称（只能包含小写字母、数字和连字符）'
    )
    description = serializers.CharField(
        help_text='Recipe 描述'
    )
    runtime = serializers.ChoiceField(
        choices=Recipe.RuntimeType.choices,
        help_text='运行时类型'
    )
    version = serializers.RegexField(
        regex=r'^\d+\.\d+\.\d+$',
        help_text='语义版本号（如 1.0.0）'
    )
    content = serializers.CharField(
        max_length=1048576,  # 1MB
        help_text='Recipe 脚本内容'
    )
    changelog = serializers.CharField(
        required=False,
        default='',
        help_text='版本更新说明'
    )
    is_public = serializers.BooleanField(
        default=True,
        help_text='是否公开'
    )
    is_premium = serializers.BooleanField(
        default=False,
        help_text='是否需要订阅'
    )


# ==================== 评分序列化器 ====================

class RatingRequestSerializer(serializers.Serializer):
    """评分请求序列化器"""
    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
        help_text='评分（1-5）'
    )
    comment = serializers.CharField(
        required=False,
        default='',
        help_text='评论内容'
    )


class RatingResponseSerializer(serializers.ModelSerializer):
    """评分响应序列化器"""
    user = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = RecipeRating
        fields = ('id', 'user', 'rating', 'comment', 'created_at', 'updated_at')
        read_only_fields = fields


# ==================== 会话同步序列化器 ====================

class SyncedSessionSerializer(serializers.ModelSerializer):
    """同步会话序列化器"""
    class Meta:
        model = SyncedSession
        fields = (
            'id', 'session_id', 'name', 'agent_type',
            'metadata', 'file_size', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'file_size', 'created_at', 'updated_at')


class SessionUploadSerializer(serializers.Serializer):
    """会话上传请求序列化器"""
    session_id = serializers.CharField(
        max_length=100,
        help_text='本地会话 ID'
    )
    name = serializers.CharField(
        max_length=200,
        required=False,
        default='',
        help_text='会话名称'
    )
    agent_type = serializers.CharField(
        max_length=50,
        help_text='Agent 类型'
    )
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text='会话元信息'
    )
    file = serializers.FileField(
        help_text='会话压缩包（.tar.gz）'
    )

    def validate_file(self, value):
        """验证文件"""
        # 检查文件大小（50MB 限制）
        max_size = 50 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f'文件大小超过限制（最大 50MB，当前 {value.size / 1024 / 1024:.2f}MB）'
            )
        return value


# ==================== Claude Code 镜像序列化器（US6） ====================

class ClaudeCodeVersionSerializer(serializers.Serializer):
    """Claude Code 版本序列化器"""
    version = serializers.CharField()
    released_at = serializers.DateTimeField()
    changelog = serializers.CharField(allow_blank=True)
    deprecated = serializers.BooleanField()


class ClaudeCodeBinarySerializer(serializers.Serializer):
    """Claude Code 二进制序列化器"""
    platform = serializers.CharField()
    arch = serializers.CharField()
    file_size = serializers.IntegerField()
    sha256 = serializers.CharField()
    download_count = serializers.IntegerField(required=False)


class ClaudeCodeVersionDetailSerializer(serializers.Serializer):
    """Claude Code 版本详情序列化器（含二进制列表）"""
    version = serializers.CharField()
    released_at = serializers.DateTimeField()
    changelog = serializers.CharField(allow_blank=True)
    deprecated = serializers.BooleanField()
    binaries = ClaudeCodeBinarySerializer(many=True, required=False)


class ClaudeCodeDownloadResponseSerializer(serializers.Serializer):
    """Claude Code 下载响应序列化器"""
    version = serializers.CharField()
    platform = serializers.CharField()
    arch = serializers.CharField()
    download_url = serializers.URLField()
    sha256 = serializers.CharField()
    file_size = serializers.IntegerField()


class ClaudeCodeLatestResponseSerializer(serializers.Serializer):
    """Claude Code 最新版本响应序列化器"""
    version = serializers.CharField()
    released_at = serializers.DateTimeField()
    download_url = serializers.URLField()
    sha256 = serializers.CharField()
    file_size = serializers.IntegerField()
