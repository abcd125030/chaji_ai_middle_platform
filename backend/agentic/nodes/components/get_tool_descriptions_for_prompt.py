# -*- coding: utf-8 -*-
"""
get_tool_descriptions_for_prompt.py

获取所有可用工具的详细描述（仅libs类别，排除generator目录）。
供 prompt_builder.py 调用，用于生成工具使用说明文档。
注意：generator目录下的工具是输出工具，不能直接给planner使用。

返回值示例:
    返回格式化的 Markdown 文本，包含每个工具的名称、描述和参数说明：
    '''
    ### Tool: `web_search`
    **Description**: 使用搜索引擎查询互联网信息
    **Parameters**:
    - query (str, required): 搜索查询关键词
    - max_results (int, optional): 最大返回结果数，默认为5
    
    ### Tool: `pandas_data_calculator`
    **Description**: 使用pandas进行表格数据计算和分析
    **Parameters**:
    - data (dict, required): 表格数据，格式为 {"columns": [...], "data": [...]}
    - operation (str, required): 要执行的操作，如 "sum", "mean", "group_by" 等
    - params (dict, optional): 操作相关的参数
    '''
"""

from typing import List, Dict, Any

from tools.core.registry import ToolRegistry


def get_tool_descriptions_for_prompt() -> str:
    """
    获取所有可用工具的详细描述（仅libs类别，排除generator目录）。
    
    返回:
        str: 格式化的工具描述文本，使用 Markdown 格式。
        
        返回值格式：
        - 每个工具以 ### 级标题开始
        - 包含 Description 和 Parameters 两个部分
        - 参数说明包括参数名、类型、是否必需和描述
        
        特殊情况：
        - 如果没有可用工具，返回 "暂无可用工具"
        - 如果工具没有参数，Parameters 部分显示 "无需参数"
    
    示例:
        >>> result = get_tool_descriptions_for_prompt()
        >>> print(result)
        ### Tool: `web_search`
        **Description**: 使用搜索引擎查询互联网信息，获取最新的网络资讯
        **Parameters**:
        - query (str, required): 搜索查询关键词
        - max_results (int, optional): 最大返回结果数，默认为5
        - language (str, optional): 结果语言偏好，默认为"zh-CN"
        
        ### Tool: `knowledge_base`
        **Description**: 检索企业知识库中的文档和信息
        **Parameters**:
        - query (str, required): 检索关键词
        - collection (str, optional): 指定检索的知识库集合
        - top_k (int, optional): 返回最相关的文档数，默认为3
        
        ### Tool: `pandas_data_calculator`
        **Description**: 使用pandas进行表格数据计算和分析
        **Parameters**:
        - data (dict, required): 表格数据，格式为 {"columns": [...], "data": [...]}
        - operation (str, required): 要执行的操作类型
        - params (dict, optional): 操作相关的参数配置
        
        >>> # 当没有工具时
        >>> # 假设 registry 中没有 libs 类别的工具
        >>> result = get_tool_descriptions_for_prompt()
        >>> print(result)
        暂无可用工具
    """
    registry = ToolRegistry()
    tool_descriptions = []
    
    # 获取所有工具，然后筛选出tools.libs目录下的工具
    all_tools = list(registry.list_tools_with_details())
    
    # 筛选出libs目录下的工具，但排除generator目录
    libs_tools = []
    for tool_info in all_tools:
        tool_name = tool_info.get("name", "")
        try:
            # 获取工具类来检查其模块路径
            tool_class = registry.get_tool(tool_name)
            if tool_class:
                module_path = tool_class.__module__
                # 检查是否在tools.libs路径下，但排除generator子目录
                if module_path.startswith("tools.libs.") and not module_path.startswith("tools.libs.generator"):
                    libs_tools.append(tool_info)
        except:
            pass
    
    if not libs_tools:
        return "暂无可用工具"
    
    for tool_info in libs_tools:
        tool_name = tool_info.get("name", "unknown")
        description = tool_info.get("description", "无描述")
        
        try:
            # 获取工具类并实例化
            tool_class = registry.get_tool(tool_name)
            if not tool_class:
                continue
                
            tool_instance = tool_class()
            
            # 获取参数描述
            param_description = _get_formatted_parameter_description(tool_instance)
            
            # 构建工具描述
            tool_desc = _format_tool_description(tool_name, description, param_description)
            tool_descriptions.append(tool_desc)
            
        except Exception as e:
            # 如果获取工具实例失败，使用基本信息
            tool_desc = f"### Tool: `{tool_name}`\n"
            tool_desc += f"**Description**: {description}\n"
            tool_desc += f"**Parameters**: 参数信息不可用 (错误: {str(e)})"
            tool_descriptions.append(tool_desc)
    
    return "\n\n".join(tool_descriptions)


def _get_formatted_parameter_description(tool_instance) -> str:
    """
    获取格式化的参数描述。
    
    参数:
        tool_instance: 工具实例对象
    
    返回:
        str: 格式化的参数描述文本
    """
    try:
        # 尝试调用工具的 get_parameter_description 方法
        if hasattr(tool_instance, 'get_parameter_description'):
            param_desc = tool_instance.get_parameter_description()
            if param_desc:
                return param_desc
        
        # 如果没有该方法或返回空，尝试从参数schema获取
        if hasattr(tool_instance, 'get_parameters_schema'):
            schema = tool_instance.get_parameters_schema()
            return _format_parameters_from_schema(schema)
        
        # 如果都没有，返回默认信息
        return "无需参数"
        
    except Exception:
        return "参数信息不可用"


def _format_parameters_from_schema(schema: Dict[str, Any]) -> str:
    """
    从参数 schema 格式化参数描述。
    
    参数:
        schema: 参数的 JSON Schema
    
    返回:
        str: 格式化的参数列表
    """
    if not schema or not isinstance(schema, dict):
        return "无需参数"
    
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    if not properties:
        return "无需参数"
    
    param_lines = []
    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "any")
        param_desc = param_info.get("description", "")
        is_required = param_name in required
        
        # 构建参数行
        required_text = "required" if is_required else "optional"
        
        if param_desc:
            line = f"- {param_name} ({param_type}, {required_text}): {param_desc}"
        else:
            line = f"- {param_name} ({param_type}, {required_text})"
        
        # 添加默认值信息（如果有）
        if "default" in param_info:
            line += f"，默认为 {param_info['default']}"
        
        param_lines.append(line)
    
    return "\n".join(param_lines)


def _format_tool_description(tool_name: str, description: str, param_description: str) -> str:
    """
    格式化单个工具的完整描述。
    
    参数:
        tool_name: 工具名称
        description: 工具描述
        param_description: 参数描述
    
    返回:
        str: 格式化的工具描述文本
    
    示例:
        >>> desc = _format_tool_description(
        ...     "web_search", 
        ...     "搜索互联网信息",
        ...     "- query (str, required): 搜索关键词"
        ... )
        >>> print(desc)
        ### Tool: `web_search`
        **Description**: 搜索互联网信息
        **Parameters**:
        - query (str, required): 搜索关键词
    """
    tool_desc = f"### Tool: `{tool_name}`\n"
    tool_desc += f"**Description**: {description}\n"
    tool_desc += f"**Parameters**:\n{param_description}"
    return tool_desc