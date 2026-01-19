#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试chat_history功能
"""

import os
import sys
import django

# 设置Django环境
sys.path.insert(0, '/Users/chagee/Repos/X/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from agentic.utils.processor_state import create_initial_state, create_state_with_history
from agentic.core.schemas import RuntimeState
import json

def test_chat_history():
    print("=" * 60)
    print("测试chat_history功能")
    print("=" * 60)
    
    # 测试1：创建初始状态，传入历史对话
    print("\n测试1: 创建初始状态（有历史对话）")
    conversation_history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助您的吗？"}
    ]
    
    state1 = create_initial_state(
        initial_task_goal="吃了吗",
        conversation_history=conversation_history,
        usage="test"
    )
    
    print(f"任务目标: {state1.task_goal[:100]}...")
    print(f"chat_history内容: {json.dumps(state1.chat_history, ensure_ascii=False, indent=2)}")
    print(f"chat_history长度: {len(state1.chat_history)}")
    
    # 测试2：模拟AI回复后的状态
    print("\n测试2: 模拟AI回复")
    state1.chat_history.append({
        "role": "assistant",
        "content": "我是AI助手，我不需要吃饭，但谢谢您的关心！您吃了吗？"
    })
    print(f"添加AI回复后的chat_history: {json.dumps(state1.chat_history, ensure_ascii=False, indent=2)}")
    
    # 测试3：基于历史状态创建新状态
    print("\n测试3: 基于历史状态创建新状态")
    historical_states = [state1]
    
    state2 = create_state_with_history(
        historical_states=historical_states,
        new_goal="天气怎么样",
        usage="test"
    )
    
    print(f"新任务目标: {state2.task_goal[:200]}...")
    print(f"合并后的chat_history: {json.dumps(state2.chat_history, ensure_ascii=False, indent=2)}")
    print(f"chat_history长度: {len(state2.chat_history)}")
    
    # 测试4：确认历史对话被正确保存和使用
    print("\n测试4: 验证历史对话上下文")
    print("任务目标中是否包含历史对话？", "历史对话上下文" in state2.task_goal)
    print("chat_history中是否有完整的对话历史？", len(state2.chat_history) == 5)  # 2个历史 + 1个当前用户 + 1个AI回复 + 1个新用户输入
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    test_chat_history()