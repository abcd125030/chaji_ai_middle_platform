# -*- coding: utf-8 -*-
"""
build_todo_section_for_prompt.py

构建任务清单部分的文本描述。
供 prompt_builder.py 调用，用于生成任务清单说明文档。

返回值示例:
    返回格式化的 Markdown 文本，包含任务清单的进度、推荐执行任务和待完成任务：
    '''
    ### 任务清单（完成：2/5 | 进度：40%）

    **🎯 推荐执行任务：**
    - **任务1**: 搜索相关资料
      - **建议工具**：web_search, knowledge_base
      - **执行提示**：先搜索最新信息，再查询知识库
    
    **待完成任务：**
      - 📌 任务1: 搜索相关资料
      - 📌 任务2: 分析数据
      - ⚡ 任务3: 生成报告
    
    **已完成任务：**（2项）
      - ✅ 任务4: 数据收集
      - ✅ 任务5: 数据清洗
    '''
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentic.core.schemas import RuntimeState


def build_todo_section_for_prompt(state: 'RuntimeState') -> str:
    """
    构建任务清单部分的文本描述。
    
    参数:
        state: 运行时状态对象，包含任务清单信息
    
    返回:
        str: 格式化的任务清单文本，使用 Markdown 格式。
        
        返回值格式：
        - 任务清单标题包含完成数量和进度百分比
        - 推荐执行任务部分显示下一个可执行的任务
        - 待完成任务列表显示所有待处理和进行中的任务
        - 已完成任务显示最近完成的3个任务
        
        特殊情况：
        - 如果没有任务清单，返回空字符串
        - 如果没有可执行任务，不显示推荐执行任务部分
        - 如果没有已完成任务，不显示已完成任务部分
    
    示例:
        >>> from agentic.core.schemas import RuntimeState
        >>> state = RuntimeState()
        >>> state.todo = [
        ...     {'id': 1, 'task': '搜索资料', 'status': 'pending', 
        ...      'suggested_tools': ['web_search'], 'execution_tips': '使用最新数据'},
        ...     {'id': 2, 'task': '分析数据', 'status': 'processing'},
        ...     {'id': 3, 'task': '生成报告', 'status': 'completed'}
        ... ]
        >>> result = build_todo_section_for_prompt(state)
        >>> print(result)
        ### 任务清单（完成：1/3 | 进度：33%）
        
        **🎯 推荐执行任务：**
        - **任务1**: 搜索资料
          - **建议工具**：web_search
          - **执行提示**：使用最新数据
        
        **待完成任务：**
          - 📌 任务1: 搜索资料
          - ⚡ 任务2: 分析数据
        
        **已完成任务：**（1项）
          - ✅ 任务3: 生成报告
    """
    if not state.todo:
        return ""
        
    completed_count = sum(1 for t in state.todo if t.get('status') == 'completed')
    processing_count = sum(1 for t in state.todo if t.get('status') == 'processing')
    failed_count = sum(1 for t in state.todo if t.get('status') == 'failed')
    pending_count = sum(1 for t in state.todo if t.get('status', 'pending') == 'pending')
    total_count = len(state.todo)
    
    # 计算进度
    total_progress = (completed_count / total_count * 100) if total_count > 0 else 0
    
    # 构建任务清单文本
    todo_text = f"\n### 任务清单（完成：{completed_count}/{total_count} | 进度：{total_progress:.0f}%）\n"
    
    # 找出可执行的任务
    executable_tasks = []
    for task in state.todo:
        if task.get('status', 'pending') == 'pending':
            dependencies = task.get('dependencies', [])
            unmet_deps = []
            
            if dependencies:
                for dep_id in dependencies:
                    dep_task = next((t for t in state.todo if t.get('id') == dep_id), None)
                    if not dep_task or dep_task.get('status', 'pending') != 'completed':
                        unmet_deps.append(dep_id)
            
            if not unmet_deps:
                executable_tasks.append(task)
    
    # 显示推荐的下一个任务
    if executable_tasks:
        next_task = executable_tasks[0]
        todo_text += f"\n**🎯 推荐执行任务：**\n"
        todo_text += f"- **任务{next_task.get('id')}**: {next_task.get('task')}\n"
        todo_text += f"  - **建议工具**：{', '.join(next_task.get('suggested_tools', ['未指定']))}\n"
        if next_task.get('execution_tips'):
            todo_text += f"  - **执行提示**：{next_task.get('execution_tips')}\n"
    
    # 显示待完成任务
    todo_text += "\n**待完成任务：**\n"
    for task in state.todo:
        if task.get('status', 'pending') in ['pending', 'processing']:
            task_id = task.get('id', '?')
            task_desc = task.get('task', '未知任务')
            status_icon = "⚡" if task.get('status') == 'processing' else "📌"
            todo_text += f"  - {status_icon} 任务{task_id}: {task_desc}\n"
    
    # 显示已完成任务（简略）
    if completed_count > 0:
        todo_text += f"\n**已完成任务：**（{completed_count}项）\n"
        for task in [t for t in state.todo if t.get('status') == 'completed'][:3]:
            task_id = task.get('id', '?')
            task_desc = task.get('task', '未知任务')
            todo_text += f"  - ✅ 任务{task_id}: {task_desc}\n"
    
    return todo_text