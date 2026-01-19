"""
节点基类和注册器
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
import logging

from ..core.schemas import RuntimeState

logger = logging.getLogger('django')


class BaseNode(ABC):
    """所有节点的基类"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        """
        初始化节点
        
        参数:
            name: 节点名称
            config: 节点配置
        """
        self.name = name
        self.config = config or {}
    
    @abstractmethod
    def execute(self, state: RuntimeState) -> Dict[str, Any]:
        """
        执行节点逻辑
        
        参数:
            state: 运行时状态
        
        返回:
            执行结果
        """
        pass
    
    def pre_execute(self, state: RuntimeState):
        """执行前的钩子"""
        logger.debug(f"节点 {self.name} 开始执行")
    
    def post_execute(self, state: RuntimeState, result: Dict[str, Any]):
        """执行后的钩子"""
        logger.debug(f"节点 {self.name} 执行完成")
    
    def run(self, state: RuntimeState) -> Dict[str, Any]:
        """
        运行节点（包含前后钩子）
        
        参数:
            state: 运行时状态
        
        返回:
            执行结果
        """
        self.pre_execute(state)
        result = self.execute(state)
        self.post_execute(state, result)
        return result


class NodeRegistry:
    """节点注册器"""
    
    def __init__(self):
        """初始化注册器"""
        self._nodes: Dict[str, Type[BaseNode]] = {}
    
    def register(self, node_type: str, node_class: Type[BaseNode]):
        """
        注册节点类型
        
        参数:
            node_type: 节点类型名称
            node_class: 节点类
        """
        if not issubclass(node_class, BaseNode):
            raise TypeError(f"{node_class} 必须是 BaseNode 的子类")
        
        self._nodes[node_type] = node_class
        logger.info(f"注册节点类型: {node_type} -> {node_class.__name__}")
    
    def get_node_class(self, node_type: str) -> Optional[Type[BaseNode]]:
        """
        获取节点类
        
        参数:
            node_type: 节点类型名称
        
        返回:
            节点类，如果不存在返回 None
        """
        return self._nodes.get(node_type)
    
    def list_node_types(self) -> list:
        """
        列出所有注册的节点类型
        
        返回:
            节点类型列表
        """
        return list(self._nodes.keys())