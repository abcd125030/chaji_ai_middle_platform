"""
生成器工具的共享上下文提取模块

提供统一的方法从 RuntimeState 中提取所需的上下文数据，
供 report_generator 和 text_generator 调用。
"""

from typing import Dict, Any, List, Optional
import json
import logging

logger = logging.getLogger('django')


def extract_context_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 RuntimeState 中提取生成器工具所需的上下文数据
    
    参数:
        state: RuntimeState 的字典形式，包含完整的执行状态
        
    返回:
        包含以下字段的字典:
        - task_goal: 原始任务目标
        - tool_outputs: 工具输出列表
        - chat_history: 对话历史
        - preprocessed_files: 预处理的文件数据
        - user_prompt: 本轮用户的输入
    """
    # 获取原始任务目标
    task_goal = state.get('_original_task_goal') or state.get('task_goal', '')
    
    # 提取工具输出
    tool_outputs = _extract_tool_outputs(state.get('action_history', []))
    
    # 获取对话历史
    chat_history = state.get('chat_history', [])
    
    # 获取本轮用户输入（从 chat_history 最后一条获取）
    user_prompt = ''
    if chat_history and len(chat_history) > 0:
        last_message = chat_history[-1]
        if isinstance(last_message, dict) and last_message.get('role') == 'user':
            user_prompt = last_message.get('content', '')
    
    # 如果 chat_history 为空或没有用户消息，使用 task_goal
    if not user_prompt:
        user_prompt = task_goal
    
    # 获取预处理文件
    preprocessed_files = state.get('preprocessed_files', {})
    
    return {
        'task_goal': task_goal,
        'tool_outputs': tool_outputs,
        'chat_history': chat_history,
        'preprocessed_files': preprocessed_files,
        'user_prompt': user_prompt
    }


def _extract_tool_outputs(action_history: List[Any]) -> List[Dict[str, Any]]:
    """
    从 action_history 中提取所有工具输出

    action_history 是嵌套列表结构: [[round1_actions], [round2_actions], ...]
    每个round是一个列表，包含多个action dict

    返回:
        工具输出列表，每个元素包含:
        - source: 工具名称
        - content: 输出内容
        - citations: 引用信息（如果有）
    """
    outputs = []

    # 扁平化处理：action_history是嵌套列表
    for round_actions in action_history:
        # 如果是列表，遍历其中的actions
        if isinstance(round_actions, list):
            actions_to_process = round_actions
        # 如果是dict（旧格式兼容），直接处理
        elif isinstance(round_actions, dict):
            actions_to_process = [round_actions]
        else:
            continue

        # 用于追踪当前工具名称（tool_output 需要从前面的 plan 节点获取工具名）
        current_tool_name = None

        # 处理本轮的所有actions
        for item in actions_to_process:
            if not isinstance(item, dict):
                continue

            item_type = item.get('type')
            data = item.get('data', {})

            # 提取规划节点的思考过程和工具名称
            if item_type == 'plan':
                thought = data.get('output')
                if thought:
                    outputs.append({
                        'source': 'planner_thought',
                        'content': thought
                    })
                    logger.debug("[CONTEXT] 提取到规划节点的思考过程")

                # 记录plan节点指定的工具名称，供后续tool_output使用
                if data.get('action') == 'CALL_TOOL':
                    current_tool_name = data.get('tool_name')

            # 提取工具输出
            elif item_type == 'tool_output':
                output_value = data.get('output')
                if output_value:
                    # 使用从plan节点获取的工具名，如果没有则尝试从data中获取
                    tool_name = current_tool_name or data.get('tool_name', '未知工具')

                    # 构建输出项
                    output_item = {
                        'source': tool_name,
                        'content': output_value
                    }

                    # 特殊处理包含引用的输出（如 GoogleSearch）
                    if data.get('citations'):
                        output_item['citations'] = data.get('citations')

                    outputs.append(output_item)
                    logger.debug(f"[CONTEXT] 提取到 {tool_name} 的输出数据")

                    # 重置工具名称，避免影响后续的tool_output
                    current_tool_name = None

            # 提取反思节点的输出
            elif item_type == 'reflection':
                reflection = data.get('output')
                if reflection:
                    outputs.append({
                        'source': 'reflection',
                        'content': reflection
                    })
                    logger.debug("[CONTEXT] 提取到反思节点的输出")

    logger.info(f"[CONTEXT] 总共提取到 {len(outputs)} 个数据源")
    return outputs


def format_tool_outputs_as_text(tool_outputs: List[Dict[str, Any]]) -> str:
    """
    将工具输出列表格式化为文本
    
    参数:
        tool_outputs: 工具输出列表
        
    返回:
        格式化后的文本字符串
    """
    if not tool_outputs:
        return ""
    
    formatted_parts = []
    for output in tool_outputs:
        source = output.get('source', '未知来源')
        content = output.get('content', '')
        
        # 格式化单个输出
        formatted_part = f"【{source}】\n{content}"
        
        # 如果有引用信息，添加引用
        if output.get('citations'):
            citations = output.get('citations')
            if isinstance(citations, list):
                formatted_part += "\n参考来源："
                for citation in citations:
                    if isinstance(citation, dict):
                        title = citation.get('title', '')
                        url = citation.get('url', '')
                        if url:
                            formatted_part += f"\n- {title}: {url}"
        
        formatted_parts.append(formatted_part)
    
    return "\n\n---\n\n".join(formatted_parts)


def format_tool_outputs_as_json(tool_outputs: List[Dict[str, Any]]) -> str:
    """
    将工具输出列表格式化为 JSON 字符串
    
    参数:
        tool_outputs: 工具输出列表
        
    返回:
        JSON 格式的字符串
    """
    if not tool_outputs:
        return "[]"
    
    return json.dumps(tool_outputs, ensure_ascii=False, indent=2)


def get_preprocessed_documents(preprocessed_files: Dict[str, Any]) -> Dict[str, str]:
    """
    从预处理文件中提取文档内容
    
    返回:
        文档字典，键为文件名，值为内容
    """
    if not preprocessed_files:
        return {}
    
    return preprocessed_files.get('documents', {})


def get_preprocessed_tables(preprocessed_files: Dict[str, Any]) -> Dict[str, Any]:
    """
    从预处理文件中提取表格数据
    
    返回:
        表格字典，键为文件名，值为表格数据
    """
    if not preprocessed_files:
        return {}
    
    return preprocessed_files.get('tables', {})