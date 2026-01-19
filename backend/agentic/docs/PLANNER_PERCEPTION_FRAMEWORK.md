# Planner 感知框架设计文档

## 设计理念

### 核心比喻：大模型如瞎子

**预设前提**：如果什么都不思考，大模型等同于瞎子。

就像瞎子面对他人提问时，需要系统化的"感知"过程来了解客观实际情况：

1. **听** - 理解问题（用户说了什么）
2. **摸** - 感知环境（已有什么信息）
3. **想** - 推理需求（还需要什么）
4. **问** - 获取信息（如何获取）
5. **判** - 评估完整度（够不够）
6. **答** - 组织输出（怎么说）

### 核心问题

Planner 需要系统化地回答这些问题：

```
【问题理解】
- 用户 prompt 是什么？
- 用户预期是什么样的？

【上下文评估】
- 已经有上下文了吗？
- 跟哪个历史信息有关吗？

【信息需求】
- 需要哪些信息来解决这个问题？
- 所有需要的信息中：
  - 哪些来自于经验？
  - 哪些需要搜索调研？
  - 哪些需要写代码去读取特定文件？
  - 哪些通过工具或数据节点就可以访问？

【缺口分析】
- 缺失的信息有哪些？
- 对信息完整度的要求是否过高了？

【输出规划】
- 用户偏好的风格是否有历史记录？
- 输出的内容应该是什么样的结构？
```

### 设计原则

1. **模块化感知**：每个感知是独立的短问题，planner 拼接这些模块
2. **层次递进**：先理解输入，再盘点资源，最后做决策
3. **依赖传递**：后续感知可以使用前置感知的结果
4. **避免重复**：部分感知可以缓存，避免重复执行
5. **简单实现**：使用简单函数 + LLM 调用 + 内存缓存，不引入复杂基础设施

## 感知模块架构

### 核心思想

将 Planner 的思考过程分解为 **9 个独立的短问题**：

```python
# 每个感知模块是一个独立函数
def perceive_xxx(state, **dependencies) -> str:
    """
    输入：RuntimeState + 依赖的前置感知结果
    处理：调用 LLM 回答一个短问题
    输出：简短的文本答案（不是 JSON）
    """
    prompt = build_short_question(...)
    return call_simple_llm(prompt)

# Planner 拼接这些模块
def planner_node_modular(state, ...):
    # 第一层：理解输入
    result_1 = perceive_dialog_context(state)
    result_2 = perceive_current_question(state, result_1)  # 依赖 result_1
    result_3 = perceive_question_type(state, result_1, result_2)  # 依赖多个
    ...

    # 第二层：盘点资源
    result_6 = perceive_available_data(state)
    ...

    # 第三层：决策
    decision = make_final_decision(all_perceptions, state)
    return decision
```

### 缓存机制（简化版）

使用**内存缓存**避免重复执行部分感知：

```python
# 全局缓存字典
perception_cache = {}

def get_or_compute_perception(key, compute_fn, state, force_recompute=False):
    """获取或计算感知结果"""
    cache_key = f"{state.session_id}:{key}"

    if not force_recompute and cache_key in perception_cache:
        logger.debug(f"[缓存命中] {key}")
        return perception_cache[cache_key]

    result = compute_fn(state)
    perception_cache[cache_key] = result
    return result
```

## 感知维度分类（9个模块）

### 第一层：理解输入（5个模块）

**核心原则**：层层递进，前面的感知结果可以传递给后面使用。

| 序号 | 模块名称 | 目的 | 依赖 | 输出 |
|------|---------|------|------|------|
| 1 | **多轮对话的语境** | 梳理对话历史，建立整体语境 | 无 | "之前讨论了XX话题，关键信息：A、B" |
| 2 | **用户当前说了什么** | **在语境中**理解当前问题 | 依赖1 | "用户的核心问题是：XX" |
| 3 | **当前问题的定位** | 判断是继承/针对/孤立问题 | 依赖1、2 | "继承：延续之前的XX任务" |
| 4 | **意图分析** | 推测用户为什么问这个 | 依赖2 | "用户想要XX，真实目的是YY" |
| 5 | **上下文要素** | 识别时间/地点/领域 | 依赖2 | "时间相关、话题领域：XX" |

### 第二层：盘点资源（4个模块）

| 序号 | 模块名称 | 目的 | 依赖 | 输出 |
|------|---------|------|------|------|
| 6 | **现有数据盘点** | 列出已经有哪些数据 | 无（独立） | "已有数据：A工具结果、B文件内容" |
| 7 | **可复用内容识别** | 判断哪些内容可以直接复用 | 依赖6 | "可复用：数据A的XX部分" |
| 8 | **信息缺口** | 识别还缺少哪些关键信息 | 依赖2、6 | "缺少：XX数据（高优先级）" |
| 9 | **质量标准** | 评估现有信息是否足够 | 依赖2、6、8 | "足够/不足 + 理由" |

### 第三层：决策（基于前两层的"反省"）

汇总所有感知结果，调用决策 LLM 生成 `PlannerOutput`（结构化输出）。

## 实现方案（简化版）

### 9个感知模块的实现

每个感知模块是一个独立的 Python 函数，接收必要的依赖，返回简短的文本答案。

#### 模块文件：`backend/agentic/nodes/perception_modules.py`

```python
# -*- coding: utf-8 -*-
"""
感知模块集合

每个模块负责回答一个短问题，返回简短的文本答案（不是JSON）
"""

from typing import Optional
from ..core.schemas import RuntimeState
from ..utils.logger_config import logger
from llm.core_service import CoreLLMService
from llm.config_manager import ModelConfigManager


def call_simple_llm(prompt: str, model_name: str = "gpt-4o-mini") -> str:
    """
    调用 LLM 回答简短问题
   
    使用轻量级模型，快速返回简短答案
    """
    core_service = CoreLLMService()
    config_manager = ModelConfigManager()
    model_config = config_manager.get_model_config(model_name)
   
    llm = core_service.get_llm(model_config, model_name=model_name)
    response = llm.invoke(prompt)
   
    return response.strip()


# ========== 第一层：理解输入 ==========

def perceive_dialog_context(state: RuntimeState) -> str:
    """模块1：多轮对话的语境"""
    if not state.chat_history:
        return "无对话历史，这是首次对话。"
   
    from .planner import format_chat_history_for_prompt
    chat_history_text = format_chat_history_for_prompt(state.chat_history)
   
    prompt = f"""对话历史：
{chat_history_text}

请简述：
1. 之前讨论了什么话题？（一句话）
2. 关键信息点有哪些？（列出2-3个）

简洁回答，不要啰嗦。"""
   
    return call_simple_llm(prompt)


def perceive_current_question(state: RuntimeState, dialog_context: str) -> str:
    """模块2：用户当前说了什么（代入语境）"""
   
    if dialog_context == "无对话历史，这是首次对话。":
        prompt = f"""用户说：{state.task_goal}

请用一句话总结：用户的核心问题是什么？"""
    else:
        prompt = f"""对话语境：
{dialog_context}

用户当前说：{state.task_goal}

请结合对话语境，用一句话总结：用户当前的核心问题是什么？"""
   
    return call_simple_llm(prompt)


def perceive_question_type(
    state: RuntimeState,
    dialog_context: str,
    current_question: str
) -> str:
    """模块3：当前问题的定位（依赖语境和当前问题）"""
   
    if dialog_context == "无对话历史，这是首次对话。":
        return "孤立：全新独立的问题（首次对话）"
   
    action_summary = ""
    if state.action_history:
        action_summary = f"\n执行历史：执行了 {len(state.action_history)} 轮操作"
   
    prompt = f"""对话语境：
{dialog_context}

用户当前问题：
{current_question}
{action_summary}

请判断问题类型（选一个）：
- 继承：延续之前的任务
- 针对：针对某次回答追问
- 孤立：全新独立的问题

格式：类型 + 理由（一句话）"""
   
    return call_simple_llm(prompt)


def perceive_intent(state: RuntimeState, current_question: str) -> str:
    """模块4：意图分析（依赖当前问题）"""
    prompt = f"""用户问题：{current_question}

请推测：用户为什么问这个？真实目的是什么？
（一句话，简洁）"""
   
    return call_simple_llm(prompt)


def perceive_context_elements(state: RuntimeState, current_question: str) -> str:
    """模块5：上下文要素（依赖当前问题）"""
    prompt = f"""用户问题：{current_question}

请识别（如果有）：
- 时间相关？
- 地点相关？
- 话题领域？

简洁回答，没有则写"无"。"""
   
    return call_simple_llm(prompt)


# ========== 第二层：盘点资源 ==========

def perceive_available_data(state: RuntimeState) -> str:
    """模块6：现有数据盘点"""
    from .planner import (
        get_data_catalog_summary_for_prompt,
        build_action_history_prompt
    )
   
    data_summary = get_data_catalog_summary_for_prompt(state)
    action_history_text = build_action_history_prompt(
        state.action_history[-1] if state.action_history else [],
        format_type="simple"
    )
   
    prompt = f"""数据目录：
{data_summary}

执行历史：
{action_history_text}

请列出：已经有哪些数据？（每项一句话，不超过5项）"""
   
    return call_simple_llm(prompt)


def perceive_reusable_content(state: RuntimeState, available_data: str) -> str:
    """模块7：可复用内容识别（依赖现有数据盘点）"""
    prompt = f"""已有数据：
{available_data}

请判断：哪些内容可以直接复用？
（列出2-3项，每项一句话，没有则写"无"）"""
   
    return call_simple_llm(prompt)


def perceive_information_gaps(
    state: RuntimeState,
    current_question: str,
    available_data: str
) -> str:
    """模块8：信息缺口（依赖当前问题和现有数据）"""
    prompt = f"""用户问题：
{current_question}

已有数据：
{available_data}

请列出：还缺少哪些关键信息？
（按重要性排序，每项一句话，不超过3项）"""
   
    return call_simple_llm(prompt)


def perceive_quality_standard(
    state: RuntimeState,
    current_question: str,
    available_data: str,
    information_gaps: str
) -> str:
    """模块9：质量标准（依赖多个前置结果）"""
    prompt = f"""用户问题：
{current_question}

已有数据：
{available_data}

信息缺口：
{information_gaps}

请评估：
1. 现有信息是否足够回答用户问题？（是/否）
2. 信息质量如何？（完整/基本满足/不足）
3. 理由（一句话）

格式：是/否 + 质量等级 + 理由"""
   
    return call_simple_llm(prompt)
```

### Planner 拼接这些模块

#### 模块化 Planner：`backend/agentic/nodes/planner_modular.py`

```python
# -*- coding: utf-8 -*-
"""
模块化 Planner 节点

将 Planner 的思考过程分解为 9 个独立的感知模块
"""

from typing import Dict, Any, Optional
from ..core.schemas import RuntimeState, PlannerOutput
from ..utils.logger_config import logger
from .perception_modules import (
    # 第一层
    perceive_dialog_context,
    perceive_current_question,
    perceive_question_type,
    perceive_intent,
    perceive_context_elements,
    # 第二层
    perceive_available_data,
    perceive_reusable_content,
    perceive_information_gaps,
    perceive_quality_standard,
)


def planner_node_modular(
    state: RuntimeState,
    nodes_map: Optional[Dict[str, Any]] = None,
    edges_map: Optional[Dict[str, Any]] = None,
    user=None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """模块化 Planner 节点（正确的依赖顺序）"""
   
    logger.info(f"[模块化 PLANNER] 开始规划任务: {state.task_goal[:100]}")
   
    # ========== 第一层：理解输入 ==========
    logger.info("[PLANNER] ========== 第一层：理解输入 ==========")
   
    # 1. 先建立语境（无依赖）
    logger.info("[PLANNER] 1/9 多轮对话的语境")
    dialog_context = perceive_dialog_context(state)
    logger.debug(f"  结果: {dialog_context}")
   
    # 2. 在语境中理解当前问题（依赖1）
    logger.info("[PLANNER] 2/9 用户当前说了什么")
    current_question = perceive_current_question(state, dialog_context)
    logger.debug(f"  结果: {current_question}")
   
    # 3. 判断问题定位（依赖1、2）
    logger.info("[PLANNER] 3/9 当前问题的定位")
    question_type = perceive_question_type(state, dialog_context, current_question)
    logger.debug(f"  结果: {question_type}")
   
    # 4. 意图分析（依赖2）
    logger.info("[PLANNER] 4/9 意图分析")
    intent_analysis = perceive_intent(state, current_question)
    logger.debug(f"  结果: {intent_analysis}")
   
    # 5. 上下文要素（依赖2）
    logger.info("[PLANNER] 5/9 上下文要素")
    context_elements = perceive_context_elements(state, current_question)
    logger.debug(f"  结果: {context_elements}")
   
    # ========== 第二层：盘点资源 ==========
    logger.info("[PLANNER] ========== 第二层：盘点资源 ==========")
   
    # 6. 现有数据盘点（无依赖第一层）
    logger.info("[PLANNER] 6/9 现有数据盘点")
    available_data = perceive_available_data(state)
    logger.debug(f"  结果: {available_data}")
   
    # 7. 可复用内容识别（依赖6）
    logger.info("[PLANNER] 7/9 可复用内容识别")
    reusable_content = perceive_reusable_content(state, available_data)
    logger.debug(f"  结果: {reusable_content}")
   
    # 8. 信息缺口（依赖2、6）
    logger.info("[PLANNER] 8/9 信息缺口")
    information_gaps = perceive_information_gaps(state, current_question, available_data)
    logger.debug(f"  结果: {information_gaps}")
   
    # 9. 质量标准（依赖2、6、8）
    logger.info("[PLANNER] 9/9 质量标准")
    quality_standard = perceive_quality_standard(
        state, current_question, available_data, information_gaps
    )
    logger.debug(f"  结果: {quality_standard}")
   
    # ========== 第三层：决策 ==========
    logger.info("[PLANNER] ========== 第三层：决策 ==========")
   
    # 汇总所有感知结果
    input_perceptions = {
        "dialog_context": dialog_context,
        "current_question": current_question,
        "question_type": question_type,
        "intent_analysis": intent_analysis,
        "context_elements": context_elements,
    }
   
    resource_perceptions = {
        "available_data": available_data,
        "reusable_content": reusable_content,
        "information_gaps": information_gaps,
        "quality_standard": quality_standard,
    }
   
    # 基于"反省"做决策
    decision = make_final_decision(
        input_perceptions=input_perceptions,
        resource_perceptions=resource_perceptions,
        state=state,
        nodes_map=nodes_map,
        user=user,
        session_id=session_id
    )
   
    return {"current_plan": decision}


def make_final_decision(
    input_perceptions: Dict[str, str],
    resource_perceptions: Dict[str, str],
    state: RuntimeState,
    nodes_map: Optional[Dict[str, Any]],
    user,
    session_id: Optional[str]
) -> PlannerOutput:
    """基于所有感知结果做最终决策"""
   
    from llm.core_service import CoreLLMService
    from llm.config_manager import ModelConfigManager
    from agentic.core.model_config_service import NodeModelConfigService
    from ..utils.logger_config import log_llm_request, log_llm_response
    from .planner import (
        get_tool_descriptions_for_prompt,
        build_action_history_prompt,
        get_data_catalog_summary_for_prompt,
        build_todo_section_for_prompt,
        format_chat_history_for_prompt,
        replace_data_markers
    )
   
    # 构建增强的 prompt
    tool_descriptions = get_tool_descriptions_for_prompt()
   
    current_action_history = state.action_history
    if current_action_history and isinstance(current_action_history[-1], list):
        current_action_history = current_action_history[-1]
   
    action_history_prompt = build_action_history_prompt(
        current_action_history,
        format_type="detailed"
    )
   
    data_summary = get_data_catalog_summary_for_prompt(state)
    todo_section = build_todo_section_for_prompt(state)
   
    chat_history_text = ""
    if state.chat_history:
        chat_history_text = format_chat_history_for_prompt(state.chat_history)
   
    user_info = ""
    if state.user_context:
        user_id = state.user_context.get('user_id', 'unknown')
        username = state.user_context.get('username', 'unknown')
        display_name = state.user_context.get('display_name', username)
        user_info = f"\n当前用户: {display_name} (ID: {user_id})\n"
   
    # System prompt
    system_prompt = f"""# 智能任务规划器

你负责理解用户需求并智能地选择合适的响应方式。

## 场景识别
- **日常对话**：问候、闲聊等简单交互，直接友好回复即可
- **简单任务**：单一明确的请求，可直接执行工具或给出答案
- **复杂任务**：如果评估任务需要超过3次工具调用才能完成，优先使用 TodoGenerator 创建任务清单

## 核心能力
1. **理解**: 准确判断用户意图（日常对话 vs 任务需求）
2. **规划**: 对于复杂任务，分解为可执行步骤（使用TodoGenerator）
3. **执行**: 调用合适的工具
4. **复用**: 充分利用已有结果
5. **评估**: 判断是否满足需求
6. **适应**: 根据反馈调整计划

## 可用工具详情与使用参数
{tool_descriptions}

## 关于任务完成（FINISH）

- 结合历史步骤理解已经获取的信息，如果足够输出符合用户prompt预期的结果，则选择 FINISH
- 系统会自动收集所有执行历史数据构建上下文，无需你提供具体内容
- 必须提供 output_guidance 输出指导，告诉系统如何组织和呈现答案
- 输出节点会根据任务特征自动选择合适的格式化工具
- 不要滥用知识库工具存储数据，除非是有价值的信息或用户的偏好、习惯、个性化信息

## 输出格式

**只有两种有效的action值：**
1. "CALL_TOOL" - 调用工具执行任务
2. "FINISH" - 完成任务（准备产出回答）

当使用 FINISH 时：
```json
{{
    "thought": "总结已完成的工作和关键发现",
    "action": "FINISH",
    "output_guidance": {{
        "key_points": ["要点1", "要点2"],
        "format_requirements": "格式要求",
        "quality_requirements": "质量要求",
        "custom_prompt": "额外指导"
    }}
}}
```

当使用 CALL_TOOL 时：
```json
{{
    "thought": "你的思考过程",
    "action": "CALL_TOOL",
    "tool_name": "工具名称",
    "tool_input": {{}},
    "expected_outcome": "期望的执行结果"
}}
```
"""
   
    # 构建包含感知结果的 user prompt
    thinking_section = f"""### 深度分析（基于系统化感知）

为了做出更好的决策，系统已从多个维度进行了分析：

#### 第一层：理解输入
- **对话语境**: {input_perceptions['dialog_context']}
- **当前问题**: {input_perceptions['current_question']}
- **问题定位**: {input_perceptions['question_type']}
- **意图分析**: {input_perceptions['intent_analysis']}
- **上下文要素**: {input_perceptions['context_elements']}

#### 第二层：盘点资源
- **现有数据**: {resource_perceptions['available_data']}
- **可复用内容**: {resource_perceptions['reusable_content']}
- **信息缺口**: {resource_perceptions['information_gaps']}
- **质量标准**: {resource_perceptions['quality_standard']}
"""
   
    user_prompt = f"""## 当前状态信息

### 原始任务
{state._original_task_goal or state.task_goal}
{user_info}
{chat_history_text}

### 执行历史
{action_history_prompt}

{data_summary}

{todo_section}

{thinking_section}

## 最终决策

基于以上所有信息和深度分析，请做出最终决策：下一步应该执行什么操作？"""
   
    # 实例化服务
    core_service = CoreLLMService()
    config_manager = ModelConfigManager()
   
    # 获取模型配置
    model_name = NodeModelConfigService.get_model_for_node('planner', nodes_map)
    model_config = config_manager.get_model_config(model_name)
   
    # 获取结构化输出 LLM
    LLM = core_service.get_structured_llm(
        PlannerOutput,
        model_config,
        user=user,
        session_id=session_id,
        model_name=model_name,
        source_app='agentic',
        source_function='nodes.planner_modular.make_final_decision'
    )
   
    # 记录请求
    log_llm_request("planner_modular", system_prompt, user_prompt, model_name)
   
    try:
        # 调用 LLM
        llm_result = LLM.invoke(user_prompt, system_prompt=system_prompt)
        log_llm_response("planner_modular", llm_result)
       
        # 后处理
        llm_result = _post_process_decision(llm_result, state)
       
        # 更新行动历史
        _update_action_history(state, llm_result)
       
        return llm_result
   
    except Exception as e:
        if "结构化输出解析失败" in str(e):
            logger.warning("[模块化 PLANNER] 结构化输出解析失败，重试一次")
            llm_result = LLM.invoke(user_prompt, system_prompt=system_prompt)
            log_llm_response("planner_modular", llm_result)
            llm_result = _post_process_decision(llm_result, state)
            _update_action_history(state, llm_result)
            return llm_result
        else:
            raise


def _post_process_decision(llm_result: PlannerOutput, state: RuntimeState) -> PlannerOutput:
    """后处理决策结果（与原 planner 逻辑一致）"""
    from .planner import replace_data_markers
   
    # 处理 FINISH
    if llm_result.action == "FINISH":
        if llm_result.final_answer:
            logger.warning(f"[模块化 PLANNER] 警告：Planner 提供了 final_answer，但系统将忽略它")
            llm_result.final_answer = None
            llm_result.title = None
   
    # 处理工具调用
    elif llm_result.action == "CALL_TOOL" and llm_result.tool_name:
        tool_input = llm_result.tool_input or {}
       
        # 自动补充 TodoGenerator 参数
        if llm_result.tool_name == "TodoGenerator":
            if "available_tools" not in tool_input:
                logger.info("[模块化 PLANNER] 自动补充 TodoGenerator 参数")
                from tools.core.registry import ToolRegistry
                registry = ToolRegistry()
                tools_list = registry.list_tools_with_details(category='libs')
               
                available_tools = []
                for tool_info in tools_list:
                    tool_name = tool_info["name"]
                    if tool_name != 'TodoGenerator':
                        available_tools.append({
                            "name": tool_name,
                            "description": tool_info.get("description", "")
                        })
               
                tool_input["available_tools"] = available_tools
       
        # 替换数据标记
        tool_input = replace_data_markers(tool_input, state)
        llm_result.tool_input = tool_input
   
    return llm_result


def _update_action_history(state: RuntimeState, llm_result: PlannerOutput):
    """更新行动历史（与原 planner 逻辑一致）"""
    plan_dict = llm_result.model_dump()
    plan_data = {
        "output": plan_dict.get("thought", ""),
        "action": plan_dict.get("action", ""),
        "tool_name": plan_dict.get("tool_name"),
        "tool_input": plan_dict.get("tool_input")
    }
   
    if not state.action_history:
        state.action_history = [[{"type": "plan", "data": plan_data}]]
    elif not isinstance(state.action_history[-1], list):
        raise ValueError("action_history 必须是嵌套列表格式")
    else:
        state.action_history[-1].append({"type": "plan", "data": plan_data})
```

### 集成到主 Planner

修改 `backend/agentic/nodes/planner.py`，添加开关：

```python
def planner_node(
    state: RuntimeState,
    nodes_map: Optional[Dict[str, Any]] = None,
    edges_map: Optional[Dict[str, Any]] = None,
    user=None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Planner 节点入口"""
   
    import os
    use_modular_planner = os.getenv('USE_MODULAR_PLANNER', 'false').lower() == 'true'
   
    if use_modular_planner:
        logger.info("[PLANNER] 使用模块化版本")
        from .planner_modular import planner_node_modular
        return planner_node_modular(state, nodes_map, edges_map, user, session_id)
   
    # 原有实现
    logger.info("[PLANNER] 使用原始版本")
    # ... 原有代码 ...
```

## 使用指南

### 配置环境变量

```bash
# backend/.env
USE_MODULAR_PLANNER=true  # 启用模块化 Planner
```

### 测试

```bash
# 启用模块化 Planner
export USE_MODULAR_PLANNER=true

# 运行测试
cd /Users/chagee/Repos/X/backend
source .venv/bin/activate
python manage.py test agentic.tests.test_planner
```

### 调试

查看日志输出，每个感知模块都会打印：
- 模块序号和名称
- 感知结果（简短文本）

示例日志：
```
[PLANNER] ========== 第一层：理解输入 ==========
[PLANNER] 1/9 多轮对话的语境
  结果: 之前讨论了用户数据分析，关键信息：需要行为数据、时间范围30天
[PLANNER] 2/9 用户当前说了什么
  结果: 用户的核心问题是：如何生成数据分析报告
...
```

## 优势总结

| 维度 | 原版 planner | 模块化 planner |
|------|-------------|---------------|
| **思考方式** | 一次性大 prompt | 9个短问题，层层递进 |
| **依赖关系** | 隐式（在prompt中） | 显式（参数传递） |
| **可控性** | LLM 自由发挥 | 每个模块独立可控 |
| **可调试** | 难以定位问题 | 每步都有清晰日志 |
| **可扩展** | 修改大 prompt | 增加一个感知函数 |
| **实现复杂度** | 简单 | 中等（9个函数） |
| **基础设施** | 无 | 无（仅内存缓存） |

## 下一步

1. **实现 9 个感知模块**：创建 `perception_modules.py`
2. **实现模块化 Planner**：创建 `planner_modular.py`
3. **集成到主 Planner**：添加环境变量开关
4. **单元测试**：测试每个感知模块的输出
5. **端到端测试**：对比原版和模块化版本的效果
6. **性能评估**：token 消耗对比（可能会稍高，因为多次 LLM 调用）
7. **效果评估**：决策质量是否提升（更准确的理解和规划）
