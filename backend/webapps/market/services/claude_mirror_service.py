"""
Claude Code 镜像服务

提供 Claude Code 二进制的版本查询和下载 URL 生成功能
数据源：Google Cloud Storage (storage.googleapis.com)
"""

import logging
from typing import Optional
from django.conf import settings
from django.db.models import F

from ..models import ClaudeCodeVersion, ClaudeCodeBinary

logger = logging.getLogger('django')

# GCS 存储桶配置
GCS_BUCKET_BASE_URL = 'https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases'

# 支持的平台架构列表（与 GCS 目录名一致）
SUPPORTED_PLATFORM_ARCHS = [
    'linux-x64',
    'linux-arm64',
    'linux-x64-musl',
    'linux-arm64-musl',
    'darwin-x64',
    'darwin-arm64',
    'win32-x64',
]


class ClaudeMirrorServiceError(Exception):
    """Claude 镜像服务错误基类"""

    def __init__(self, message: str, code: str = 'mirror_error'):
        self.message = message
        self.code = code
        super().__init__(message)


class VersionNotFoundError(ClaudeMirrorServiceError):
    """版本不存在错误"""

    def __init__(self, version: str):
        super().__init__(
            message=f'Claude Code 版本 {version} 不存在',
            code='version_not_found'
        )


class BinaryNotFoundError(ClaudeMirrorServiceError):
    """二进制不存在错误"""

    def __init__(self, platform_arch: str, version: str = 'latest'):
        super().__init__(
            message=f'未找到 Claude Code {version} ({platform_arch}) 的二进制文件',
            code='binary_not_found'
        )


class ClaudeMirrorService:
    """Claude Code 镜像服务"""

    @classmethod
    def get_latest_version(cls) -> Optional[ClaudeCodeVersion]:
        """
        获取最新版本信息

        Returns:
            ClaudeCodeVersion: 最新版本对象，如果没有则返回 None
        """
        return ClaudeCodeVersion.objects.filter(
            deprecated=False
        ).order_by('-released_at').first()

    @classmethod
    def get_version(cls, version: str) -> ClaudeCodeVersion:
        """
        获取指定版本信息

        Args:
            version: 版本号

        Returns:
            ClaudeCodeVersion: 版本对象

        Raises:
            VersionNotFoundError: 版本不存在
        """
        try:
            return ClaudeCodeVersion.objects.get(version=version)
        except ClaudeCodeVersion.DoesNotExist:
            raise VersionNotFoundError(version)

    @classmethod
    def list_available_versions(cls, include_deprecated: bool = False) -> list:
        """
        列出所有可用版本

        Args:
            include_deprecated: 是否包含已废弃版本

        Returns:
            list: 版本列表
        """
        queryset = ClaudeCodeVersion.objects.all()
        if not include_deprecated:
            queryset = queryset.filter(deprecated=False)

        return list(queryset.order_by('-released_at')[:10])

    @classmethod
    def get_binary(
        cls,
        platform_arch: str,
        version: str = None
    ) -> ClaudeCodeBinary:
        """
        获取指定平台架构的二进制文件信息

        Args:
            platform_arch: 平台架构（如 linux-x64, darwin-arm64）
            version: 版本号，默认为最新版本

        Returns:
            ClaudeCodeBinary: 二进制文件对象

        Raises:
            VersionNotFoundError: 版本不存在
            BinaryNotFoundError: 二进制不存在
        """
        # 验证平台架构
        if platform_arch not in SUPPORTED_PLATFORM_ARCHS:
            raise BinaryNotFoundError(platform_arch, version or 'latest')

        # 获取版本
        if version:
            version_obj = cls.get_version(version)
        else:
            version_obj = cls.get_latest_version()
            if not version_obj:
                raise BinaryNotFoundError(platform_arch, 'latest')

        # 查找二进制
        try:
            return ClaudeCodeBinary.objects.get(
                version=version_obj,
                platform_arch=platform_arch
            )
        except ClaudeCodeBinary.DoesNotExist:
            raise BinaryNotFoundError(platform_arch, version_obj.version)

    @classmethod
    def check_binary_exists(cls, version: str, platform_arch: str) -> bool:
        """
        检查二进制文件是否存在

        Args:
            version: 版本号
            platform_arch: 平台架构

        Returns:
            bool: 是否存在
        """
        return ClaudeCodeBinary.objects.filter(
            version__version=version,
            platform_arch=platform_arch
        ).exists()

    @classmethod
    def get_download_url(cls, binary: ClaudeCodeBinary) -> str:
        """
        生成 R2 签名下载 URL

        Args:
            binary: ClaudeCodeBinary 实例

        Returns:
            str: 签名 URL
        """
        try:
            import boto3
            from botocore.config import Config

            # 从 settings 获取 R2 配置
            r2_config = getattr(settings, 'R2_CONFIG', {})
            if not r2_config:
                logger.warning('R2 配置未找到，返回存储路径')
                return binary.storage_key

            client = boto3.client(
                's3',
                endpoint_url=r2_config.get('endpoint_url'),
                aws_access_key_id=r2_config.get('access_key_id'),
                aws_secret_access_key=r2_config.get('secret_access_key'),
                config=Config(signature_version='s3v4'),
                region_name='auto'
            )

            url = client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': r2_config.get('bucket_name'),
                    'Key': binary.storage_key,
                },
                ExpiresIn=3600  # 1 小时有效
            )

            return url

        except Exception as e:
            logger.error(f'生成 R2 签名 URL 失败: {e}')
            return binary.storage_key

    @classmethod
    def get_gcs_download_url(cls, version: str, platform_arch: str) -> str:
        """
        获取 GCS 官方源下载 URL

        Args:
            version: 版本号
            platform_arch: 平台架构

        Returns:
            str: GCS 下载 URL
        """
        return f'{GCS_BUCKET_BASE_URL}/{version}/{platform_arch}/claude'

    @classmethod
    def increment_download_count(cls, binary: ClaudeCodeBinary) -> None:
        """
        增加下载计数

        Args:
            binary: ClaudeCodeBinary 实例
        """
        ClaudeCodeBinary.objects.filter(pk=binary.pk).update(
            download_count=F('download_count') + 1
        )

    @classmethod
    def get_version_info(cls, version_obj: ClaudeCodeVersion, platform_arch: str = None) -> dict:
        """
        获取版本详细信息

        Args:
            version_obj: ClaudeCodeVersion 实例
            platform_arch: 可选，指定平台架构

        Returns:
            dict: 版本信息
        """
        result = {
            'version': version_obj.version,
            'released_at': version_obj.released_at.isoformat(),
            'changelog': version_obj.changelog,
            'deprecated': version_obj.deprecated,
        }

        if platform_arch:
            try:
                binary = cls.get_binary(platform_arch, version_obj.version)
                result.update({
                    'platform_arch': platform_arch,
                    'file_size': binary.file_size,
                    'sha256': binary.sha256,
                    'download_count': binary.download_count,
                })
            except BinaryNotFoundError:
                result['binary_available'] = False
        else:
            # 列出所有可用的二进制
            binaries = version_obj.binaries.all()
            result['binaries'] = [
                {
                    'platform_arch': b.platform_arch,
                    'file_size': b.file_size,
                    'sha256': b.sha256,
                }
                for b in binaries
            ]

        return result

    @classmethod
    def get_supported_platforms(cls) -> list:
        """获取支持的平台架构列表"""
        return SUPPORTED_PLATFORM_ARCHS.copy()
