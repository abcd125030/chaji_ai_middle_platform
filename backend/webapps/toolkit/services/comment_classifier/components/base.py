"""
基础组件抽象类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging


@dataclass
class ComponentResult:
    """组件执行结果"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseComponent(ABC):
    """
    基础组件抽象类
    所有组件都必须继承此类
    """
    
    def __init__(self, config: Any):
        """
        初始化组件
        
        Args:
            config: 组件配置
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialized = False
        self.initialize()
    
    def initialize(self):
        """初始化组件资源"""
        self._initialized = True
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行组件逻辑
        
        Args:
            **kwargs: 组件输入参数
            
        Returns:
            组件执行结果
        """
        pass
    
    def validate_input(self, **kwargs) -> bool:
        """
        验证输入参数
        
        Args:
            **kwargs: 输入参数
            
        Returns:
            验证是否通过
        """
        return True
    
    def cleanup(self):
        """清理组件资源"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """获取组件状态"""
        return {
            'name': self.__class__.__name__,
            'initialized': self._initialized,
            'config': self.config.to_dict() if hasattr(self.config, 'to_dict') else str(self.config)
        }
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()