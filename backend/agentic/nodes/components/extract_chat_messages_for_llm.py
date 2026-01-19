# -*- coding: utf-8 -*-
"""
extract_chat_messages_for_llm.py

将对话历史转换为可直接发送给LLM的消息格式。
"""

from typing import List, Optional


def extract_chat_messages_for_llm(chat_history: List[dict], system_prompt: str = None) -> List[dict]:
    """
    将对话历史转换为可直接发送给LLM的消息格式。
    
    参数:
    chat_history (List[dict]): 历史对话记录
    system_prompt (str): 系统提示词（可选）
    
    返回:
    List[dict]: LLM消息格式
    """
    messages = []
    
    # 添加系统提示词（如果有）
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # 添加历史对话
    if chat_history:
        messages.extend(chat_history)
    
    return messages