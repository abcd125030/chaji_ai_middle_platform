# -*- coding: utf-8 -*-
"""
format_chat_history_for_prompt.py

格式化对话历史。
供 prompt_builder.py 调用，用于生成对话历史记录。

返回值示例:
    返回格式化的 Markdown 文本，包含最近的对话历史：
    '''
    ### 历史对话记录

    **用户**: 请帮我分析最新的市场数据
    
    **助手**: 我来帮您分析最新的市场数据。让我先搜索相关信息...
    
    **用户**: 重点关注科技行业的趋势
    
    **助手**: 好的，我将重点为您分析科技行业的趋势。根据最新数据显示...
    
    ---
    '''
"""

from typing import List, Dict, Any


def format_chat_history_for_prompt(chat_history: List[Dict[str, Any]], max_turns: int = 10) -> str:
    """
    格式化对话历史。
    
    参数:
        chat_history: 对话历史列表，每个元素包含 role 和 content 字段
        max_turns: 最大轮数，限制显示的对话轮数
    
    返回:
        str: 格式化后的对话历史，使用 Markdown 格式。
        
        返回值格式：
        - 使用 ### 级标题表示对话记录标题
        - 用户消息以 **用户**: 开头
        - 助手消息以 **助手**: 开头
        - 其他角色消息以 **{role}**: 开头
        - 内容超过500字符会被截断
        - 每条消息后有空行分隔
        - 末尾有分隔线
        
        特殊情况：
        - 如果没有对话历史，返回空字符串
        - 只显示最近的 max_turns 轮对话（每轮包含用户和助手两条消息）
        - 过长的内容会被截断到497字符并添加省略号
    
    示例:
        >>> chat_history = [
        ...     {"role": "user", "content": "你好"},
        ...     {"role": "assistant", "content": "您好！有什么可以帮助您的吗？"},
        ...     {"role": "user", "content": "请帮我分析这份数据"},
        ...     {"role": "assistant", "content": "好的，我来帮您分析数据..."},
        ... ]
        >>> result = format_chat_history_for_prompt(chat_history, max_turns=2)
        >>> print(result)
        ### 历史对话记录
        
        **用户**: 你好
        
        **助手**: 您好！有什么可以帮助您的吗？
        
        **用户**: 请帮我分析这份数据
        
        **助手**: 好的，我来帮您分析数据...
        
        ---
        
        >>> # 内容过长的情况
        >>> long_content = "这是一段非常长的文本" * 100
        >>> chat_history = [
        ...     {"role": "user", "content": long_content},
        ...     {"role": "assistant", "content": "收到您的长文本"}
        ... ]
        >>> result = format_chat_history_for_prompt(chat_history)
        >>> print(len(result.split("**用户**: ")[1].split("\\n")[0]))  # 截断后的长度
        500  # 497字符 + 3个省略号字符
        
        >>> # 空历史的情况
        >>> result = format_chat_history_for_prompt([])
        >>> print(result)
        
        
        >>> # 未知角色的情况  
        >>> chat_history = [
        ...     {"role": "system", "content": "系统消息"},
        ...     {"role": "function", "content": "函数调用结果"}
        ... ]
        >>> result = format_chat_history_for_prompt(chat_history)
        >>> print(result)
        ### 历史对话记录
        
        **system**: 系统消息
        
        **function**: 函数调用结果
        
        ---
    """
    if not chat_history:
        return ""
    
    lines = ["### 历史对话记录\n"]
    
    # 只取最近的max_turns轮对话
    recent_history = chat_history[-(max_turns * 2):] if len(chat_history) > max_turns * 2 else chat_history
    
    for msg in recent_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        # 截断过长的内容
        if len(content) > 500:
            content = content[:497] + "..."
        
        if role == "user":
            lines.append(f"**用户**: {content}")
        elif role == "assistant":
            lines.append(f"**助手**: {content}")
        else:
            lines.append(f"**{role}**: {content}")
        lines.append("")  # 空行分隔
    
    lines.append("---\n")  # 分隔线
    return "\n".join(lines)