# -*- coding: utf-8 -*-
"""
format_chat_history.py

格式化对话历史为文本形式。
"""

from typing import List


def format_chat_history(chat_history: List[dict], max_turns: int = 10) -> str:
    """
    格式化对话历史为文本形式，用于嵌入到prompt中。
    
    参数:
    chat_history (List[dict]): OpenAI格式的对话历史 [{role: "user"/"assistant", content: "..."}]
    max_turns (int): 最多包含的对话轮数，避免上下文过长
    
    返回:
    str: 格式化后的对话历史文本
    """
    if not chat_history:
        return ""
    
    lines = ["### 历史对话记录\n"]
    
    # 只取最近的max_turns轮对话（每轮包含user和assistant）
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