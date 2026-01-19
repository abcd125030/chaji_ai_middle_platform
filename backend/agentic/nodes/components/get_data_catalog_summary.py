# -*- coding: utf-8 -*-
"""
get_data_catalog_summary.py

获取详细的数据目录摘要。
"""

from typing import TYPE_CHECKING

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import RuntimeState


def get_data_catalog_summary(state: 'RuntimeState') -> str:
    """
    获取详细的数据目录摘要，包含具体的文件名。
    
    参数:
    state (RuntimeState): 当前运行时状态
    
    返回:
    str: 详细的数据目录描述文本，包含以下内容结构：
        1. 预处理文件部分（如果有）：
           - 文档列表："文档(数量): `文件1`, `文件2`, `文件3`..."
             * 最多显示前3个文件名
             * 超过3个时末尾添加"..."
           - 表格列表："表格(数量): `文件1`, `文件2`, `文件3`..."
             * 格式同文档列表
        2. 历史执行结果部分：
           - 可用历史结果（充分的成功结果）：
             "可用历史结果(数量): `action_id` (工具名: 简要描述前30字符)..."
             * 最多显示前3个结果
           - 其他成功结果（不充分但成功的）：
             "其他结果(数量): `action_id` (工具名)"
             * 最多显示前2个结果
        
        各部分用", "连接成一行文本。
        如果某部分为空则跳过该部分。
    
    示例输出1（完整）:
        文档(3): `report.docx`, `analysis.pdf`, `summary.txt`, 
        表格(2): `data.xlsx`, `results.csv`, 
        可用历史结果(2): `a1b2c3` (GoogleSearch: 找到10条相关结果关于AI技术...), `d4e5f6` (KnowledgeBase: 成功检索文档内容包含5个章节...)
    
    示例输出2（部分）:
        文档(1): `meeting_notes.docx`, 
        可用历史结果(1): `x9y8z7` (TextGenerator: 文本分析完成，正面占比70%...)
    
    示例输出3（空）:
        返回空字符串
    """
    parts = []
    
    # 预处理文件
    # 兼容 origin_data 和直接的 preprocessed_files
    preprocessed_files = None
    if hasattr(state, 'origin_data') and state.origin_data.get("preprocessed_files"):
        # origin_data 是动态属性，需要 hasattr 检查
        preprocessed_files = state.origin_data["preprocessed_files"]
    elif state.preprocessed_files:
        # preprocessed_files 是 Pydantic 模型定义的字段，直接访问
        preprocessed_files = state.preprocessed_files
    
    if preprocessed_files:
        # 文档列表
        documents = preprocessed_files.get("documents", {})
        if documents:
            doc_list = []
            for filename in documents.keys():
                # 截取文件名的前30个字符作为简短描述
                short_name = filename if len(filename) <= 30 else filename[:27] + "..."
                doc_list.append(f"`{filename}`")
            parts.append(f"文档({len(documents)}): {', '.join(doc_list[:3])}" + 
                        ("..." if len(doc_list) > 3 else ""))
        
        # 表格列表
        tables = preprocessed_files.get("tables", {})
        if tables:
            table_list = []
            for filename in tables.keys():
                short_name = filename if len(filename) <= 30 else filename[:27] + "..."
                table_list.append(f"`{filename}`")
            parts.append(f"表格({len(tables)}): {', '.join(table_list[:3])}" + 
                        ("..." if len(table_list) > 3 else ""))
    
    # 历史执行结果
    valuable_results = [(aid, data) for aid, data in state.full_action_data.items() 
                       if data.get("status") == "success" and data.get("reflection", {}).get("is_sufficient", False)]
    if valuable_results:
        result_entries = []
        for action_id, data in valuable_results[:3]:
            tool_name = data.get("tool_name", "unknown")
            brief_description = data.get("brief_description", "")[:30]
            # 提供更详细的信息，包括工具名和简要描述
            result_entries.append(f"`{action_id}` ({tool_name}: {brief_description})")
        parts.append(f"可用历史结果({len(valuable_results)}): {', '.join(result_entries)}" + 
                    ("..." if len(valuable_results) > 3 else ""))
    
    # 如果有任何成功的结果（不管是否充分），也列出来
    all_success = [(aid, data) for aid, data in state.full_action_data.items() if data.get("status") == "success"]
    if len(all_success) > len(valuable_results):
        other_results = [(aid, data) for aid, data in all_success if (aid, data) not in valuable_results][:2]
        if other_results:
            other_entries = [f"`{aid}` ({data.get('tool_name', 'unknown')})" for aid, data in other_results]
            parts.append(f"其他结果: {', '.join(other_entries)}")

    return "### 可用的用户数据:\n" + "\n".join(f"- {part}" for part in parts) if parts else ""