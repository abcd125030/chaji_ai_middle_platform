"""
RuntimeState Schema 定义
基于 HUMAN_AI_VIBE_CODING.md 的设计，实现新的状态管理结构
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """节点类型枚举"""
    PLANNER = "planner"
    TOOL_CALL = "tool_call"
    REFLECTION = "reflection"
    OUTPUT_SELECTOR = "output_selector"  # 选择合适的输出工具
    OUTPUT = "output"  # 具体的输出工具节点
    END = "end"


class ContentType(Enum):
    """内容类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    DATA = "data"


class UsageType(Enum):
    """使用类型枚举"""
    REFACTOR = "refactor"
    MODIFY = "modify"
    REFERENCE = "reference"
    ANALYSIS = "analysis"
    OUTPUT = "output"
    CORE_CONTENT = "core_content"
    VISUALIZE = "visualize"
    NARRATE = "narrate"
    STRUCTURE = "structure"
    SUMMARIZE = "summarize"


class ImportanceLevel(Enum):
    """重要性级别枚举"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ResourceMapping:
    """资源映射信息"""
    provider: Optional[str] = None  # aliyun|tencent|aws|gcc|local
    path: Optional[str] = None  # 存储路径
    public: Optional[str] = None  # 公共访问链接


@dataclass
class ContextInfo:
    """上下文信息（原contexts的内容）"""
    type: ContentType  # 内容类型
    content: Any  # 实际内容
    important: bool = False  # 重要性标记
    importance_level: ImportanceLevel = ImportanceLevel.MEDIUM  # 重要性级别
    usage_type: UsageType = UsageType.REFERENCE  # 使用类型
    reason: Optional[str] = None  # 重要性说明
    mapping: Optional[ResourceMapping] = None  # 资源映射


@dataclass
class ActionHistory:
    """
    action_history 的单个记录结构
    合并了原 contexts 的功能
    """
    # 基本信息
    id: str  # 唯一标识
    node: str  # 节点名称
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 执行信息
    preparation: Dict[str, Any] = field(default_factory=dict)  # 准备工作
    summary: str = ""  # 执行摘要
    result: Dict[str, Any] = field(default_factory=dict)  # 完整结果
    
    # 上下文信息（合并自contexts）
    context: Optional[ContextInfo] = None
    
    # 元信息
    usage: Dict[str, int] = field(default_factory=dict)  # token用量统计
    next: List[str] = field(default_factory=list)  # 下一步节点
    relevance: float = 0.0  # 对最终输出的相关性 (0-1)


@dataclass
class TodoItem:
    """TODO任务项"""
    id: str
    task: str  # 任务描述
    status: str = "pending"  # pending|in_progress|completed
    result: Optional[str] = None  # 任务结果


@dataclass
class OutputStructure:
    """输出结构预定义"""
    id: str
    expected_result: str  # 预期结果
    content: str = ""  # 实际内容
    type: str = "text"  # text|data|image


@dataclass
class FileInfo:
    """文件信息结构"""
    name: str
    type: str  # 文件类型
    local_path: str = ""  # 本地文件路径
    mapping: Optional[ResourceMapping] = None


@dataclass
class RuntimeState:
    """
    智能体图的全局运行时状态
    简化版本，移除冗余字段，专注于核心数据管理
    """
    # === 用户输入相关 ===
    prompt: str  # 用户发来的消息
    task_goal: str = ""  # 任务目标（由特定工具分析生成）
    
    # === 用户上下文 ===
    user_context: Dict[str, Any] = field(default_factory=dict)  # 用户信息（ID、角色、权限等）
    
    # === 文件处理 ===
    origin_files: List[FileInfo] = field(default_factory=list)  # 原始文件信息
    preprocessed_files: Dict[str, Any] = field(default_factory=lambda: {
        'documents': {},  # markdown格式的文档内容
        'tables': {},     # 表格数据
        'other_files': {} # 其他类型文件
    })
    
    # === 记忆系统 ===
    memory: List[Dict[str, Any]] = field(default_factory=list)  # 相关历史记忆
    
    # === 执行计划 ===
    scenario: str = ""  # 场景（预定义但留空）
    output_style: str = ""  # 输出风格（预定义但留空）
    output_structure: List[OutputStructure] = field(default_factory=list)  # 输出结构
    
    # === 执行历史（核心） ===
    action_history: List[ActionHistory] = field(default_factory=list)  # 执行历史和上下文
    
    # === 对话历史 ===
    chat_history: List[Dict[str, str]] = field(default_factory=list)  # OpenAI标准格式
    
    # === 任务管理 ===
    todo: List[TodoItem] = field(default_factory=list)  # TODO任务清单
    
    # === 统计信息 ===
    usage: Dict[str, int] = field(default_factory=lambda: {
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0
    })  # token用量统计
    
    # === 会话信息 ===
    session_id: Optional[str] = None  # 会话ID
    turn_id: Optional[str] = None  # 轮次ID
    
    def add_action(self, 
                   node: str,
                   summary: str,
                   result: Optional[Dict[str, Any]] = None,
                   context: Optional[ContextInfo] = None,
                   preparation: Optional[Dict[str, Any]] = None,
                   usage: Optional[Dict[str, int]] = None,
                   next_nodes: Optional[List[str]] = None,
                   relevance: float = 0.0) -> ActionHistory:
        """
        添加一个新的action记录
        """
        import uuid
        action = ActionHistory(
            id=str(uuid.uuid4()),
            node=node,
            summary=summary,
            result=result or {},
            context=context,
            preparation=preparation or {},
            usage=usage or {},
            next=next_nodes or [],
            relevance=relevance
        )
        self.action_history.append(action)
        
        # 更新总usage
        if usage:
            for key, value in usage.items():
                if key in self.usage:
                    self.usage[key] += value
                else:
                    self.usage[key] = value
        
        return action
    
    def get_last_action(self) -> Optional[ActionHistory]:
        """获取最后一个action记录"""
        return self.action_history[-1] if self.action_history else None
    
    def get_actions_by_node(self, node_name: str) -> List[ActionHistory]:
        """获取特定节点的所有action记录"""
        return [action for action in self.action_history if action.node == node_name]
    
    def get_relevant_contexts(self, min_relevance: float = 0.5) -> List[ContextInfo]:
        """获取相关性高的上下文信息"""
        contexts = []
        for action in self.action_history:
            if action.relevance >= min_relevance and action.context:
                contexts.append(action.context)
        return contexts
    
    def update_usage(self, prompt_tokens: int = 0, completion_tokens: int = 0):
        """更新token使用统计"""
        self.usage['prompt_tokens'] += prompt_tokens
        self.usage['completion_tokens'] += completion_tokens
        self.usage['total_tokens'] = self.usage['prompt_tokens'] + self.usage['completion_tokens']
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'prompt': self.prompt,
            'task_goal': self.task_goal,
            'user_context': self.user_context,
            'origin_files': [
                {
                    'name': f.name,
                    'type': f.type,
                    'local_path': f.local_path,
                    'mapping': {
                        'provider': f.mapping.provider,
                        'path': f.mapping.path,
                        'public': f.mapping.public
                    } if f.mapping else None
                }
                for f in self.origin_files
            ],
            'preprocessed_files': self.preprocessed_files,
            'memory': self.memory,
            'scenario': self.scenario,
            'output_style': self.output_style,
            'output_structure': [
                {
                    'id': o.id,
                    'expected_result': o.expected_result,
                    'content': o.content,
                    'type': o.type
                }
                for o in self.output_structure
            ],
            'action_history': [
                {
                    'id': action.id,
                    'node': action.node,
                    'timestamp': action.timestamp.isoformat(),
                    'preparation': action.preparation,
                    'summary': action.summary,
                    'result': action.result,
                    'context': {
                        'type': action.context.type.value,
                        'content': action.context.content,
                        'important': action.context.important,
                        'importance_level': action.context.importance_level.value,
                        'usage_type': action.context.usage_type.value,
                        'reason': action.context.reason,
                        'mapping': {
                            'provider': action.context.mapping.provider,
                            'path': action.context.mapping.path,
                            'public': action.context.mapping.public
                        } if action.context.mapping else None
                    } if action.context else None,
                    'usage': action.usage,
                    'next': action.next,
                    'relevance': action.relevance
                }
                for action in self.action_history
            ],
            'chat_history': self.chat_history,
            'todo': [
                {
                    'id': t.id,
                    'task': t.task,
                    'status': t.status,
                    'result': t.result
                }
                for t in self.todo
            ],
            'usage': self.usage,
            'session_id': self.session_id,
            'turn_id': self.turn_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuntimeState':
        """从字典创建RuntimeState实例"""
        state = cls(
            prompt=data.get('prompt', ''),
            task_goal=data.get('task_goal', ''),
            user_context=data.get('user_context', {}),
            memory=data.get('memory', []),
            scenario=data.get('scenario', ''),
            output_style=data.get('output_style', ''),
            chat_history=data.get('chat_history', []),
            session_id=data.get('session_id'),
            turn_id=data.get('turn_id')
        )
        
        # 处理文件信息
        for file_info in data.get('origin_files', []):
            mapping = file_info.get('mapping')
            state.origin_files.append(FileInfo(
                name=file_info['name'],
                type=file_info['type'],
                local_path=file_info.get('local_path', ''),
                mapping=ResourceMapping(**mapping) if mapping else None
            ))
        
        # 处理预处理文件
        state.preprocessed_files = data.get('preprocessed_files', {
            'documents': {},
            'tables': {},
            'other_files': {}
        })
        
        # 处理输出结构
        for output_info in data.get('output_structure', []):
            state.output_structure.append(OutputStructure(
                id=output_info['id'],
                expected_result=output_info['expected_result'],
                content=output_info.get('content', ''),
                type=output_info.get('type', 'text')
            ))
        
        # 处理action_history
        for action_data in data.get('action_history', []):
            context_data = action_data.get('context')
            context = None
            if context_data:
                mapping_data = context_data.get('mapping')
                context = ContextInfo(
                    type=ContentType(context_data['type']),
                    content=context_data['content'],
                    important=context_data.get('important', False),
                    importance_level=ImportanceLevel(context_data.get('importance_level', 'medium')),
                    usage_type=UsageType(context_data.get('usage_type', 'reference')),
                    reason=context_data.get('reason'),
                    mapping=ResourceMapping(**mapping_data) if mapping_data else None
                )
            
            action = ActionHistory(
                id=action_data['id'],
                node=action_data['node'],
                timestamp=datetime.fromisoformat(action_data['timestamp']),
                preparation=action_data.get('preparation', {}),
                summary=action_data.get('summary', ''),
                result=action_data.get('result', {}),
                context=context,
                usage=action_data.get('usage', {}),
                next=action_data.get('next', []),
                relevance=action_data.get('relevance', 0.0)
            )
            state.action_history.append(action)
        
        # 处理TODO
        for todo_data in data.get('todo', []):
            state.todo.append(TodoItem(
                id=todo_data['id'],
                task=todo_data['task'],
                status=todo_data.get('status', 'pending'),
                result=todo_data.get('result')
            ))
        
        # 处理usage
        state.usage = data.get('usage', {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        })
        
        return state