"""
MinerU 服务模块
"""

from .optimized_service import OptimizedMinerUService
from .storage_adapter import MinerUStorageAdapter

# 为了向后兼容，创建别名
MinerUService = OptimizedMinerUService

__all__ = [
    'OptimizedMinerUService',
    'MinerUStorageAdapter',
    'MinerUService',  # 向后兼容别名
]