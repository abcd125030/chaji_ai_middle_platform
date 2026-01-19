# -*- coding: utf-8 -*-
"""
format_action_summaries_with_step_info.py

按照优化后的格式生成历史步骤描述。
"""

from typing import List, Optional, TYPE_CHECKING

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import ActionSummary


def format_action_summaries_with_step_info(action_summaries: List['ActionSummary'],
                                          user_input: str,
                                          usage_prompt: Optional[str] = None) -> str:
    """
    按照优化后的格式生成历史步骤描述。
    每个步骤包含步骤索引、动作类型、摘要信息和充分性状态。
    
    参数:
    action_summaries (List[ActionSummary]): 执行历史摘要列表
    user_input (str): 原始用户输入
    usage_prompt (Optional[str]): 场景提示词
    
    返回:
    str: 格式化后的历史步骤描述文本
    """
    lines = ["```执行历史"]
    
    lines.append(f"用户原始需求：\n{user_input}")
    
    # 如果有场景提示词，添加说明
    if usage_prompt:
        lines.append(f"\n解决当前需求的方法框架：\n{usage_prompt}")
    
    # 如果没有历史记录
    if not action_summaries:
        lines.append("\n尚无执行历史。")
        lines.append("\n现在思考：我们是否已经能够调用 generate 工具来产出最终回答")
        return "\n".join(lines)
    
    # 格式化每个步骤
    step_index = 0
    for i in range(len(action_summaries)):
        summary = action_summaries[i]
        step_index += 1
        
        # 根据工具类型确定动作动词
        action_verb = "执行了"
        if i > 0 and i % 2 == 0:  # 偶数位置通常是reflection
            action_verb = "检查结果"
        elif summary.tool_name in ["planner", "planning"]:
            action_verb = "思考"
        else:
            action_verb = "得到"
        
        # 状态和充分性描述
        if summary.status == "failed":
            status_text = "【执行失败】"
        elif summary.status == "partial":
            status_text = "【部分成功】"
        else:
            status_text = ""
        
        sufficient_text = "已" if summary.is_sufficient else "未"
        
        # 构建步骤描述
        step_desc = f"在第 {step_index} 步时，{action_verb} {summary.brief_description}，" \
                   f"{status_text}此步骤{sufficient_text}达到能够直接响应用户需求的条件。"
        
        lines.append(step_desc)
    
    # 添加失败统计
    failed_tools = {}
    for summary in action_summaries:
        if summary.status == "failed":
            tool = summary.tool_name
            if tool not in failed_tools:
                failed_tools[tool] = 0
            failed_tools[tool] += 1
    
    if failed_tools:
        lines.append("\n【失败统计】")
        for tool, count in failed_tools.items():
            lines.append(f"- {tool} 工具失败了 {count} 次")
    lines.append("```\n")
    lines.append("\n现在思考：我们是否已经能够调用 generate 工具来产出最终回答")
    
    return "\n".join(lines)