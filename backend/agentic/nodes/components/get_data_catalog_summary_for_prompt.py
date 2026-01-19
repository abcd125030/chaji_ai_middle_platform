# -*- coding: utf-8 -*-
"""
get_data_catalog_summary_for_prompt.py

获取数据目录摘要。
供 prompt_builder.py 调用，用于生成数据目录摘要信息。

返回值示例:
    返回格式化的 Markdown 文本，包含预处理文件和工具执行结果的摘要：
    '''
    ### 📂 数据目录

    **📄 文档** (3 个):
      - `doc_001`: 这是一份关于市场分析的报告，包含了2024年第一季度...
      - `doc_002`: 产品规格说明书，详细介绍了新款设备的技术参数...
      - `doc_003`: 用户手册第一章：快速入门指南...
    
    **📊 表格** (2 个):
      - `table_001`: 10行×5列
      - `table_002`: 50行×8列
    
    **🖼️ 图片** (4 个):
      - `image_001`
      - `image_002`
      - `image_003`
      - ...及其他 1 个图片
    
    **🔧 工具结果**:
      - web_search: 3 个结果 [act_001, act_002, act_003...]
      - table_analyzer: 2 个结果 [act_004, act_005...]
    '''
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentic.core.schemas import RuntimeState


def get_data_catalog_summary_for_prompt(state: 'RuntimeState') -> str:
    """
    获取数据目录摘要。
    
    参数:
        state: 运行时状态对象，包含预处理文件和执行历史信息
    
    返回:
        str: 数据目录摘要文本，使用 Markdown 格式。
        
        返回值格式：
        - 使用 ### 级标题表示数据目录
        - 分类显示文档、表格、图片等预处理文件
        - 每类最多显示3个示例，超过3个显示省略信息
        - 文档显示前50个字符的内容预览
        - 表格显示行数和列数
        - 图片仅显示ID
        - 工具结果按工具名分组显示数量和动作ID
        
        特殊情况：
        - 如果没有预处理文件和执行历史，返回空字符串
        - 优先从 origin_data 获取预处理文件，其次从 preprocessed_files 获取
        - 只显示成功执行的工具结果
    
    示例:
        >>> from agentic.core.schemas import RuntimeState, ActionSummary
        >>> state = RuntimeState()
        >>> # 设置预处理文件
        >>> state.preprocessed_files = {
        ...     "documents": {
        ...         "doc_001": {"content": "这是第一个文档的内容，包含了详细的分析报告..."},
        ...         "doc_002": {"content": "第二个文档是产品说明书"},
        ...         "doc_003": {"content": "第三个文档是用户指南"},
        ...         "doc_004": {"content": "第四个文档是技术规格"}
        ...     },
        ...     "tables": {
        ...         "table_001": {"headers": ["A", "B", "C"], "data": [[1,2,3], [4,5,6]]},
        ...         "table_002": {"headers": ["X", "Y"], "data": [[1,2]]}
        ...     },
        ...     "images": {
        ...         "image_001": {},
        ...         "image_002": {}
        ...     }
        ... }
        >>> # 设置执行历史
        >>> state.full_action_data = {
        ...     "act_001": {
        ...         "tool_name": "web_search",
        ...         "status": "success",
        ...         "result": {"message": "找到5条相关结果"}
        ...     },
        ...     "act_002": {
        ...         "tool_name": "web_search", 
        ...         "status": "success",
        ...         "result": {"message": "找到3条补充信息"}
        ...     },
        ...     "act_003": {
        ...         "tool_name": "table_analyzer",
        ...         "status": "failed",
        ...         "result": None
        ...     }
        ... }
        >>> result = get_data_catalog_summary_for_prompt(state)
        >>> print(result)
        ### 📂 数据目录
        
        **📄 文档** (4 个):
          - `doc_001`: 这是第一个文档的内容，包含了详细的分析报告...
          - `doc_002`: 第二个文档是产品说明书...
          - `doc_003`: 第三个文档是用户指南...
          - ...及其他 1 个文档
        
        **📊 表格** (2 个):
          - `table_001`: 2行×3列
          - `table_002`: 1行×2列
        
        **🖼️ 图片** (2 个):
          - `image_001`
          - `image_002`
        
        **🔧 工具结果**:
          - web_search: 2 个结果 [act_001, act_002...]
    """
    lines = []
    
    # 获取预处理文件信息
    preprocessed_files = {}
    if hasattr(state, 'origin_data') and state.origin_data.get("preprocessed_files"):
        preprocessed_files = state.origin_data["preprocessed_files"]
    elif state.preprocessed_files:
        preprocessed_files = state.preprocessed_files
    
    if not preprocessed_files and not state.full_action_data:
        return ""
    
    lines.append("### 📂 数据目录")
    
    # 显示预处理文件
    if preprocessed_files:
        # 文档
        if preprocessed_files.get("documents"):
            docs = preprocessed_files["documents"]
            lines.append(f"\n**📄 文档** ({len(docs)} 个):")
            for doc_id, doc_data in list(docs.items())[:3]:  # 最多显示3个
                content_preview = str(doc_data.get('content', ''))[:50]
                lines.append(f"  - `{doc_id}`: {content_preview}...")
            if len(docs) > 3:
                lines.append(f"  - ...及其他 {len(docs)-3} 个文档")
        
        # 表格
        if preprocessed_files.get("tables"):
            tables = preprocessed_files["tables"]
            lines.append(f"\n**📊 表格** ({len(tables)} 个):")
            for table_id, table_data in list(tables.items())[:3]:
                rows = len(table_data.get('data', []))
                cols = len(table_data.get('headers', []))
                lines.append(f"  - `{table_id}`: {rows}行×{cols}列")
            if len(tables) > 3:
                lines.append(f"  - ...及其他 {len(tables)-3} 个表格")
        
        # 图片
        if preprocessed_files.get("images"):
            images = preprocessed_files["images"]
            lines.append(f"\n**🖼️ 图片** ({len(images)} 个):")
            for img_id in list(images.keys())[:3]:
                lines.append(f"  - `{img_id}`")
            if len(images) > 3:
                lines.append(f"  - ...及其他 {len(images)-3} 个图片")
    
    # 显示工具执行结果数据
    if state.full_action_data:
        tool_results = {}
        for action_id, data in state.full_action_data.items():
            if data.get("status") == "success":
                tool_name = data.get("tool_name", "unknown")
                if tool_name not in tool_results:
                    tool_results[tool_name] = []
                tool_results[tool_name].append(action_id)
        
        if tool_results:
            lines.append(f"\n**🔧 工具结果**:")
            for tool, action_ids in tool_results.items():
                lines.append(f"  - {tool}: {len(action_ids)} 个结果 [{', '.join(action_ids[:3])}...]")
    
    return "\n".join(lines) if lines else ""