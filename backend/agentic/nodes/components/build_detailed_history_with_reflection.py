# -*- coding: utf-8 -*-
"""
build_detailed_history_with_reflection.py

构建包含reflection评价的详细执行历史。
"""

from typing import TYPE_CHECKING

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import RuntimeState


def build_detailed_history_with_reflection(state: 'RuntimeState') -> str:
    """
    构建包含reflection评价的详细执行历史。
    将每个工具调用的reflection评价与对应的action_id关联。
    
    参数:
    state (RuntimeState): 当前运行时状态
    
    返回:
    str: 详细的执行历史文本，包含以下内容结构：
        1. 标题："### 执行历史（含评价）"
        2. 每个执行步骤的详细信息块：
           - 步骤标题："#### 步骤X: 工具名 [action_id]"
           - 状态行："状态: ✓成功/✗失败/◐部分"
           - 输入参数："输入: {参数字典}"（限制100字符）
           - 关键结果："结果:"后跟多行结果（每个结果项前缀"  - "）
           - 评价部分（如果有reflection）：
             * "📊 评价:"
             * "  - 质量: X/5"
             * "  - 相关性: X/5"
             * "  - 充分性: 是/否"
             * "  - 评语: 具体评价内容"
           - 步骤间用空行分隔
        3. 总结部分：
           - "#### 总结"
           - "共执行 X 步，成功 Y 步"
           - "✓ 已获得充分信息" 或 "⚠ 需要更多信息"
           - 思考提示："现在思考：我们是否已经能够调用 generate 工具来产出最终回答"
    
    示例输出:
        ### 执行历史（含评价）
        
        #### 步骤1: GoogleSearch [a1b2c3]
        状态: ✓成功
        输入: {'query': '最新AI技术进展'}
        结果:
          - 找到10篇相关文章
          - 涵盖GPT、Claude等模型最新进展
        📊 评价:
          - 质量: 4/5
          - 相关性: 5/5
          - 充分性: 是
          - 评语: 搜索结果高度相关，信息较新
        
        #### 步骤2: KnowledgeBase [d4e5f6]
        状态: ✓成功
        输入: {'operation': 'retrieve', 'doc_id': 'doc_001', 'page_range': '1-5'}
        结果:
          - 成功检索5页内容
          - 包含技术规范详细说明
        
        #### 总结
        共执行 2 步，成功 2 步
        ✓ 已获得充分信息
        
        现在思考：我们是否已经能够调用 generate 工具来产出最终回答
    """
    # 注意：action_history现在可能是嵌套列表结构
    # 使用 full_action_data 替代 action_summaries
    if not state.full_action_data:
        return "尚未执行任何操作"
    
    lines = ["## 📋 执行历史详情（含Reflection评价）\n"]
    
    # 用表格形式展示更清晰
    lines.append("| 步骤 | 工具 | Action ID | 执行状态 | 结果充分性 | Reflection评价 |")
    lines.append("|------|------|-----------|----------|------------|----------------|")
    
    for i, (action_id, full_data) in enumerate(state.full_action_data.items(), 1):
        # 获取工具名称
        tool_name = full_data.get("tool_name", "unknown")
        
        # 获取reflection数据
        reflection = full_data.get("reflection", {})
        
        # 状态图标
        status = full_data.get("status", "unknown")
        status_icon = {
            "success": "✅成功",
            "failed": "❌失败",
            "partial": "⚠️部分"
        }.get(status, "❓未知")
        
        # 充分性判断（从reflection中获取）
        is_sufficient = reflection.get("is_sufficient", False)
        sufficient_icon = "✅充分" if is_sufficient else "⚠️不充分"
        
        # 获取reflection结论（截断以适应表格）
        conclusion = reflection.get('conclusion', '无评价')
        if len(conclusion) > 50:
            conclusion = conclusion[:47] + "..."
        
        # 添加表格行
        lines.append(f"| {i} | {tool_name} | `{action_id}` | {status_icon} | {sufficient_icon} | {conclusion} |")
    
    lines.append("")  # 空行
    
    # 添加详细的评价信息
    lines.append("### 📊 详细评价信息\n")
    
    for i, (action_id, full_data) in enumerate(state.full_action_data.items(), 1):
        tool_name = full_data.get("tool_name", "unknown")
        reflection = full_data.get("reflection", {})
        brief_description = full_data.get("brief_description", "")
        key_results = full_data.get("key_results", [])
        is_sufficient = reflection.get("is_sufficient", False)
        
        if reflection and (reflection.get('conclusion') or key_results):
            lines.append(f"**步骤{i} - {tool_name}** (`{action_id}`):")
            if brief_description:
                lines.append(f"- 执行内容: {brief_description}")
            if key_results:
                lines.append(f"- 关键结果: {' | '.join(key_results[:3])}")
            if reflection.get('conclusion'):
                lines.append(f"- Reflection评价: {reflection['conclusion']}")
            lines.append(f"- 可引用性: {'✅ 可作为 ${' + action_id + '} 引用' if is_sufficient else '❌ 结果不充分，不建议引用'}")
            lines.append("")
    
    # 添加汇总统计
    total = len(state.full_action_data)
    success = sum(1 for data in state.full_action_data.values() if data.get("status") == "success")
    sufficient = sum(1 for data in state.full_action_data.values() if data.get("reflection", {}).get("is_sufficient", False))
    
    lines.append("### 📈 执行统计\n")
    lines.append(f"- **总执行步骤**: {total}")
    lines.append(f"- **成功步骤**: {success}/{total}")
    lines.append(f"- **充分结果**: {sufficient}/{total}")
    
    # 列出可引用的充分结果
    valuable_actions = [(aid, data) for aid, data in state.full_action_data.items() 
                       if data.get("status") == "success" and data.get("reflection", {}).get("is_sufficient", False)]
    if valuable_actions:
        lines.append("\n### ✅ 可直接引用的充分结果\n")
        lines.append("以下结果经Reflection评价为充分，可以通过 `${action_id}` 格式引用：\n")
        for action_id, full_data in valuable_actions:
            tool_name = full_data.get("tool_name", "unknown")
            brief_description = full_data.get("brief_description", "")
            reflection = full_data.get("reflection", {})
            conclusion_snippet = reflection.get('conclusion', '')[:50] if reflection else ''
            lines.append(f"- `${{{action_id}}}` - **{tool_name}**: {brief_description}")
            if conclusion_snippet:
                lines.append(f"  - 评价: {conclusion_snippet}")
    
    # 列出不充分的结果作为警示
    insufficient_actions = [(aid, data) for aid, data in state.full_action_data.items() 
                           if not data.get("reflection", {}).get("is_sufficient", False)]
    if insufficient_actions:
        lines.append("\n### ⚠️ 不充分的结果（需要补充）\n")
        for action_id, full_data in insufficient_actions:
            tool_name = full_data.get("tool_name", "unknown")
            reflection = full_data.get("reflection", {})
            reason = reflection.get('conclusion', '未知原因')[:50] if reflection else '未知原因'
            lines.append(f"- {tool_name} (`{action_id}`): {reason}")
    
    return "\n".join(lines)