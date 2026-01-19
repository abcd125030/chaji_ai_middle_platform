from typing import Any, Dict, List, Type, Optional, Union
from .types import ToolType


class ToolRegistry:
    """工具注册中心"""
    _instance = None
    # 将 _tools 结构改为: { 'tool_name': { 'class': ToolClass, 'description': '...', 'category': 'libs/outputs' } }
    _tools: Dict[str, Dict[str, Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, name: str, tool_class: Type, description: str, 
                  tool_type: Optional[Union[ToolType, str]] = None,
                  category: Optional[str] = None):
        """
        注册工具及其描述
        
        Args:
            name: 工具名称
            tool_class: 工具类
            description: 工具描述
            tool_type: 工具类型（ToolType枚举或字符串）
            category: 工具分类 ('libs' 或 'outputs')，如果未指定则从模块路径推断
        """
        # 处理工具类型
        if tool_type is not None:
            if isinstance(tool_type, str):
                tool_type = ToolType.from_string(tool_type)
            elif not isinstance(tool_type, ToolType):
                raise ValueError(f"tool_type must be ToolType enum or string, got {type(tool_type)}")
            # 设置工具类的类型属性
            tool_class.tool_type = tool_type
        
        # 如果未指定分类，从模块路径推断
        if category is None:
            module_path = tool_class.__module__
            if 'tools.libs' in module_path:
                category = 'libs'
            elif 'tools.outputs' in module_path:
                category = 'outputs'
            else:
                category = 'unknown'
        
        self._tools[name] = {
            "class": tool_class,
            "description": description,
            "category": category,
            "tool_type": tool_type.value if tool_type else None
        }

    def get_tool(self, name: str) -> Type:
        """获取工具类"""
        if name in self._tools:
            return self._tools[name]["class"]
        from .exceptions import ToolNotFoundError  # 局部导入以避免循环依赖
        raise ToolNotFoundError(f"Tool {name} not found")

    def get_tool_description(self, name: str) -> str:
        """获取工具的描述"""
        if name in self._tools:
            return self._tools[name]["description"]
        from .exceptions import ToolNotFoundError
        raise ToolNotFoundError(f"Tool {name} not found")

    def list_tools(self) -> List[str]:
        """列出所有可用工具的名称"""
        return list(self._tools.keys())

    def list_tools_with_details(self, category: Optional[str] = None, 
                                tool_type: Optional[Union[ToolType, str]] = None) -> List[Dict[str, Any]]:
        """
        列出工具的详细信息 (名称, 描述, 分类, 类型)
        
        Args:
            category: 可选的分类过滤器 ('libs' 或 'outputs')
            tool_type: 可选的类型过滤器 (ToolType枚举或字符串)
        
        Returns:
            工具详细信息列表
        """
        # 处理类型过滤器
        if tool_type is not None:
            if isinstance(tool_type, str):
                tool_type_value = tool_type
            elif isinstance(tool_type, ToolType):
                tool_type_value = tool_type.value
            else:
                raise ValueError(f"tool_type must be ToolType enum or string")
        else:
            tool_type_value = None
        
        details = []
        for name, data in self._tools.items():
            # 检查分类过滤
            if category is not None and data.get("category") != category:
                continue
            # 检查类型过滤
            if tool_type_value is not None and data.get("tool_type") != tool_type_value:
                continue
            
            details.append({
                "name": name,
                "description": data["description"],
                "category": data.get("category", "unknown"),
                "tool_type": data.get("tool_type")
            })
        return details
    
    def list_tools_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        按分类列出所有工具
        
        Returns:
            字典，键为分类名称，值为该分类下的工具列表
        """
        categorized_tools = {
            "libs": [],
            "outputs": [],
            "unknown": []
        }
        
        for name, data in self._tools.items():
            category = data.get("category", "unknown")
            tool_info = {
                "name": name,
                "description": data["description"],
                "tool_type": data.get("tool_type")
            }
            
            if category in categorized_tools:
                categorized_tools[category].append(tool_info)
            else:
                categorized_tools["unknown"].append(tool_info)
        
        # 移除空分类
        return {k: v for k, v in categorized_tools.items() if v}
    
    def list_tools_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        按类型列出所有工具
        
        Returns:
            字典，键为类型名称，值为该类型下的工具列表
        """
        typed_tools = {}
        
        for name, data in self._tools.items():
            tool_type = data.get("tool_type")
            if tool_type:
                if tool_type not in typed_tools:
                    typed_tools[tool_type] = []
                typed_tools[tool_type].append({
                    "name": name,
                    "description": data["description"],
                    "category": data.get("category")
                })
        
        # 添加未分类的工具
        untyped = []
        for name, data in self._tools.items():
            if not data.get("tool_type"):
                untyped.append({
                    "name": name,
                    "description": data["description"],
                    "category": data.get("category")
                })
        
        if untyped:
            typed_tools["untyped"] = untyped
            
        return typed_tools

    def get_tool_class_path(self, name: str) -> str:
        """
        获取工具类的完整 Python 导入路径。
        例如 'myapp.tools.MyToolClass'
        """
        if name in self._tools:
            tool_class = self._tools[name]["class"]
            return f"{tool_class.__module__}.{tool_class.__qualname__}"
        from .exceptions import ToolNotFoundError
        raise ToolNotFoundError(f"Tool {name} not found in registry.")


# 装饰器用于自动注册工具
def register_tool(name: str, description: str, 
                 tool_type: Optional[Union[ToolType, str]] = None,
                 category: Optional[str] = None):
    """
    工具注册装饰器
    
    Args:
        name: 工具名称
        description: 工具描述
        tool_type: 工具类型（ToolType枚举或字符串）
        category: 工具分类 ('libs' 或 'outputs')，如果未指定则从模块路径推断
    """
    def decorator(cls):
        registry = ToolRegistry()
        registry.register(name, cls, description, tool_type, category)
        return cls
    return decorator