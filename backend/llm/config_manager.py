import logging
import os
from typing import Dict, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

class ModelConfigManager:
    """
    模型配置管理器
    负责从数据库查找模型配置信息
    """
    
    def __init__(self):
        self._config_cache = {}
        self.cache_timeout = 3600  # 1小时缓存
        self.load_from_redis = os.getenv('LOAD_LLM_FROM_REDIS', 'False').lower() == 'true'
    
    def get_model_config(self, model_name: str) -> Dict:
        """
        根据模型名称获取完整配置
        返回: {model_id, endpoint, api_key, custom_headers, params, vendor_name}
        """
        # 如果未启用缓存，则直接从数据库加载
        if not self.load_from_redis:
            # logger.info(f"缓存未启用，直接从数据库查询模型配置: {model_name}")
            return self._load_from_database(model_name)

        # --- 缓存启用时的逻辑 ---
        cache_key = f"model_config_{model_name}"
        
        # 先检查内存缓存
        if model_name in self._config_cache:
            logger.info(f"从内存缓存获取模型配置: {model_name}")
            return self._config_cache[model_name]
        
        # 再检查Django缓存
        cached_config = cache.get(cache_key)
        if cached_config:
            logger.info(f"从Django缓存获取模型配置: {model_name}")
            self._config_cache[model_name] = cached_config
            return cached_config
        
        # 从数据库查询
        logger.info(f"从数据库查询模型配置: {model_name}")
        config = self._load_from_database(model_name)
        
        # 保存到缓存
        self._config_cache[model_name] = config
        cache.set(cache_key, config, self.cache_timeout)
        
        return config
    
    def _load_from_database(self, model_name: str) -> Dict:
        """从数据库加载模型配置"""
        from django.db.models import Q
        from router.models import LLMModel, VendorAPIKey
        from backend.utils.db_connection import ensure_db_connection_safe
        
        try:
            # 确保数据库连接有效（使用更强力的连接恢复）
            ensure_db_connection_safe()
            # 同时尝试通过 model_id 或 name 字段查找
            llm_model = LLMModel.objects.select_related('endpoint').filter(
                Q(model_id=model_name) | Q(name=model_name)
            ).first()
            
            if not llm_model:
                logger.error(f"Model '{model_name}' not found in database (by model_id or name)")
                raise LLMModel.DoesNotExist(f"Model '{model_name}' not found")
            
            # 查找API key
            api_key = ""
            try:
                # 优先使用新的 vendor 外键关联
                if llm_model.endpoint.vendor:
                    vendor_key = VendorAPIKey.objects.get(
                        vendor=llm_model.endpoint.vendor
                    )
                # 兼容旧的 vendor_name 字段
                elif llm_model.endpoint.vendor_name:
                    vendor_key = VendorAPIKey.objects.get(
                        vendor_name=llm_model.endpoint.vendor_name
                    )
                else:
                    raise VendorAPIKey.DoesNotExist("No vendor specified for endpoint")
                
                api_key = vendor_key.api_key
            except VendorAPIKey.DoesNotExist:
                vendor_info = llm_model.endpoint.vendor.display_name if llm_model.endpoint.vendor else llm_model.endpoint.vendor_name
                logger.warning(f"No API key found for vendor: {vendor_info}")
            
            config = {
                'model_id': llm_model.model_id,
                'endpoint': llm_model.endpoint.endpoint,
                'api_key': api_key,
                'custom_headers': llm_model.custom_headers or {},
                'params': llm_model.params or {},
                'vendor_name': llm_model.endpoint.vendor_name,
                'model_type': llm_model.model_type,
                'api_standard': llm_model.api_standard
            }
            
            # logger.info(f"成功加载模型配置: {model_name}")
            return config
            
        except LLMModel.DoesNotExist:
            logger.error(f"Model '{model_name}' not found in database")
            raise ValueError(f"Model '{model_name}' not found in configuration")
        except Exception as e:
            logger.error(f"Failed to load model config for '{model_name}': {e}")
            raise ValueError(f"Failed to load model config: {e}")
    
    def get_user_model_configs(self, llm_model_dict: Dict) -> Dict[str, Dict]:
        """
        批量获取用户有权限的模型配置
        用于外部API的权限验证
        """
        configs = {}
        for model_name, user_config in llm_model_dict.items():
            try:
                # 合并数据库配置和用户权限配置
                db_config = self.get_model_config(model_name)
                
                # 用户权限配置可能覆盖默认配置
                final_config = {
                    **db_config,
                    'model_endpoint': user_config['model_endpoint'],
                    'model_key': user_config['model_key'],
                    'custom_headers': user_config.get('custom_headers', db_config['custom_headers']),
                    'params': user_config.get('params', db_config['params'])
                }
                
                configs[model_name] = final_config
            except Exception as e:
                logger.error(f"Failed to get config for model '{model_name}': {e}")
                continue
        
        return configs
    
    def clear_cache(self, model_name: Optional[str] = None):
        """清除缓存"""
        if not self.load_from_redis:
            logger.info("缓存未启用，跳过清除操作。")
            return

        if model_name:
            self._config_cache.pop(model_name, None)
            cache.delete(f"model_config_{model_name}")
            logger.info(f"清除模型配置缓存: {model_name}")
        else:
            self._config_cache.clear()
            # 清除所有模型配置缓存
            from django.core.cache.utils import make_template_fragment_key
            cache.clear()
            logger.info("清除所有模型配置缓存")