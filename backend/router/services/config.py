"""
模型配置服务
提供获取和管理模型配置的服务层方法
"""
import logging
from typing import Dict, List, Any, Optional
from django.db.models import Q, Count
from django.core.cache import cache

from ..models import LLMModel, VendorEndpoint, VendorAPIKey
from ..vendor_models import Vendor

logger = logging.getLogger('django')


class ModelConfigService:
    """模型配置服务，提供模型配置的查询和管理功能"""
    
    def __init__(self):
        self.cache_timeout = 300  # 缓存5分钟
    
    def get_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个模型的完整配置
        
        Args:
            model_id: 模型标识符
            
        Returns:
            模型配置字典，包含所有配置信息
        """
        cache_key = f'model_config_{model_id}'
        cached_config = cache.get(cache_key)
        
        if cached_config:
            return cached_config
        
        try:
            model = LLMModel.objects.select_related(
                'endpoint', 
                'endpoint__vendor'
            ).get(model_id=model_id)
            
            config = {
                'model_id': model.model_id,
                'name': model.name,
                'model_type': model.model_type,
                'description': model.description,
                'api_standard': model.api_standard,
                'endpoint': {
                    'url': model.endpoint.endpoint if model.endpoint else None,
                    'vendor': model.endpoint.vendor.vendor_id if model.endpoint and model.endpoint.vendor else None,
                    'service_type': model.endpoint.service_type if model.endpoint else None,
                },
                'params': model.params or {},
                'custom_headers': model.custom_headers or {},
                'adapter_config': model.adapter_config or {},
                'statistics': {
                    'call_count': model.call_count,
                    'success_count': model.success_count,
                    'success_rate': round(model.success_count / model.call_count * 100, 2) if model.call_count > 0 else 0,
                }
            }
            
            cache.set(cache_key, config, self.cache_timeout)
            return config
            
        except LLMModel.DoesNotExist:
            logger.warning(f"Model {model_id} not found")
            return None
    
    def list_models_by_type(self, model_type: str = None) -> Dict[str, List[Dict]]:
        """
        按类型列出所有模型配置
        
        Args:
            model_type: 可选，指定模型类型过滤
            
        Returns:
            按类型分组的模型配置字典
        """
        cache_key = f'models_by_type_{model_type or "all"}'
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        queryset = LLMModel.objects.select_related('endpoint', 'endpoint__vendor')
        
        if model_type:
            queryset = queryset.filter(model_type=model_type)
        
        models_by_type = {}
        
        for model in queryset:
            type_key = model.model_type
            if type_key not in models_by_type:
                models_by_type[type_key] = []
            
            models_by_type[type_key].append({
                'model_id': model.model_id,
                'name': model.name,
                'description': model.description,
                'vendor': model.endpoint.vendor.display_name if model.endpoint and model.endpoint.vendor else 'Unknown',
                'api_standard': model.api_standard,
            })
        
        cache.set(cache_key, models_by_type, self.cache_timeout)
        return models_by_type
    
    def get_available_models(self, capabilities: List[str] = None) -> List[Dict[str, Any]]:
        """
        获取所有可用的模型（按能力过滤）
        
        Args:
            capabilities: 能力列表，如 ['text', 'embedding']
            
        Returns:
            可用模型列表
        """
        queryset = LLMModel.objects.select_related('endpoint', 'endpoint__vendor')
        
        if capabilities:
            queryset = queryset.filter(model_type__in=capabilities)
        
        # 只返回有有效端点的模型
        queryset = queryset.filter(endpoint__isnull=False)
        
        models = []
        for model in queryset:
            # 检查是否有API密钥
            has_api_key = False
            if model.endpoint and model.endpoint.vendor:
                has_api_key = VendorAPIKey.objects.filter(
                    vendor=model.endpoint.vendor
                ).exists()
            
            models.append({
                'model_id': model.model_id,
                'name': model.name,
                'type': model.model_type,
                'vendor': model.endpoint.vendor.display_name if model.endpoint.vendor else 'Unknown',
                'available': has_api_key,
                'api_standard': model.api_standard,
            })
        
        return models
    
    def get_vendor_models(self, vendor_id: str) -> List[Dict[str, Any]]:
        """
        获取特定供应商的所有模型配置
        
        Args:
            vendor_id: 供应商标识符
            
        Returns:
            该供应商的模型列表
        """
        cache_key = f'vendor_models_{vendor_id}'
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            vendor = Vendor.objects.get(vendor_id=vendor_id)
            
            models = LLMModel.objects.filter(
                endpoint__vendor=vendor
            ).select_related('endpoint')
            
            result = []
            for model in models:
                result.append({
                    'model_id': model.model_id,
                    'name': model.name,
                    'type': model.model_type,
                    'description': model.description,
                    'endpoint': model.endpoint.endpoint,
                    'api_standard': model.api_standard,
                    'params': model.params,
                })
            
            cache.set(cache_key, result, self.cache_timeout)
            return result
            
        except Vendor.DoesNotExist:
            logger.warning(f"Vendor {vendor_id} not found")
            return []
    
    def get_model_statistics(self) -> Dict[str, Any]:
        """
        获取模型使用统计信息
        
        Returns:
            统计信息字典
        """
        cache_key = 'model_statistics'
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        # 总体统计
        total_models = LLMModel.objects.count()
        
        # 按类型统计
        type_stats = {}
        for model_type, type_name in LLMModel.MODEL_TYPE_CHOICES:
            count = LLMModel.objects.filter(model_type=model_type).count()
            if count > 0:
                type_stats[type_name] = count
        
        # 按供应商统计
        vendor_stats = {}
        for vendor in Vendor.objects.filter(is_active=True):
            count = LLMModel.objects.filter(endpoint__vendor=vendor).count()
            if count > 0:
                vendor_stats[vendor.display_name] = count
        
        # 最常用的模型
        top_models = LLMModel.objects.order_by('-call_count')[:10]
        most_used = []
        for model in top_models:
            if model.call_count > 0:
                most_used.append({
                    'model_id': model.model_id,
                    'name': model.name,
                    'call_count': model.call_count,
                    'success_rate': round(model.success_count / model.call_count * 100, 2) if model.call_count > 0 else 0,
                })
        
        stats = {
            'total_models': total_models,
            'by_type': type_stats,
            'by_vendor': vendor_stats,
            'most_used': most_used,
            'active_vendors': Vendor.objects.filter(is_active=True).count(),
            'total_api_calls': sum(m.call_count for m in LLMModel.objects.all()),
        }
        
        cache.set(cache_key, stats, 60)  # 缓存1分钟
        return stats
    
    def search_models(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索模型配置
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的模型列表
        """
        models = LLMModel.objects.filter(
            Q(name__icontains=query) |
            Q(model_id__icontains=query) |
            Q(description__icontains=query)
        ).select_related('endpoint', 'endpoint__vendor')
        
        result = []
        for model in models:
            result.append({
                'model_id': model.model_id,
                'name': model.name,
                'type': model.model_type,
                'vendor': model.endpoint.vendor.display_name if model.endpoint and model.endpoint.vendor else 'Unknown',
                'description': model.description,
            })
        
        return result
    
    def get_model_defaults(self, model_type: str) -> Dict[str, Any]:
        """
        获取特定类型模型的默认配置参数
        
        Args:
            model_type: 模型类型
            
        Returns:
            默认参数字典
        """
        defaults = {
            'text': {
                'temperature': 0.7,
                'max_tokens': 1000,
                'top_p': 1.0,
                'frequency_penalty': 0,
                'presence_penalty': 0,
            },
            'reasoning': {
                'temperature': 1.0,
                'max_tokens': 4096,
            },
            'embedding': {
                'dimensions': 1536,
                'batch_size': 100,
            },
            'rerank': {
                'top_n': 10,
                'return_documents': False,
            },
            'vision': {
                'detail': 'auto',
                'max_tokens': 1000,
            },
            'speech': {
                'voice': 'alloy',
                'speed': 1.0,
            },
        }
        
        return defaults.get(model_type, {})
    
    def clear_cache(self) -> int:
        """
        清除所有模型配置缓存
        
        Returns:
            清除的缓存条目数
        """
        pattern = 'model_*'
        cache_keys = cache.keys(pattern)
        count = len(cache_keys)
        
        for key in cache_keys:
            cache.delete(key)
        
        logger.info(f"Cleared {count} model configuration cache entries")
        return count