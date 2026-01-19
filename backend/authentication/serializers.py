from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """用户信息序列化器"""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'auth_type', 'avatar_url', 'is_staff', 'is_superuser')
        read_only_fields = ('id', 'auth_type', 'is_staff', 'is_superuser')

class FeishuLoginSerializer(serializers.Serializer):
    """飞书登录请求序列化器"""
    code = serializers.CharField(required=True)
    state = serializers.CharField(required=True)
    code_verifier = serializers.CharField(required=False)  # PKCE验证器

class TokenSerializer(serializers.Serializer):
    """JWT令牌序列化器"""
    access = serializers.CharField()
    refresh = serializers.CharField()
    token_type = serializers.CharField(default='Bearer')
