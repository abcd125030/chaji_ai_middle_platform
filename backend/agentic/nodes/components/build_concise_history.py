# -*- coding: utf-8 -*-
"""
build_concise_history.py

构建简洁的执行历史摘要。
"""

from typing import List, TYPE_CHECKING

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import ActionSummary


def build_concise_history(summaries: List['ActionSummary']) -> str:
    """
    构建简洁的执行历史摘要。
    
    参数:
    summaries (List[ActionSummary]): 执行历史摘要列表
    
    返回:
    str: 格式化的历史摘要文本，包含以下内容结构：
        1. 执行步骤列表，每行格式为：
           "序号. 状态标记 工具名 [action_id]: 关键结果"
           - 状态标记：✓（成功）、✗（失败）、◐（部分成功）
           - 工具名：执行的工具名称
           - action_id：唯一标识符，用于引用
           - 关键结果：前30个字符的结果摘要
        2. 统计信息行：
           "共执行 X 步，成功 Y 步"
        3. 充分性判断：
           "✓ 已获得充分信息" 或 "⚠ 信息可能不充分"
    
    示例输出:
        1. ✓ GoogleSearch [a1b2c3]: 找到10条相关搜索结果...
        2. ✓ KnowledgeBase [d4e5f6]: 成功检索5个相关文档
        3. ✗ TableAnalyzer [g7h8i9]: 表格数据格式错误
        
        共执行 3 步，成功 2 步
        ⚠ 信息可能不充分
    """
    if not summaries:
        return "尚未执行任何操作"
    
    lines = []
    success_count = 0
    fail_count = 0
    
    for i, summary in enumerate(summaries, 1):
        # 状态标记
        if summary.status == "success":
            status = "✓"
            success_count += 1
        elif summary.status == "failed":
            status = "✗"
            fail_count += 1
        else:
            status = "◐"  # partial
        
        # 关键结果
        result = summary.key_results[0] if summary.key_results else "无结果"
        if len(result) > 30:
            result = result[:27] + "..."
        
        # 添加简洁的一行描述，包含 action_id 以便引用
        lines.append(f"{i}. {status} {summary.tool_name} [{summary.action_id}]: {result}")
    
    # 添加统计信息
    total = len(summaries)
    lines.append(f"\n共执行 {total} 步，成功 {success_count} 步")
    
    # 检查是否有充分的结果
    sufficient = any(s.is_sufficient for s in summaries)
    if sufficient:
        lines.append("✓ 已获得充分信息")
    else:
        lines.append("⚠ 信息可能不充分")
    
    return "\n".join(lines)