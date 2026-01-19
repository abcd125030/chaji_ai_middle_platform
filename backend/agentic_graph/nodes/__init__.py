"""
Graph 节点模块
"""
from .base import BaseNode, NodeRegistry
from .start import StartNode
from .end import EndNode
from .planner import PlannerNode
from .tool import ToolNode
from .reflection import ReflectionNode
from .output import OutputNode

# 注册内置节点
registry = NodeRegistry()

# 注册基础节点
registry.register('start', StartNode)
registry.register('end', EndNode)

# 注册功能节点
registry.register('planner', PlannerNode)
registry.register('tool', ToolNode)
registry.register('reflection', ReflectionNode)
registry.register('output', OutputNode)

__all__ = [
    'BaseNode',
    'NodeRegistry',
    'StartNode',
    'EndNode',
    'PlannerNode',
    'ToolNode',
    'ReflectionNode',
    'OutputNode',
    'registry'
]