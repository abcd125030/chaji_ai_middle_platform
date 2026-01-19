"""
AI处理器基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional


class BaseAIProcessor(ABC):
    """
    AI处理器基类
    所有AI处理器必须继承此类
    """
    
    def __init__(self, config: Any):
        """
        初始化处理器
        
        Args:
            config: 处理器配置
        """
        self.config = config
        self.api_key = None
        self.base_url = None
        self.model_name = None
    
    @abstractmethod
    async def process_single(self, content: str) -> Dict[str, Any]:
        """
        处理单条内容
        
        Args:
            content: 待处理内容
            
        Returns:
            处理结果
        """
        pass
    
    @abstractmethod
    async def process_batch(self, contents: List[str]) -> List[Dict[str, Any]]:
        """
        批量处理内容
        
        Args:
            contents: 待处理内容列表
            
        Returns:
            处理结果列表
        """
        pass
    
    def update_category_keywords(self, category_path: str, keywords: List[str]):
        """
        更新分类关键词
        
        Args:
            category_path: 分类路径
            keywords: 关键词列表
        """
        # TODO: 实现关键词更新逻辑
        pass