# -*- coding: utf-8 -*-
"""
format_action_summaries.py

格式化执行历史摘要为精简的 Markdown 文本。
"""

from typing import List, TYPE_CHECKING

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import ActionSummary


def format_action_summaries(summaries: List['ActionSummary']) -> str:
    """
    格式化执行历史摘要为精简的 Markdown 文本。
    
    参数:
    summaries (List[ActionSummary]): 执行历史摘要列表。
    
    返回:
    str: 格式化后的摘要文本。
    """
    if not summaries:
        return "尚无执行历史。"
    
    # 使用表格格式展示摘要，更加紧凑
    lines = ["## 执行历史摘要\n"]
    lines.append("| 时间 | 工具 | 描述 | 状态 | 关键结果 |")
    lines.append("|------|------|------|------|----------|")
    
    for summary in summaries:
        # 提取时间（只显示时分秒）
        time_str = summary.timestamp.split('T')[1][:8] if 'T' in summary.timestamp else summary.timestamp[:8]
        
        # 状态图标
        status_icon = {
            "success": "✅",
            "failed": "❌",
            "partial": "⚠️"
        }.get(summary.status, "❓")
        
        # 合并关键结果
        results = " | ".join(summary.key_results) if summary.key_results else "无"
        
        # 添加行
        lines.append(f"| {time_str} | {summary.tool_name} | {summary.brief_description} | {status_icon} | {results} |")
    
    # 添加摘要统计
    total = len(summaries)
    success = len([s for s in summaries if s.status == "success"])
    failed = len([s for s in summaries if s.status == "failed"])
    partial = len([s for s in summaries if s.status == "partial"])
    
    lines.append(f"\n**统计**: 总计 {total} 次执行，成功 {success} 次，失败 {failed} 次，部分成功 {partial} 次")
    
    # 如果有不充分的结果，特别标注
    insufficient = [s for s in summaries if not s.is_sufficient]
    if insufficient:
        lines.append(f"\n**注意**: 有 {len(insufficient)} 次执行结果不够充分，可能需要补充信息")
    
    return "\n".join(lines)