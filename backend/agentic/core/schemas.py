# backend/agentic/schemas.py

"""
智能体核心数据模式定义模块

=== 文件概述 ===
本模块定义了智能体系统中所有核心数据结构的 Pydantic 模型，主要用于规范化智能体的输入输出、
状态管理和节点间的数据传递。这些模式确保了整个智能体图（agent graph）中数据流的一致性和可靠性。

=== 主要功能 ===
1. 工具输出标准化：定义统一的工具执行结果格式
2. 节点输出规范：规范 Planner、Reflection 等节点的输出结构
3. 状态管理：维护智能体运行时的全局状态信息
4. 数据摘要：提供执行历史和文件数据的精简摘要机制
5. 数据提取：支持基于路径的数据访问和相关数据提取

=== 数据流向 ===
输入：
- 用户任务目标（task_goal）
- 用户上传的文件（preprocessed_files）
- 原始图片数据（origin_images）
- 历史对话记录（chat_history）

处理流程：
1. Planner 节点分析任务，输出 PlannerOutput（包含工具调用决策）
2. 工具执行后返回 ToolOutputFormat 格式的结果
3. Reflection 节点分析工具结果，输出 ReflectionOutput
4. RuntimeState 维护全局状态，记录执行历史和数据
5. 通过 full_action_data 保存完整的执行历史
6. 最终通过 FinalizerGuidance 指导答案生成

输出：
- 标准化的工具执行结果
- 节点间传递的结构化数据
- 智能体的最终答案和执行摘要

=== 核心类关系 ===
RuntimeState (全局状态容器)
├── full_action_data{} (完整执行历史)
├── PreprocessedFileSummary[] (文件摘要)
├── PlannerOutput (规划决策)
├── ReflectionOutput (反思结果)
├── ToolOutputFormat (工具输出)
└── FinalizerGuidance (最终指导)

=== 函数调用关系 ===
1. RuntimeState.get_data_catalog() -> 生成数据目录
2. RuntimeState.extract_data_by_path() -> 按路径提取数据
3. RuntimeState.extract_relevant_data() -> 提取相关历史数据
4. RuntimeState.get_full_action_data() -> 获取完整执行数据
5. PreprocessedFilesSummaries.get_summary_by_key() -> 按键获取摘要

=== 外部依赖（非标准库）===
系统级依赖：
- Django 日志系统：logger = logging.getLogger("django")
- 智能体图节点：Planner、Reflection、End 等节点会使用这些模式
- 工具系统：各种工具需要返回 ToolOutputFormat 格式
- 数据预处理模块：负责填充 preprocessed_files 数据

业务级依赖：
- todo_generator 工具：管理 TODO 任务
- GoogleSearch 工具：搜索相关数据
- Chat 工具：对话功能
- report_generator 工具：生成报告
- data_analysis 工具：数据分析
- get_preprocessed_data 工具：获取预处理数据

=== 重要说明 ===
1. 所有工具必须返回 ToolOutputFormat 格式，确保 Reflection 节点能够统一处理
2. RuntimeState 使用私有属性缓存数据目录，避免重复计算
3. Planner 不应直接填写 final_answer 和 title，这些由专门节点处理
4. TODO 管理已迁移到 todo_generator 工具，相关字段保留仅为向后兼容
5. 数据提取支持文件名包含点号的情况，特别处理 preprocessed_files 路径

=== 版本兼容性 ===
- 保留已弃用字段以确保向后兼容
- 使用 Pydantic v2 的 model_validator 进行数据验证
- 支持额外字段（extra="allow"）以适应未来扩展
"""

# 导入所需的类型提示模块
from typing import List, Dict, Any, Literal, Optional
# 导入 Pydantic 库中的 BaseModel 和 Field，用于定义数据模型和字段描述
from pydantic import BaseModel, Field, PrivateAttr, model_validator
# 导入日志模块
import logging

logger = logging.getLogger("django")

class ToolOutputFormat(BaseModel):
    """
    统一的工具输出格式。
    所有工具都必须返回这种格式，以便 reflection 节点能够以一致的方式分析结果。
    """
    # 状态：成功、失败或部分成功
    status: Literal["success", "failed", "partial"] = Field(
        description="执行状态"
    )
    
    # 简要消息，描述执行情况
    message: str = Field(
        description="执行情况的简要描述"
    )
    
    # 主要结果数据（reflection 主要分析的字段）
    primary_result: Optional[Any] = Field(
        default=None,
        description="工具执行的主要结果，如：总结文本、分析结果、搜索结果等"
    )
    
    # 关键指标（reflection 用于评估的量化数据）
    key_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="关键指标，如：处理行数、找到的记录数、准确率等"
    )
    
    # 结果元数据（供进一步处理使用）
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="额外的元数据信息"
    )
    
    # 原始数据（如果需要保留）
    raw_data: Optional[Any] = Field(
        default=None,
        description="原始数据，供需要的场景使用"
    )

class FinalizerGuidance(BaseModel):
    """
    Planner 给 end 的指导信息
    """
    # 重点关注的要点
    key_points: List[str] = Field(
        default_factory=list,
        description="需要在最终答案中重点体现的要点"
    )
    
    # 答案格式要求
    format_requirements: Optional[str] = Field(
        default=None,
        description="答案的格式要求，如：列表形式、段落形式、表格形式等"
    )
    
    # 答案水准要求
    quality_requirements: Optional[str] = Field(
        default=None,
        description="答案的质量和深度要求，如：简洁明了、详细深入、专业术语等"
    )
    
    # 结构化要求
    structure_template: Optional[str] = Field(
        default=None,
        description="答案的结构模板，如：背景-分析-结论、问题-原因-解决方案等"
    )
    
    # 自定义提示词
    custom_prompt: Optional[str] = Field(
        default=None,
        description="给 end 的自定义提示词，用于特殊场景的精确控制"
    )
    
    # 需要强调的历史结果
    emphasized_action_ids: List[str] = Field(
        default_factory=list,
        description="需要特别强调使用的 action_ids，这些结果应该在答案中占据主要位置"
    )
    
    # 需要弱化的历史结果  
    deemphasized_action_ids: List[str] = Field(
        default_factory=list,
        description="需要弱化使用的 action_ids，这些结果仅作为补充信息"
    )

class PlannerOutput(BaseModel):
    """
    定义规划器（Planner）节点的结构化输出。
    这个模型用于规范规划器在决定下一步行动时所生成的数据格式。
    """
    # 规划器决策背后的推理过程
    thought: str = Field(description="规划器决策背后的推理过程。")

    # 下一步要采取的行动，可以是"CALL_TOOL"（调用工具）或"FINISH"（完成任务）
    # 注意：TODO管理应通过调用todo_generator工具实现，而不是特殊动作
    action: Literal["CALL_TOOL", "FINISH"] = Field(description="下一步要采取的行动。")

    # 要调用的工具的名称，如果 action 是 "CALL_TOOL" 则必须提供，否则为 None
    tool_name: Optional[str] = Field(default=None, description="要调用的工具的名称。")

    # 工具的输入参数，一个字典，如果 action 是 "CALL_TOOL" 则必须提供，否则为 None
    tool_input: Optional[Dict[str, Any]] = Field(default=None, description="工具的输入。")
    
    # 新增：期望的执行结果
    expected_outcome: Optional[str] = Field(
        default=None,
        description="期望工具执行后达到的结果，供 reflection 节点评估使用"
    )
    
    # 已弃用：TODO管理应通过todo_generator工具实现
    # 保留这些字段仅为向后兼容，新代码不应使用
    new_todos: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="[已弃用] 请使用todo_generator工具管理TODO"
    )
    
    # 已弃用：TODO管理应通过todo_generator工具实现
    todo_updates: Optional[Dict[str, Any]] = Field(
        default=None,
        description="[已弃用] 请使用todo_generator工具管理TODO"
    )
    
    # 最终答案 - 保留用于向后兼容，但不应由 Planner 直接填写
    final_answer: Optional[str] = Field(
        default=None, 
        description="最终答案。注意：Planner 不应直接填写此字段，应由 end 节点生成"
    )
    
    # 标题 - 保留用于向后兼容
    title: Optional[str] = Field(
        default=None,
        description="对话标题。注意：Planner 不应直接填写此字段，系统会自动生成"
    )
    
    # 新增：给 end 的指导信息
    output_guidance: Optional[Dict[str, Any]] = Field(
        default=None,
        description="当 action=FINISH 时，给 end 的指导信息，包括重点关注要点、答案格式要求等"
    )

class ReflectionOutput(BaseModel):
    """
    定义反思（Reflection）节点的结构化输出。
    这个模型用于规范反思节点对行动结果进行总结和评估时所生成的数据格式。
    增强版：添加语义摘要能力。
    """
    # 对行动结果的总结
    conclusion: str = Field(description="对行动结果的总结。")
    
    # 语义摘要：一句话总结这次执行
    summary: str = Field(
        default="",
        description="一句话语义摘要，描述工具完成了什么任务，获得了什么结果"
    )
    
    # 对任务的影响
    impact: str = Field(
        default="",
        description="这次执行对整体任务的影响和贡献"
    )

    # 工具调用是否达到了预期目标
    is_finished: bool = Field(description="工具调用是否正常完成。")
    
    # 添加 is_sufficient 字段
    is_sufficient: bool = Field(default=True, description="工具调用的结果是否足够充分。")
    
    # 关键发现（可选）
    key_findings: List[str] = Field(
        default_factory=list,
        description="从工具输出中提取的关键发现或要点"
    )


class PreprocessedFileSummary(BaseModel):
    """
    预处理文件的摘要信息。
    用于向 planner 展示可用数据的概要，而不是完整内容。
    """
    file_key: str = Field(description="文件的唯一标识符，用于后续获取完整数据")
    file_type: Literal["document", "table", "other"] = Field(description="文件类型")
    summary: str = Field(description="内容摘要，100-200字的简要描述")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据信息，如文档长度、表格维度、文件大小等"
    )
    suggested_tools: List[str] = Field(
        default_factory=list,
        description="建议使用的工具列表"
    )

class PreprocessedFilesSummaries(BaseModel):
    """
    所有预处理文件的摘要集合。
    """
    summaries: List[PreprocessedFileSummary] = Field(
        default_factory=list,
        description="所有文件的摘要列表"
    )
    total_files: int = Field(default=0, description="文件总数")
    
    def get_summary_by_key(self, file_key: str) -> Optional[PreprocessedFileSummary]:
        """根据文件key获取对应的摘要"""
        for summary in self.summaries:
            if summary.file_key == file_key:
                return summary
        return None

class RuntimeState(BaseModel):
    """
    表示智能体图的全局运行时状态。
    这个类维护了智能体在执行任务过程中的所有关键信息，包括任务目标、行动历史、对话历史等。
    
    优化后的结构更加精简，移除了中间状态字段，专注于核心数据管理。
    """
    # 必填字段
    task_goal: str = Field(description="智能体需要完成的任务目标（包含usage的完整描述）")
    
    # 可选字段，使用Field设置默认值
    preprocessed_files: Dict[str, Any] = Field(
        default_factory=lambda: {
            'documents': {},  # 存储 markdown 格式的文档内容，键为文件名，值为内容
            'tables': {},     # 存储表格数据，键为文件名，值为表格数据结构
            'images': {},     # 存储图片的文字描述，键为文件名，值为描述信息
            'other_files': {} # 存储其他类型文件，键为文件名，值为文件内容
        },
        description="预处理后的文件数据"
    )
    origin_images: List[str] = Field(default_factory=list, description="用户上传的原始图片（base64格式）")
    # action_history现在支持两种格式：扁平列表（向后兼容）和嵌套列表（新格式）
    # 嵌套格式：[[第一轮对话的历史], [第二轮对话的历史], ...]
    action_history: List[Any] = Field(default_factory=list, description="智能体的行动历史（支持扁平和嵌套列表格式）")
    context_memory: Dict[str, Any] = Field(default_factory=dict, description="会话级上下文记忆")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="用户上下文信息")
    chat_history: List[Dict[str, str]] = Field(default_factory=list, description="历史对话记录")
    
    # 运行时生成的字段
    todo: List[Dict[str, Any]] = Field(default_factory=list, description="TODO任务清单")
    full_action_data: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="完整数据存储")
    
    # 私有字段（不会被序列化）
    _data_catalog_cache: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    _original_task_goal: str = PrivateAttr(default="")
    usage: Optional[str] = Field(default=None, description="使用情况或额外信息")
    
    class Config:
        """Pydantic配置"""
        extra = "allow"  # 允许额外字段，保证向后兼容
        arbitrary_types_allowed = True  # 允许任意类型
    
    @model_validator(mode='before')
    @classmethod
    def process_task_goal(cls, values):
        """处理task_goal的拼接逻辑"""
        if isinstance(values, dict):
            task_goal = values.get('task_goal', '')
            usage = values.get('usage')
            
            # 保存原始task_goal（用于_original_task_goal）
            original_task_goal = task_goal
            
            # 处理task_goal的拼接
            if usage:
                processed_task_goal = usage + "\n以下是用户要求：\n```" + task_goal + "```"
            else:
                processed_task_goal = "以下是用户需求：\n```" + task_goal + "```"
            
            values['task_goal'] = processed_task_goal
            # 注意：_original_task_goal是私有属性，需要在__init__后设置
            
        return values
    
    def __init__(self, **data):
        """重写__init__以处理私有属性"""
        # 保存原始task_goal值
        original_task_goal = data.get('task_goal', '')
        
        # 调用父类__init__
        super().__init__(**data)
        
        # 设置私有属性
        self._original_task_goal = original_task_goal
        
        # 移除的字段（不再需要）：
        # - current_plan: 移到执行器的局部变量
        # - current_tool_output: 移到执行器的局部变量
        # - context: 设计上存在问题，暂时移除
        # - _preprocessed_summaries_cache: 整合到data_catalog_cache中
    
    def get_full_action_data(self, action_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 action_id 获取完整的执行数据。
        
        参数:
        action_id (str): 行动的唯一标识符。
        
        返回:
        Optional[Dict[str, Any]]: 完整的执行数据，如果不存在则返回 None。
        """
        return self.full_action_data.get(action_id)
    
    def extract_relevant_data(self, tool_name: str, context_hints: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        根据工具名称和上下文提示提取相关数据。
        
        参数:
        tool_name (str): 即将调用的工具名称。
        context_hints (Optional[List[str]]): 上下文提示，帮助判断需要哪些历史数据。
        
        返回:
        Dict[str, Any]: 相关的完整数据。
        """
        relevant_data = {}
        
        # 根据工具类型确定需要的历史数据
        # 由于 action_summaries 已废弃，直接从 full_action_data 获取数据
        if tool_name == "report_generator":
            # report_generator 可能需要所有 GoogleSearch 和 Chat 的结果
            for action_id, data in self.full_action_data.items():
                if data.get("tool_name") in ["GoogleSearch", "Chat"]:
                    relevant_data[action_id] = data
        
        elif tool_name == "data_analysis":
            # data_analysis 可能需要之前的表格数据
            for action_id, data in self.full_action_data.items():
                if data.get("tool_name") in ["get_preprocessed_data", "data_extraction"]:
                    relevant_data[action_id] = data
        
        # 如果有上下文提示，根据关键词匹配
        if context_hints:
            for hint in context_hints:
                hint_lower = hint.lower()
                for action_id, data in self.full_action_data.items():
                    # 检查数据中的相关字段是否包含提示词
                    data_str = str(data).lower()
                    if hint_lower in data_str and action_id not in relevant_data:
                        relevant_data[action_id] = data
        
        return relevant_data
    
    def get_data_catalog(self) -> Dict[str, Any]:
        """
        获取 state 中所有可用数据的目录（高度抽象，不暴露具体内容）。
        
        返回:
        Dict[str, Any]: 数据目录，只描述数据类型和结构，不包含具体信息。
        """
        
        # 如果有缓存，直接返回
        if self._data_catalog_cache is not None:
            
            return self._data_catalog_cache
            
        # 为文档和表格生成抽象标识符
        documents = self.preprocessed_files.get("documents", {})
        tables = self.preprocessed_files.get("tables", {})
        
        # 生成抽象的数据引用
        doc_refs = {}
        for idx, doc_key in enumerate(documents.keys()):
            doc_refs[f"doc_{idx+1}"] = f"preprocessed_files.documents.{doc_key}"
        
        table_refs = {}
        for idx, table_key in enumerate(tables.keys()):
            table_refs[f"table_{idx+1}"] = f"preprocessed_files.tables.{table_key}"
        
        catalog = {
            "available_data_types": {
                "preprocessed_files": {
                    "documents": {
                        "count": len(documents),
                        "refs": doc_refs  # 抽象引用映射
                    },
                    "tables": {
                        "count": len(tables),
                        "refs": table_refs  # 抽象引用映射
                    },
                    "other_files": {
                        "count": len(self.preprocessed_files.get("other_files", []))
                    }
                },
                "execution_history": {
                    "total_actions": len(self.full_action_data),
                    "by_tool": {},  # 按工具分组的执行次数
                    "action_refs": {}  # action_id 映射
                }
            }
        }
        
        # 统计每个工具的执行次数，并收集成功的 action_ids
        tool_counts = {}
        action_refs = {}
        successful_actions = []
        
        # 从 full_action_data 中提取执行历史信息
        for action_id, data in self.full_action_data.items():
            tool_name = data.get("tool_name", "unknown")
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
            
            # 收集成功的 action 作为可用数据源
            if data.get("status") == "success":
                action_info = {
                    "action_id": action_id,
                    "tool": tool_name,
                    "timestamp": data.get("timestamp", ""),
                    "has_data": bool(data.get("result"))
                }
                successful_actions.append(action_info)
                # 创建更易读的引用
                action_refs[action_id] = {
                    "tool": tool_name,
                    "sufficient": True
                }
        
        catalog["available_data_types"]["execution_history"]["by_tool"] = tool_counts
        catalog["available_data_types"]["execution_history"]["successful_actions"] = successful_actions
        catalog["available_data_types"]["execution_history"]["action_results"] = action_refs

        
        # 缓存结果
        self._data_catalog_cache = catalog
        
        return catalog
    
    def extract_data_by_path(self, path: str) -> Any:
        """
        根据路径从 state 中提取数据。
        
        参数:
        path (str): 数据路径，如 "preprocessed_files.documents.uuid-filename.pdf"
        
        返回:
        Any: 提取的数据，如果路径无效则返回 None。
        """
        try:
            # 特殊处理 preprocessed_files 路径，因为文件名可能包含点号
            if path.startswith('preprocessed_files.'):
                # 分割成最多3部分：preprocessed_files, documents/tables/other_files, filename
                parts = path.split('.', 2)
                if len(parts) == 3:
                    # parts[0] = 'preprocessed_files'
                    # parts[1] = 'documents' 或 'tables' 或 'other_files'
                    # parts[2] = 完整的文件名（可能包含点号）
                    data = self
                    # 先获取 preprocessed_files
                    if hasattr(data, parts[0]):
                        data = getattr(data, parts[0])
                    elif isinstance(data, dict) and parts[0] in data:
                        data = data[parts[0]]
                    else:
                        return None
                    
                    # 再获取 documents/tables/other_files
                    if isinstance(data, dict) and parts[1] in data:
                        data = data[parts[1]]
                    else:
                        return None
                    
                    # 最后获取文件内容
                    if isinstance(data, dict) and parts[2] in data:
                        return data[parts[2]]
                    else:
                        return None
            
            # 其他路径按原方式处理
            parts = path.split('.')
            data = self
            for part in parts:
                if hasattr(data, part):
                    data = getattr(data, part)
                elif isinstance(data, dict) and part in data:
                    data = data[part]
                else:
                    return None
            return data
        except Exception as e:
            logger.warning(f"extract_data_by_path 错误: {path} - {str(e)}")
            return None
    
    def get_origin_data_structure(self) -> List[Dict[str, str]]:
        """
        生成所有原始数据的结构描述。
        返回一个列表，描述每个数据项的类型和引用路径，但不包含实际内容。
        
        这个方法用于向Planner展示可用数据的结构，而不暴露具体内容。
        
        返回:
        List[Dict[str, str]]: 数据结构描述列表，每项包含content（引用路径）和type（数据类型）
        """
        structure = []
        
        # 1. 添加用户问题文本
        structure.append({
            "content": self._original_task_goal,
            "type": "text"
        })
        
        # 2. 添加原始图片引用
        for i in range(len(self.origin_images)):
            structure.append({
                "content": f"origin_images[{i}]",
                "type": "image"
            })
        
        # 3. 添加预处理文档引用
        for doc_name, doc_data in self.preprocessed_files.get("documents", {}).items():
            # 从文档数据中获取原始文件名
            original_name = doc_data.get('name', doc_name) if isinstance(doc_data, dict) else doc_name
            structure.append({
                "content": f"preprocessed_files.documents.{doc_name}",
                "type": "text",
                "original_name": original_name  # 添加原始文件名信息
            })
        
        # 4. 添加预处理表格引用
        for table_name, table_data in self.preprocessed_files.get("tables", {}).items():
            # 从表格数据中获取原始文件名
            original_name = table_data.get('name', table_name) if isinstance(table_data, dict) else table_name
            structure.append({
                "content": f"preprocessed_files.tables.{table_name}",
                "type": "table",
                "original_name": original_name  # 添加原始文件名信息
            })
        
        # 5. 添加其他文件引用
        for file_name in self.preprocessed_files.get("other_files", {}):
            structure.append({
                "content": f"preprocessed_files.other_files.{file_name}",
                "type": "file"
            })
        
        return structure