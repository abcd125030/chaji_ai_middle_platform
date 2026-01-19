"""
输出节点
负责根据 Planner 提供的 output_guidance 选择合适的输出工具生成最终答案
"""
import logging  # T010: 启用日志记录
import json
from typing import Dict, Any, Optional
from ..core.schemas import RuntimeState
from llm.core_service import CoreLLMService
from llm.config_manager import ModelConfigManager

# T010: 初始化logger
logger = logging.getLogger('django')

def clean_action_id(action_id: str) -> str:
    """清理action_id，移除${}占位符格式"""
    if action_id.startswith('${') and action_id.endswith('}'):
        return action_id[2:-1]  # 移除 ${ 和 }
    return action_id

# 错误码定义
class ErrorCode:
    """
    Output 节点错误码定义

    错误码格式: ON_XXXX
    - ON: Output Node 前缀
    - XXXX: 四位数字编码

    错误码映射关系:
    ===================================
    业务错误码 | HTTP状态码 | 错误描述
    ===================================
    ON_0000  | 200      | 成功
    ON_1001  | 400      | 无法获取历史数据
    ON_1002  | 400      | LLM 响应格式异常
    ON_2001  | 503      | LLM 服务不可用（网络错误）
    ON_2002  | 504      | LLM 服务超时
    ON_2003  | 429      | LLM 服务限流
    ON_2004  | 401      | LLM 认证失败
    ON_3001  | 500      | 内部处理错误
    ON_3002  | 500      | 配置错误
    """
    SUCCESS = "ON_0000"
    NO_HISTORY_DATA = "ON_1001"
    INVALID_LLM_RESPONSE = "ON_1002"
    LLM_SERVICE_UNAVAILABLE = "ON_2001"
    LLM_SERVICE_TIMEOUT = "ON_2002"
    LLM_RATE_LIMIT = "ON_2003"
    LLM_AUTH_ERROR = "ON_2004"
    INTERNAL_ERROR = "ON_3001"
    CONFIG_ERROR = "ON_3002"

# 错误消息映射
ERROR_MESSAGES = {
    ErrorCode.NO_HISTORY_DATA: "无法获取指定的历史数据",
    ErrorCode.INVALID_LLM_RESPONSE: "AI 模型返回数据格式异常",
    ErrorCode.LLM_SERVICE_UNAVAILABLE: "AI 服务暂时不可用，请稍后重试",
    ErrorCode.LLM_SERVICE_TIMEOUT: "AI 服务响应超时，请稍后重试",
    ErrorCode.LLM_RATE_LIMIT: "请求频率过高，请稍后重试",
    ErrorCode.LLM_AUTH_ERROR: "AI 服务认证失败",
    ErrorCode.INTERNAL_ERROR: "内部处理错误",
    ErrorCode.CONFIG_ERROR: "服务配置错误"
}

def get_error_code_from_exception(e: Exception) -> str:
    """
    根据异常类型返回对应的错误码

    参数:
    e: 异常对象

    返回:
    错误码字符串
    """
    error_str = str(e).lower()

    # 网络连接错误
    if any(keyword in error_str for keyword in [
        'connectionpool', 'connection', 'proxy', 'network',
        'remote end closed', 'max retries exceeded'
    ]):
        return ErrorCode.LLM_SERVICE_UNAVAILABLE

    # 超时错误
    if any(keyword in error_str for keyword in ['timeout', 'timed out']):
        return ErrorCode.LLM_SERVICE_TIMEOUT

    # 限流错误
    if any(keyword in error_str for keyword in ['rate limit', '429', 'too many requests']):
        return ErrorCode.LLM_RATE_LIMIT

    # 认证错误
    if any(keyword in error_str for keyword in ['401', 'unauthorized', 'auth', 'authentication']):
        return ErrorCode.LLM_AUTH_ERROR

    # 配置错误
    if any(keyword in error_str for keyword in ['config', 'configuration']):
        return ErrorCode.CONFIG_ERROR

    # 默认为内部错误
    return ErrorCode.INTERNAL_ERROR

def generate_output_tool_input(
    state: RuntimeState,
    output_guidance: Optional[Any],
    tool_name: str
) -> Dict[str, Any]:
    """
    为输出工具准备输入参数（简化版本 - 直接传递 state）

    参数:
    state: 运行时状态
    output_guidance: Planner的指导信息
    tool_name: 输出工具名称

    返回:
    工具输入参数字典
    """
    # 将 RuntimeState 转换为字典形式
    if hasattr(state, 'model_dump'):
        state_dict = state.model_dump()
    elif hasattr(state, 'dict'):
        state_dict = state.dict()
    else:
        # 如果是普通对象，获取其属性
        state_dict = {
            'task_goal': state.task_goal,
            '_original_task_goal': getattr(state, '_original_task_goal', state.task_goal),
            'action_history': state.action_history,
            'chat_history': state.chat_history,
            'preprocessed_files': state.preprocessed_files,
            'user_context': getattr(state, 'user_context', {})
        }
    
    # 确保 _original_task_goal 被包含在 state_dict 中
    if hasattr(state, '_original_task_goal'):
        state_dict['_original_task_goal'] = state._original_task_goal
    
    # 统一的输入格式：传递完整的 state 和可选的 output_guidance
    tool_input = {
        'state': state_dict
    }
    
    # 根据不同的工具类型添加特定参数
    if tool_name in ['ReportGenerator', 'report_generator', 'TextGenerator', 'text_generator']:
        # 这些工具都使用新的统一输入格式
        if output_guidance:
            tool_input['output_guidance'] = output_guidance
    else:
        # 其他工具保持原有逻辑（向后兼容）
        tool_input['user_id'] = state.user_id if hasattr(state, 'user_id') else None
        if output_guidance:
            tool_input.update(output_guidance)

    logger.debug(f"""
[OUTPUT] 为工具准备输入
工具名称: {tool_name}
输入包含字段: {list(tool_input.keys())}
""")

    return tool_input


def output_node(
    state: RuntimeState,
    nodes_map: Optional[Dict[str, Any]] = None,
    user=None,
    session_id: Optional[str] = None,
    output_guidance: Optional[Any] = None
) -> Dict[str, Any]:
    """
    必须从提供的输出工具列表中选择一个工具来生成最终答案

    参数:
    state: 运行时状态
    nodes_map: 节点配置映射
    user: 用户对象（用于日志记录）
    session_id: 会话ID（用于日志记录）
    output_guidance: Planner 提供的指导信息

    返回:
    选择输出工具的决策
    """
    logger.info(f"""
[OUTPUT] 开始输出节点处理
用户ID: {getattr(state, 'user_id', 'N/A')}
任务目标: {getattr(state, '_original_task_goal', getattr(state, 'task_goal', 'N/A'))}
是否有输出指导: {output_guidance is not None}
""")

    # 获取可用的输出类工具
    from tools.core.registry import ToolRegistry
    registry = ToolRegistry()

    # 动态获取所有 generator 类别的工具作为输出工具
    output_tools = []
    all_tools_info = registry.list_tools_with_details(category='generator')
    
    for tool_info in all_tools_info:
        output_tools.append(tool_info['name'])

    logger.info(f"""
[OUTPUT] 发现可用输出工具
工具数量: {len(output_tools)}
工具列表: {', '.join(output_tools)}
""")

    # 收集输出工具的详细信息
    available_output_tools = []

    for tool_name in output_tools:
        try:
            # 从所有工具信息中查找特定工具
            tool_info = next((t for t in all_tools_info if t['name'] == tool_name), None)
            if tool_info:
                tool_class = registry.get_tool(tool_name)
                tool_instance = tool_class()
                param_schema = tool_instance.get_input_schema()

                available_output_tools.append({
                    'name': tool_name,
                    'description': tool_info.get('description', ''),
                    'parameters': param_schema
                })
            else:
                logger.warning(f"""
[OUTPUT] 未找到输出工具
工具名称: {tool_name}
""")
        except Exception as e:
            logger.warning(f"""
[OUTPUT] 无法获取输出工具信息
工具名称: {tool_name}
错误: {str(e)}
""")

    # 如果没有可用的输出工具，抛出错误
    if not available_output_tools:
        raise ValueError("[OUTPUT] 错误：没有可用的输出工具")

    # 构建提示词，让 LLM 选择最合适的输出工具
    core_service = CoreLLMService()
    config_manager = ModelConfigManager()

    # 使用统一的模型配置服务获取模型名称
    from agentic.core.model_config_service import NodeModelConfigService
    model_name = NodeModelConfigService.get_model_for_node('output', nodes_map)

    # 获取模型配置
    model_config = config_manager.get_model_config(model_name)

    # 准备工具信息的JSON格式
    tools_info = [
        {
            "name": tool['name'],
            "description": tool['description'],
            "parameters": tool['parameters']
        }
        for tool in available_output_tools
    ]

    # 构建系统提示词
    system_prompt = """你是一个输出工具选择专家。你的任务是根据用户需求和规划器的指导，从可用工具列表中选择最合适的一个来生成最终答案。

## 选择原则
1. **匹配度优先**：选择最符合用户需求和输出格式要求的工具
2. **功能适配**：考虑工具的能力是否满足任务需求
3. **格式要求**：优先满足指导信息中的格式要求

## 输出格式
必须返回一个严格的JSON对象，格式如下：
{
    "tool_name": "选中工具的名称（必须是提供列表中的工具）",
    "reason": "选择理由（简要说明为什么这个工具最合适）"
}

重要：
- tool_name 必须精确匹配提供的工具列表中的名称
- 不要添加任何JSON之外的文本
- 确保JSON格式正确可解析"""

    # 构建用户提示词
    user_prompt = f"""## 任务信息

### 用户原始需求
{state._original_task_goal}

### 规划器输出指导
{json.dumps(output_guidance, ensure_ascii=False, indent=2) if output_guidance else '{}'}

### 可用输出工具
{json.dumps(tools_info, ensure_ascii=False, indent=2)}

请根据以上信息选择最合适的输出工具。"""

    # 调用 LLM 选择工具
    try:
        # 使用文本生成模式
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 记录LLM请求
        system_prompt = messages[0]['content'] if messages and messages[0]['role'] == 'system' else ""
        user_prompt = messages[-1]['content'] if messages else ""
        log_llm_request("output_selector", system_prompt, user_prompt, model_name)
        
        # 调用 LLM API
        response = core_service.call_llm(
            model_id=model_config['model_id'],
            endpoint=model_config['endpoint'],
            api_key=model_config['api_key'],
            messages=messages,
            custom_headers=model_config.get('custom_headers'),
            params=model_config.get('params'),
            user=user,
            session_id=session_id,
            model_name=model_name,
            vendor_name=model_config.get('vendor_name'),
            vendor_id=model_config.get('vendor_id'),
            source_app='agentic',
            source_function='nodes.output.output_node'
        )
        
        # 记录LLM响应
        log_llm_response("output_selector", response)
        
        # 从响应中提取内容
        if isinstance(response, dict):
            response = response.get('choices', [{}])[0].get('message', {}).get('content', '')

        # 解析响应
        import re
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            tool_selection = json.loads(json_match.group())
            logger.info(f"""
[OUTPUT] LLM成功选择输出工具
选择的工具: {tool_selection.get('tool_name')}
选择理由: {tool_selection.get('reason', '未提供理由')}
""")
            # 从解析结果中提取工具名
            selected_tool = tool_selection.get('tool_name')
            if not selected_tool:
                # 如果没有明确指定工具，优先选择 TextGenerator
                text_generator = next((t for t in available_output_tools if t['name'] == 'TextGenerator'), None)
                if text_generator:
                    selected_tool = 'TextGenerator'
                    logger.warning(f"""
[OUTPUT] LLM未明确指定工具，使用默认工具
默认工具: TextGenerator
""")
                else:
                    selected_tool = available_output_tools[0]['name']
                    # 未找到TextGenerator日志将在后续添加
        else:
            # 如果解析失败，优先选择 TextGenerator，如果没有则使用第一个工具
            text_generator = next((t for t in available_output_tools if t['name'] == 'TextGenerator'), None)
            if text_generator:
                selected_tool = 'TextGenerator'
                # LLM响应解析失败警告将在后续添加
            else:
                selected_tool = available_output_tools[0]['name']
                # LLM响应解析失败未找到TextGenerator警告将在后续添加
    except Exception as e:
        # 如果调用失败，优先选择 TextGenerator，如果没有则使用第一个工具
        text_generator = next((t for t in available_output_tools if t['name'] == 'TextGenerator'), None)
        if text_generator:
            selected_tool = 'TextGenerator'
            # LLM调用失败错误日志将在后续添加
        else:
            selected_tool = available_output_tools[0]['name']
            # LLM调用失败未找到TextGenerator错误日志将在后续添加

    # 准备选中工具的输入参数
    tool_input = generate_output_tool_input(
        state, output_guidance, selected_tool
    )

    logger.info(f"""
[OUTPUT] 返回工具选择决策
选中工具: {selected_tool}
输入字段数: {len(tool_input)}
""")

    # 返回工具选择决策（供 processor 处理）
    return {
        'output_tool_decision': {
            'tool_name': selected_tool,
            'tool_input': tool_input
        }
    }