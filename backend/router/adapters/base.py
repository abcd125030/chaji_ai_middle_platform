"""
基础适配器类
定义所有模型适配器的接口
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ModelAdapter(ABC):
    """模型适配器基类"""
    
    def __init__(self, model_config: Dict[str, Any]):
        """
        初始化适配器
        
        Args:
            model_config: 模型配置，包含model_id, vendor, endpoint等信息
        """
        self.model_config = model_config
        self.model_id = model_config.get('model_id')
        self.vendor = model_config.get('vendor')
        self.endpoint = model_config.get('endpoint')
    
    @abstractmethod
    def prepare_request(self, **kwargs) -> Dict[str, Any]:
        """
        准备请求体
        将统一格式转换为特定模型的请求格式
        
        Returns:
            适配后的请求体
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析响应体
        将特定模型的响应格式转换为统一格式
        
        Args:
            response: 原始响应体
            
        Returns:
            统一格式的响应
        """
        pass
    
    def get_headers(self) -> Dict[str, str]:
        """
        获取请求头
        可以被子类重写以添加特定的请求头
        """
        return {
            "Content-Type": "application/json"
        }
    
    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """
        统一错误处理
        """
        return {
            "error": str(error),
            "model": self.model_id,
            "vendor": self.vendor
        }


class TextModelAdapter(ModelAdapter):
    """文本生成模型适配器基类"""
    
    def prepare_request(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """
        准备文本生成请求
        大多数文本模型使用类似的格式
        """
        return {
            "model": self.model_id,
            "messages": messages,
            **kwargs  # temperature, max_tokens等参数
        }
    
    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析文本生成响应
        提取content字段
        """
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return {
                "content": message.get("content", ""),
                "role": message.get("role", "assistant"),
                "model": response.get("model"),
                "usage": response.get("usage")
            }
        return {"content": "", "error": "No choices in response"}


class EmbeddingModelAdapter(ModelAdapter):
    """向量嵌入模型适配器基类"""
    
    def prepare_request(self, input_text: str, **kwargs) -> Dict[str, Any]:
        """
        准备嵌入请求
        """
        # 处理输入格式（有些API接受字符串，有些需要列表）
        if self.vendor in ['openai', 'aliyun']:
            input_data = input_text if isinstance(input_text, list) else [input_text]
        else:
            input_data = input_text
        
        return {
            "model": self.model_id,
            "input": input_data,
            **kwargs
        }
    
    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析嵌入响应
        统一返回向量格式
        """
        # OpenAI格式
        if "data" in response:
            embeddings = []
            for item in response["data"]:
                if "embedding" in item:
                    embeddings.append(item["embedding"])
            return {
                "embeddings": embeddings,
                "model": response.get("model"),
                "usage": response.get("usage")
            }
        
        # 其他可能的格式
        if "embeddings" in response:
            return {
                "embeddings": response["embeddings"],
                "model": response.get("model")
            }
        
        return {"embeddings": [], "error": "Unknown embedding response format"}


class RerankModelAdapter(ModelAdapter):
    """重排序模型适配器基类"""
    
    def prepare_request(self, query: str, documents: List[str], **kwargs) -> Dict[str, Any]:
        """
        准备重排序请求
        """
        return {
            "model": self.model_id,
            "query": query,
            "documents": documents,
            "top_n": kwargs.get("top_n", len(documents)),
            **kwargs
        }
    
    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析重排序响应
        统一返回排序结果
        """
        # Cohere格式
        if "results" in response:
            results = []
            for item in response["results"]:
                results.append({
                    "index": item.get("index"),
                    "score": item.get("relevance_score", item.get("score")),
                    "document": item.get("document", {}).get("text", "")
                })
            return {
                "results": results,
                "model": response.get("model")
            }
        
        # 其他格式
        if "data" in response:
            results = []
            for item in response["data"]:
                results.append({
                    "index": item.get("index"),
                    "score": item.get("score"),
                    "document": item.get("text", "")
                })
            return {"results": results}
        
        return {"results": [], "error": "Unknown rerank response format"}


class ReasoningModelAdapter(TextModelAdapter):
    """推理模型适配器基类"""
    
    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析推理模型响应
        需要处理不同格式的thinking内容
        """
        result = super().parse_response(response)
        
        # OpenAI o1格式：reasoning_content字段
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            if "reasoning_content" in message:
                result["thinking"] = message["reasoning_content"]
                return result
        
        # DeepSeek格式：reasoning_tokens
        if "reasoning_tokens" in response.get("usage", {}):
            # 从content中提取thinking部分
            content = result.get("content", "")
            thinking, answer = self._extract_thinking_from_content(content)
            result["thinking"] = thinking
            result["content"] = answer
            return result
        
        # Groq格式：<think>标签
        content = result.get("content", "")
        if "<think>" in content and "</think>" in content:
            thinking, answer = self._extract_thinking_from_tags(content)
            result["thinking"] = thinking
            result["content"] = answer
            return result
        
        return result
    
    def _extract_thinking_from_tags(self, content: str) -> tuple[str, str]:
        """从<think>标签中提取思考内容"""
        import re
        pattern = r'<think>(.*?)</think>'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            thinking = match.group(1).strip()
            answer = re.sub(pattern, '', content, flags=re.DOTALL).strip()
            return thinking, answer
        return "", content
    
    def _extract_thinking_from_content(self, content: str) -> tuple[str, str]:
        """
        从内容中提取思考部分
        某些模型可能用特定分隔符或格式
        """
        # 这里需要根据具体模型的格式来实现
        # 例如：思考部分在前，答案在后，用特定分隔符分隔
        if "\n---\n" in content:
            parts = content.split("\n---\n", 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        return "", content