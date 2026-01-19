"""
Claude Code 二进制同步任务

从 Google Cloud Storage 同步 Claude Code 二进制文件到 R2 存储
"""

import hashlib
import json
import logging
import tempfile
from datetime import timedelta
from typing import Optional

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from ..models import ClaudeCodeVersion, ClaudeCodeBinary, ClaudeCodeDownloadLog

logger = logging.getLogger('django')

# GCS 配置
GCS_BASE_URL = 'https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases'

# 支持的平台架构
SUPPORTED_PLATFORM_ARCHS = [
    'linux-x64',
    'linux-arm64',
    'linux-x64-musl',
    'linux-arm64-musl',
    'darwin-x64',
    'darwin-arm64',
    'win32-x64',
]

# 版本保留数量
MAX_VERSIONS_TO_KEEP = 3


def get_latest_version() -> Optional[str]:
    """
    从 GCS 获取最新版本号

    Returns:
        str: 最新版本号，如 '2.1.12'
    """
    try:
        url = f'{GCS_BASE_URL}/latest'
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text.strip()
    except Exception as e:
        logger.error(f'获取 Claude Code 最新版本失败: {e}')
        return None


def get_manifest(version: str) -> Optional[dict]:
    """
    获取版本的 manifest.json

    Args:
        version: 版本号

    Returns:
        dict: manifest 数据
    """
    try:
        url = f'{GCS_BASE_URL}/{version}/manifest.json'
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f'获取 Claude Code {version} manifest 失败: {e}')
        return None


def download_binary_to_r2(
    version: str,
    platform_arch: str,
    sha256: str,
    file_size: int
) -> Optional[str]:
    """
    下载二进制文件并上传到 R2

    Args:
        version: 版本号
        platform_arch: 平台架构
        sha256: 预期的 SHA256 校验和
        file_size: 预期的文件大小

    Returns:
        str: R2 存储路径，失败返回 None
    """
    try:
        import boto3
        from botocore.config import Config

        # 从 settings 获取 R2 配置
        r2_config = getattr(settings, 'R2_CONFIG', {})
        if not r2_config:
            logger.error('R2 配置未找到')
            return None

        # 下载二进制文件
        gcs_url = f'{GCS_BASE_URL}/{version}/{platform_arch}/claude'
        logger.info(f'下载 Claude Code {version} ({platform_arch}) 从 {gcs_url}')

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            response = requests.get(gcs_url, stream=True, timeout=600)
            response.raise_for_status()

            # 计算 SHA256
            sha256_hash = hashlib.sha256()
            downloaded_size = 0

            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
                sha256_hash.update(chunk)
                downloaded_size += len(chunk)

            tmp_file_path = tmp_file.name

        # 验证文件大小
        if downloaded_size != file_size:
            logger.error(
                f'文件大小不匹配: 预期 {file_size}, 实际 {downloaded_size}'
            )
            return None

        # 验证 SHA256
        computed_sha256 = sha256_hash.hexdigest()
        if computed_sha256 != sha256:
            logger.error(
                f'SHA256 不匹配: 预期 {sha256}, 实际 {computed_sha256}'
            )
            return None

        # 上传到 R2
        storage_key = f'claude-code/{version}/{platform_arch}/claude'

        client = boto3.client(
            's3',
            endpoint_url=r2_config.get('endpoint_url'),
            aws_access_key_id=r2_config.get('access_key_id'),
            aws_secret_access_key=r2_config.get('secret_access_key'),
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )

        with open(tmp_file_path, 'rb') as f:
            client.upload_fileobj(
                f,
                r2_config.get('bucket_name'),
                storage_key,
                ExtraArgs={
                    'ContentType': 'application/octet-stream',
                }
            )

        logger.info(f'已上传 {storage_key} 到 R2')
        return storage_key

    except Exception as e:
        logger.error(f'下载/上传 Claude Code {version} ({platform_arch}) 失败: {e}')
        return None


def cleanup_old_versions():
    """
    清理旧版本

    保留最新的 MAX_VERSIONS_TO_KEEP 个版本，删除旧版本的数据库记录和 R2 文件
    """
    try:
        import boto3
        from botocore.config import Config

        # 获取所有版本，按发布时间降序
        versions = ClaudeCodeVersion.objects.order_by('-released_at')
        versions_to_delete = versions[MAX_VERSIONS_TO_KEEP:]

        if not versions_to_delete:
            logger.info('没有需要清理的旧版本')
            return

        r2_config = getattr(settings, 'R2_CONFIG', {})
        client = None
        if r2_config:
            client = boto3.client(
                's3',
                endpoint_url=r2_config.get('endpoint_url'),
                aws_access_key_id=r2_config.get('access_key_id'),
                aws_secret_access_key=r2_config.get('secret_access_key'),
                config=Config(signature_version='s3v4'),
                region_name='auto'
            )

        for version in versions_to_delete:
            logger.info(f'清理旧版本: {version.version}')

            # 删除 R2 文件
            if client:
                for binary in version.binaries.all():
                    try:
                        client.delete_object(
                            Bucket=r2_config.get('bucket_name'),
                            Key=binary.storage_key
                        )
                        logger.info(f'已删除 R2 文件: {binary.storage_key}')
                    except Exception as e:
                        logger.warning(f'删除 R2 文件失败: {binary.storage_key}, {e}')

            # 删除数据库记录（级联删除 binaries）
            version.delete()
            logger.info(f'已删除版本记录: {version.version}')

    except Exception as e:
        logger.error(f'清理旧版本失败: {e}')


def cleanup_old_download_logs():
    """
    清理 24 小时前的下载日志
    """
    try:
        threshold = timezone.now() - timedelta(hours=24)
        deleted_count, _ = ClaudeCodeDownloadLog.objects.filter(
            created_at__lt=threshold
        ).delete()

        if deleted_count > 0:
            logger.info(f'已清理 {deleted_count} 条过期下载日志')

    except Exception as e:
        logger.error(f'清理下载日志失败: {e}')


@shared_task(bind=True, max_retries=3)
def sync_claude_code_releases(self):
    """
    同步 Claude Code 发布版本

    Celery 定时任务：每小时执行一次
    1. 获取最新版本号
    2. 检查是否已同步
    3. 下载并上传各平台二进制到 R2
    4. 清理旧版本
    5. 清理过期下载日志
    """
    logger.info('开始同步 Claude Code 发布版本')

    try:
        # 1. 获取最新版本
        latest_version = get_latest_version()
        if not latest_version:
            logger.warning('无法获取最新版本')
            return {'status': 'error', 'message': '无法获取最新版本'}

        logger.info(f'最新版本: {latest_version}')

        # 2. 检查是否已同步
        if ClaudeCodeVersion.objects.filter(version=latest_version).exists():
            logger.info(f'版本 {latest_version} 已同步，跳过')
            # 仍然执行清理任务
            cleanup_old_download_logs()
            return {'status': 'skipped', 'message': f'版本 {latest_version} 已存在'}

        # 3. 获取 manifest
        manifest = get_manifest(latest_version)
        if not manifest:
            logger.warning(f'无法获取 {latest_version} 的 manifest')
            return {'status': 'error', 'message': '无法获取 manifest'}

        # 4. 创建版本记录
        version_obj = ClaudeCodeVersion.objects.create(
            version=latest_version,
            released_at=timezone.now(),  # 可以从 manifest 中获取更准确的时间
            changelog='',
        )
        logger.info(f'创建版本记录: {latest_version}')

        # 5. 同步各平台二进制
        platforms_data = manifest.get('platforms', {})
        synced_count = 0
        failed_platforms = []

        for platform_arch in SUPPORTED_PLATFORM_ARCHS:
            platform_info = platforms_data.get(platform_arch)
            if not platform_info:
                logger.warning(f'manifest 中未找到 {platform_arch}')
                continue

            sha256 = platform_info.get('sha256')
            file_size = platform_info.get('size')

            if not sha256 or not file_size:
                logger.warning(f'{platform_arch} 缺少 sha256 或 size 信息')
                continue

            # 下载并上传
            storage_key = download_binary_to_r2(
                latest_version,
                platform_arch,
                sha256,
                file_size
            )

            if storage_key:
                # 创建二进制记录
                ClaudeCodeBinary.objects.create(
                    version=version_obj,
                    platform_arch=platform_arch,
                    file_size=file_size,
                    sha256=sha256,
                    storage_key=storage_key,
                )
                synced_count += 1
                logger.info(f'已同步 {platform_arch}')
            else:
                failed_platforms.append(platform_arch)
                logger.error(f'同步 {platform_arch} 失败')

        # 6. 清理旧版本
        cleanup_old_versions()

        # 7. 清理过期下载日志
        cleanup_old_download_logs()

        result = {
            'status': 'success',
            'version': latest_version,
            'synced_platforms': synced_count,
            'failed_platforms': failed_platforms,
        }
        logger.info(f'同步完成: {result}')
        return result

    except Exception as e:
        logger.error(f'同步 Claude Code 发布版本失败: {e}')
        raise self.retry(exc=e, countdown=300)  # 5 分钟后重试


@shared_task
def manual_sync_version(version: str):
    """
    手动同步指定版本

    Args:
        version: 要同步的版本号
    """
    logger.info(f'手动同步版本: {version}')

    # 检查是否已存在
    if ClaudeCodeVersion.objects.filter(version=version).exists():
        return {'status': 'error', 'message': f'版本 {version} 已存在'}

    # 获取 manifest
    manifest = get_manifest(version)
    if not manifest:
        return {'status': 'error', 'message': '无法获取 manifest'}

    # 创建版本记录
    version_obj = ClaudeCodeVersion.objects.create(
        version=version,
        released_at=timezone.now(),
        changelog='',
    )

    # 同步各平台
    platforms_data = manifest.get('platforms', {})
    synced_count = 0

    for platform_arch in SUPPORTED_PLATFORM_ARCHS:
        platform_info = platforms_data.get(platform_arch)
        if not platform_info:
            continue

        sha256 = platform_info.get('sha256')
        file_size = platform_info.get('size')

        if not sha256 or not file_size:
            continue

        storage_key = download_binary_to_r2(
            version,
            platform_arch,
            sha256,
            file_size
        )

        if storage_key:
            ClaudeCodeBinary.objects.create(
                version=version_obj,
                platform_arch=platform_arch,
                file_size=file_size,
                sha256=sha256,
                storage_key=storage_key,
            )
            synced_count += 1

    return {
        'status': 'success',
        'version': version,
        'synced_platforms': synced_count,
    }
