#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试改进后的planner对简单问候的处理
"""

import os
import sys
import django
import json
import logging

# 设置Django环境
sys.path.insert(0, '/Users/chagee/Repos/X/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agentic.core.schemas import RuntimeState
from agentic.nodes.planner import planner_node

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('django')

def test_simple_greeting():
    """测试简单问候的处理"""
    
    # 创建测试状态
    state = RuntimeState()
    state.task_goal = "吃了吗"
    state._original_task_goal = "吃了吗"
    state.user_query = "吃了吗"
    state.scenario = "chat"
    
    # 设置用户上下文
    state.user_context = {
        'user_id': '2',
        'username': 'caijia',
        'display_name': '蔡佳'
    }
    
    # 设置对话历史
    state.chat_history = [
        {'role': 'user', 'content': '你好'},
        {'role': 'assistant', 'content': '你好！有什么可以帮助你的吗？'}
    ]
    
    # 初始化action_history为嵌套列表结构
    state.action_history = [[]]  # 当前对话的历史
    
    # 不设置todo，测试是否会强制创建
    state.todo = []
    
    print("=" * 60)
    print("测试场景：简单日常问候 - '吃了吗'")
    print("=" * 60)
    print(f"用户：{state.user_context['display_name']} (ID: {state.user_context['user_id']})")
    print(f"消息：{state.user_query}")
    print("=" * 60)
    
    try:
        # 调用planner节点
        result = planner_node(state, user=None, session_id='test-session')
        
        # 获取规划结果
        plan = result.get('current_plan')
        
        print("\n规划结果：")
        print("-" * 40)
        print(f"思考: {plan.thought}")
        print(f"动作: {plan.action}")
        
        if plan.action == "CALL_TOOL":
            print(f"工具: {plan.tool_name}")
            print(f"工具输入: {json.dumps(plan.tool_input, ensure_ascii=False, indent=2)}")
        elif plan.action == "FINISH":
            print("决定: 直接完成任务")
            if plan.output_guidance:
                print(f"输出指导: {json.dumps(plan.output_guidance.model_dump() if hasattr(plan.output_guidance, 'model_dump') else plan.output_guidance, ensure_ascii=False, indent=2)}")
        
        print("=" * 60)
        
        # 分析结果
        if plan.action == "CALL_TOOL" and plan.tool_name == "TodoGenerator":
            print("\n⚠️  问题：简单问候仍然调用了TodoGenerator")
            print("需要进一步优化提示词")
        else:
            print("\n✅ 成功：简单问候没有触发TodoGenerator")
            print("系统正确识别了日常对话场景")
            
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

def test_complex_task():
    """测试复杂任务的处理"""
    
    # 创建测试状态
    state = RuntimeState()
    state.task_goal = "帮我分析一下最近三个月的销售数据，生成趋势报告，并给出改进建议"
    state._original_task_goal = state.task_goal
    state.user_query = state.task_goal
    state.scenario = "chat"
    
    # 设置用户上下文
    state.user_context = {
        'user_id': '2',
        'username': 'caijia',
        'display_name': '蔡佳'
    }
    
    # 初始化action_history
    state.action_history = [[]]
    state.todo = []
    
    print("\n" + "=" * 60)
    print("测试场景：复杂任务 - 需要多步骤处理")
    print("=" * 60)
    print(f"任务：{state.task_goal}")
    print("=" * 60)
    
    try:
        # 调用planner节点
        result = planner_node(state, user=None, session_id='test-session')
        
        # 获取规划结果
        plan = result.get('current_plan')
        
        print("\n规划结果：")
        print("-" * 40)
        print(f"思考: {plan.thought}")
        print(f"动作: {plan.action}")
        
        if plan.action == "CALL_TOOL":
            print(f"工具: {plan.tool_name}")
            if plan.tool_name == "TodoGenerator":
                print("✅ 正确：复杂任务触发了TodoGenerator")
            else:
                print(f"选择了其他工具: {plan.tool_name}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("开始测试改进后的Planner...")
    print("\n" + "=" * 80)
    
    # 测试简单问候
    test_simple_greeting()
    
    # 测试复杂任务
    test_complex_task()
    
    print("\n测试完成！")