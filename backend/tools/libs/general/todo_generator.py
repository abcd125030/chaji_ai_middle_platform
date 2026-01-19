"""
TODO任务清单生成工具模块

此模块实现了将非结构化文本转换为结构化TODO任务清单的功能，是agentic工具系统的一个核心组件。
通过接收任意形式的文本描述（如会议记录、需求文档、邮件内容等），利用LLM的自然语言理解能力，
智能分析并生成可执行的结构化任务列表。

## 输入输出规范

### 输入参数 (TodoGeneratorInput)
- text_input (str, 必需): 非结构化的文本输入，支持任意格式的文本描述
- context (str, 可选): 额外的背景信息，帮助更好理解文本内容
- priority_hint (str, 可选): 优先级提示，默认为"常规"
- model_name (str, 可选): 指定使用的LLM模型，默认从配置中获取

### execute方法参数
- tool_input (Dict[str, Any]): 包含上述输入参数
- runtime_state (Any): 运行时状态信息
- user_id (Optional[Union[str, int]]): 用户标识符，用于个性化服务和日志追踪

### 输出格式
标准化的工具输出包含：
- status: 执行状态 (success/error)
- output: 语义化的markdown格式文本，可直接展示给用户
- type: 输出类型标识 ("markdown")
- raw_data: 结构化的原始数据 (TodoListResponse对象的字典形式)
- metrics: 关键指标列表
- metadata: 元数据信息
- message: 执行结果消息

## 内部处理流程

1. **输入验证阶段**
   - 验证必需参数user_id和text_input的存在性
   - 提取可选参数并设置默认值

2. **LLM分析阶段**
   - 构建专门的prompt模板，引导LLM进行任务分析
   - 通过CoreLLMService获取结构化LLM调用器
   - 使用ModelConfigManager管理模型配置
   - 调用LLM生成结构化的TodoListResponse

3. **数据处理阶段**
   - 将Pydantic模型转换为字典格式
   - 格式化输出为用户友好的markdown文本
   - 构建完整的工具输出结构

4. **异常处理阶段**
   - 捕获并处理LLM调用异常
   - 在失败时提供默认的任务模板
   - 记录详细的错误信息用于调试

## 核心类和函数关系

### 数据模型类
- TodoItem: 单个任务项的数据结构定义
  - 包含任务描述、依赖关系、建议工具、执行提示等字段
  - 支持任务状态管理和重试机制
- TodoListResponse: 完整TODO清单的数据结构
  - 包含任务列表和整体摘要信息

### 主要功能类
- TodoGeneratorTool: 核心工具类，继承自BaseTool
  - get_input_schema(): 定义输入参数的JSON Schema
  - execute(): 主要执行逻辑，协调整个处理流程
  - _generate_todo_list(): 核心LLM调用逻辑
  - _format_todo_output(): 格式化输出为markdown文本

## 外部依赖和调用关系

### 工具框架依赖
- tools.core.base.BaseTool: 工具基类，定义工具接口规范
- tools.core.registry.register_tool: 工具注册装饰器，用于工具发现和管理
- tools.core.types.ToolType: 工具类型枚举定义

### LLM服务依赖
- llm.core_service.CoreLLMService: 核心LLM服务类
  - get_structured_llm(): 获取支持结构化输出的LLM调用器
- llm.config_manager.ModelConfigManager: 模型配置管理器
  - get_model_config(): 获取指定模型的配置信息

### 调用流程说明
1. 工具通过@register_tool装饰器注册到工具系统
2. 运行时通过BaseTool接口被调用
3. 内部通过CoreLLMService获取LLM能力
4. 使用ModelConfigManager管理模型配置
5. 返回标准化的工具输出格式

## 技术特点

- 支持任意非结构化文本输入的智能解析
- 基于Pydantic的严格数据结构定义
- 完整的错误处理和容错机制
- 结构化的LLM输出确保数据一致性
- 用户友好的markdown格式输出
- 详细的日志记录支持调试和监控

## 使用场景

- 会议记录转TODO清单
- 需求文档任务分解
- 邮件内容行动项提取
- 口头指示结构化整理
- 项目计划任务梳理
"""

import os
from typing import Dict, Any, List, Optional, Union
from tools.core.base import BaseTool
from tools.core.registry import register_tool
from tools.core.types import ToolType
from tools.core.output_format import ToolOutputFormat
from llm.core_service import CoreLLMService
from llm.config_manager import ModelConfigManager
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger("django")

class TodoItem(BaseModel):
    """单个TODO任务项"""
    id: int = Field(description="任务编号")
    task: str = Field(description="任务描述")
    dependencies: List[int] = Field(default_factory=list, description="依赖的任务编号列表")
    suggested_tools: List[str] = Field(default_factory=list, description="建议使用的工具")
    execution_tips: str = Field(default="", description="执行建议或注意事项")
    success_criteria: str = Field(description="完成标准")
    status: str = Field(default="pending", description="任务状态: pending(待执行)/processing(执行中)/completed(已完成)/failed(失败)")
    retry: int = Field(default=0, description="当前重试次数")
    max_retry: int = Field(default=2, description="最大重试次数")

class TodoListResponse(BaseModel):
    """TODO清单输出格式"""
    todo_list: List[TodoItem] = Field(description="任务清单")
    summary: str = Field(description="任务清单摘要")


class TodoGeneratorInput(BaseModel):
    """TODO生成器工具输入参数模型"""
    text_input: str = Field(description="非结构化的文本输入，如会议记录、需求描述、邮件内容、口头指示等")
    context: Optional[str] = Field(
        default="",
        description="额外的背景信息，帮助更好地理解文本内容"
    )
    priority_hint: Optional[str] = Field(
        default="常规",
        description="优先级提示，如'紧急'、'重要'、'常规'等"
    )
    model_name: Optional[str] = Field(
        default=None,
        description="指定使用的LLM模型"
    )

@register_tool(
    name="TodoGenerator",
    description="将非结构化的文本信息转换为结构化的TODO任务清单。接收任意文本描述（如会议记录、需求文档、口头指示等），通过LLM分析理解后生成可执行的结构化任务列表。",
    tool_type=ToolType.GENERAL,
    category="general"
)
class TodoGeneratorTool(BaseTool):
    """TODO任务清单生成工具 - 将非结构化文本转换为结构化任务列表"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return TodoGeneratorInput.model_json_schema()
    
    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        # 使用Pydantic模型验证输入
        try:
            parsed_input = TodoGeneratorInput(**tool_input)
        except Exception as e:
            return {
                "status": "error",
                "output": f"输入参数验证失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "error_type": "ValidationError"
                },
                "message": f"输入参数验证失败: {str(e)}"
            }
        
        text_input = parsed_input.text_input
        context = parsed_input.context
        priority_hint = parsed_input.priority_hint
        model_name = parsed_input.model_name or self.config.get('model_name', os.getenv('DEFAULT_MODEL', 'Groq GPT OSS 120b'))
        
        try:
            todo_response = self._generate_todo_list(
                text_input, 
                context,
                priority_hint,
                model_name
            )
            
            # 转换为字典格式
            todo_dict = todo_response.model_dump() if hasattr(todo_response, 'model_dump') else todo_response
            
            # 构建语义化的输出文本
            output_text = self._format_todo_output(todo_dict, priority_hint)
            
            # 构建关键指标列表
            metrics_list = [
                f"生成了{len(todo_dict.get('todo_list', []))}个任务",
                f"优先级: {priority_hint}",
                f"使用模型: {model_name}"
            ]
            
            return {
                "status": "success",
                "output": output_text,  # 语义化的文本输出，下游节点可直接使用
                "type": "markdown",     # 输出类型为markdown格式
                "raw_data": todo_dict,  # 保留原始的结构化数据
                "metrics": metrics_list,
                "metadata": {
                    "tool_input": {
                        "text_input": text_input[:500] + "..." if len(text_input) > 500 else text_input,
                        "context": context,
                        "priority_hint": priority_hint
                    },
                    "model_used": model_name,
                    "summary": todo_dict.get('summary', ''),
                    "user_id": user_id
                },
                "message": f"成功从文本生成{len(todo_dict.get('todo_list', []))}个TODO任务"
            }
        except Exception as e:
            logger.error(f"[TodoGenerator] Error generating todo list: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "output": f"无法生成TODO清单: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "tool_input": {
                        "text_input": text_input[:500] + "..." if len(text_input) > 500 else text_input,
                        "context": context,
                        "priority_hint": priority_hint
                    },
                    "error": str(e),
                    "user_id": user_id
                },
                "message": f"TODO清单生成失败: {str(e)}"
            }
    
    def _generate_todo_list(
        self, 
        text_input: str, 
        context: str,
        priority_hint: str,
        model_name: str
    ) -> TodoListResponse:
        """从非结构化文本生成结构化TODO任务清单"""
        
        # 构建提示词 - 专注于从非结构化文本提取和结构化任务
        prompt = f"""你是一个专业的任务分析助手，擅长从非结构化的文本中提取、理解并生成结构化的TODO任务清单。

## 输入文本
以下是需要分析的非结构化文本内容：
---
{text_input}
---

{f'## 背景信息\n{context}' if context else ''}

## 优先级提示
{priority_hint}

## 任务分析和生成要求

请仔细分析上述文本内容，理解其中包含的任务、需求或待办事项，然后生成一个结构化的TODO清单。

### 分析步骤：
1. **识别任务**：从文本中识别所有明确或隐含的任务、行动项、需求或待办事项
2. **理解上下文**：理解任务的背景、目的和重要性
3. **任务分解**：将复杂任务分解为可执行的具体步骤
4. **确定依赖**：识别任务之间的依赖关系和执行顺序
5. **设定标准**：为每个任务定义清晰的完成标准

### 生成要求：
1. **完整性**：确保不遗漏文本中提到的任何重要任务
2. **可操作性**：每个任务都应该是具体、可执行的动作
3. **结构化**：按照逻辑顺序组织任务，标注依赖关系
4. **执行指导**：
   - suggested_tools：建议使用的工具或方法（如需要特定工具，请推断合适的工具类型）
   - execution_tips：提供有价值的执行建议和注意事项
5. **完成标准**：每个任务都要有明确、可验证的完成标准（success_criteria）
6. **优先级考虑**：根据优先级提示（{priority_hint}）合理安排任务顺序

### 特别注意：
- 如果文本中没有明确的工具要求，suggested_tools 可以为空列表或建议通用工具
- 对于模糊或不完整的描述，基于常识和最佳实践进行合理推断
- 保持任务的原始意图，不要过度解读或添加无关任务
- 任务ID应该从1开始递增
- 依赖关系用任务ID列表表示（如 [1, 2] 表示依赖任务1和2）

### 输出摘要（summary）要求：
生成一个简洁的摘要，概括：
1. 总共识别了多少个任务
2. 主要的任务类别或领域
3. 整体的优先级和时间要求（如果文本中有提及）

请生成结构化的TODO清单。"""

        try:
            # 使用 CoreLLMService 和 ModelConfigManager
            core_service = CoreLLMService()
            config_manager = ModelConfigManager()
            
            # 获取模型配置
            model_config = config_manager.get_model_config(model_name)
            
            # 获取结构化 LLM 调用器
            structured_llm = core_service.get_structured_llm(
                output_schema=TodoListResponse,
                model_config=model_config,
                model_name=model_name,
                source_app='tools',
                source_function='todo_generator.TodoGenerator'
            )
            
            # 调用 LLM
            response = structured_llm.invoke(prompt)
            
            logger.info(f"[TodoGenerator] Successfully generated todo list with {len(response.todo_list)} tasks")
            
            return response
            
        except Exception as e:
            logger.error(f"[TodoGenerator] LLM call failed: {str(e)}")
            # 返回一个默认的响应
            return TodoListResponse(
                todo_list=[
                    TodoItem(
                        id=1,
                        task="分析输入文本并理解任务需求",
                        dependencies=[],
                        suggested_tools=[],
                        execution_tips="仔细阅读文本，识别关键任务和需求",
                        success_criteria="完成文本分析并确定主要任务"
                    ),
                    TodoItem(
                        id=2,
                        task="制定具体执行计划",
                        dependencies=[1],
                        suggested_tools=[],
                        execution_tips="基于识别的任务制定详细计划",
                        success_criteria="执行计划制定完成"
                    )
                ],
                summary="基础任务清单（自动生成失败，提供默认模板）- 包含2个基础任务"
            )
    
    def _format_todo_output(self, todo_dict: Dict[str, Any], priority_hint: str) -> str:
        """将结构化的TODO数据格式化为语义化的markdown文本"""
        
        lines = []
        
        # 添加标题和摘要
        lines.append("# TODO任务清单")
        lines.append("")
        
        # 添加摘要信息
        if todo_dict.get('summary'):
            lines.append(f"**摘要**: {todo_dict['summary']}")
            lines.append("")
        
        # 添加优先级信息
        lines.append(f"**优先级**: {priority_hint}")
        lines.append("")
        
        # 添加任务列表
        lines.append("## 任务列表")
        lines.append("")
        
        todo_list = todo_dict.get('todo_list', [])
        
        for item in todo_list:
            # 任务标题
            lines.append(f"### {item.get('id', 0)}. {item.get('task', '未命名任务')}")
            lines.append("")
            
            # 任务状态
            status = item.get('status', 'pending')
            status_text = {
                'pending': '待执行',
                'processing': '执行中',
                'completed': '已完成',
                'failed': '失败'
            }.get(status, status)
            lines.append(f"- **状态**: {status_text}")
            
            # 完成标准
            if item.get('success_criteria'):
                lines.append(f"- **完成标准**: {item['success_criteria']}")
            
            # 执行建议
            if item.get('execution_tips'):
                lines.append(f"- **执行建议**: {item['execution_tips']}")
            
            # 建议工具
            suggested_tools = item.get('suggested_tools', [])
            if suggested_tools:
                tools_str = ', '.join(suggested_tools)
                lines.append(f"- **建议工具**: {tools_str}")
            
            # 依赖关系
            dependencies = item.get('dependencies', [])
            if dependencies:
                deps_str = ', '.join([f"任务{dep}" for dep in dependencies])
                lines.append(f"- **依赖**: {deps_str}")
            
            # 重试信息
            retry = item.get('retry', 0)
            max_retry = item.get('max_retry', 2)
            if retry > 0:
                lines.append(f"- **重试**: {retry}/{max_retry}")
            
            lines.append("")
        
        # 添加统计信息
        lines.append("## 统计信息")
        lines.append("")
        lines.append(f"- 总任务数: {len(todo_list)}")
        
        # 统计各状态的任务数
        status_counts = {}
        for item in todo_list:
            status = item.get('status', 'pending')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            status_text = {
                'pending': '待执行',
                'processing': '执行中',
                'completed': '已完成',
                'failed': '失败'
            }.get(status, status)
            lines.append(f"- {status_text}: {count}")
        
        return "\n".join(lines)