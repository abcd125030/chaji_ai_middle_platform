"""
配置加载器 - 从YAML文件加载用户配额和配置模板
支持文件修改自动刷新
"""

import os
import yaml
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置文件加载器"""
    
    # 默认配置
    DEFAULT_CACHE_TTL = 300  # 5分钟缓存过期
    DEFAULT_AUTO_RELOAD = True  # 默认开启自动重载
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置加载器
        
        Args:
            config_dir: 配置目录路径，默认为 authentication/config
        """
        if config_dir is None:
            config_dir = os.path.join(
                os.path.dirname(__file__),
                'config'
            )
        
        self.config_dir = Path(config_dir)
        self.templates_dir = self.config_dir / 'templates'
        self._config_cache = {}
        self._file_mtimes = {}  # 记录文件修改时间
        self._cache_timestamps = {}  # 记录缓存时间
        self._main_config = None
        
        # 配置参数
        self.cache_ttl = getattr(settings, 'CONFIG_CACHE_TTL', self.DEFAULT_CACHE_TTL)
        self.auto_reload = getattr(settings, 'CONFIG_AUTO_RELOAD', self.DEFAULT_AUTO_RELOAD)
        
        # 加载主配置文件
        self._load_main_config()
    
    def _load_main_config(self) -> None:
        """加载主配置文件"""
        config_file = self.config_dir / 'config.yaml'
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._main_config = yaml.safe_load(f)
                    logger.info(f"加载主配置文件: {config_file}")
            except Exception as e:
                logger.error(f"加载主配置文件失败: {e}")
                self._main_config = {}
        else:
            logger.warning(f"主配置文件不存在: {config_file}")
            self._main_config = {}
    
    def _is_file_modified(self, file_path: Path) -> bool:
        """
        检查文件是否被修改
        
        Args:
            file_path: 文件路径
        
        Returns:
            是否被修改
        """
        if not file_path.exists():
            return False
            
        current_mtime = file_path.stat().st_mtime
        last_mtime = self._file_mtimes.get(str(file_path), 0)
        
        if current_mtime > last_mtime:
            self._file_mtimes[str(file_path)] = current_mtime
            return True
        return False
    
    def _is_cache_expired(self, cache_key: str) -> bool:
        """
        检查缓存是否过期
        
        Args:
            cache_key: 缓存键
        
        Returns:
            是否过期
        """
        if cache_key not in self._cache_timestamps:
            return True
            
        elapsed = time.time() - self._cache_timestamps[cache_key]
        return elapsed > self.cache_ttl
    
    def load_template(self, template_path: str, use_cache: bool = True, strict: bool = False) -> Dict[str, Any]:
        """
        加载单个模板文件
        
        Args:
            template_path: 模板文件相对路径（相对于templates目录）
            use_cache: 是否使用缓存
            strict: 严格模式，文件不存在时抛出异常
        
        Returns:
            模板配置字典
        
        Raises:
            FileNotFoundError: 严格模式下文件不存在时抛出
        """
        # 构建完整路径
        full_path = self.templates_dir / template_path
        
        # 检查缓存和文件修改
        if use_cache and template_path in self._config_cache:
            # 检查是否需要刷新缓存
            should_reload = False
            
            # 1. 检查文件是否被修改（如果开启自动重载）
            if self.auto_reload and self._is_file_modified(full_path):
                logger.info(f"检测到文件修改，重新加载: {template_path}")
                should_reload = True
            
            # 2. 检查缓存是否过期
            elif self._is_cache_expired(template_path):
                logger.debug(f"缓存过期，重新加载: {template_path}")
                should_reload = True
            
            if not should_reload:
                return self._config_cache[template_path]
        
        # 确保文件存在
        if not full_path.exists():
            error_msg = f"模板文件不存在: {full_path}"
            logger.error(error_msg)
            
            if strict:
                raise FileNotFoundError(error_msg)
            
            return {}
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
                # 缓存配置
                if use_cache:
                    self._config_cache[template_path] = config
                    self._cache_timestamps[template_path] = time.time()
                    self._file_mtimes[str(full_path)] = full_path.stat().st_mtime
                
                logger.debug(f"加载模板文件: {template_path}")
                return config
                
        except Exception as e:
            logger.error(f"加载模板文件失败 {template_path}: {e}")
            return {}
    
    def load_quota_template(self, template_name: str) -> Dict[str, Any]:
        """
        加载配额模板
        
        Args:
            template_name: 模板名称（free_user, vip_user, max_user）
        
        Returns:
            配额配置字典
        """
        template_path = f"quotas/{template_name}.yaml"
        config = self.load_template(template_path)
        
        if not config:
            logger.warning(f"配额模板 {template_name} 加载失败，使用默认值")
            return self._get_default_quota()
        
        # 转换为扁平化的点分隔格式
        return self._flatten_quota_config(config)
    
    def _flatten_quota_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        将嵌套的配额配置转换为扁平化的点分隔格式
        
        Args:
            config: 原始配置字典
        
        Returns:
            扁平化的配置字典
        """
        result = {}
        
        # 处理各个配额部分
        sections = ['llm_calls', 'tokens', 'storage', 'rate_limits', 'features']
        
        for section in sections:
            if section in config:
                for key, value in config[section].items():
                    # 处理数学表达式
                    if isinstance(value, str) and '*' in value:
                        value = self._evaluate_expression(value)
                    result[f"{section}.{key}"] = value
        
        return result
    
    def _evaluate_expression(self, expr: str) -> int:
        """
        安全地计算简单的数学表达式
        
        Args:
            expr: 表达式字符串，如 "2000000*60"
        
        Returns:
            计算结果
        """
        try:
            # 只允许数字和基本运算符
            import re
            if re.match(r'^[\d\s\*\+\-\/\(\)]+$', expr):
                return eval(expr)
            else:
                logger.warning(f"不安全的表达式: {expr}")
                return 0
        except Exception as e:
            logger.error(f"计算表达式失败 {expr}: {e}")
            return 0
    
    def _get_default_quota(self) -> Dict[str, Any]:
        """获取默认配额配置"""
        return {
            "llm_calls.gpt35_daily": 5,
            "llm_calls.gpt4_monthly": 0,
            "tokens.max_per_request": 1000,
            "storage.space_mb": 50,
            "features.knowledge_base": 1,
            "features.advanced_tools": 0
        }
    
    def load_user_defaults(self) -> Dict[str, Any]:
        """加载用户默认配置"""
        template_path = "defaults/user_profile.yaml"
        return self.load_template(template_path)
    
    def load_rate_limits(self, user_type: str = "free") -> Dict[str, Any]:
        """
        加载速率限制配置
        
        Args:
            user_type: 用户类型（anonymous, free, vip, max_user）
        
        Returns:
            速率限制配置
        """
        config = self.load_template("limits/rate_limits.yaml")
        
        if not config:
            return self._get_default_rate_limits()
        
        # 获取特定用户类型的限制
        user_limits = config.get('by_user_type', {}).get(user_type, {})
        
        # 合并全局限制
        global_limits = config.get('global', {})
        
        return {
            **global_limits,
            **user_limits
        }
    
    def _get_default_rate_limits(self) -> Dict[str, Any]:
        """获取默认速率限制"""
        return {
            "requests_per_minute": 10,
            "requests_per_hour": 100,
            "burst_size": 2
        }
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """获取功能开关配置"""
        if not self._main_config:
            return {
                "quota_enforcement": True,
                "auto_reset": True,
                "cache_enabled": True,
                "audit_logging": False
            }
        
        return self._main_config.get('features', {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        if not self._main_config:
            return {
                "enabled": True,
                "prefix": "user_service",
                "ttl": 300
            }
        
        return self._main_config.get('cache', {})
    
    def reload_configs(self) -> None:
        """重新加载所有配置"""
        self._config_cache.clear()
        self._load_main_config()
        logger.info("重新加载所有配置文件")
    
    def list_available_templates(self, template_type: str = "quotas") -> List[str]:
        """
        列出可用的模板
        
        Args:
            template_type: 模板类型（quotas, defaults, limits）
        
        Returns:
            模板名称列表
        """
        template_dir = self.templates_dir / template_type
        
        if not template_dir.exists():
            return []
        
        templates = []
        for file_path in template_dir.glob("*.yaml"):
            template_name = file_path.stem
            templates.append(template_name)
        
        return templates


# 全局配置加载器实例
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """获取全局配置加载器实例"""
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader()
    
    return _config_loader


# 便捷函数
def load_quota_template(template_name: str) -> Dict[str, Any]:
    """加载配额模板的便捷函数"""
    loader = get_config_loader()
    return loader.load_quota_template(template_name)


def load_user_defaults() -> Dict[str, Any]:
    """加载用户默认配置的便捷函数"""
    loader = get_config_loader()
    return loader.load_user_defaults()


def get_rate_limits(user_type: str = "free") -> Dict[str, Any]:
    """获取速率限制的便捷函数"""
    loader = get_config_loader()
    return loader.load_rate_limits(user_type)