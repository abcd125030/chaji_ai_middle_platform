"""
适配器工厂
根据模型配置自动选择和创建适配器
"""
from typing import Dict, Type, Optional
from .base import (
    ModelAdapter,
    TextModelAdapter,
    EmbeddingModelAdapter,
    RerankModelAdapter,
    ReasoningModelAdapter
)


class AdapterRegistry:
    """适配器注册中心"""
    
    def __init__(self):
        self._adapters: Dict[str, Type[ModelAdapter]] = {}
        self._vendor_adapters: Dict[str, Dict[str, Type[ModelAdapter]]] = {}
        self._model_specific_adapters: Dict[str, Type[ModelAdapter]] = {}
        
        # 注册默认适配器
        self._register_defaults()
    
    def _register_defaults(self):
        """注册默认的适配器"""
        # 按模型类型注册默认适配器
        self._adapters['text'] = TextModelAdapter
        self._adapters['embedding'] = EmbeddingModelAdapter
        self._adapters['rerank'] = RerankModelAdapter
        self._adapters['reasoning'] = ReasoningModelAdapter
        self._adapters['vision'] = TextModelAdapter  # 视觉模型通常使用文本适配器
        
        # 为特定供应商注册专用适配器（如果需要）
        self._vendor_adapters['groq'] = {
            'reasoning': GroqReasoningAdapter
        }
        self._vendor_adapters['deepseek'] = {
            'reasoning': DeepSeekReasoningAdapter
        }
        
        # 为特定模型注册专用适配器
        self._model_specific_adapters['o1-preview'] = OpenAIO1Adapter
        self._model_specific_adapters['o1-mini'] = OpenAIO1Adapter
    
    def register(self, key: str, adapter_class: Type[ModelAdapter], 
                 vendor: Optional[str] = None, model_id: Optional[str] = None):
        """
        注册适配器
        
        Args:
            key: 模型类型或标识
            adapter_class: 适配器类
            vendor: 供应商（可选）
            model_id: 特定模型ID（可选）
        """
        if model_id:
            self._model_specific_adapters[model_id] = adapter_class
        elif vendor:
            if vendor not in self._vendor_adapters:
                self._vendor_adapters[vendor] = {}
            self._vendor_adapters[vendor][key] = adapter_class
        else:
            self._adapters[key] = adapter_class
    
    def get_adapter(self, model_config: Dict) -> ModelAdapter:
        """
        根据模型配置获取适配器
        
        优先级：
        1. 特定模型ID的适配器
        2. 供应商+类型的适配器
        3. 通用类型适配器
        4. 默认文本适配器
        """
        model_id = model_config.get('model_id')
        vendor = model_config.get('vendor')
        model_type = model_config.get('model_type', 'text')
        
        adapter_class = None
        
        # 1. 检查特定模型适配器
        if model_id in self._model_specific_adapters:
            adapter_class = self._model_specific_adapters[model_id]
        
        # 2. 检查供应商特定适配器
        elif vendor in self._vendor_adapters:
            vendor_adapters = self._vendor_adapters[vendor]
            if model_type in vendor_adapters:
                adapter_class = vendor_adapters[model_type]
        
        # 3. 使用通用类型适配器
        if not adapter_class:
            adapter_class = self._adapters.get(model_type, TextModelAdapter)
        
        return adapter_class(model_config)


# 具体的供应商适配器实现

class GroqReasoningAdapter(ReasoningModelAdapter):
    """Groq推理模型适配器"""
    
    def parse_response(self, response: Dict) -> Dict:
        """处理Groq特有的<think>标签格式"""
        result = super().parse_response(response)
        # Groq的thinking在content中用<think>标签包裹
        content = result.get("content", "")
        if "<think>" in content:
            thinking, answer = self._extract_thinking_from_tags(content)
            result["thinking"] = thinking
            result["content"] = answer
        return result


class DeepSeekReasoningAdapter(ReasoningModelAdapter):
    """DeepSeek推理模型适配器"""
    
    def prepare_request(self, messages: list, **kwargs) -> Dict:
        """DeepSeek可能需要特殊的请求参数"""
        request = super().prepare_request(messages, **kwargs)
        # 添加DeepSeek特定参数
        if self.model_id and 'reasoner' in self.model_id.lower():
            request['reasoning_mode'] = True
        return request
    
    def parse_response(self, response: Dict) -> Dict:
        """处理DeepSeek的推理响应"""
        result = super().parse_response(response)
        # DeepSeek可能在usage中包含reasoning_tokens
        usage = response.get("usage", {})
        if "reasoning_tokens" in usage:
            result["reasoning_tokens"] = usage["reasoning_tokens"]
        return result


class OpenAIO1Adapter(ReasoningModelAdapter):
    """OpenAI O1模型适配器"""
    
    def prepare_request(self, messages: list, **kwargs) -> Dict:
        """O1模型不支持system消息和某些参数"""
        # 过滤掉system消息
        filtered_messages = [m for m in messages if m.get("role") != "system"]
        
        # O1不支持temperature等参数
        filtered_kwargs = {k: v for k, v in kwargs.items() 
                          if k not in ['temperature', 'top_p', 'frequency_penalty']}
        
        return super().prepare_request(filtered_messages, **filtered_kwargs)
    
    def parse_response(self, response: Dict) -> Dict:
        """处理O1的reasoning_content"""
        result = super().parse_response(response)
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            if "reasoning_content" in message:
                result["thinking"] = message["reasoning_content"]
        return result


# 创建全局注册中心实例
adapter_registry = AdapterRegistry()


class AdapterFactory:
    """适配器工厂类"""
    
    @staticmethod
    def create_adapter(model_config: Dict) -> ModelAdapter:
        """
        创建适配器实例
        
        Args:
            model_config: 包含model_id, vendor, model_type等信息
            
        Returns:
            对应的适配器实例
        """
        return adapter_registry.get_adapter(model_config)
    
    @staticmethod
    def register_adapter(key: str, adapter_class: Type[ModelAdapter], **kwargs):
        """注册新的适配器"""
        adapter_registry.register(key, adapter_class, **kwargs)