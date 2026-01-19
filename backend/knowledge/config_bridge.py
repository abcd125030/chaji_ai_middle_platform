"""
知识库配置桥接器
将知识库服务与路由器的模型配置连接起来，复用已有的模型配置
"""
import logging
from typing import Dict, Optional, Any
from django.core.exceptions import ObjectDoesNotExist

from router.models import LLMModel, VendorAPIKey
from llm.config_manager import ModelConfigManager
from .models import KnowledgeConfig

logger = logging.getLogger("django")


class KnowledgeConfigBridge:
    """
    知识库配置桥接器
    从路由器获取模型配置，知识库配置仅保留向量存储等专有设置
    """
    
    def __init__(self):
        self.model_config_manager = ModelConfigManager()
        self._kb_config_cache = None
    
    def get_knowledge_base_config(self) -> KnowledgeConfig:
        """获取知识库基础配置（仅用于向量存储等设置）"""
        if self._kb_config_cache:
            return self._kb_config_cache
            
        try:
            self._kb_config_cache = KnowledgeConfig.objects.get(is_active=True)
            return self._kb_config_cache
        except KnowledgeConfig.DoesNotExist:
            raise ValueError("未找到激活的知识库配置。请在管理后台配置并激活一个。")
        except KnowledgeConfig.MultipleObjectsReturned:
            logger.error("发现多个激活的知识库配置")
            raise ValueError("找到多个激活的知识库配置。请确保只有一个配置处于激活状态。")
    
    def get_llm_config(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取LLM配置
        优先使用路由器中的模型配置
        
        Args:
            model_name: 模型名称，如果为None则使用知识库配置中的默认模型
            
        Returns:
            包含LLM配置的字典
        """
        kb_config = self.get_knowledge_base_config()
        
        # 确定使用的模型名称
        if not model_name:
            model_name = kb_config.llm_model_name
            
        # 从路由器获取模型配置
        try:
            router_config = self.model_config_manager.get_model_config(model_name)
            
            # 构建LLM配置
            llm_config = {
                "provider": self._map_vendor_to_provider(router_config.get('vendor_name')),
                "config": {
                    "model": router_config['model_id'],
                    "api_key": router_config['api_key'],
                    "temperature": kb_config.llm_temperature,  # 使用知识库的温度设置
                }
            }
            
            # 处理base_url - 移除末尾的具体API路径
            if router_config.get('endpoint'):
                endpoint = router_config['endpoint']
                # 如果endpoint包含具体API路径，只保留基础URL
                if '/chat/completions' in endpoint:
                    endpoint = endpoint.replace('/chat/completions', '')
                llm_config["config"]["openai_base_url"] = endpoint
                
            return llm_config
            
        except (ValueError, ObjectDoesNotExist) as e:
            logger.warning(f"无法从路由器获取模型配置 {model_name}，回退到知识库配置: {e}")
            # 回退到知识库配置
            return self._get_fallback_llm_config(kb_config)
    
    def get_embedder_config(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取Embedder配置
        优先从路由器获取 embedding 类型的模型
        
        Args:
            model_name: 模型名称，如果为None则使用知识库配置中的默认模型
            
        Returns:
            包含Embedder配置的字典
        """
        kb_config = self.get_knowledge_base_config()
        
        # 确定使用的模型名称
        if not model_name:
            model_name = kb_config.embedder_model_name
        
        # 尝试从路由器获取 embedding 模型
        try:
            # 首先尝试通过名称查找
            embedding_model = LLMModel.objects.filter(
                model_type='embedding',
                model_id=model_name
            ).select_related('endpoint').first()
            
            if not embedding_model:
                # 尝试通过 name 字段查找
                embedding_model = LLMModel.objects.filter(
                    model_type='embedding',
                    name=model_name
                ).select_related('endpoint').first()
            
            if embedding_model:
                # 获取API密钥
                api_key = self._get_api_key_for_model(embedding_model)
                
                # 构建embedder配置
                provider = self._map_vendor_to_provider(
                    embedding_model.endpoint.get_vendor_display()
                )
                
                embedder_config = {
                    "provider": provider,
                    "config": {
                        "model": embedding_model.model_id,
                        "api_key": api_key,
                    }
                }
                
                # 处理base_url - 阿里云使用OpenAI兼容接口
                if embedding_model.endpoint.endpoint:
                    endpoint = embedding_model.endpoint.endpoint
                    # 移除末尾的具体API路径
                    if '/embeddings' in endpoint:
                        endpoint = endpoint.replace('/embeddings', '')
                    
                    # 阿里云虽然provider是aliyun，但实际使用OpenAI兼容接口
                    if provider in ["openai", "aliyun"]:
                        # mem0 期望 openai provider 使用 openai_base_url 字段
                        # 但如果 provider 是 aliyun，我们需要将其转换为 openai
                        if provider == "aliyun":
                            embedder_config["provider"] = "openai"  # 覆盖为openai以兼容mem0
                        embedder_config["config"]["openai_base_url"] = endpoint
                    else:
                        # 对于其他provider，可能需要不同的字段名
                        embedder_config["config"]["base_url"] = embedding_model.endpoint.endpoint
                
                # mem0 使用 embedding_dims 参数来指定向量维度
                if kb_config.embedder_dimensions:
                    embedder_config["config"]["embedding_dims"] = kb_config.embedder_dimensions
                    
                logger.info(f"从路由器获取到 embedding 模型配置: {model_name}")
                return embedder_config
                
        except Exception as e:
            logger.warning(f"无法从路由器获取 embedding 模型 {model_name}: {e}")
        
        # 回退到知识库配置
        logger.info(f"使用知识库配置中的 embedder: {model_name}")
        return self._get_fallback_embedder_config(kb_config)
    
    def get_vector_store_config(self) -> Dict[str, Any]:
        """
        获取向量存储配置
        这个配置仍然从知识库配置中获取
        
        Returns:
            包含向量存储配置的字典
        """
        kb_config = self.get_knowledge_base_config()
        
        if kb_config.vector_store_provider == 'qdrant':
            config = {
                "provider": "qdrant",
                "config": {
                    "host": kb_config.qdrant_host,
                    "port": kb_config.qdrant_port,
                }
            }
            if kb_config.qdrant_api_key:
                config["config"]["api_key"] = kb_config.qdrant_api_key
        else:
            # 默认使用内存存储
            config = {
                "provider": "chroma",
                "config": {
                    "path": "./chroma_db"
                }
            }
            
        return config
    
    def get_mem0_config(self, collection_name: str) -> Dict[str, Any]:
        """
        获取完整的mem0配置
        整合LLM、Embedder和向量存储配置
        
        Args:
            collection_name: 集合名称
            
        Returns:
            包含完整mem0配置的字典
        """
        kb_config = self.get_knowledge_base_config()
        
        # 获取向量存储配置
        vector_config = self.get_vector_store_config()
        if vector_config["provider"] == "qdrant":
            vector_config["config"]["collection_name"] = collection_name
        elif vector_config["provider"] == "chroma":
            vector_config["config"]["collection_name"] = collection_name
        
        # 获取embedder配置
        embedder_config = self.get_embedder_config()
        
        # 构建mem0配置
        mem0_config = {
            "vector_store": vector_config,
            "embedder": embedder_config,
            "version": "v1.1"
        }
        
        # 可选：添加LLM配置（如果需要）
        # 注意：KnowledgeConfig 不直接存储 API key，从路由器配置获取
        try:
            llm_config = self.get_llm_config()
            if llm_config and llm_config["config"].get("api_key"):
                mem0_config["llm"] = llm_config
        except Exception as e:
            logger.warning(f"无法获取LLM配置: {e}")
        
        return mem0_config
    
    def _get_api_key_for_model(self, llm_model: LLMModel) -> str:
        """获取模型的API密钥"""
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
            
            return vendor_key.api_key
        except VendorAPIKey.DoesNotExist:
            logger.warning(f"未找到模型的API密钥: {llm_model.name}")
            return ""
    
    def _map_vendor_to_provider(self, vendor_name: str) -> str:
        """
        将供应商名称映射到provider标识符
        
        Args:
            vendor_name: 供应商名称
            
        Returns:
            provider标识符
        """
        vendor_mapping = {
            'OpenRouter': 'openrouter',
            'openrouter': 'openrouter',
            'frago': 'frago',
            '茶姬': 'chagee',
            'chagee': 'chagee',
            '阿里云百炼大模型': 'aliyun',
            'aliyun': 'aliyun',
            'groq': 'groq',
            'OpenAI': 'openai',
            'openai': 'openai',
        }
        
        return vendor_mapping.get(vendor_name, 'openai')
    
    def _get_fallback_llm_config(self, kb_config: KnowledgeConfig) -> Dict[str, Any]:
        """获取回退的LLM配置（从知识库配置）"""
        import os
        
        # 从环境变量获取配置
        api_key = os.environ.get('GROQ_API_KEY', '')
        base_url = os.environ.get('GROQ_BASE_URL', 'https://api.groq.com/openai/v1')
        
        llm_config = {
            "provider": "groq",  # 默认使用groq
            "config": {
                "model": kb_config.llm_model_name,
                "temperature": kb_config.llm_temperature,
                "api_key": api_key,
            }
        }
        if base_url:
            llm_config["config"]["openai_base_url"] = base_url
            
        return llm_config
    
    def _get_fallback_embedder_config(self, kb_config: KnowledgeConfig) -> Dict[str, Any]:
        """获取回退的Embedder配置（从知识库配置）"""
        import os
        
        # 判断模型类型并获取相应的API配置
        if 'text-embedding-v' in kb_config.embedder_model_name.lower():
            # 阿里云的 text-embedding 模型
            api_key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('DOUBAO_API_KEY', '')
            embedder_config = {
                "provider": "openai",  # 使用 OpenAI 兼容模式
                "config": {
                    "model": kb_config.embedder_model_name,
                    "api_key": api_key,
                    "openai_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  # 修正字段名
                }
            }
        else:
            # 其他模型，默认使用 OpenAI
            api_key = os.environ.get('OPENAI_API_KEY', '')
            base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
            embedder_config = {
                "provider": "openai",
                "config": {
                    "model": kb_config.embedder_model_name,
                    "api_key": api_key,
                    "openai_base_url": base_url,
                }
            }
        
        # 注意：mem0 不支持 dimensions 参数
        # if kb_config.embedder_dimensions:
        #     embedder_config["config"]["dimensions"] = kb_config.embedder_dimensions
            
        return embedder_config
    
    def clear_cache(self):
        """清除缓存"""
        self._kb_config_cache = None
        self.model_config_manager.clear_cache()
        logger.info("清除知识库配置桥接器缓存")


# 全局实例
knowledge_config_bridge = KnowledgeConfigBridge()