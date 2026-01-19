"""
文本生成工具模块 (Text Generator Tool)

该模块提供了基于大语言模型的文本生成功能，支持多种文本处理任务如内容生成、文档分析、
摘要提取、问题解答、信息提取、文本改写、翻译等。

========================================
输入输出规范
========================================

输入参数 (TextGeneratorInput):
- query (必需): 文本生成指令或要求
- referenced_data (可选): 引用数据对象
  ├── documents: 文档数据 {文档ID: 文档内容(Markdown)}
  ├── tables: 表格数据 {表格ID: 表格数据}
  └── action_results: 历史执行结果 {action_id: 执行结果}
- message (可选): query的别名
- model_name (可选): 指定使用的模型名称

execute方法参数:
- tool_input (Dict[str, Any]): 包含上述输入参数
- runtime_state (Any): 运行时状态信息
- user_id (Optional[Union[str, int]]): 用户标识符，用于个性化服务和日志追踪

输出格式:
- status: 执行状态 ("success" | "error")
- output: 生成的文本内容
- type: 输出类型 ("text")
- raw_data: 原始数据包括生成文本、使用模型、增强消息
- metrics: 执行指标数组
- metadata: 元数据信息
- message: 状态消息

========================================
内部处理流程
========================================

1. 参数验证与预处理
   ├── 提取用户消息 (query 或 message)
   ├── 验证必需的 user_id 参数
   └── 获取可选的 referenced_data

2. 上下文增强处理
   ├── 调用 _format_referenced_data() 格式化引用数据
   ├── 将格式化后的数据追加到用户消息中
   └── 构造增强消息 (enhanced_message)

3. LLM 调用与响应生成
   ├── 调用 _generate_chat_response() 生成文本
   ├── 使用 CoreLLMService 获取结构化LLM调用器
   ├── 基于 TextGenerationResponse 模式生成结构化输出
   └── 返回生成的文本内容

4. 结果封装与返回
   ├── 封装成功响应 (包含输出、指标、元数据)
   └── 异常处理与错误响应

========================================
函数调用关系
========================================

TextGeneratorTool.execute()
├── _format_referenced_data()  # 格式化引用数据
│   ├── 处理 documents 数据
│   ├── 处理 tables 数据 (使用 json.dumps)
│   └── 处理 action_results 数据
└── _generate_chat_response()  # 生成聊天响应
    ├── CoreLLMService()  # 初始化LLM核心服务
    ├── ModelConfigManager()  # 初始化模型配置管理器
    ├── config_manager.get_model_config()  # 获取模型配置
    ├── core_service.get_structured_llm()  # 获取结构化LLM
    └── structured_llm.invoke()  # 调用LLM生成响应

========================================
外部函数依赖 (非Python标准库)
========================================

工具框架依赖:
- tools.core.base.BaseTool: 工具基类
- tools.core.registry.register_tool: 工具注册装饰器
- tools.core.types.ToolType: 工具类型枚举

LLM服务依赖:
- llm.core_service.CoreLLMService: LLM核心服务类
- llm.config_manager.ModelConfigManager: 模型配置管理器
- router.models.LLMModel: LLM模型ORM模型

数据结构:
- pydantic.BaseModel: Pydantic基础模型类
- pydantic.Field: 字段定义装饰器

日志记录:
- Django日志系统: logger.getLogger("django")

========================================
特殊处理机制
========================================

1. 引用数据处理: 支持Markdown文档、JSON表格和历史执行结果的上下文整合
2. 结构化输出: 使用Pydantic模式确保输出格式一致性
3. 错误容错: 完整的异常捕获和错误信息返回
4. 模型灵活性: 支持动态模型选择和配置
5. 用户个性化: 基于user_id提供个性化服务

注意事项:
- user_id 现在作为 execute 方法的参数传入，不再在 tool_input 中
- 支持多种数据源的上下文整合
- 输出遵循统一的响应格式规范
"""

import os
from tools.core.base import BaseTool
from tools.core.registry import register_tool
from tools.core.types import ToolType
from tools.libs.generator.utils import (
    extract_context_from_state,
    format_tool_outputs_as_text,
    get_preprocessed_documents,
    get_preprocessed_tables
)
from llm.core_service import CoreLLMService
from llm.config_manager import ModelConfigManager
from router.models import LLMModel
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import json

import logging
logger = logging.getLogger("django")

class TextGenerationResponse(BaseModel):
    """文本生成的输出模式"""
    response: str = Field(description="根据指令生成的文本内容")
    title: str = Field(description="为生成的内容创建一个简短的标题，概括主要内容")


class TextGeneratorInput(BaseModel):
    """文本生成器工具输入参数模型 - 接收完整的 RuntimeState"""
    state: Dict[str, Any] = Field(description="运行时状态，包含所有执行历史和上下文")
    # 可选的模型指定
    model_name: Optional[str] = Field(
        default=None,
        description="指定使用的模型名称"
    )

@register_tool(
    name="TextGenerator",
    description="【通用文本对话工具】适用于日常对话、简单问答和基础文本生成任务。输入：文本指令+可选上下文数据。输出：自然语言文本回复。适用场景：问候对话、简单问题解答、日常交流、短文本创作、内容润色等。对于复杂报告生成或语言翻译任务，请使用专门的ReportGenerator或Translator工具。",
    tool_type=ToolType.GENERATOR,
    category="generator"
)
class TextGeneratorTool(BaseTool):
    """文本生成工具"""

    def get_input_schema(self) -> Dict[str, Any]:
        return TextGeneratorInput.model_json_schema()
    
    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        # 使用Pydantic模型验证输入
        try:
            parsed_input = TextGeneratorInput(**tool_input)
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
        
        # 获取用户消息（使用本轮用户输入或任务目标）
        user_message = context['user_prompt'] or context['task_goal']
        model_name = parsed_input.model_name or self.config.get('model_name', os.getenv('DEFAULT_MODEL', 'gemini-2.5-flash'))
        
        # 构建增强消息（添加工具输出和预处理文件作为上下文）
        enhanced_message = user_message
        
        # 添加工具输出上下文
        if context['tool_outputs']:
            formatted_outputs = format_tool_outputs_as_text(context['tool_outputs'])
            enhanced_message = f"{enhanced_message}\n\n===执行历史数据===\n{formatted_outputs}"
            logger.info(f"[TEXT_GENERATOR] 提取到 {len(context['tool_outputs'])} 个工具输出，格式化后长度: {len(formatted_outputs)} 字符")
        
        # 添加预处理文件上下文（如果有）
        documents = get_preprocessed_documents(context['preprocessed_files'])
        tables = get_preprocessed_tables(context['preprocessed_files'])
        
        if documents:
            doc_text = "\n\n".join([f"文档：{name}\n{content}" for name, content in documents.items()])
            enhanced_message = f"{enhanced_message}\n\n===文档数据===\n{doc_text}"
        
        if tables:
            table_text = "\n\n".join([f"表格：{name}\n{json.dumps(data, ensure_ascii=False, indent=2)}" for name, data in tables.items()])
            enhanced_message = f"{enhanced_message}\n\n===表格数据===\n{table_text}"
        
        try:
            logger.info(f"[TEXT_GENERATOR] 使用模型: {model_name}")
            logger.info(f"[TEXT_GENERATOR] 准备调用LLM，enhanced_message长度: {len(enhanced_message)} 字符")
            logger.debug(f"[TEXT_GENERATOR] enhanced_message内容: {enhanced_message[:500]}...")
            response = self._generate_chat_response(enhanced_message, model_name, user_id)
            response_content = response['content']
            response_title = response['title']
            logger.info(f"[TEXT_GENERATOR] LLM返回内容长度: {len(response_content)} 字符")
            return {
                "status": "success",
                "output": response_content,
                "type": "text",
                "raw_data": {
                    "generated_text": response_content,
                    "model_used": model_name,
                    "enhanced_message": enhanced_message
                },
                "metrics": [
                    f"输入长度: {len(user_message)} 字符",
                    f"输出长度: {len(response_content)} 字符",
                    f"使用模型: {model_name}",
                    f"包含上下文数据: {'是' if (context['tool_outputs'] or documents or tables) else '否'}"
                ],
                "metadata": {
                    "title": response_title,
                    "user_message": user_message,
                    "user_id": user_id,
                    "has_context_data": bool(context['tool_outputs'] or documents or tables)
                },
                "message": "文本生成完成"
            }
        except Exception as e:
            return {
                "status": "error",
                "output": f"生成失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "user_message": user_message,
                    "error": str(e),
                    "user_id": user_id
                },
                "message": f"文本生成服务暂时不可用: {str(e)}"
            }
    
    def _generate_chat_response(self, message: str, model_name: str, user_id: Optional[Union[str, int]]) -> Dict[str, str]:
        # 直接使用 CoreLLMService 和 ModelConfigManager
        core_service = CoreLLMService()
        config_manager = ModelConfigManager()
        
        # 获取模型配置
        model_config = config_manager.get_model_config(model_name)
        
        # 获取结构化 LLM 调用器
        structured_llm = core_service.get_structured_llm(
            output_schema=TextGenerationResponse,
            model_config=model_config,
            model_name=model_name,
            source_app='tools',
            source_function='chat.TextGenerator'
        )
        
        # 构建提示词
        prompt = f"""文本生成任务：

生成要求：
{message}

重要提示：
1. 根据上述要求生成相应的文本内容
2. 如果包含【相关数据】部分，必须基于这些数据进行生成
3. 不要捏造或想象不存在的内容
4. 如果数据不足以完成生成任务，请明确指出
5. 为你生成的内容创建一个简短的标题（10个字以内），概括主要内容

请生成文本内容和标题："""
        
        # 调用 LLM
        logger.info(f"[TEXT_GENERATOR] 准备调用structured_llm.invoke，prompt长度: {len(prompt)} 字符")
        response = structured_llm.invoke(prompt)
        logger.info(f"[TEXT_GENERATOR] structured_llm返回类型: {type(response)}, response对象: {response}")

        logger.info(f"[text generation] LLM response: {response.response}, title: {response.title}")

        # 返回响应内容和标题
        return {
            'content': response.response.strip() if response and hasattr(response, 'response') else str(response),
            'title': response.title if response and hasattr(response, 'title') else '文本生成完成'
        }
    
