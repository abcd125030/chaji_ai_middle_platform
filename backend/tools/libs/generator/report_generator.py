"""
专业报告生成工具模块

本模块实现了一个专业的报告生成工具，作为输出工具链的核心组件，负责将各种数据源整合并生成结构化的专业报告。

## 输入输出说明

### 输入参数 (ReportGeneratorInput)
- topic (必需): str - 报告的主题或标题
- report_structure (可选): str - 指定的报告内容结构和章节安排
- requirements (可选): str - 对报告的具体要求和重点描述  
- background_info (可选): str - 相关背景信息或上下文

### execute方法参数
- tool_input (Dict[str, Any]): 包含上述输入参数
- runtime_state (Any): 运行时状态信息
- user_id (Optional[Union[str, int]]): 用户标识符，用于个性化服务和日志追踪

### 输出格式
- status: str - 执行状态 ("success" | "error")
- output: str - 生成的Markdown格式报告内容
- type: str - 输出类型 ("markdown" | "text")
- raw_data: dict - 原始数据，包含输入参数和处理结果
- metrics: list - 执行指标（报告长度、章节数量等）
- metadata: dict - 元数据信息
- message: str - 执行结果描述

## 内部处理流程

1. **参数解析**: 从tool_input中提取topic、report_structure、requirements、background_info
2. **报告生成**: 调用_generate_report方法，使用LLM生成专业报告
3. **结果包装**: 将生成的报告内容包装为标准化的工具输出格式
4. **异常处理**: 捕获并处理生成过程中的异常

### _generate_report 内部逻辑
1. **提示词构建**: 根据输入参数构建结构化的LLM提示词
2. **LLM配置**: 获取CoreLLMService实例和模型配置
3. **结构化输出**: 使用ReportOutput模式确保输出格式一致
4. **内容生成**: 调用LLM生成专业报告内容

## 函数调用关系

### 主要调用链路
ReportGeneratorTool.execute() 
  └── _generate_report()
      ├── CoreLLMService() - 获取LLM服务实例
      ├── ModelConfigManager() - 获取模型配置管理器
      ├── config_manager.get_model_config() - 获取指定模型配置
      ├── core_service.get_structured_llm() - 获取结构化LLM实例
      └── structured_llm.invoke() - 调用LLM生成报告

### 类继承关系
ReportGeneratorTool extends BaseTool
  └── 实现抽象方法: get_input_schema(), execute()

## 外部依赖函数

### 工具框架依赖 (tools.*)
- tools.core.registry.register_tool: 工具注册装饰器，将工具注册到系统中
- tools.core.types.ToolType: 工具类型枚举，定义工具分类
- tools.core.base.BaseTool: 工具基类，提供工具标准接口

### LLM服务依赖 (llm.*)
- llm.core_service.CoreLLMService: 核心LLM服务类，提供统一的LLM调用接口
  * get_structured_llm(): 获取结构化输出的LLM实例
- llm.config_manager.ModelConfigManager: 模型配置管理器
  * get_model_config(): 根据模型名称获取对应的配置参数

### 配置获取
- self.config.get(): 获取工具配置中的参数
- os.getenv(): 获取环境变量配置（如DEFAULT_MODEL）

## 设计模式与架构

- **工厂模式**: 通过CoreLLMService获取不同类型的LLM实例
- **模板方法**: BaseTool定义工具执行模板，子类实现具体逻辑
- **结构化输出**: 使用Pydantic的BaseModel确保输出格式一致性
- **装饰器模式**: @register_tool自动注册工具到系统

## 使用场景

- 研究报告生成：将收集的数据整理为专业研究报告
- 深度分析报告：对复杂问题进行深入分析并输出结构化报告  
- 综合评估报告：汇总多方面信息生成评估文档
- 汇总文档：将散乱信息整合为有序的文档输出

"""

from tools.core.registry import register_tool
from tools.core.types import ToolType
from tools.core.base import BaseTool
from llm.core_service import CoreLLMService
from llm.config_manager import ModelConfigManager
from tools.libs.generator.utils import (
    extract_context_from_state,
    format_tool_outputs_as_json
)
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import os
import logging

logger = logging.getLogger('django')

class ReportOutput(BaseModel):
    """报告生成的输出格式"""
    report_content: str = Field(description="生成的报告内容")
    report_structure: str = Field(description="报告的结构大纲")
    title: str = Field(description="报告的标题，简明扼要地概括报告的主要内容")


class ReportGeneratorInput(BaseModel):
    """报告生成器工具输入参数模型 - 接收完整的 RuntimeState"""
    state: Dict[str, Any] = Field(description="运行时状态，包含所有执行历史和上下文")
    # 可选的额外指导参数（用于兼容旧版本）
    output_guidance: Optional[Dict[str, Any]] = Field(
        default=None,
        description="输出指导信息，包含格式要求、重点等"
    )

@register_tool(
    name="ReportGenerator",
    description="【复杂报告生成工具】专门用于生成结构化的专业报告，适用于需要整合多源数据并进行深度分析的复杂任务。输入：主题+结构化要求+背景信息+引用数据。输出：完整的Markdown格式专业报告。适用场景：研究报告、深度分析报告、综合评估报告、项目总结报告等需要专业格式化输出的复杂场景。不适用于简单对话或短文本生成。",
    tool_type=ToolType.GENERATOR,
    category="generator"
)
class ReportGeneratorTool(BaseTool):
    """
    专业报告输出工具：作为输出工具链的核心组件，负责将数据转换为结构化报告
    
    主要功能：
    - 数据整合：汇总多源数据（文档、表格、执行结果）
    - 格式化输出：生成符合专业标准的Markdown报告
    - 智能结构：根据内容自动确定报告结构
    - 质量保证：确保输出的准确性和专业性
    """
    
    def get_input_schema(self) -> Dict[str, Any]:
        """返回工具输入的JSON Schema定义"""
        return ReportGeneratorInput.model_json_schema()
    
    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        # 使用Pydantic模型验证输入
        try:
            parsed_input = ReportGeneratorInput(**tool_input)
        except Exception as e:
            return {
                "status": "error",
                "output": f"输入参数验证失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "error_type": "ValidationError",
                    "user_id": user_id
                },
                "message": f"输入参数验证失败: {str(e)}"
            }
        
        # 从 state 中提取上下文
        context = extract_context_from_state(parsed_input.state)
        
        # 获取基本参数
        topic = context['task_goal']  # 使用原始任务目标作为主题
        
        # 从 output_guidance 中提取指导信息（如果有）
        output_guidance = parsed_input.output_guidance or {}
        report_structure = output_guidance.get('format_requirements', '')
        requirements = output_guidance.get('key_points', '')
        if isinstance(requirements, list):
            requirements = ', '.join(requirements)
        
        # 构建背景信息：包含收集到的工具输出
        background_info = output_guidance.get('quality_requirements', '')
        
        # 添加工具输出作为参考数据
        if context['tool_outputs']:
            reference_data = format_tool_outputs_as_json(context['tool_outputs'])
            background_info = f"{background_info}\n\n参考数据：\n{reference_data}" if background_info else f"参考数据：\n{reference_data}"
        
        try:
            # 生成报告
            report_result = self._generate_report(
                topic=topic,
                report_structure=report_structure,
                requirements=requirements,
                background_info=background_info
            )
            report_content = report_result['content']
            report_title = report_result['title']
            
            return {
                "status": "success",
                "output": report_content,
                "type": "markdown",
                "raw_data": {
                    "title": report_title,
                    "final_answer": report_content,
                    "report_structure": report_structure,
                    "requirements": requirements,
                    "background_info": background_info
                },
                "metrics": [
                    f"报告长度: {len(report_content)} 字符",
                    f"章节数量: {report_content.count('#')} 个",
                    f"输出格式: Markdown",
                    f"结构指定: {'是' if report_structure else '否'}"
                ],
                "metadata": {
                    "title": report_title,
                    "has_report_structure": bool(report_structure),
                    "has_requirements": bool(requirements),
                    "has_background": bool(background_info),
                    "tool_category": "output_tools",
                    "tool_name": "report_generator",
                    "user_id": user_id
                },
                "message": f"成功输出关于「{report_title}」的专业报告"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "output": f"报告生成失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "title": topic,
                    "error": str(e),
                    "tool_name": "report_generator",
                    "user_id": user_id
                },
                "message": f"报告生成失败: {str(e)}"
            }
    
    def _generate_report(self, topic: str, report_structure: str, requirements: str, 
                        background_info: str) -> Dict[str, str]:
        """使用LLM生成专业格式化报告
        
        作为输出工具，负责：
        1. 整合多源数据
        2. 按照指定结构生成内容
        3. 确保输出质量
        
        Args:
            topic: 报告主题
            report_structure: 报告内容结构安排
            requirements: 具体要求
            background_info: 背景信息
        """
        
        # 构建提示词 - 强调作为输出工具的职责
        prompt = f"""作为专业报告输出工具，请根据以下收集到的信息生成一份结构化的专业报告。

# 报告主题
{topic}

# 报告内容结构
{report_structure if report_structure else "根据内容自动确定合适的报告结构"}

# 具体要求
{requirements if requirements else "无特殊要求"}

# 背景信息
{background_info if background_info else "无背景信息"}

# 输出格式要求
1. 使用标准Markdown格式输出
2. 结构层次分明，使用合适的标题层级（#, ##, ###）
3. 内容准确、客观、专业，符合行业标准
4. {"按照指定的报告结构组织内容" if report_structure else "根据内容自动优化报告结构"}
5. 包含执行摘要、主体内容、结论建议等关键部分

# 输出质量标准
- 确保逻辑清晰、论述完整
- 输出内容可直接用于专业场景
{"- 严格遵循指定的内容结构安排" if report_structure else ""}
- 为报告创建一个简明扼要的标题，准确概括报告的主要内容

请生成高质量的专业报告："""
        
        # 直接使用CoreLLMService生成报告
        core_service = CoreLLMService()
        config_manager = ModelConfigManager()
        model_name = self.config.get('model_name', os.getenv('DEFAULT_MODEL', 'gemini-2.5-flash'))
        
        # 获取模型配置
        model_config = config_manager.get_model_config(model_name)
        
        structured_llm = core_service.get_structured_llm(
            output_schema=ReportOutput,
            model_config=model_config,
            model_name=model_name,
            source_app='tools',
            source_function='report_generator'
        )
        
        result = structured_llm.invoke(prompt)
        
        return {
            'content': result.report_content if hasattr(result, 'report_content') else str(result),
            'title': result.title if hasattr(result, 'title') else topic
        }
    
