# -*- coding: utf-8 -*-
"""
build_action_history_prompt.py

构建基于 action_history 的历史步骤提示词。

本模块直接从 RuntimeState 的 action_history 字段中提取执行历史，
生成适合 Planner 节点使用的历史步骤描述提示词。

## 设计理念
- 直接从 action_history 读取数据，避免依赖派生的 action_summaries
- 根据 action_history 中的 plan/reflection 配对生成执行步骤描述
- 支持灵活的展示策略（简洁/详细/自定义）

## 数据源
action_history 结构：
- {"type": "plan", "data": {...}} - 规划数据
- {"type": "reflection", "data": {...}} - 反思数据（包含action_id）

## 输出格式
根据不同的展示策略，生成不同详细程度的历史描述。
"""

from typing import List, Dict, Any, Optional, Literal
import logging

logger = logging.getLogger("django")


def build_action_history_prompt(
    action_history: List[Dict[str, Any]],
    format_type: Literal["concise", "detailed", "minimal"] = "detailed",
    max_steps: Optional[int] = None
) -> str:
    """
    从 action_history 构建历史步骤的提示词。
    
    参数:
        action_history: 包含 plan 和 reflection 的历史记录列表
        format_type: 格式类型
            - "minimal": 最简洁，仅显示工具和状态
            - "concise": 简洁版，包含工具、状态和关键结果
            - "detailed": 详细版，包含完整的思考、工具、结果和反思
        max_steps: 最多显示的步骤数（从最近的开始）
    
    返回:
        str: 格式化的历史步骤描述
    """
    
    if not action_history:
        return "尚未执行任何操作"
    
    # 将 action_history 配对成执行步骤（plan + reflection）
    steps = []
    current_step = {}
    
    for item in action_history:
        if item.get("type") == "plan":
            # 开始新的步骤
            if current_step:
                # 如果有未完成的步骤（只有plan没有reflection），也加入
                steps.append(current_step)
            current_step = {"plan": item.get("data", {})}
        
        elif item.get("type") == "reflection":
            # 完成当前步骤
            if current_step:
                current_step["reflection"] = item.get("data", {})
                steps.append(current_step)
                current_step = {}
    
    # 处理最后一个可能未完成的步骤
    if current_step:
        steps.append(current_step)
    
    # 限制显示的步骤数
    if max_steps and len(steps) > max_steps:
        steps = steps[-max_steps:]  # 取最近的N个步骤
    
    # 根据格式类型生成输出
    if format_type == "minimal":
        return _format_minimal(steps)
    elif format_type == "concise":
        return _format_concise(steps)
    else:  # detailed
        return _format_detailed(steps)


def _format_minimal(steps: List[Dict[str, Any]]) -> str:
    """生成最简格式的历史描述。"""
    if not steps:
        return "尚未执行任何操作"
    
    lines = ["【执行历史】"]
    
    for i, step in enumerate(steps, 1):
        plan = step.get("plan", {})
        reflection = step.get("reflection", {})
        
        # 从plan中获取工具名称
        tool_name = plan.get("tool_name")
        if not tool_name:
            tool_name = "思考"
        
        # 状态符号
        if reflection:
            status = reflection.get("status", "unknown")
            if status == "success" and reflection.get("is_sufficient"):
                status_icon = "✓"
            elif status == "success":
                status_icon = "◐"
            elif status == "failed" or status == "error":
                status_icon = "✗"
            else:
                status_icon = "◯"
        else:
            status_icon = "◯"
        
        lines.append(f"{i}. {status_icon} {tool_name}")
    
    return "\n".join(lines)


def _format_concise(steps: List[Dict[str, Any]]) -> str:
    """生成简洁格式的历史描述。"""
    if not steps:
        return "尚未执行任何操作"
    
    lines = ["【执行历史摘要】"]
    
    for i, step in enumerate(steps, 1):
        plan = step.get("plan", {})
        reflection = step.get("reflection", {})
        
        # 从plan中获取工具名称
        tool_name = plan.get("tool_name")
        if not tool_name:
            tool_name = "思考"
        
        action = plan.get("action", "")
        
        # 状态符号和文本
        if reflection:
            status = reflection.get("status", "unknown")
            summary = reflection.get("summary", "")
            
            if status == "success" and reflection.get("is_sufficient"):
                status_icon = "✓"
                status_text = "成功"
            elif status == "success":
                status_icon = "◐"
                status_text = "部分完成"
            elif status == "failed":
                status_icon = "✗"
                status_text = "失败"
            elif status == "error":
                status_icon = "✗"
                status_text = "错误"
            else:
                status_icon = "◯"
                status_text = status
        else:
            status_icon = "◯"
            status_text = "未评估"
            summary = ""
        
        lines.append(f"\n步骤{i}. {status_icon} {tool_name} - {status_text}")
        
        if action:
            lines.append(f"  意图: {action[:50]}...")
        
        if summary:
            lines.append(f"  结果: {summary}")
    
    # 添加统计
    total = len(steps)
    completed = sum(1 for s in steps if s.get("reflection", {}).get("status") == "success")
    sufficient = sum(1 for s in steps if s.get("reflection", {}).get("is_sufficient"))
    
    lines.append(f"\n【统计】共执行 {total} 步，成功 {completed} 步，充分 {sufficient} 步")
    
    return "\n".join(lines)


def _format_detailed(steps: List[Dict[str, Any]]) -> str:
    """生成详细格式的历史描述。"""
    if not steps:
        return "尚未执行任何操作"
    
    lines = ["【详细执行历史】"]
    lines.append("=" * 60)
    
    for i, step in enumerate(steps, 1):
        plan = step.get("plan", {})
        reflection = step.get("reflection", {})
        
        # 从plan中获取工具名称，如果没有则标记为"思考"
        tool_name = plan.get("tool_name")
        if not tool_name:
            # 如果没有tool_name，可能是纯思考步骤
            tool_name = "思考"
        
        tool_input = plan.get("tool_input", {})
        thought = plan.get("output", "")  # planner的thought存在output字段
        
        lines.append(f"\n【步骤 {i}】{tool_name}")
        lines.append("-" * 40)
        
        # 规划信息
        if thought:
            lines.append(f"思考: {thought}")
        
        # 工具输入（简化显示）
        if tool_input and tool_name != "思考":
            if isinstance(tool_input, dict):
                # 只显示关键参数
                input_summary = []
                for k, v in list(tool_input.items())[:3]:  # 最多显示3个参数
                    if isinstance(v, str) and len(v) > 50:
                        v = v[:47] + "..."
                    input_summary.append(f"{k}={v}")
                if len(tool_input) > 3:
                    input_summary.append(f"...等{len(tool_input)}个参数")
                lines.append(f"输入: {', '.join(input_summary)}")
        
        # 执行结果
        if reflection:
            # 从reflection中获取状态，如果没有则为未知
            status = reflection.get("status", "unknown")
            summary = reflection.get("summary", "")
            conclusion = reflection.get("conclusion", "")
            key_findings = reflection.get("key_findings", [])
            is_sufficient = reflection.get("is_sufficient", False)
            
            # 状态
            if status == "success" and is_sufficient:
                status_desc = "✓ 成功且充分"
            elif status == "success":
                status_desc = "◐ 成功但不充分"
            elif status == "failed":
                status_desc = "✗ 执行失败"
            elif status == "error":
                status_desc = "✗ 执行错误"
            else:
                # 其他状态（包括unknown）
                status_desc = f"◯ {status}"
            
            lines.append(f"状态: {status_desc}")
            
            # 摘要
            if summary:
                lines.append(f"摘要: {summary}")
            
            # 关键发现
            if key_findings:
                findings_str = " | ".join(key_findings[:3])  # 最多显示3个
                if len(key_findings) > 3:
                    findings_str += f" | ...等{len(key_findings)}项"
                lines.append(f"发现: {findings_str}")
            
            # 评价
            if conclusion:
                lines.append(f"评价: {conclusion[:100]}...")
        else:
            # 如果没有reflection，说明这个步骤还未执行reflection节点
            # 但在action_history中的数据应该都是已完成的，所以这种情况比较特殊
            lines.append("状态: ◯ 未评估（缺少反思数据）")
    
    lines.append("\n" + "=" * 60)
    
    # 添加整体评估
    total = len(steps)
    completed = sum(1 for s in steps if s.get("reflection", {}).get("status") == "success")
    sufficient = sum(1 for s in steps if s.get("reflection", {}).get("is_sufficient"))
    failed = sum(1 for s in steps if s.get("reflection", {}).get("status") == "failed")
    
    lines.append("【执行总结】")
    lines.append(f"- 总步骤数: {total}")
    lines.append(f"- 成功执行: {completed}/{total}")
    lines.append(f"- 充分结果: {sufficient}/{total}")
    if failed > 0:
        lines.append(f"- 失败步骤: {failed}")
    
    # 判断整体进展
    if sufficient >= 3:
        lines.append("- 整体评估: 已获得充分信息，可以考虑生成最终答案")
    elif completed >= 2:
        lines.append("- 整体评估: 有一定进展，继续收集信息或尝试其他工具")
    else:
        lines.append("- 整体评估: 进展有限，需要调整策略或使用其他工具")
    
    return "\n".join(lines)