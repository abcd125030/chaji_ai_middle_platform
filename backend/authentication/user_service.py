"""
用户服务层 - 提供统一的用户信息管理和访问接口
支持嵌套结构的配额和使用统计管理
"""

from typing import Optional, Dict, List, Any, Union
from django.db import transaction
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging
import json

from .models_extension import UserProfile
from .config_loader import get_config_loader, load_quota_template

logger = logging.getLogger(__name__)
User = get_user_model()


class UserService:
    """统一的用户服务层"""
    
    # 从配置文件加载缓存设置
    _config_loader = get_config_loader()
    _cache_config = _config_loader.get_cache_config()
    
    # 缓存键前缀
    CACHE_PREFIX = _cache_config.get("prefix", "user_service")
    CACHE_TTL = _cache_config.get("ttl", 300)  # 默认5分钟缓存
    
    # ==================== 基础方法 ====================
    
    @classmethod
    def get_or_create_profile(cls, user_id: int) -> UserProfile:
        """获取或创建用户配置文件"""
        try:
            user = User.objects.get(id=user_id)
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            if created:
                logger.info(f"为用户 {user.username} (ID: {user_id}) 创建了新的配置文件")
            
            return profile
        except User.DoesNotExist:
            logger.error(f"用户 ID {user_id} 不存在")
            raise ValueError(f"用户 ID {user_id} 不存在")
    
    @classmethod
    def get_user_context(cls, user_id: int) -> Dict[str, Any]:
        """
        获取用户完整的上下文信息
        
        Args:
            user_id: 用户ID
        
        Returns:
            包含用户完整信息的字典
        """
        # 尝试从缓存获取
        cache_key = f"{cls.CACHE_PREFIX}:context:{user_id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        try:
            user = User.objects.select_related('profile').get(id=user_id)
            profile = getattr(user, 'profile', None)
            
            # 如果没有profile，创建一个
            if not profile:
                profile = cls.get_or_create_profile(user_id)
            
            context = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'display_name': user.get_full_name() or user.username,
                'role': user.role,
                'status': user.status,
                'tags': profile.tags,
                'preferences': profile.preferences or {},
                'capabilities': profile.capabilities or {},
                'context_data': profile.context_data or {},
                'quotas': profile.quotas or {},
            }
            
            # 缓存结果
            cache.set(cache_key, json.dumps(context), cls.CACHE_TTL)
            
            return context
            
        except User.DoesNotExist:
            logger.error(f"用户 ID {user_id} 不存在")
            return {}
    
    @classmethod
    def get_user_collection_name(cls, user_id: int, base_name: str) -> str:
        """
        生成用户专属的collection名称
        
        Args:
            user_id: 用户ID
            base_name: 基础collection名称
        
        Returns:
            格式化的collection名称
        """
        profile = cls.get_or_create_profile(user_id)
        return profile.get_collection_name(base_name)
    
    @classmethod
    def get_user_capabilities(cls, user_id: int) -> List[str]:
        """
        获取用户的能力权限列表
        
        Args:
            user_id: 用户ID
        
        Returns:
            用户可用的能力列表
        """
        profile = cls.get_or_create_profile(user_id)
        capabilities = profile.capabilities or {}
        
        # 返回允许的能力列表
        allowed = capabilities.get('allowed', [])
        
        # 根据用户角色添加默认能力
        user = User.objects.get(id=user_id)
        if user.role == User.Role.SUPER_ADMIN:
            # 超级管理员拥有所有能力
            allowed.extend(['admin_tools', 'system_config', 'user_management'])
        elif user.role == User.Role.ADMIN:
            # 管理员拥有部分管理能力
            allowed.extend(['user_view', 'content_management'])
        
        # 去重并返回
        return list(set(allowed))
    
    # ==================== 嵌套结构辅助方法 ====================
    
    @classmethod
    def _get_nested_value(cls, data: Optional[dict], path: Union[str, List[str]], default=None):
        """
        获取嵌套字典值
        
        Args:
            data: 数据字典
            path: 路径，如 "llm_calls.gpt4_monthly" 或 ["llm_calls", "gpt4_monthly"]
            default: 默认值
        
        Returns:
            找到的值或默认值
        """
        if not data:
            return default
            
        if isinstance(path, str):
            keys = path.split('.')
        else:
            keys = path
            
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value
    
    @classmethod
    def _set_nested_value(cls, data: dict, path: Union[str, List[str]], value: Any) -> None:
        """
        设置嵌套字典值，自动创建中间层级
        
        Args:
            data: 数据字典
            path: 路径，如 "llm_calls.gpt4_monthly"
            value: 要设置的值
        """
        if isinstance(path, str):
            keys = path.split('.')
        else:
            keys = path
            
        # 遍历到倒数第二层，创建必要的中间字典
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                current[key] = {}  # 覆盖非字典值
            current = current[key]
            
        # 设置最终值
        current[keys[-1]] = value
    
    # ==================== 统一的配额操作接口 ====================
    
    @classmethod
    def check_quota(cls, user_id: int, resource_path: str, amount: int = 1) -> bool:
        """
        统一的配额检查接口
        
        Args:
            user_id: 用户ID
            resource_path: 资源路径，如 "llm_calls.gpt4_monthly"
            amount: 需要的数量
        
        Returns:
            是否有足够的配额
        
        Examples:
            check_quota(user_id, "llm_calls.gpt4_monthly", 1)
            check_quota(user_id, "storage.space_mb", 10)
        """
        profile = cls.get_or_create_profile(user_id)
        
        # 获取配额限制
        quota_limit = cls._get_nested_value(profile.quotas, resource_path, 0)
        
        if quota_limit == 0:
            return False  # 0 = 禁用
        if quota_limit == -1:
            return True   # -1 = 无限制
            
        # 获取当前使用量
        usage = cls._get_nested_value(profile.usage_stats, resource_path, 0)
        
        # 检查是否超过配额
        return (usage + amount) <= quota_limit
    
    @classmethod
    @transaction.atomic
    def consume_quota(cls, user_id: int, resource_path: str, amount: int = 1) -> bool:
        """
        统一的配额消耗接口
        
        Args:
            user_id: 用户ID
            resource_path: 资源路径
            amount: 消耗的数量
        
        Returns:
            是否成功消耗配额
        """
        if not cls.check_quota(user_id, resource_path, amount):
            logger.warning(f"用户 {user_id} 的 {resource_path} 配额不足")
            return False
            
        profile = cls.get_or_create_profile(user_id)
        
        # 确保 usage_stats 存在
        if not profile.usage_stats:
            profile.usage_stats = {}
        
        # 获取当前值并更新
        current = cls._get_nested_value(profile.usage_stats, resource_path, 0)
        cls._set_nested_value(profile.usage_stats, resource_path, current + amount)
        
        # 更新时间戳
        timestamp_key = f"timestamps.last_{resource_path.replace('.', '_')}"
        cls._set_nested_value(
            profile.usage_stats,
            timestamp_key,
            timezone.now().isoformat()
        )
        
        profile.save(update_fields=['usage_stats', 'updated_at'])
        cls.invalidate_user_cache(user_id)
        
        logger.info(f"用户 {user_id} 消耗 {resource_path}: {amount}")
        return True
    
    # ==================== 批量操作方法 ====================
    
    @classmethod
    @transaction.atomic
    def batch_update_quotas(cls, user_id: int, quota_updates: Dict[str, Any]) -> None:
        """
        批量更新配额
        
        Args:
            user_id: 用户ID
            quota_updates: 配额更新字典，键为路径，值为新配额
        
        Example:
            batch_update_quotas(user_id, {
                "llm_calls.gpt4_monthly": 2000,
                "storage.space_mb": 1000,
                "features.advanced_tools": 1
            })
        """
        profile = cls.get_or_create_profile(user_id)
        
        if not profile.quotas:
            profile.quotas = {}
            
        for path, value in quota_updates.items():
            cls._set_nested_value(profile.quotas, path, value)
            
        profile.save(update_fields=['quotas', 'updated_at'])
        cls.invalidate_user_cache(user_id)
        
        logger.info(f"批量更新用户 {user_id} 的配额: {list(quota_updates.keys())}")
    
    @classmethod
    @transaction.atomic
    def batch_consume_quotas(cls, user_id: int, consumptions: Dict[str, int]) -> Dict[str, bool]:
        """
        批量消耗配额
        
        Args:
            user_id: 用户ID
            consumptions: 消耗字典，键为资源路径，值为消耗量
        
        Returns:
            每个资源的消耗结果
        """
        results = {}
        profile = cls.get_or_create_profile(user_id)
        
        if not profile.usage_stats:
            profile.usage_stats = {}
        
        for resource_path, amount in consumptions.items():
            if cls.check_quota(user_id, resource_path, amount):
                current = cls._get_nested_value(profile.usage_stats, resource_path, 0)
                cls._set_nested_value(profile.usage_stats, resource_path, current + amount)
                results[resource_path] = True
            else:
                results[resource_path] = False
                logger.warning(f"用户 {user_id} 的 {resource_path} 配额不足")
        
        if any(results.values()):  # 如果有任何成功的消耗，保存
            profile.save(update_fields=['usage_stats', 'updated_at'])
            cls.invalidate_user_cache(user_id)
        
        return results
    
    # ==================== 配额模板系统 ====================
    
    @classmethod
    def apply_quota_template(cls, user_id: int, template_name: str) -> None:
        """
        应用配额模板
        
        Args:
            user_id: 用户ID
            template_name: 模板名称 ("free_user", "vip_user", "max_user", "enterprise_user")
        """
        from .models_extension import UserProfile
        
        # 从配置文件加载模板
        template = load_quota_template(template_name)
        
        if not template:
            raise ValueError(f"未知的配额模板: {template_name}")
        
        # 更新配额
        cls.batch_update_quotas(user_id, template)
        
        # 同时更新 subscription_type 字段
        profile = cls.get_or_create_profile(user_id)
        subscription_type_map = {
            'free_user': UserProfile.SubscriptionType.FREE,
            'vip_user': UserProfile.SubscriptionType.VIP,
            'enterprise_user': UserProfile.SubscriptionType.ENTERPRISE,
            'max_user': UserProfile.SubscriptionType.MAX,
        }
        
        if template_name in subscription_type_map:
            profile.subscription_type = subscription_type_map[template_name]
            profile.save(update_fields=['subscription_type', 'updated_at'])
            
        logger.info(f"为用户 {user_id} 应用配额模板: {template_name}")
    
    # ==================== 智能重置方法 ====================
    
    @classmethod
    @transaction.atomic
    def reset_periodic_usage(cls, user_id: int, period: str = "daily") -> None:
        """
        重置周期性使用统计
        
        Args:
            user_id: 用户ID
            period: 周期类型 ("daily", "monthly", "per_minute", "per_hour")
        """
        profile = cls.get_or_create_profile(user_id)
        
        if not profile.usage_stats:
            return
            
        # 递归遍历并重置匹配的键
        def reset_matching_keys(data: dict, suffix: str):
            for key, value in list(data.items()):
                if isinstance(value, dict):
                    reset_matching_keys(value, suffix)
                elif isinstance(key, str) and key.endswith(suffix):
                    data[key] = 0
                    
        # 根据周期类型确定后缀
        suffix_map = {
            "daily": "_daily",
            "monthly": "_monthly",
            "per_minute": "_per_minute",
            "per_hour": "_per_hour"
        }
        
        suffix = suffix_map.get(period)
        if not suffix:
            raise ValueError(f"未知的周期类型: {period}")
            
        reset_matching_keys(profile.usage_stats, suffix)
        
        # 更新重置时间戳
        if "timestamps" not in profile.usage_stats:
            profile.usage_stats["timestamps"] = {}
            
        profile.usage_stats["timestamps"][f"last_reset_{period}"] = timezone.now().isoformat()
        
        profile.save(update_fields=['usage_stats', 'updated_at'])
        cls.invalidate_user_cache(user_id)
        
        logger.info(f"重置用户 {user_id} 的 {period} 使用统计")
    
    # ==================== 配额查询和报告 ====================
    
    @classmethod
    def get_quota_usage_report(cls, user_id: int) -> Dict[str, Any]:
        """
        获取配额使用报告
        
        Args:
            user_id: 用户ID
        
        Returns:
            配额使用报告，包含每个资源的使用情况
            
        Example返回值:
            {
                "llm_calls": {
                    "gpt4_monthly": {
                        "used": 150,
                        "limit": 1000,
                        "percentage": 15.0,
                        "remaining": 850
                    }
                }
            }
        """
        profile = cls.get_or_create_profile(user_id)
        
        def build_report(quota_dict: dict, usage_dict: dict) -> dict:
            """递归构建报告"""
            result = {}
            
            for key, value in quota_dict.items():
                if isinstance(value, dict):
                    # 递归处理嵌套字典
                    usage_sub = usage_dict.get(key, {}) if usage_dict else {}
                    result[key] = build_report(value, usage_sub)
                else:
                    # 计算使用情况
                    used = usage_dict.get(key, 0) if usage_dict else 0
                    
                    if value == -1:  # 无限制
                        result[key] = {
                            "used": used,
                            "limit": "unlimited",
                            "percentage": 0,
                            "remaining": "unlimited"
                        }
                    elif value == 0:  # 禁用
                        result[key] = {
                            "used": used,
                            "limit": 0,
                            "percentage": 0,
                            "remaining": 0,
                            "disabled": True
                        }
                    else:  # 正常配额
                        percentage = (used / value * 100) if value > 0 else 0
                        result[key] = {
                            "used": used,
                            "limit": value,
                            "percentage": round(percentage, 2),
                            "remaining": max(0, value - used)
                        }
                        
            return result
        
        # 构建报告
        if profile.quotas:
            report = build_report(
                profile.quotas,
                profile.usage_stats or {}
            )
        else:
            report = {}
            
        # 添加时间戳信息
        if profile.usage_stats and "timestamps" in profile.usage_stats:
            report["timestamps"] = profile.usage_stats["timestamps"]
            
        return report
    
    @classmethod
    def check_feature_enabled(cls, user_id: int, feature_name: str) -> bool:
        """
        检查功能是否启用
        
        Args:
            user_id: 用户ID
            feature_name: 功能名称（不需要完整路径）
        
        Returns:
            功能是否启用
        """
        profile = cls.get_or_create_profile(user_id)
        
        # 尝试从 features 分类中查找
        feature_value = cls._get_nested_value(
            profile.quotas,
            f"features.{feature_name}",
            0
        )
        
        return feature_value != 0  # 0表示禁用，1或-1表示启用
    
    # ==================== 用户信息管理 ====================
    
    @classmethod
    def update_user_tags(cls, user_id: int, tags: List[str], append: bool = False) -> None:
        """
        更新用户标签
        
        Args:
            user_id: 用户ID
            tags: 新的标签列表
            append: 是否追加到现有标签
        """
        profile = cls.get_or_create_profile(user_id)
        
        if append:
            existing_tags = profile.tags or []
            profile.tags = list(set(existing_tags + tags))
        else:
            profile.tags = tags
        
        profile.save(update_fields=['tags', 'updated_at'])
        cls.invalidate_user_cache(user_id)
        
        logger.info(f"更新用户 {user_id} 的标签: {profile.tags}")
    
    @classmethod
    def update_user_preferences(cls, user_id: int, preferences: Dict[str, Any], merge: bool = True) -> None:
        """
        更新用户偏好设置
        
        Args:
            user_id: 用户ID
            preferences: 新的偏好设置
            merge: 是否与现有设置合并
        """
        profile = cls.get_or_create_profile(user_id)
        
        if merge and profile.preferences:
            # 深度合并
            def deep_merge(base: dict, update: dict):
                for key, value in update.items():
                    if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                        deep_merge(base[key], value)
                    else:
                        base[key] = value
            
            deep_merge(profile.preferences, preferences)
        else:
            profile.preferences = preferences
        
        profile.save(update_fields=['preferences', 'updated_at'])
        cls.invalidate_user_cache(user_id)
    
    # ==================== 缓存管理 ====================
    
    @classmethod
    def invalidate_user_cache(cls, user_id: int) -> None:
        """清除用户相关的所有缓存"""
        cache_key = f"{cls.CACHE_PREFIX}:context:{user_id}"
        cache.delete(cache_key)
        logger.debug(f"清除了用户 {user_id} 的缓存")
    
    # ==================== 向后兼容方法（已废弃，但保留） ====================
    
    @classmethod
    def check_user_quota(cls, user_id: int, category: str, resource: str, amount: int = 1) -> bool:
        """
        [已废弃] 请使用 check_quota
        检查用户配额是否足够
        """
        resource_path = f"{category}.{resource}"
        return cls.check_quota(user_id, resource_path, amount)
    
    @classmethod
    @transaction.atomic
    def consume_user_quota(cls, user_id: int, category: str, resource: str, amount: int = 1) -> bool:
        """
        [已废弃] 请使用 consume_quota
        消耗用户配额
        """
        resource_path = f"{category}.{resource}"
        return cls.consume_quota(user_id, resource_path, amount)