"""
frago Cloud Market 限流类

包含 Claude Code 镜像下载的 IP 限流实现
"""

from datetime import timedelta
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

from .models import ClaudeCodeDownloadLog


class ClaudeCodeDownloadThrottle(BaseThrottle):
    """
    Claude Code 下载限流器

    规则：每 IP 每小时最多 3 次下载
    基于 ClaudeCodeDownloadLog 统计
    """

    # 限流配置
    RATE_LIMIT = 3  # 每小时最大下载次数
    RATE_PERIOD = timedelta(hours=1)  # 限流周期

    def allow_request(self, request, view):
        """
        检查请求是否允许

        Returns:
            bool: True 允许请求，False 拒绝请求
        """
        self.ip_address = self.get_ident(request)
        self.now = timezone.now()
        self.period_start = self.now - self.RATE_PERIOD

        # 统计该 IP 在限流周期内的下载次数
        download_count = ClaudeCodeDownloadLog.objects.filter(
            ip_address=self.ip_address,
            created_at__gte=self.period_start
        ).count()

        # 计算剩余次数
        self.remaining = max(0, self.RATE_LIMIT - download_count)

        return download_count < self.RATE_LIMIT

    def wait(self):
        """
        返回需要等待的秒数

        Returns:
            float: 等待秒数，如果无法确定则返回 None
        """
        # 获取最早的下载记录
        earliest_download = ClaudeCodeDownloadLog.objects.filter(
            ip_address=self.ip_address,
            created_at__gte=self.period_start
        ).order_by('created_at').first()

        if earliest_download:
            # 计算该记录过期时间
            expires_at = earliest_download.created_at + self.RATE_PERIOD
            wait_seconds = (expires_at - self.now).total_seconds()
            return max(0, wait_seconds)

        return None

    def get_ident(self, request):
        """
        获取请求的唯一标识（IP 地址）

        支持通过 X-Forwarded-For 获取真实 IP
        """
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            # 取第一个 IP（客户端真实 IP）
            return xff.split(',')[0].strip()

        return request.META.get('REMOTE_ADDR', '0.0.0.0')


def record_download(ip_address, binary):
    """
    记录下载日志

    Args:
        ip_address: 请求 IP
        binary: ClaudeCodeBinary 实例

    Returns:
        ClaudeCodeDownloadLog: 创建的日志记录
    """
    return ClaudeCodeDownloadLog.objects.create(
        ip_address=ip_address,
        binary=binary
    )


def get_rate_limit_info(ip_address):
    """
    获取 IP 的限流信息

    Args:
        ip_address: 请求 IP

    Returns:
        dict: 包含 remaining（剩余次数）、reset_at（重置时间）
    """
    now = timezone.now()
    period_start = now - ClaudeCodeDownloadThrottle.RATE_PERIOD

    # 统计下载次数
    download_count = ClaudeCodeDownloadLog.objects.filter(
        ip_address=ip_address,
        created_at__gte=period_start
    ).count()

    remaining = max(0, ClaudeCodeDownloadThrottle.RATE_LIMIT - download_count)

    # 计算重置时间
    earliest = ClaudeCodeDownloadLog.objects.filter(
        ip_address=ip_address,
        created_at__gte=period_start
    ).order_by('created_at').first()

    if earliest and download_count >= ClaudeCodeDownloadThrottle.RATE_LIMIT:
        reset_at = earliest.created_at + ClaudeCodeDownloadThrottle.RATE_PERIOD
    else:
        reset_at = None

    return {
        'remaining': remaining,
        'limit': ClaudeCodeDownloadThrottle.RATE_LIMIT,
        'reset_at': reset_at.isoformat() if reset_at else None,
    }
