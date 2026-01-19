# -*- coding: utf-8 -*-
"""
output_format.py

定义工具层的统一输出格式。

设计原则：
1. 工具产出的是语义化的上下文，而非结构化数据
2. output 必须是下游节点（reflection/planner）能直接理解的模态数据
3. 工具的核心职责是生成可用的上下文，为最终的答案生成提供素材
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ToolOutputFormat(BaseModel):
    """
    工具层的统一输出格式。
    
    所有工具必须返回这种格式，确保下游节点能够统一处理。
    """
    
    # 执行状态
    status: Literal["success", "error", "partial"] = Field(
        description="工具执行状态：success-成功，error-失败，partial-部分成功"
    )
    
    # 核心输出：语义化的模态数据
    output: Any = Field(
        description="""
        工具的语义化输出，必须是下游节点能理解的模态数据。
        例如：
        - GoogleSearch: 搜索结果的文本总结（带引用标记）
        - calculator: 计算结果的文本描述
        - pandas_data_calculator: 数据分析的文本报告或图表
        - report_generator: 生成的报告全文
        这是工具真正的产出，用于构建最终答案的上下文。
        """
    )
    
    # 输出类型
    type: Literal["text", "markdown", "chart", "image", "mixed"] = Field(
        default="text",
        description="""
        output 的模态类型，帮助下游节点理解如何处理：
        - text: 纯文本
        - markdown: Markdown格式文本（包含表格、列表等）
        - chart: 图表数据（如 echarts 配置）
        - image: 图片（base64 或 URL）
        - mixed: 混合类型（包含多种模态）
        """
    )
    
    # 原始数据：工具核心能力的完整输出
    raw_data: Optional[Any] = Field(
        default=None,
        description="""
        工具核心能力的原始输出，保留完整信息供需要时使用。
        例如：
        - GoogleSearch: 包含所有搜索结果和引用的详细数据
        - pandas_data_calculator: 完整的数据分析结果
        output 是 raw_data 的语义化表达。
        """
    )
    
    # 关键指标：文本化的度量信息
    metrics: List[str] = Field(
        default_factory=list,
        description="""
        关键指标的文本描述列表，直接可读，无需解析。
        例如：
        - ["找到5条相关结果", "覆盖3个主要来源"]
        - ["计算耗时0.3秒", "处理了1000行数据"]
        - ["生成报告3500字", "包含5个章节"]
        """
    )
    
    # 元数据
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
        执行元数据，包含：
        - tool_input: 工具输入参数
        - execution_time: 执行耗时
        - model_used: 使用的模型（如适用）
        - 其他工具特定的元信息
        """
    )
    
    # 简要消息
    message: str = Field(
        default="",
        description="一句话描述执行情况，用于日志和摘要"
    )


class ToolOutputValidator:
    """工具输出格式验证器"""
    
    @staticmethod
    def validate(output: Dict[str, Any]) -> bool:
        """
        验证输出是否符合标准格式。
        
        参数:
            output: 待验证的输出字典
            
        返回:
            bool: 是否符合标准格式
        """
        required_fields = {"status", "output", "type"}
        return all(field in output for field in required_fields)
    
    @staticmethod
    def ensure_format(output: Any) -> Dict[str, Any]:
        """
        确保输出符合标准格式，必要时进行转换。
        
        参数:
            output: 工具的原始输出
            
        返回:
            符合标准格式的输出字典
        """
        # 如果已经是标准格式，直接返回
        if isinstance(output, dict) and ToolOutputValidator.validate(output):
            return output
        
        # 否则进行智能转换
        if isinstance(output, str):
            # 纯字符串输出
            return {
                "status": "success",
                "output": output,
                "type": "text",
                "metrics": [],
                "metadata": {},
                "message": "执行成功"
            }
        
        elif isinstance(output, dict):
            # 尝试从旧格式转换
            status = output.get("status", "success")
            
            # 智能提取 output
            possible_output_keys = ["data", "result", "content", "text", "output"]
            main_output = None
            for key in possible_output_keys:
                if key in output:
                    main_output = output[key]
                    break
            
            if main_output is None:
                # 如果没有找到，使用整个字典（排除元数据字段）
                exclude_keys = {"status", "message", "error", "timestamp"}
                main_output = {k: v for k, v in output.items() if k not in exclude_keys}
            
            # 判断输出类型
            output_type = "text"
            if isinstance(main_output, str):
                if "```" in main_output or "#" in main_output:
                    output_type = "markdown"
            elif isinstance(main_output, dict) and "chart" in str(main_output).lower():
                output_type = "chart"
            
            return {
                "status": status,
                "output": main_output,
                "type": output_type,
                "raw_data": output,
                "metrics": [],
                "metadata": {},
                "message": output.get("message", "")
            }
        
        else:
            # 其他类型，包装为标准格式
            return {
                "status": "success",
                "output": str(output),
                "type": "text",
                "raw_data": output,
                "metrics": [],
                "metadata": {},
                "message": "执行成功"
            }


# 导出供其他模块使用
__all__ = ["ToolOutputFormat", "ToolOutputValidator"]