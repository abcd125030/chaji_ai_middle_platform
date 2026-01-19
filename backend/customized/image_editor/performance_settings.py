"""
性能优化配置文件
集中管理所有性能相关的配置参数
"""
import os

# ==================== 缓存配置 ====================
CACHE_CONFIG = {
    # Redis缓存配置
    'REDIS': {
        'HOST': os.getenv('REDIS_HOST', 'localhost'),
        'PORT': int(os.getenv('REDIS_PORT', 6379)),
        'DB': int(os.getenv('REDIS_CACHE_DB', 1)),  # 使用不同的DB避免与Celery冲突
        'PASSWORD': os.getenv('REDIS_PASSWORD', ''),
        'MAX_CONNECTIONS': 500,  # 连接池最大连接数（支持10000请求/分钟）
        'CONNECTION_POOL_KWARGS': {
            'max_connections': 500,
            'retry_on_timeout': True,
            'socket_keepalive': True,
            'socket_keepalive_options': {
                1: 1,  # TCP_KEEPIDLE
                2: 1,  # TCP_KEEPINTVL
                3: 5,  # TCP_KEEPCNT
            }
        }
    },
    
    # 缓存TTL配置（秒）
    'TTL': {
        'TASK_PROCESSING': 300,      # 处理中任务缓存5分钟
        'TASK_SUCCESS': 3600,         # 成功任务缓存1小时
        'TASK_FAILED': 1800,          # 失败任务缓存30分钟
        'USER_RATE_LIMIT': 60,        # 用户限流缓存1分钟
        'HOT_DATA': 60,               # 热点数据缓存1分钟
        'API_RESPONSE': 60,           # API响应缓存1分钟
    },
    
    # 缓存策略
    'STRATEGY': {
        'ENABLE_COMPRESSION': True,    # 启用压缩
        'COMPRESSION_LEVEL': 6,        # 压缩级别(1-9)
        'ENABLE_PIPELINE': True,       # 启用管道批量操作
        'PIPELINE_SIZE': 100,          # 管道批量大小
    }
}

# ==================== 数据库优化配置 ====================
# 注意：数据库连接池配置已移至 Django settings.py（使用 PgBouncer）
# 这里只保留查询优化相关配置
DATABASE_OPTIMIZATION = {
    # 查询优化
    'QUERY': {
        'ENABLE_QUERY_CACHE': True,   # 启用查询缓存
        'QUERY_CACHE_SIZE': 1000,     # 查询缓存大小
        'BATCH_SIZE': 100,            # 批量操作大小
        'PREFETCH_RELATED': True,     # 启用预取关联
        'SELECT_RELATED': True,       # 启用选择关联
    },
    
    # 索引策略
    'INDEX': {
        'AUTO_CREATE_INDEX': True,    # 自动创建索引
        'INDEX_HINT': True,           # 使用索引提示
    }
}

# ==================== Celery队列优化配置 ====================
# 注意：Celery 主要配置已在 Django settings.py 中定义
# 这里只保留任务级别的配置参考值
CELERY_OPTIMIZATION = {
    # 队列优先级
    'PRIORITY': {
        'HIGH': 10,                   # 高优先级
        'NORMAL': 5,                  # 普通优先级
        'LOW': 1,                     # 低优先级
    },
    
    # 重试策略（供任务使用）
    'RETRY': {
        'MAX_RETRIES': 3,             # 最大重试次数
        'RETRY_BACKOFF': True,        # 启用退避
        'RETRY_BACKOFF_MAX': 600,    # 最大退避时间（秒）
        'RETRY_JITTER': True,         # 添加抖动
    }
}

# ==================== API限流配置 ====================
RATE_LIMIT_CONFIG = {
    # 用户级别限流
    'USER': {
        'DEFAULT': {
            'LIMIT': 167,             # 每秒请求数（原10000/分钟 ≈ 167 QPS）
            'WINDOW': 1,              # 时间窗口（秒）
        },
        'VIP': {
            'LIMIT': 10,              # VIP用户限制（原500/分钟 ≈ 8-10 QPS）
            'WINDOW': 1,
        },
        'BATCH': {
            'LIMIT': 1,               # 批量接口限制（原10/分钟 ≈ 1 QPS）
            'WINDOW': 1,
        }
    },
    
    # IP级别限流
    'IP': {
        'LIMIT': 20,                  # 每IP每秒请求数（原1000/分钟 ≈ 17-20 QPS）
        'WINDOW': 1,
        'BLACKLIST_THRESHOLD': 200,   # 黑名单阈值（原10000/分钟 ≈ 167-200 QPS）
    },
    
    # 全局限流
    'GLOBAL': {
        'LIMIT': 167,                 # 全局每秒请求数（原10000/分钟 ≈ 167 QPS）
        'WINDOW': 1,
        'CIRCUIT_BREAKER': {
            'ENABLED': True,          # 启用熔断器
            'FAILURE_THRESHOLD': 0.5, # 失败率阈值
            'RECOVERY_TIMEOUT': 30,   # 恢复时间（秒）
        }
    }
}

# ==================== 批量回调配置 ====================
BATCH_CALLBACK_CONFIG = {
    'ENABLED': False,                 # 是否启用批量回调（设为False后任务完成立即回调）
    'BATCH_SIZE': 5,                 # 增加批次大小（因为任务完成慢）
    'MAX_DELAY': 3.0,                # 增加延迟时间（给更多任务聚集的机会）
    'MIN_INTERVAL': 1.0,              # 增加批次间隔（降低带宽压力）
    'MAX_BANDWIDTH_MBPS': 500,         # 限制带宽使用（Mbps）
    
    # 高级配置
    'ADAPTIVE_BATCH': True,           # 自适应批次大小
    'PEAK_HOURS': [                   # 高峰时段（增加延迟）
        (9, 11),   # 上午9-11点
        (14, 16),  # 下午2-4点
        (20, 22),  # 晚上8-10点
    ],
    'PEAK_DELAY_MULTIPLIER': 1.5,     # 高峰时段延迟倍数
    'PRIORITY_THRESHOLD': 100,        # 优先级阈值（ms）
    
    # 失败重试配置
    'RETRY': {
        'MAX_RETRIES': 3,             # 最大重试次数
        'BACKOFF_BASE': 2,            # 退避基数
        'MAX_BACKOFF': 60,            # 最大退避时间（秒）
    },
    
    # 监控配置
    'MONITORING': {
        'LOG_STATS_INTERVAL': 60,     # 统计日志间隔（秒）
        'ALERT_QUEUE_SIZE': 100,      # 队列告警阈值
        'ALERT_DELAY': 10,            # 延迟告警阈值（秒）
    }
}

# ==================== 外部API配置 ====================
EXTERNAL_API_CONFIG = {
    # 豆包API配置
    'DOUBAO': {
        'TIMEOUT': 30,                # 请求超时（秒）
        'MAX_RETRIES': 2,             # 最大重试次数
        'POOL_SIZE': 10,              # 连接池大小
        'RATE_LIMIT': 100,            # 每分钟请求限制
    },
    
    # 火山引擎API配置
    'VOLCENGINE': {
        'TIMEOUT': 20,
        'MAX_RETRIES': 2,
        'POOL_SIZE': 10,
        'RATE_LIMIT': 200,
    },
    
    # 通用配置
    'DEFAULT': {
        'CONNECTION_TIMEOUT': 5,      # 连接超时（秒）
        'READ_TIMEOUT': 30,           # 读取超时（秒）
        'KEEP_ALIVE': True,           # 保持连接
        'VERIFY_SSL': True,           # SSL验证
    }
}

# ==================== 监控配置 ====================
MONITORING_CONFIG = {
    # 指标收集
    'METRICS': {
        'ENABLED': True,              # 启用指标收集
        'INTERVAL': 60,               # 收集间隔（秒）
        'RETENTION': 86400,           # 保留时间（秒）
        'EXPORT_FORMAT': 'prometheus', # 导出格式
    },
    
    # 日志配置
    'LOGGING': {
        'LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
        'MAX_FILE_SIZE': 100 * 1024 * 1024,  # 100MB
        'BACKUP_COUNT': 10,           # 保留文件数
        'FORMAT': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
    },
    
    # 健康检查
    'HEALTH_CHECK': {
        'ENABLED': True,
        'INTERVAL': 30,               # 检查间隔（秒）
        'TIMEOUT': 5,                 # 检查超时（秒）
        'ENDPOINTS': [
            '/api/health',
            '/api/status',
        ]
    },
    
    # 告警配置
    'ALERTING': {
        'ENABLED': True,
        'THRESHOLDS': {
            'ERROR_RATE': 0.1,        # 错误率阈值
            'LATENCY_P95': 1.0,       # P95延迟阈值（秒）
            'QUEUE_SIZE': 1000,       # 队列大小阈值
            'MEMORY_USAGE': 0.8,      # 内存使用率阈值
        }
    }
}

# ==================== 性能目标 ====================
PERFORMANCE_TARGETS = {
    'API_LATENCY': {
        'P50': 0.1,                   # 50分位延迟目标（秒）
        'P95': 0.5,                   # 95分位延迟目标（秒）
        'P99': 1.0,                   # 99分位延迟目标（秒）
    },
    'THROUGHPUT': {
        'TARGET': 10000,              # 目标吞吐量（请求/分钟）
        'PEAK': 15000,                # 峰值吞吐量（请求/分钟）
    },
    'ERROR_RATE': {
        'TARGET': 0.001,              # 目标错误率（0.1%）
        'MAX': 0.01,                  # 最大错误率（1%）
    },
    'AVAILABILITY': {
        'TARGET': 0.999,              # 目标可用性（99.9%）
    }
}

# ==================== 优化开关 ====================
OPTIMIZATION_FLAGS = {
    'ENABLE_CACHE': True,             # 启用缓存
    'ENABLE_COMPRESSION': True,       # 启用压缩
    'ENABLE_PIPELINE': True,          # 启用管道
    'ENABLE_BATCH_OPERATIONS': True,  # 启用批量操作
    'ENABLE_ASYNC_PROCESSING': True,  # 启用异步处理
    'ENABLE_CONNECTION_POOLING': True, # 启用连接池
    'ENABLE_QUERY_OPTIMIZATION': True, # 启用查询优化
    'ENABLE_RATE_LIMITING': True,     # 启用限流
    'ENABLE_CIRCUIT_BREAKER': True,   # 启用熔断器
    'ENABLE_MONITORING': True,        # 启用监控
    'ENABLE_AUTO_SCALING': False,     # 启用自动扩缩容（需要K8s）
}

# ==================== 导出配置函数 ====================
def get_performance_config():
    """获取完整的性能配置"""
    return {
        'cache': CACHE_CONFIG,
        'database': DATABASE_OPTIMIZATION,
        'celery': CELERY_OPTIMIZATION,
        'rate_limit': RATE_LIMIT_CONFIG,
        'external_api': EXTERNAL_API_CONFIG,
        'monitoring': MONITORING_CONFIG,
        'targets': PERFORMANCE_TARGETS,
        'flags': OPTIMIZATION_FLAGS,
    }

# 注意：apply_django_settings 函数已被移除
# Django 配置现在直接在 settings.py 中管理
# 数据库配置现在通过 PgBouncer 统一管理，无需额外配置