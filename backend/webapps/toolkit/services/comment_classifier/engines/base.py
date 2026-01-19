"""
分类引擎基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional


class BaseClassifierEngine(ABC):
    """
    分类引擎基类
    所有分类引擎必须继承此类
    """
    
    def __init__(self, config: Any):
        """
        初始化引擎
        
        Args:
            config: 引擎配置
        """
        self.config = config
        self.categories_config = None
        self._load_categories_config()
    
    def _load_categories_config(self):
        """加载分类配置"""
        # TODO: 从配置路径加载分类层级配置
        pass
    
    @abstractmethod
    def classify(self, content: str) -> Tuple[Optional[str], float, str]:
        """
        对单条内容进行分类
        
        Args:
            content: 待分类内容
            
        Returns:
            (分类路径, 置信度, 分类器名称)
        """
        pass
    
    @abstractmethod
    def classify_batch(self, contents: List[str]) -> List[Dict[str, Any]]:
        """
        批量分类
        
        Args:
            contents: 待分类内容列表
            
        Returns:
            分类结果列表
        """
        pass
    
    def get_category_metadata(self, category_path: str) -> Dict[str, str]:
        """
        获取分类元数据
        
        Args:
            category_path: 分类路径
            
        Returns:
            元数据字典
        """
        return {
            'user_stage': '',
            'is_valid': '',
            'is_it_related': ''
        }