"""
反思评估节点
负责评估工具执行结果是否达到预期，生成反思结论
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..core.schemas import RuntimeState, PlannerOutput, ReflectionOutput
from llm.core_service import CoreLLMService
from llm.config_manager import ModelConfigManager
from .components import safe_json_dumps
from ..utils.logger_config import logger, log_llm_request, log_llm_response, log_state_change

# 为了保持向后兼容
_safe_json_dumps = safe_json_dumps


def _format_metrics(metrics):
    """格式化 metrics 为可读字符串"""
    if not metrics:
        return "无关键指标"
    
    if isinstance(metrics, list):
        # 新格式：列表形式的 metrics
        if not metrics:
            return "无关键指标"
        return "\n".join(f"- {metric}" for metric in metrics)
    elif isinstance(metrics, dict):
        # 旧格式：字典形式的 metrics
        if not metrics:
            return "无关键指标"
        return "\n".join(f"- {key}: {value}" for key, value in metrics.items())
    else:
        return str(metrics)


def reflection_node(state: RuntimeState, nodes_map: Optional[Dict[str, Any]] = None, 
                   edges_map: Optional[Dict[str, Any]] = None, 
                   current_plan: Optional[PlannerOutput] = None,
                   current_tool_output: Optional[Dict[str, Any]] = None,
                   user=None, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    反思器节点函数。
    评估上一次工具执行的结果是否达到了预期。它会生成一个包含结论和成功状态的反思结果。
    此节点通常在工具执行器（tool_executor）之后被调用。

    参数:
    state (RuntimeState): 当前的运行时状态。
    nodes_map (Optional[Dict[str, Any]]): 包含图中所有节点的字典，用于获取节点配置。
    edges_map (Optional[Dict[str, Any]]): 包含图中所有边的字典（在此节点中未使用，但为了接口一致性保留）。
    current_plan (Optional[PlannerOutput]): 当前的执行计划。
    current_tool_output (Optional[Dict[str, Any]]): 当前工具的输出结果。
    user: 用户对象（用于日志记录）
    session_id (Optional[str]): 会话ID（用于日志记录）

    返回:
    Dict[str, Any]: 包含更新后的行动历史的字典，键为"action_history"。
    """
    
    # 实例化核心LLM服务和配置管理器
    core_service = CoreLLMService()
    config_manager = ModelConfigManager()
    
    # 使用统一的模型配置服务获取模型名称
    from agentic.core.model_config_service import NodeModelConfigService
    model_name = NodeModelConfigService.get_model_for_node('reflection', nodes_map)
    
    # 获取模型配置（已包含vendor_name）
    model_config = config_manager.get_model_config(model_name)
    
    # 获取一个结构化输出的LLM实例，其输出将严格符合ReflectionOutput Pydantic模型
    structured_llm = core_service.get_structured_llm(
        ReflectionOutput, 
        model_config,
        user=user,
        session_id=session_id,
        model_name=model_name,
        source_app='agentic',
        source_function='nodes.reflection.reflection_node'
    ) # 反思可以使用更快的LLM
    
    # 确保 current_plan 和 current_tool_output 存在，这是反思节点运行的前提
    if not current_plan or current_tool_output is None:
        # 这应该是一个异常情况，因为 reflection 节点总是在 tool_executor 之后被调用，此时这些数据应已存在
        raise ValueError("Reflection node called without current_plan or current_tool_output.")

    # 从工具输出中提取关键信息（优先使用统一输出格式）
    tool_status = current_tool_output.get("status", "unknown")
    tool_message = current_tool_output.get("message", "")
    
    # 优先使用新的统一格式
    if "output" in current_tool_output and "type" in current_tool_output:
        # 新格式：直接使用 output 作为主要结果
        primary_result = current_tool_output.get("output")
        output_type = current_tool_output.get("type", "text")
        key_metrics = current_tool_output.get("metrics", [])  # 新格式是列表
        raw_data = current_tool_output.get("raw_data", {})
    else:
        # 兼容旧格式
        key_metrics = current_tool_output.get("key_metrics", {})
        raw_data = current_tool_output.get("raw_data", {})
        
        # 从 raw_data 中提取主要结果（适配旧格式）
        if isinstance(raw_data, dict) and "text" in raw_data:
            primary_result = raw_data.get("text")
        elif isinstance(raw_data, dict):
            primary_result = raw_data.get("data", raw_data)
        else:
            primary_result = raw_data
        
        # 再次兼容：直接从 data 字段提取
        if primary_result is None and "data" in current_tool_output:
            primary_result = current_tool_output["data"]
        
        output_type = "text"  # 旧格式默认为文本
    
    # 获取期望结果（如果 planner 提供了）
    expected_outcome = current_plan.expected_outcome if hasattr(current_plan, 'expected_outcome') and current_plan.expected_outcome else "未明确指定具体期望结果，需要根据工具的实际输出进行评估"
    
    # 构建系统提示词（包含反思规则和指导）
    system_prompt = """# 反思评估者

你是一个负责评估工具执行结果的反思节点。你的任务是严格评估每一步操作的执行情况和结果质量，并生成语义化的摘要。

## 评估原则
1. **客观评估**: 基于实际执行结果进行客观判断
2. **严格标准**: 对结果的充分性保持严格标准
3. **清晰总结**: 提供简明扼要的结论
4. **语义摘要**: 生成真正理解工具输出语义的摘要，而非机械提取

## 评估维度
- **执行状态**: 工具是否成功执行（查看status字段）
- **结果质量**: 输出内容是否有意义且充分
- **目标达成**: 是否达到了预期目标
- **语义理解**: 理解工具完成了什么任务，获得了什么核心结果

## 输出要求
你需要生成以下内容：
1. **conclusion**: 对执行结果的详细评价（2-3句话）
2. **summary**: 一句话语义摘要，描述"工具做了什么，得到了什么结果"
   - 示例："搜索了最新AI技术趋势，找到5篇相关文章并总结了主要观点"
   - 示例："分析了销售数据表，发现Q4增长率达到25%"
3. **impact**: 这次执行对整体任务的影响和贡献
4. **key_findings**: 从输出中提取的3-5个关键发现（每个不超过20字）
5. **is_finished**: 工具是否成功执行完成
6. **is_sufficient**: 结果是否充分满足需求

## TODO任务评估标准
对于todo_generator工具，需要评估：
- 任务分解是否合理和完整
- 任务数量是否适当（通常3-10个）
- 每个任务是否有明确的：任务描述、优先级、预计时间、建议工具、成功标准
- 任务间的依赖关系是否清晰
- 整体任务规划是否能够解决用户问题

## 注意事项
- 重点关注工具的实际输出内容，理解其语义
- summary 应该是自然语言描述，不是机械提取
- key_findings 应该是具体的发现，而非泛泛描述
- 工具可能使用不同的模型，这与你自身无关"""

    # 构建用户提示词（包含具体的执行信息）
    # 工具显示信息
    tool_name_display = current_plan.tool_name
    tool_input_display = _safe_json_dumps(current_plan.tool_input)
    
    user_prompt = f"""## 当前评估任务

### 执行计划
**思考过程**: {current_plan.thought}
**调用工具**: {tool_name_display}
**工具输入**:
```json
{tool_input_display}
```

### 期望结果
{expected_outcome}

### 实际执行结果
**执行状态**: {tool_status}
**返回消息**: {tool_message}
**输出类型**: {output_type if 'output_type' in locals() else 'text'}
**主要结果**:
```
{_safe_json_dumps(primary_result) if primary_result is not None else "无主要结果"}
```
**关键指标**:
{_format_metrics(key_metrics)}

请基于以上信息，评估这次工具调用的执行情况和结果质量。"""

    # 打印完整的反思提示词（用于调试，单个 logger 调用）
    reflection_debug_info = f"""
{"=" * 60}
🔍 REFLECTION NODE - 完整请求信息
{"=" * 60}

【System Prompt】
{system_prompt}

{"=" * 60}

【User Prompt】
{user_prompt}

{"=" * 60}
"""
    logger.info(reflection_debug_info)
    
    try:
        # 记录LLM请求
        log_llm_request("reflection", system_prompt, user_prompt, model_name)
        # 调用LLM进行反思评估，传入系统提示词和用户提示词
        llm_reflection_result = structured_llm.invoke(user_prompt, system_prompt=system_prompt)
        # 记录LLM响应
        log_llm_response("reflection", llm_reflection_result)
    except Exception as e:
        if "结构化输出解析失败" in str(e):
            llm_reflection_result = structured_llm.invoke(user_prompt, system_prompt=system_prompt) # 重试一次
        else:
            raise e
    
    # 将 reflection 添加到行动历史中
    # 每个条目都是一个字典，包含 'type' 和 'data'
    reflection_data = None
    action_id = None  # 提前声明 action_id
    
    if llm_reflection_result:
        # 提取所有字段，包括新增的语义摘要字段
        reflection_dict = llm_reflection_result.model_dump()
        # 保留所有字段，同时将conclusion映射为output（向后兼容）
        reflection_data = {
            "output": reflection_dict.get("conclusion", ""),  # 统一使用output字段（向后兼容）
            "conclusion": reflection_dict.get("conclusion", ""),  # 保留原始字段
            "summary": reflection_dict.get("summary", ""),  # 新增：语义摘要
            "impact": reflection_dict.get("impact", ""),  # 新增：任务影响
            "key_findings": reflection_dict.get("key_findings", []),  # 新增：关键发现
            "is_finished": reflection_dict.get("is_finished", False),
            "is_sufficient": reflection_dict.get("is_sufficient", False),
            # action_id 将在生成 action_summary 后填充
        }
    
    # 先不添加到 action_history，等生成 action_summary 后再添加（包含action_id）
    
    # 处理TodoGenerator的输出，更新state.todo
    if current_plan and current_plan.tool_name == "TodoGenerator":
        # 优先检查新格式：raw_data 字段
        if current_tool_output and current_tool_output.get('raw_data'):
            raw_data = current_tool_output['raw_data']
            if isinstance(raw_data, dict) and 'todo_list' in raw_data:
                # TodoGenerator 新格式输出
                state.todo = raw_data['todo_list']
                logger.info(f"[REFLECTION] TodoGenerator 创建了 {len(state.todo)} 个任务")
                # 合并所有TODO信息到一个日志条目
                todo_list_str = "========== TodoGenerator创建TODO清单 ==========\n"
                for idx, task in enumerate(state.todo, 1):
                    task_id = task.get('id', '?')
                    task_desc = task.get('task', '未知任务')
                    todo_list_str += f"  #{task_id}: {task_desc})\n"
                logger.info(f"[TODO状态变更]\n{todo_list_str}")
        
        # 兼容旧格式：检查 tool_output 字段
        elif current_tool_output and current_tool_output.get('tool_output'):
            todo_data = current_tool_output['tool_output']
            if 'todo_list' in todo_data:
                # TodoGenerator 旧格式输出
                state.todo = todo_data['todo_list']
                logger.info(f"[REFLECTION] TodoGenerator (旧格式) 创建了 {len(state.todo)} 个任务")
                # 合并所有TODO信息到一个日志条目
                todo_list_str = "========== TodoGenerator创建TODO清单 ==========\n"
                for idx, task in enumerate(state.todo, 1):
                    task_id = task.get('id', '?')
                    task_desc = task.get('task', '未知任务')
                    todo_list_str += f"  #{task_id}: {task_desc})\n"
                logger.info(f"[TODO状态变更]\n{todo_list_str}")
        
        # 也检查直接的tool_output格式 (某些情况下可能直接在tool_output根级别)
        elif current_tool_output and 'todo_list' in current_tool_output:
            state.todo = current_tool_output['todo_list']
            logger.info(f"[REFLECTION] TodoGenerator 直接输出创建了 {len(state.todo)} 个任务")
            # 合并所有TODO信息到一个日志条目
            todo_list_str = "========== TodoGenerator创建TODO清单 ==========\n"
            for idx, task in enumerate(state.todo, 1):
                task_id = task.get('id', '?')
                task_desc = task.get('task', '未知任务')
                todo_list_str += f"  #{task_id}: {task_desc})\n"
            logger.info(f"[TODO状态变更]\n{todo_list_str}")
    
    # 添加 reflection 数据到 action_history
    # 生成唯一的 action_id
    timestamp = datetime.now()
    action_id = f"action_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
    
    if reflection_data:
        reflection_data["action_id"] = action_id  # 添加 action_id 关联
        # action_history 必须是嵌套列表结构：添加到最后一个子列表（当前对话）
        if not state.action_history:
            # 如果为空，初始化为嵌套结构
            state.action_history = [[{
                "type": "reflection",
                "data": reflection_data
            }]]
        elif not isinstance(state.action_history[-1], list):
            # 格式不合法
            raise ValueError("action_history 必须是嵌套列表格式")
        else:
            # 添加到最后一个子列表
            state.action_history[-1].append({
                "type": "reflection",
                "data": reflection_data
            })
    
    # 清除数据目录缓存
    state._data_catalog_cache = None
    
    # 合并日志输出
    logger.info(
        f"[REFLECTION] 更新状态:\n"
        f"  - 添加 reflection: {action_id} - {current_plan.tool_name}\n"
        f"  - action_history 总条目: {len(state.action_history)}\n"
        f"  - 已清除数据目录缓存"
    )
    
    # 存储完整数据（保留以便其他地方可能依赖）
    state.full_action_data[action_id] = {
        "plan": current_plan.model_dump(),
        "tool_output": current_tool_output,
        "reflection": llm_reflection_result.model_dump()
    }
    
    # 检查并更新TODO任务状态
    if state.todo and len(state.todo) > 0:
        tool_name = current_plan.tool_name
        tool_status = current_tool_output.get("status", "unknown")
        
        # 记录更新的任务
        updated_tasks = []
        task_check_logs = []  # 收集任务检查日志
        
        for todo_item in state.todo:
            # 跳过已完成或失败的任务
            if todo_item.get('status', 'pending') in ['completed', 'failed']:
                continue
            
            # 只处理processing状态的任务（正在执行的任务）
            if todo_item.get('status') != 'processing':
                continue
            
            task_id = todo_item.get('id', '?')
            task_desc = todo_item.get('task', '')
            suggested_tools = todo_item.get('suggested_tools', [])
            
            # 更宽松的条件：检查工具是否相关（不要求严格匹配suggested_tools）
            # 1. 首先检查是否使用了建议的工具
            is_suggested_tool = tool_name in suggested_tools
            
            # 2. 如果不在建议工具中，检查工具是否与任务相关
            # 例如：TextGenerator可能用于多种文本生成任务
            tool_keywords = {
                'TextGenerator': ['分析', '总结', '生成', '提取', '整合', '评估'],
                'GoogleSearch': ['搜索', '查找', '检索', '查询'],
                'knowledge_base': ['知识库', '查询', '检索', '文档'],
            }
            
            # 检查工具是否可能完成该任务
            is_related_tool = False
            if tool_name in tool_keywords:
                is_related_tool = any(kw in task_desc for kw in tool_keywords[tool_name])
            
            # 如果工具相关（建议的或相关的）
            if is_suggested_tool or is_related_tool:
                task_check_logs.append(f"  - 任务{task_id}使用了{'建议' if is_suggested_tool else '相关'}工具 {tool_name}")
                
                # 检查工具执行是否成功且结果充分
                if tool_status == "success" and llm_reflection_result.is_sufficient:
                    # 更智能的相关性检查：基于任务描述和工具输入/输出的语义相关性
                    tool_input_str = str(current_plan.tool_input) if current_plan.tool_input else ""
                    tool_output_str = str(current_tool_output.get('data', ''))[:500]  # 检查输出的前500字符
                    reflection_text = llm_reflection_result.conclusion if hasattr(llm_reflection_result, 'conclusion') else ''
                    
                    # 提取任务关键词（过滤掉太短的词）
                    task_keywords = [kw for kw in task_desc.lower().split() if len(kw) > 2]
                    
                    # 检查任务关键词是否出现在工具输入、输出或反思结论中
                    combined_text = f"{tool_input_str} {tool_output_str} {reflection_text}".lower()
                    is_relevant = any(keyword in combined_text for keyword in task_keywords) if task_keywords else True
                    
                    if is_relevant:
                        # 【关键修复】检查任务依赖是否满足
                        dependencies = todo_item.get('dependencies', [])
                        dependencies_met = True
                        unmet_dependencies = []
                        
                        if dependencies:
                            for dep_id in dependencies:
                                # 查找依赖任务
                                dep_task = next((t for t in state.todo if t.get('id') == dep_id), None)
                                if not dep_task or dep_task.get('status', 'pending') != 'completed':
                                    dependencies_met = False
                                    unmet_dependencies.append(dep_id)
                            
                            if not dependencies_met:
                                logger.warning(
                                    f"[TODO依赖检查] ⚠️ 任务{task_id}的依赖未满足\n"
                                    f"  需要先完成: {unmet_dependencies}\n"
                                    f"  虽然工具执行成功，但不能标记为完成"
                                )
                                continue  # 跳过此任务，不标记为完成
                            else:
                                logger.info(f"[TODO依赖检查] ✅ 任务{task_id}的所有依赖已满足: {dependencies}")
                        
                        # 依赖满足，可以标记为完成
                        old_status = todo_item.get('status', 'processing')
                        todo_item['status'] = 'completed'  # 更新status字段
                        todo_item['completed_at'] = datetime.now().isoformat()  # 【新增】记录完成时间
                        
                        # 【新增】计算执行时间
                        if 'started_at' in todo_item:
                            try:
                                start_time = datetime.fromisoformat(todo_item['started_at'])
                                execution_time = (datetime.now() - start_time).total_seconds()
                                todo_item['execution_time'] = execution_time
                                logger.info(f"[TODO执行时间] 任务{task_id}执行耗时: {execution_time:.1f}秒")
                            except:
                                pass
                        
                        updated_tasks.append(task_id)
                        # 重置重试计数（成功完成）
                        if 'retry' in todo_item:
                            logger.info(f"[TODO状态变更] 任务{task_id}在第{todo_item['retry']+1}次尝试后成功完成")
                        
                        # 详细记录任务完成（合并成一条日志）
                        execution_info = ""
                        if 'execution_time' in todo_item:
                            execution_info = f"\n  执行耗时: {todo_item['execution_time']:.1f}秒"
                        
                        logger.info(
                            f"[TODO状态变更] ========== 任务完成 ==========\n"
                            f"  任务ID: {task_id}\n"
                            f"  任务描述: {task_desc[:100]}\n"
                            f"  状态变更: {old_status} → completed\n"
                            f"  执行工具: {tool_name}\n"
                            f"  完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{execution_info}\n"
                            f"  关联Action: {action_summary.action_id}"
                        )
                        
                        # 记录完成详情
                        reflection_summary = ''
                        if hasattr(llm_reflection_result, 'conclusion'):
                            reflection_summary = llm_reflection_result.conclusion
                        elif hasattr(llm_reflection_result, 'evaluation'):
                            reflection_summary = llm_reflection_result.evaluation
                        
                        todo_item['completion_details'] = {
                            'completed_at': datetime.now().isoformat(),
                            'completed_by_tool': tool_name,
                            'action_id': action_summary.action_id,
                            'result_summary': reflection_summary[:200] if reflection_summary else "",
                            'tool_status': tool_status
                        }
                        
                        # 通常一次执行只完成一个主要任务，但继续检查以防有关联任务
                    else:
                        task_check_logs.append(f"  - 任务{task_id}使用了{'建议' if is_suggested_tool else '相关'}工具，但执行内容与任务描述相关性不高")
                        task_check_logs.append(f"    任务关键词: {task_keywords}")
                        task_check_logs.append(f"    工具输入前100字符: {tool_input_str[:100]}")
                elif tool_status == "success" and not llm_reflection_result.is_sufficient:
                    task_check_logs.append(f"  - 任务{task_id}执行成功但结果不充分，暂不标记为完成")
                elif tool_status != "success":
                    # 【增强】任务失败时的错误处理和重试机制
                    task_check_logs.append(f"  - ⚠️ 任务{task_id}执行失败（status={tool_status}）")
                    
                    # 更新重试计数
                    current_retry = todo_item.get('retry', 0)
                    max_retry = todo_item.get('max_retry', 3)  # 默认3次重试
                    todo_item['retry'] = current_retry + 1
                    
                    # 记录错误历史
                    if 'error_history' not in todo_item:
                        todo_item['error_history'] = []
                    
                    todo_item['error_history'].append({
                        'timestamp': datetime.now().isoformat(),
                        'tool': tool_name,
                        'status': tool_status,
                        'error': current_tool_output.get('error', '未知错误'),
                        'retry_count': todo_item['retry'],
                        'execution_time': current_tool_output.get('execution_time', 0)
                    })
                    
                    # 【新增】计算指数退避延迟（1秒、2秒、4秒、8秒）
                    backoff_delay = min(2 ** (current_retry - 1), 8)  # 最大延迟8秒
                    
                    # 【新增】检查是否超时（如果有开始时间）
                    is_timeout = False
                    if 'started_at' in todo_item:
                        elapsed = (datetime.now() - datetime.fromisoformat(todo_item['started_at'])).total_seconds()
                        task_timeout = todo_item.get('timeout', 300)  # 默认5分钟超时
                        if elapsed > task_timeout:
                            is_timeout = True
                            task_check_logs.append(f"  - ⏰ 任务{task_id}已超时（{elapsed:.1f}秒 > {task_timeout}秒）")
                    
                    # 根据重试次数和超时情况决定处理策略
                    if not is_timeout and todo_item['retry'] <= max_retry:
                        logger.info(f"[TODO重试机制] 任务{task_id}将在{backoff_delay}秒后重试（已尝试{todo_item['retry']}次/最大{max_retry}次）")
                        todo_item['status'] = 'pending'  # 回到pending状态
                        todo_item['retry_after'] = (datetime.now() + timedelta(seconds=backoff_delay)).isoformat()
                        
                        # 【新增】根据错误类型调整重试策略
                        error_msg = str(current_tool_output.get('error', '')).lower()
                        if 'rate limit' in error_msg or 'too many requests' in error_msg:
                            # API限速错误，增加延迟
                            todo_item['retry_after'] = (datetime.now() + timedelta(seconds=backoff_delay * 2)).isoformat()
                            logger.info(f"[TODO重试机制] 检测到API限速，延长重试间隔至{backoff_delay * 2}秒")
                        elif 'network' in error_msg or 'connection' in error_msg:
                            # 网络错误，快速重试
                            todo_item['retry_after'] = (datetime.now() + timedelta(seconds=1)).isoformat()
                            logger.info(f"[TODO重试机制] 检测到网络错误，1秒后快速重试")
                    else:
                        # 超过重试次数或超时，标记为失败
                        failure_reason = "超时" if is_timeout else f"重试{todo_item['retry']}次后仍失败"
                        logger.error(f"[TODO重试机制] 任务{task_id}最终失败：{failure_reason}")
                        todo_item['status'] = 'failed'
                        todo_item['failed_at'] = datetime.now().isoformat()
                        todo_item['failure_reason'] = failure_reason
            else:
                # 不是建议的工具，但仍然检查是否可能完成了任务
                # 例如：某些通用工具可能完成多种任务
                logger.debug(f"[REFLECTION] 任务{task_id}未使用建议工具（建议：{suggested_tools}，实际：{tool_name}）")
        
        # 循环结束后，检查是否有任务被更新
        if updated_tasks:
            # 【增强】统计当前进度，包括各种状态
            completed_count = sum(1 for t in state.todo if t.get('status') == 'completed')
            failed_count = sum(1 for t in state.todo if t.get('status') == 'failed')
            pending_count = sum(1 for t in state.todo if t.get('status', 'pending') == 'pending')
            total_count = len(state.todo)
            progress_percentage = (completed_count / total_count * 100) if total_count > 0 else 0
            
            logger.info(f"[TODO状态变更] ========== 进度更新汇总 ==========")
            logger.info(f"[TODO状态变更] 本次标记完成: {len(updated_tasks)} 个任务")
            logger.info(f"[TODO状态变更] 完成的任务ID: {updated_tasks}")
            logger.info(f"[TODO状态变更] 总体进度: 完成{completed_count}/{total_count} ({progress_percentage:.0f}%)")
            logger.info(f"[TODO状态变更] 状态分布: ✅完成={completed_count} ⏳待执行={pending_count} ❌失败={failed_count}")
            
            # 【新增】关键路径可视化日志
            _visualize_critical_path(state.todo)
            
            # 列出剩余未完成的任务
            remaining_tasks = [t.get('id') for t in state.todo if t.get('status', 'pending') != 'completed']
            if remaining_tasks:
                logger.info(f"[TODO状态变更] 剩余任务ID: {remaining_tasks}")
            else:
                logger.info(f"[TODO状态变更] 🎉 所有任务已完成！")
        else:
            task_check_logs.append("  - 没有任务被标记为完成")
        
        # 输出合并的任务检查日志
        if task_check_logs:
            logger.info(
                f"[REFLECTION] TODO任务检查 (共{len(state.todo)}个任务):\n" + 
                "\n".join(task_check_logs)
            )
    
    
    # 注：关于 context 的设计思考
    # context 应该用于存储跨步骤的关键洞察，而不是执行历史
    # 执行历史已经由 full_action_data 很好地处理了
    # 
    # 未来可以考虑：
    # 1. 让 planner 主动决定什么信息需要加入 context
    # 2. 或者由 reflection 节点判断某些发现特别重要需要保留
    # 3. context 应该是少量的、高价值的信息
    #
    # 暂时保留空实现，避免破坏现有逻辑
    # TODO: 重新设计 context 的使用策略
    
    # 注意：current_plan 和 current_tool_output 现在作为参数传入，不再存储在state中
    
    # 记录反思完成的日志信息
    # 返回更新后的行动历史，尽管 RuntimeState 实例本身已被修改，但返回此字典可以方便后续处理
    return {"action_history": state.action_history}


def _visualize_critical_path(todo_list):
    """
    【新增】可视化关键路径，显示任务依赖关系和执行顺序
    """
    if not todo_list:
        return
    
    # 构建任务依赖图
    task_map = {t.get('id'): t for t in todo_list}
    
    # 找出没有依赖的根任务
    root_tasks = [t for t in todo_list if not t.get('dependencies', [])]
    
    # 找出每个任务的后续任务
    dependents_map = {}
    for task in todo_list:
        task_id = task.get('id')
        dependents_map[task_id] = []
        for dep in task.get('dependencies', []):
            if dep not in dependents_map:
                dependents_map[dep] = []
            dependents_map[dep].append(task_id)
    
    # 计算关键路径长度
    def calculate_path_length(task_id, visited=None):
        if visited is None:
            visited = set()
        if task_id in visited:
            return 0
        visited.add(task_id)
        
        if task_id not in dependents_map or not dependents_map[task_id]:
            return 1
        
        max_length = 0
        for dep_id in dependents_map[task_id]:
            length = calculate_path_length(dep_id, visited.copy())
            max_length = max(max_length, length)
        return 1 + max_length
    
    # 找出关键路径（最长路径）
    critical_paths = []
    for root in root_tasks:
        path_length = calculate_path_length(root.get('id'))
        critical_paths.append((root.get('id'), path_length))
    
    # 按路径长度排序
    critical_paths.sort(key=lambda x: x[1], reverse=True)
    
    if critical_paths:
        # 构建关键路径的可视化字符串
        path_viz = "[TODO关键路径] ========== 关键路径分析 ==========\n"
        
        # 显示前3条关键路径
        for i, (task_id, length) in enumerate(critical_paths[:3], 1):
            task = task_map.get(task_id)
            if task:
                status_icon = {
                    'completed': '✅',
                    'processing': '⚡',
                    'failed': '❌',
                    'pending': '⏳'
                }.get(task.get('status', 'pending'), '⏳')
                
                path_viz += f"  路径{i}: {status_icon} 任务{task_id}(长度:{length})"
                
                # 显示路径上的任务链
                current_id = task_id
                path_chain = [f"{task_id}"]
                while current_id in dependents_map and dependents_map[current_id]:
                    # 选择最长的后续路径
                    next_tasks = [(t, calculate_path_length(t)) for t in dependents_map[current_id]]
                    if next_tasks:
                        next_tasks.sort(key=lambda x: x[1], reverse=True)
                        current_id = next_tasks[0][0]
                        path_chain.append(str(current_id))
                    else:
                        break
                    
                    if len(path_chain) > 5:  # 限制显示长度
                        path_chain.append("...")
                        break
                
                if len(path_chain) > 1:
                    path_viz += " -> " + " -> ".join(path_chain[1:])
                path_viz += "\n"
        
        # 统计信息
        pending_critical = sum(1 for tid, _ in critical_paths if task_map.get(tid, {}).get('status', 'pending') == 'pending')
        completed_critical = sum(1 for tid, _ in critical_paths if task_map.get(tid, {}).get('status') == 'completed')
        
        path_viz += f"  关键路径统计: 总计{len(critical_paths)}条 | 待处理{pending_critical}条 | 已完成{completed_critical}条"
        
        logger.info(path_viz)