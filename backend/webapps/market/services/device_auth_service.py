"""
设备认证服务 - OAuth 2.0 Device Authorization Grant (RFC 8628)

实现 CLI 登录的设备认证流程:
1. CLI 请求 device_code 和 user_code
2. 用户在浏览器中输入 user_code 并授权
3. CLI 轮询获取 access_token
"""

import secrets
import string
import logging
from datetime import timedelta
from typing import Tuple, Optional, Dict, Any

from django.utils import timezone
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import DeviceCode

logger = logging.getLogger('django')


class DeviceAuthService:
    """设备认证服务"""

    # 配置参数
    DEVICE_CODE_LENGTH = 64  # 设备码长度
    USER_CODE_LENGTH = 8  # 用户码长度（格式 XXXX-XXXX）
    CODE_EXPIRES_IN = 600  # 设备码过期时间（秒）
    POLL_INTERVAL = 5  # 建议轮询间隔（秒）
    VERIFICATION_URI = None  # 验证页面地址，运行时从 settings 获取

    @classmethod
    def get_verification_uri(cls) -> str:
        """获取验证页面地址"""
        if cls.VERIFICATION_URI:
            return cls.VERIFICATION_URI

        # 从 settings 获取或使用默认值
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f"{base_url}/auth/device"

    @classmethod
    def _generate_device_code(cls) -> str:
        """生成设备码（64位安全随机字符串）"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(cls.DEVICE_CODE_LENGTH))

    @classmethod
    def _generate_user_code(cls) -> str:
        """
        生成用户码（8位大写字母数字，格式 XXXX-XXXX）

        排除易混淆字符: 0, O, I, L, 1
        """
        alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        return f"{code[:4]}-{code[4:]}"

    @classmethod
    def create_device_code(cls, client_id: str, scope: str = 'market sync') -> Dict[str, Any]:
        """
        创建设备认证码

        Args:
            client_id: 客户端标识（如 frago-cli）
            scope: 授权范围

        Returns:
            包含 device_code, user_code, verification_uri, expires_in, interval 的字典
        """
        # 生成唯一的设备码和用户码
        device_code = cls._generate_device_code()
        user_code = cls._generate_user_code()

        # 确保唯一性
        while DeviceCode.objects.filter(device_code=device_code).exists():
            device_code = cls._generate_device_code()
        while DeviceCode.objects.filter(user_code=user_code).exists():
            user_code = cls._generate_user_code()

        # 计算过期时间
        expires_at = timezone.now() + timedelta(seconds=cls.CODE_EXPIRES_IN)

        # 创建数据库记录
        DeviceCode.objects.create(
            device_code=device_code,
            user_code=user_code,
            client_id=client_id,
            scope=scope,
            expires_at=expires_at
        )

        logger.info(f"设备认证码已创建: user_code={user_code}, client_id={client_id}")

        return {
            'device_code': device_code,
            'user_code': user_code,
            'verification_uri': cls.get_verification_uri(),
            'expires_in': cls.CODE_EXPIRES_IN,
            'interval': cls.POLL_INTERVAL,
        }

    @classmethod
    def authorize_device(cls, user_code: str, user) -> Tuple[bool, str]:
        """
        用户授权设备码

        Args:
            user_code: 用户码（带或不带连字符）
            user: 授权用户

        Returns:
            (success, message) 元组
        """
        # 标准化 user_code（移除连字符后重新格式化）
        normalized_code = user_code.replace('-', '').upper()
        if len(normalized_code) == 8:
            formatted_code = f"{normalized_code[:4]}-{normalized_code[4:]}"
        else:
            return False, '用户码格式无效'

        try:
            device_code = DeviceCode.objects.get(user_code=formatted_code)
        except DeviceCode.DoesNotExist:
            return False, '用户码不存在'

        # 检查过期
        if device_code.is_expired:
            device_code.status = DeviceCode.Status.EXPIRED
            device_code.save()
            return False, '用户码已过期'

        # 检查状态
        if device_code.status != DeviceCode.Status.PENDING:
            status_messages = {
                DeviceCode.Status.AUTHORIZED: '此设备码已被授权',
                DeviceCode.Status.USED: '此设备码已被使用',
                DeviceCode.Status.EXPIRED: '此设备码已过期',
                DeviceCode.Status.DENIED: '此设备码已被拒绝',
            }
            return False, status_messages.get(device_code.status, '设备码状态无效')

        # 授权
        device_code.authorize(user)
        logger.info(f"设备码已授权: user_code={formatted_code}, user={user.username}")

        return True, '授权成功'

    @classmethod
    def deny_device(cls, user_code: str) -> Tuple[bool, str]:
        """
        用户拒绝授权设备码

        Args:
            user_code: 用户码

        Returns:
            (success, message) 元组
        """
        normalized_code = user_code.replace('-', '').upper()
        if len(normalized_code) == 8:
            formatted_code = f"{normalized_code[:4]}-{normalized_code[4:]}"
        else:
            return False, '用户码格式无效'

        try:
            device_code = DeviceCode.objects.get(user_code=formatted_code)
        except DeviceCode.DoesNotExist:
            return False, '用户码不存在'

        if device_code.status != DeviceCode.Status.PENDING:
            return False, '设备码状态无效'

        device_code.deny()
        logger.info(f"设备码已拒绝: user_code={formatted_code}")

        return True, '已拒绝授权'

    @classmethod
    def poll_for_token(cls, device_code: str, client_id: str) -> Dict[str, Any]:
        """
        轮询获取访问令牌

        Args:
            device_code: 设备码
            client_id: 客户端标识

        Returns:
            成功时返回 token 信息，等待/失败时返回错误信息
        """
        try:
            dc = DeviceCode.objects.get(device_code=device_code)
        except DeviceCode.DoesNotExist:
            return {
                'error': 'invalid_grant',
                'error_description': '设备码无效',
            }

        # 验证 client_id
        if dc.client_id != client_id:
            return {
                'error': 'invalid_client',
                'error_description': '客户端标识不匹配',
            }

        # 检查过期
        if dc.is_expired:
            if dc.status == DeviceCode.Status.PENDING:
                dc.status = DeviceCode.Status.EXPIRED
                dc.save()
            return {
                'error': 'expired_token',
                'error_description': '设备码已过期',
            }

        # 根据状态返回
        if dc.status == DeviceCode.Status.PENDING:
            return {
                'error': 'authorization_pending',
                'error_description': '等待用户授权',
            }

        if dc.status == DeviceCode.Status.DENIED:
            return {
                'error': 'access_denied',
                'error_description': '用户拒绝授权',
            }

        if dc.status == DeviceCode.Status.USED:
            return {
                'error': 'invalid_grant',
                'error_description': '设备码已被使用',
            }

        if dc.status == DeviceCode.Status.EXPIRED:
            return {
                'error': 'expired_token',
                'error_description': '设备码已过期',
            }

        if dc.status == DeviceCode.Status.AUTHORIZED:
            # 生成 token
            user = dc.user
            if not user:
                return {
                    'error': 'server_error',
                    'error_description': '用户信息丢失',
                }

            tokens = cls.generate_tokens(user)

            # 标记为已使用
            dc.mark_used()
            logger.info(f"Token 已生成: device_code={device_code[:8]}..., user={user.username}")

            return {
                'access_token': str(tokens['access']),
                'refresh_token': str(tokens['refresh']),
                'token_type': 'Bearer',
                'expires_in': int(tokens['access'].lifetime.total_seconds()),
                'scope': dc.scope,
            }

        return {
            'error': 'server_error',
            'error_description': '未知状态',
        }

    @classmethod
    def generate_tokens(cls, user) -> Dict[str, Any]:
        """
        为用户生成 JWT Token

        Args:
            user: Django User 对象

        Returns:
            包含 access 和 refresh token 的字典
        """
        refresh = RefreshToken.for_user(user)
        return {
            'access': refresh.access_token,
            'refresh': refresh,
        }

    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        刷新访问令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 token 信息，失败返回 None
        """
        try:
            refresh = RefreshToken(refresh_token)
            return {
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'token_type': 'Bearer',
                'expires_in': int(refresh.access_token.lifetime.total_seconds()),
            }
        except Exception as e:
            logger.warning(f"Token 刷新失败: {e}")
            return None

    @classmethod
    def cleanup_expired_codes(cls) -> int:
        """
        清理过期的设备码

        Returns:
            清理的记录数
        """
        expired = DeviceCode.objects.filter(
            expires_at__lt=timezone.now(),
            status=DeviceCode.Status.PENDING
        )
        count = expired.count()
        expired.update(status=DeviceCode.Status.EXPIRED)

        if count > 0:
            logger.info(f"已清理 {count} 个过期的设备码")

        return count
