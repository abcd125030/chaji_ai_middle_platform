# -*- coding: utf-8 -*-
"""
planner_with_claude_code.py

使用 Claude Code CLI + Slash Commands 增强 planner 的思考流程。

核心思路：
1. 保持 planner 的整体结构不变
2. 在内部决策前，通过多轮 slash commands 进行"自我提问"
3. 每个 slash command 负责一个特定的思考维度
4. 汇总所有思考结果，形成更丰富的上下文
5. 最终调用决策 LLM 生成 PlannerOutput
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from ..utils.logger_config import logger
from ..core.schemas import RuntimeState, PlannerOutput
from .planner import (
    get_tool_descriptions_for_prompt,
    build_action_history_prompt,
    format_chat_history_for_prompt,
    get_data_catalog_summary_for_prompt,
    build_todo_section_for_prompt,
    replace_data_markers
)


@dataclass
class ThinkingStep:
    """单个思考步骤的结果"""
    command: str              # slash command 名称
    question: str             # 问题描述
    answer: str               # Claude Code 的回答
    duration: float           # 执行耗时


class ClaudeCodeThinkingEngine:
    """基于 Claude Code 的思考引擎"""

    def __init__(
        self,
        workspace: Path,
        base_url: str = None,
        model: str = None,
        timeout: int = 30
    ):
        """
        参数:
        workspace: 工作空间目录
        base_url: 自定义 API base URL
        model: 自定义模型
        timeout: 单个命令的超时时间
        """
        self.workspace = workspace
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

        # 创建工作空间
        self.workspace.mkdir(parents=True, exist_ok=True)

        # 初始化 Claude Code 配置
        self._setup_claude_code()

        # 初始化 slash commands
        self._setup_slash_commands()

    def _setup_claude_code(self):
        """设置 Claude Code 配置"""
        claude_dir = self.workspace / ".claude"
        claude_dir.mkdir(exist_ok=True)

        settings = {"env": {}}

        if self.base_url:
            settings["env"]["ANTHROPIC_BASE_URL"] = self.base_url
            logger.info(f"[思考引擎] 配置 base_url: {self.base_url}")

        if self.model:
            settings["env"]["CLAUDE_MODEL"] = self.model
            logger.info(f"[思考引擎] 配置模型: {self.model}")

        # 写入配置
        settings_file = claude_dir / "settings.json"
        settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False))

    def _setup_slash_commands(self):
        """初始化 slash commands"""
        commands_dir = self.workspace / ".claude" / "commands"
        commands_dir.mkdir(exist_ok=True)

        # 定义思考步骤的 slash commands
        commands = {
            "evaluate-progress.md": """# 评估任务进度

请分析当前任务的完成情况：

## 原始任务
{{TASK_GOAL}}

## 执行历史
{{ACTION_HISTORY}}

## 数据状态
{{DATA_SUMMARY}}

## 待办清单
{{TODO_SECTION}}

请回答以下问题：
1. 任务完成到什么程度？（用百分比估算）
2. 已经获取了哪些关键信息？
3. 还有哪些信息是必需但尚未获取的？
4. 当前进展是否符合预期？

请简洁回答，重点突出关键信息。
""",

            "analyze-available-data.md": """# 分析可用数据

请分析当前已有的数据和工具：

## 已有数据
{{DATA_SUMMARY}}

## 可用工具
{{TOOL_DESCRIPTIONS}}

## 执行历史
{{ACTION_HISTORY}}

请回答以下问题：
1. 哪些数据可以直接复用？
2. 哪些数据需要进一步处理？
3. 是否存在冗余或重复的信息？
4. 哪些工具尚未使用但可能有用？

请简洁回答，重点突出可复用的资源。
""",

            "identify-information-gaps.md": """# 识别信息缺口

请识别当前的信息缺口：

## 任务目标
{{TASK_GOAL}}

## 已获取信息
{{DATA_SUMMARY}}

## 执行历史
{{ACTION_HISTORY}}

请回答以下问题：
1. 为了完成任务，还缺少哪些关键信息？
2. 这些信息的重要性如何？（必需 / 重要 / 可选）
3. 获取这些信息需要使用哪些工具？
4. 是否存在信息获取的依赖关系？

请简洁回答，按重要性排序。
""",

            "suggest-next-action.md": """# 建议下一步行动

基于以上分析，请建议下一步行动：

## 任务目标
{{TASK_GOAL}}

## 进度评估
{{PROGRESS_EVALUATION}}

## 数据分析
{{DATA_ANALYSIS}}

## 信息缺口
{{INFORMATION_GAPS}}

## 可用工具
{{TOOL_DESCRIPTIONS}}

请回答以下问题：
1. 下一步应该做什么？（调用工具 / 完成任务）
2. 如果调用工具，应该使用哪个工具？为什么？
3. 工具的输入参数应该是什么？
4. 预期这个工具会产生什么结果？

请简洁回答，直接给出建议。
""",

            "evaluate-completion.md": """# 评估任务是否可以完成

请评估任务是否已经可以完成：

## 任务目标
{{TASK_GOAL}}

## 已获取信息
{{DATA_SUMMARY}}

## 执行历史
{{ACTION_HISTORY}}

## 用户对话历史
{{CHAT_HISTORY}}

请回答以下问题：
1. 是否已经获取了所有必需的信息？
2. 是否能够给出满足用户需求的答案？
3. 答案的质量如何？（完整 / 基本满足 / 不足）
4. 如果完成任务，应该重点呈现哪些内容？

请简洁回答，给出明确的完成 / 未完成判断。
"""
        }

        # 写入 slash command 文件
        for filename, content in commands.items():
            command_file = commands_dir / filename
            command_file.write_text(content, encoding='utf-8')
            logger.debug(f"[思考引擎] 创建命令: /{filename.replace('.md', '')}")

    def execute_command(self, command_name: str, context: Dict[str, str]) -> str:
        """
        执行单个 slash command

        参数:
        command_name: 命令名称（不含 /）
        context: 上下文变量（用于替换命令中的占位符）

        返回:
        str: Claude Code 的回答
        """
        import time
        start_time = time.time()

        logger.info(f"[思考引擎] 执行命令: /{command_name}")

        # 准备上下文文件（用于传递复杂内容）
        context_file = self.workspace / f".context_{command_name}.json"
        context_file.write_text(json.dumps(context, indent=2, ensure_ascii=False))

        try:
            # 构建命令
            cmd = [
                "claude",
                f"/{command_name}",  # 调用 slash command
                "--output-format", "text",  # 使用文本输出（更自然）
            ]

            # 设置环境变量
            env = {
                **os.environ.copy(),
                "HOME": str(self.workspace),
            }

            # 从 Django settings 获取 API key
            from django.conf import settings
            if hasattr(settings, 'ANTHROPIC_API_KEY'):
                env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY

            # 执行命令
            result = subprocess.run(
                cmd,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                input=self._prepare_input(command_name, context)  # 通过 stdin 传递上下文
            )

            if result.returncode != 0:
                logger.error(f"[思考引擎] 命令执行失败: {result.stderr}")
                raise Exception(f"命令执行失败: {result.stderr}")

            duration = time.time() - start_time
            logger.info(f"[思考引擎] 命令完成，耗时: {duration:.2f}s")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.warning(f"[思考引擎] 命令超时: /{command_name}")
            return "[超时：未能在规定时间内完成思考]"

        except Exception as e:
            logger.error(f"[思考引擎] 命令执行异常: {e}")
            return f"[错误：{str(e)}]"

        finally:
            # 清理临时文件
            if context_file.exists():
                context_file.unlink()

    def _prepare_input(self, command_name: str, context: Dict[str, str]) -> str:
        """
        准备命令输入（替换占位符）

        读取 slash command 文件，替换 {{VARIABLE}} 占位符
        """
        command_file = self.workspace / ".claude" / "commands" / f"{command_name}.md"

        if not command_file.exists():
            return ""

        content = command_file.read_text(encoding='utf-8')

        # 替换占位符
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, value)

        return content

    def think_step_by_step(self, state: RuntimeState, nodes_map: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        逐步思考，执行所有思考步骤

        返回:
        Dict[str, str]: 各个思考步骤的结果
        """
        # 准备基础上下文
        base_context = self._prepare_base_context(state, nodes_map)

        thinking_results = {}

        # 步骤 1：评估进度
        logger.info("[思考引擎] 步骤 1/4：评估任务进度")
        progress_eval = self.execute_command("evaluate-progress", base_context)
        thinking_results["progress_evaluation"] = progress_eval
        logger.debug(f"[思考引擎] 进度评估:\n{progress_eval}")

        # 步骤 2：分析数据
        logger.info("[思考引擎] 步骤 2/4：分析可用数据")
        data_analysis = self.execute_command("analyze-available-data", base_context)
        thinking_results["data_analysis"] = data_analysis
        logger.debug(f"[思考引擎] 数据分析:\n{data_analysis}")

        # 步骤 3：识别缺口
        logger.info("[思考引擎] 步骤 3/4：识别信息缺口")
        gaps = self.execute_command("identify-information-gaps", base_context)
        thinking_results["information_gaps"] = gaps
        logger.debug(f"[思考引擎] 信息缺口:\n{gaps}")

        # 步骤 4：评估是否可完成
        logger.info("[思考引擎] 步骤 4/4：评估任务完成度")
        completion_eval = self.execute_command("evaluate-completion", base_context)
        thinking_results["completion_evaluation"] = completion_eval
        logger.debug(f"[思考引擎] 完成度评估:\n{completion_eval}")

        return thinking_results

    def _prepare_base_context(self, state: RuntimeState, nodes_map: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """准备基础上下文（用于所有 slash commands）"""
        # 复用原 planner 的工具函数
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
            user_info = f"用户: {display_name} (ID: {user_id})"

        return {
            "TASK_GOAL": state._original_task_goal or state.task_goal,
            "USER_INFO": user_info,
            "CHAT_HISTORY": chat_history_text,
            "ACTION_HISTORY": action_history_prompt,
            "DATA_SUMMARY": data_summary,
            "TODO_SECTION": todo_section,
            "TOOL_DESCRIPTIONS": tool_descriptions,
        }


def planner_node_with_thinking(
    state: RuntimeState,
    nodes_map: Optional[Dict[str, Any]] = None,
    edges_map: Optional[Dict[str, Any]] = None,
    user=None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    增强版 planner 节点，使用 Claude Code 进行多轮思考。

    流程：
    1. 使用 Claude Code slash commands 进行多维度思考
    2. 汇总思考结果，构建增强的上下文
    3. 调用决策 LLM 生成最终 PlannerOutput

    参数：与原 planner_node 相同

    返回：与原 planner_node 相同
    """
    logger.info(f"[增强 PLANNER] 开始规划任务: {state.task_goal[:100]}")

    # 获取配置
    from django.conf import settings

    workspace_root = Path(getattr(settings, 'CLAUDE_CODE_WORKSPACE_ROOT', '/tmp/claude_planner_thinking'))
    base_url = os.getenv('CLAUDE_CODE_BASE_URL') or getattr(settings, 'CLAUDE_CODE_BASE_URL', None)
    model = os.getenv('CLAUDE_CODE_MODEL') or getattr(settings, 'CLAUDE_CODE_MODEL', None)

    # 创建用户/会话独立的工作空间
    user_id = "default"
    if user and hasattr(user, 'user_ai_id'):
        user_id = user.user_ai_id
    elif state.user_context:
        user_id = state.user_context.get('user_id', 'default')

    workspace = workspace_root / user_id / (session_id or "default")

    # 初始化思考引擎
    thinking_engine = ClaudeCodeThinkingEngine(
        workspace=workspace,
        base_url=base_url,
        model=model,
        timeout=int(os.getenv('CLAUDE_CODE_TIMEOUT', '30'))
    )

    try:
        # 【核心】执行多轮思考
        thinking_results = thinking_engine.think_step_by_step(state, nodes_map)

        # 构建增强的上下文
        enhanced_context = _build_enhanced_context(state, nodes_map, thinking_results)

        # 调用最终决策 LLM
        llm_result = _make_final_decision(state, nodes_map, enhanced_context, user, session_id)

        # 后处理（与原 planner 逻辑一致）
        llm_result = _post_process_decision(llm_result, state)

        # 添加到行动历史
        _update_action_history(state, llm_result)

        # 记录结果
        if llm_result.action == "FINISH":
            logger.info(f"[增强 PLANNER] 决定完成任务")
        else:
            logger.info(f"[增强 PLANNER] 决定使用工具: {llm_result.tool_name}")

        return {"current_plan": llm_result}

    except Exception as e:
        logger.error(f"[增强 PLANNER] 执行失败: {e}", exc_info=True)
        # 降级到原实现
        logger.warning("[增强 PLANNER] 降级到原 planner 实现")
        from .planner import _original_planner_implementation
        return _original_planner_implementation(state, nodes_map, edges_map, user, session_id)


def _build_enhanced_context(
    state: RuntimeState,
    nodes_map: Optional[Dict[str, Any]],
    thinking_results: Dict[str, str]
) -> Tuple[str, str]:
    """
    构建增强的上下文（system prompt + user prompt）

    将多轮思考的结果整合到 prompt 中
    """
    # 复用原 planner 的工具
    tool_descriptions = get_tool_descriptions_for_prompt()

    current_action_history = state.action_history
    if current_action_history and isinstance(current_action_history[-1], list):
        current_action_history = current_action_history[-1]

    action_history_prompt = build_action_history_prompt(current_action_history, format_type="detailed")
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

    # 构建 system prompt（保持原逻辑）
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
    "output_guidance": {{  // 重要：提供输出指导
        "key_points": ["要点1", "要点2"],
        "format_requirements": "格式要求（如需要表格、列表、报告等）",
        "quality_requirements": "质量要求（如详细程度、专业性等）",
        "custom_prompt": "任何额外的输出指导或特殊要求"
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

    # 构建增强的 user prompt
    # 将思考结果整合进去
    thinking_section = f"""### 深度分析

为了做出更好的决策，我已经从多个维度进行了分析：

#### 1. 任务进度评估
{thinking_results.get('progress_evaluation', '未执行')}

#### 2. 可用数据分析
{thinking_results.get('data_analysis', '未执行')}

#### 3. 信息缺口识别
{thinking_results.get('information_gaps', '未执行')}

#### 4. 完成度评估
{thinking_results.get('completion_evaluation', '未执行')}
"""

    user_prompt = f"""## 当前状态信息

### 原始任务
{state._original_task_goal}
{user_info}
{chat_history_text}

### 执行历史
{action_history_prompt}

{data_summary}

{todo_section}

{thinking_section}

## 最终决策

基于以上所有信息和深度分析，请做出最终决策：下一步应该执行什么操作？"""

    return system_prompt, user_prompt


def _make_final_decision(
    state: RuntimeState,
    nodes_map: Optional[Dict[str, Any]],
    enhanced_context: Tuple[str, str],
    user,
    session_id: Optional[str]
) -> PlannerOutput:
    """
    调用决策 LLM 生成最终决策

    使用原 planner 的 LLM 调用逻辑
    """
    from llm.core_service import CoreLLMService
    from llm.config_manager import ModelConfigManager
    from agentic.core.model_config_service import NodeModelConfigService
    from ..utils.logger_config import log_llm_request, log_llm_response

    system_prompt, user_prompt = enhanced_context

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
        source_function='nodes.planner_with_claude_code.planner_node_with_thinking'
    )

    # 记录请求
    log_llm_request("planner_enhanced", system_prompt, user_prompt, model_name)

    try:
        # 调用 LLM
        llm_result = LLM.invoke(user_prompt, system_prompt=system_prompt)
        log_llm_response("planner_enhanced", llm_result)
        return llm_result

    except Exception as e:
        if "结构化输出解析失败" in str(e):
            logger.warning("[增强 PLANNER] 结构化输出解析失败，重试一次")
            llm_result = LLM.invoke(user_prompt, system_prompt=system_prompt)
            log_llm_response("planner_enhanced", llm_result)
            return llm_result
        else:
            raise


def _post_process_decision(llm_result: PlannerOutput, state: RuntimeState) -> PlannerOutput:
    """
    后处理决策结果

    与原 planner 逻辑一致
    """
    # 处理 FINISH
    if llm_result.action == "FINISH":
        if llm_result.final_answer:
            logger.warning(f"[增强 PLANNER] 警告：Planner 提供了 final_answer，但系统将忽略它")
            llm_result.final_answer = None
            llm_result.title = None

    # 处理工具调用
    elif llm_result.action == "CALL_TOOL" and llm_result.tool_name:
        tool_input = llm_result.tool_input or {}

        # 自动补充 TodoGenerator 参数
        if llm_result.tool_name == "TodoGenerator":
            if "available_tools" not in tool_input:
                logger.info("[增强 PLANNER] 自动补充 TodoGenerator 参数")
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
    """
    更新行动历史

    与原 planner 逻辑一致
    """
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
