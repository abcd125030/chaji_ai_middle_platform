from tools.core.registry import ToolRegistry
from tools.core.exceptions import ToolError, ToolNotFoundError
from typing import Dict, Any, Optional

def execute_tool(tool_name: str, state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    统一的工具执行接口
    这个函数可以作为 agentic Node 的 python_callable 目标
    """
    try:
        registry = ToolRegistry()
        tool_class = registry.get_tool(tool_name)
        
        # 实例化工具时传入config
        tool_instance = tool_class(config=config)
        
        # 执行工具
        result = tool_instance.execute(state)
        
        # 确保成功执行时也包含 'success' 键
        if 'success' not in result:
            result['success'] = True
        return result
        
    except ToolNotFoundError as e:
        return {
            **state,
            "tool_output": f"工具未找到: {str(e)}",
            "error": str(e),
            "success": False
        }
    except ToolError as e:
        return {
            **state,
            "tool_output": f"工具执行失败: {str(e)}",
            "error": str(e),
            "success": False
        }
    except Exception as e:
        return {
            **state,
            "tool_output": f"未知错误: {str(e)}",
            "error": str(e),
            "success": False
        }
