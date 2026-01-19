"""
统一的工具输入输出接口定义
"""
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field


class UnifiedToolInput(BaseModel):
    """统一的工具输入格式"""
    # 核心输入
    query: str = Field(description="用户的查询或指令")
    
    # 引用数据（可选）
    referenced_data: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="引用的数据，包含 documents、tables、action_results 三种类型"
    )
    
    # 工具特定参数（可选）
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="工具特定的参数，如 length、format、model_name 等"
    )
    
    # 上下文信息（可选）
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="执行上下文，如 user_id、session_id 等"
    )


class UnifiedToolOutput(BaseModel):
    """统一的工具输出格式"""
    # 必需字段
    status: str = Field(description="执行状态: success/error/partial")
    message: str = Field(description="执行结果的简要描述")
    
    # 主要结果 - 必须是纯文本格式，便于用户阅读
    primary_result: str = Field(
        description="主要执行结果，必须是用户友好的纯文本格式"
    )
    
    # 结构化数据 - 供其他工具或系统使用
    structured_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="结构化的结果数据，如解析后的实体、数值等"
    )
    
    # 关键指标
    key_metrics: Optional[Dict[str, Union[int, float, str]]] = Field(
        default=None,
        description="执行过程的关键量化指标"
    )
    
    # 元数据
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="执行元数据，包含 tool_name、execution_id、timestamp 等"
    )


class ToolInterfaceSpec:
    """工具接口规范"""
    
    @staticmethod
    def format_input_for_tool(
        tool_name: str,
        query: str,
        referenced_data: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        为特定工具格式化输入
        
        这个方法将 planner 的输入转换为工具期望的格式
        """
        # 基础输入
        tool_input = {
            "query": query
        }
        
        # 添加引用数据
        if referenced_data:
            tool_input["referenced_data"] = referenced_data
        
        # 根据工具类型添加特定参数
        if tool_name == "summarize":
            tool_input["content"] = query  # summarize 工具使用 content 字段
            tool_input["length"] = kwargs.get("length", "medium")
            
        elif tool_name == "report_generator":
            tool_input["topic"] = kwargs.get("topic", query)
            tool_input["requirements"] = kwargs.get("requirements", query)
            
        elif tool_name == "web_search":
            tool_input["max_results"] = kwargs.get("max_results", 3)
            
        elif tool_name == "translate":
            tool_input["text"] = query
            tool_input["target_language"] = kwargs.get("target_language", "Chinese")
            
        # 添加其他参数
        for key, value in kwargs.items():
            if key not in tool_input:
                tool_input[key] = value
        
        return tool_input
    
    @staticmethod
    def ensure_text_output(data: Any) -> str:
        """
        确保输出是用户友好的文本格式
        
        将各种格式的数据转换为易读的文本
        """
        if isinstance(data, str):
            # 检测并格式化 JSON 字符串
            if data.strip().startswith('{') and data.strip().endswith('}'):
                try:
                    import json
                    json_obj = json.loads(data)
                    return ToolInterfaceSpec._format_json_to_text(json_obj)
                except:
                    return data
            return data
            
        elif isinstance(data, dict):
            return ToolInterfaceSpec._format_json_to_text(data)
            
        elif isinstance(data, list):
            # 格式化列表
            formatted_items = []
            for i, item in enumerate(data, 1):
                if isinstance(item, dict):
                    formatted_items.append(f"{i}. {ToolInterfaceSpec._format_json_to_text(item)}")
                else:
                    formatted_items.append(f"{i}. {str(item)}")
            return "\n".join(formatted_items)
            
        else:
            return str(data)
    
    @staticmethod
    def _format_json_to_text(json_obj: Dict[str, Any], level: int = 0) -> str:
        """
        将 JSON 对象格式化为易读的文本
        """
        if level > 3:  # 防止过深的嵌套
            return str(json_obj)
            
        formatted_parts = []
        indent = "  " * level
        
        for key, value in json_obj.items():
            # 清理键名
            clean_key = key.replace('_', ' ').title()
            if '(' in clean_key and ')' in clean_key:
                clean_key = clean_key.replace('(', '（').replace(')', '）')
            
            # 格式化值
            if isinstance(value, dict):
                formatted_parts.append(f"{indent}**{clean_key}**:")
                formatted_parts.append(ToolInterfaceSpec._format_json_to_text(value, level + 1))
            elif isinstance(value, list):
                formatted_parts.append(f"{indent}**{clean_key}**:")
                for item in value:
                    if isinstance(item, dict):
                        formatted_parts.append(f"{indent}  - {ToolInterfaceSpec._format_json_to_text(item, level + 2)}")
                    else:
                        formatted_parts.append(f"{indent}  - {str(item)}")
            elif value:  # 只显示非空值
                formatted_parts.append(f"{indent}**{clean_key}**: {value}")
        
        return "\n".join(formatted_parts)