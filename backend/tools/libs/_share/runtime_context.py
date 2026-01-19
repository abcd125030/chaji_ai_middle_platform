"""
运行时上下文提取函数模块

从RuntimeState中提取各种上下文信息，返回格式化的文本内容
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agentic.core.schemas import RuntimeState

logger = logging.getLogger(__name__)


def extract_runtime_contexts(state: 'RuntimeState') -> str:
    """
    从RuntimeState提取所有可用的上下文信息
    
    Args:
        state: RuntimeState实例，包含各种运行时状态信息
        
    Returns:
        str: 上下文信息的文本描述
    """
    try:
        context_parts = []
        
        # 1. 提取任务目标上下文
        if hasattr(state, 'task_goal') and state.task_goal:
            context_parts.append("## 任务目标")
            context_parts.append(state.task_goal)
            context_parts.append("")
        
        # 2. 提取预处理文件上下文
        preprocessed_context = _extract_preprocessed_files_context(state)
        if preprocessed_context:
            context_parts.append("## 预处理文件")
            context_parts.append(preprocessed_context)
            context_parts.append("")
        
        # 3. 提取执行历史上下文
        history_context = _extract_action_history_context(state)
        if history_context:
            context_parts.append("## 执行历史")
            context_parts.append(history_context)
            context_parts.append("")
        
        # 4. 提取TODO上下文
        todo_context = _extract_todo_context(state)
        if todo_context:
            context_parts.append("## 待办任务")
            context_parts.append(todo_context)
            context_parts.append("")
        
        # 5. 提取对话历史上下文
        chat_context = _extract_chat_history_context(state)
        if chat_context:
            context_parts.append("## 对话历史")
            context_parts.append(chat_context)
            context_parts.append("")
        
        # 6. 提取用户上下文信息
        user_context = _extract_user_context(state)
        if user_context:
            context_parts.append("## 用户上下文")
            context_parts.append(user_context)
            context_parts.append("")
        
        # 7. 提取上下文记忆
        memory_context = _extract_context_memory(state)
        if memory_context:
            context_parts.append("## 上下文记忆")
            context_parts.append(memory_context)
            context_parts.append("")
        
        result = "\n".join(context_parts).strip() if context_parts else "无可用上下文信息"
        logger.debug(f"Extracted runtime contexts: {len(result)} chars")
        return result
        
    except Exception as e:
        logger.error(f"Failed to extract runtime contexts: {str(e)}")
        return "上下文提取失败"


def _extract_preprocessed_files_context(state: 'RuntimeState') -> str:
    """提取预处理文件的上下文摘要"""
    try:
        if not hasattr(state, 'preprocessed_files'):
            return ""
        
        files = state.preprocessed_files
        if not files:
            return ""
        
        parts = []
        
        # 文档文件
        documents = files.get('documents', {})
        if documents:
            parts.append(f"- 文档文件: {len(documents)}个")
            for doc_name in list(documents.keys())[:3]:  # 只显示前3个
                parts.append(f"  • {doc_name}")
            if len(documents) > 3:
                parts.append(f"  • ...还有{len(documents)-3}个文档")
        
        # 表格文件
        tables = files.get('tables', {})
        if tables:
            parts.append(f"- 表格文件: {len(tables)}个")
            for table_name in list(tables.keys())[:3]:
                parts.append(f"  • {table_name}")
            if len(tables) > 3:
                parts.append(f"  • ...还有{len(tables)-3}个表格")
        
        # 图片文件
        images = files.get('images', {})
        if images:
            parts.append(f"- 图片文件: {len(images)}个")
        
        # 其他文件
        other_files = files.get('other_files', {})
        if other_files:
            parts.append(f"- 其他文件: {len(other_files)}个")
        
        return "\n".join(parts)
        
    except Exception as e:
        logger.warning(f"Failed to extract preprocessed files context: {e}")
        return ""


def _extract_action_history_context(state: 'RuntimeState') -> str:
    """提取执行历史的上下文摘要"""
    try:
        if not hasattr(state, 'action_summaries'):
            return ""
        
        summaries = state.action_summaries
        if not summaries:
            return ""
        
        parts = []
        
        # 统计工具使用情况
        tool_counts = {}
        for summary in summaries:
            tool_name = summary.tool_name
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        parts.append(f"已执行 {len(summaries)} 个操作:")
        for tool, count in tool_counts.items():
            parts.append(f"- {tool}: {count}次")
        
        # 显示最近的成功操作
        recent_successes = [s for s in summaries[-5:] if s.status == "success"]
        if recent_successes:
            parts.append("\n最近成功的操作:")
            for summary in recent_successes:
                parts.append(f"- {summary.tool_name}: {summary.brief_description}")
                if summary.key_results:
                    for result in summary.key_results[:2]:
                        parts.append(f"  • {result}")
        
        return "\n".join(parts)
        
    except Exception as e:
        logger.warning(f"Failed to extract action history context: {e}")
        return ""


def _extract_todo_context(state: 'RuntimeState') -> str:
    """提取TODO任务的上下文"""
    try:
        if not hasattr(state, 'todo'):
            return ""
        
        todos = state.todo
        if not todos:
            return ""
        
        parts = []
        
        # 按状态分组
        pending = []
        in_progress = []
        completed = []
        
        for todo in todos:
            status = todo.get('status', 'pending')
            if status == 'completed':
                completed.append(todo)
            elif status == 'in_progress':
                in_progress.append(todo)
            else:
                pending.append(todo)
        
        if in_progress:
            parts.append("进行中:")
            for todo in in_progress:
                parts.append(f"- {todo.get('task', '未知任务')}")
        
        if pending:
            parts.append("待处理:")
            for todo in pending[:5]:  # 只显示前5个
                parts.append(f"- {todo.get('task', '未知任务')}")
            if len(pending) > 5:
                parts.append(f"- ...还有{len(pending)-5}个待办任务")
        
        if completed:
            parts.append(f"已完成: {len(completed)}个任务")
        
        return "\n".join(parts)
        
    except Exception as e:
        logger.warning(f"Failed to extract todo context: {e}")
        return ""


def _extract_chat_history_context(state: 'RuntimeState') -> str:
    """提取对话历史的上下文摘要"""
    try:
        if not hasattr(state, 'chat_history'):
            return ""
        
        history = state.chat_history
        if not history:
            return ""
        
        parts = []
        parts.append(f"对话轮次: {len(history)}")
        
        # 只显示最近3轮对话的摘要
        recent = history[-6:] if len(history) > 6 else history  # 每轮2条消息
        
        for i in range(0, len(recent), 2):
            if i < len(recent) - 1:
                user_msg = recent[i].get('content', '')[:50]
                ai_msg = recent[i+1].get('content', '')[:50]
                parts.append(f"- 用户: {user_msg}...")
                parts.append(f"  AI: {ai_msg}...")
        
        return "\n".join(parts)
        
    except Exception as e:
        logger.warning(f"Failed to extract chat history context: {e}")
        return ""


def _extract_user_context(state: 'RuntimeState') -> str:
    """提取用户上下文信息"""
    try:
        if not hasattr(state, 'user_context'):
            return ""
        
        user_ctx = state.user_context
        if not user_ctx:
            return ""
        
        parts = []
        
        # 提取关键用户信息
        if 'user_id' in user_ctx:
            parts.append(f"- 用户ID: {user_ctx['user_id']}")
        
        if 'session_id' in user_ctx:
            parts.append(f"- 会话ID: {user_ctx['session_id']}")
        
        if 'preferences' in user_ctx:
            prefs = user_ctx['preferences']
            if isinstance(prefs, dict):
                parts.append("- 用户偏好:")
                for key, value in prefs.items():
                    parts.append(f"  • {key}: {value}")
        
        return "\n".join(parts)
        
    except Exception as e:
        logger.warning(f"Failed to extract user context: {e}")
        return ""


def _extract_context_memory(state: 'RuntimeState') -> str:
    """提取上下文记忆信息"""
    try:
        if not hasattr(state, 'context_memory'):
            return ""
        
        memory = state.context_memory
        if not memory:
            return ""
        
        parts = []
        
        # 显示记忆的关键信息
        for key, value in memory.items():
            if isinstance(value, (str, int, float)):
                parts.append(f"- {key}: {value}")
            elif isinstance(value, list):
                parts.append(f"- {key}: {len(value)}项")
            elif isinstance(value, dict):
                parts.append(f"- {key}: {len(value)}个键值对")
        
        return "\n".join(parts) if parts else ""
        
    except Exception as e:
        logger.warning(f"Failed to extract context memory: {e}")
        return ""