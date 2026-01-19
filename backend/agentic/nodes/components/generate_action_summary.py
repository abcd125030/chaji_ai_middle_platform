# -*- coding: utf-8 -*-
"""
generate_action_summary.py

生成动作摘要的工具函数模块。

本模块为 Agentic 系统中的反思节点（reflection_node）提供动作摘要生成功能，
是 reflection_node 数据处理流水线的核心组件之一。

## 输入输出

### 输入参数：
1. tool_name (str): 执行的工具名称（如 'web_search', 'report_generator' 等）
2. tool_input (Dict[str, Any]): 工具的输入参数（保留用于接口兼容，实际不使用）
3. tool_output (Dict[str, Any]): 工具的执行输出结果，遵循 ToolOutputFormat 统一格式
   - status: 执行状态 ("success"/"failed"/"partial")
   - message: 执行情况简要描述
   - primary_result: 主要结果数据
   - key_metrics: 关键指标
4. reflection (ReflectionOutput): 反思节点的语义分析结果
   - conclusion: 对行动结果的总结
   - summary: 一句话语义摘要
   - impact: 对整体任务的影响和贡献
   - is_finished: 工具调用是否正常完成
   - is_sufficient: 结果是否足够充分
   - key_findings: 关键发现列表

### 输出结果：
ActionSummary 对象，包含：
- action_id: 唯一标识符（格式：action_{timestamp}）
- timestamp: 执行时间（ISO格式）
- tool_name: 使用的工具名称
- brief_description: 简要描述（不超过50字符）
- key_results: 关键结果点列表（每个不超过20字符，最多5个）
- status: 最终执行状态（"success"/"failed"/"partial"）
- full_data_ref: 完整数据引用键（与 action_id 相同）
- is_sufficient: 结果是否充分（来自 reflection）

## 内部处理流程

### 核心设计理念：
完全依赖 reflection 节点的语义理解能力，摒弃硬编码逻辑，通过反思结果生成高质量摘要。

### 处理步骤：
1. **动作ID生成**：基于当前时间戳生成唯一的 action_id
2. **状态判定**：综合工具执行状态和反思评估结果
   - success + is_sufficient=true → "success"
   - success + is_sufficient=false → "partial"
   - 非success → "failed"
3. **语义摘要提取**：使用 reflection.summary 作为简要描述
4. **关键结果处理**：从 reflection.key_findings 中提取并格式化关键结果
5. **数据封装**：构建并返回 ActionSummary 对象

## 函数调用关系

### 直接调用者：
- `reflection_node()` (backend/agentic/nodes/reflection.py:277)
  - 作为 reflection 节点处理流程的最后一步
  - 用于生成工具执行的精简摘要

### 内部调用：
- `ActionSummary` 构造函数：从 agentic.core.schemas 模块导入
- `datetime.now()` 和字符串格式化：用于生成唯一 action_id

### 被依赖的数据结构：
- `ReflectionOutput` (agentic.core.schemas)：反思节点输出格式
- `ActionSummary` (agentic.core.schemas)：行动摘要数据模型

## 外部函数依赖（非Python标准库）

### 来自 agentic.core.schemas 模块：
1. `ActionSummary` 类：
   - 用途：定义行动摘要的数据结构
   - 位置：backend/agentic/core/schemas.py
   - 功能：结构化存储工具执行的精简信息

2. `ReflectionOutput` 类：
   - 用途：定义反思节点输出的数据结构
   - 位置：backend/agentic/core/schemas.py
   - 功能：包含语义分析结果和评估指标

### 系统集成依赖：
- **RuntimeState 系统**：生成的 ActionSummary 会被添加到全局状态的 action_summaries 列表中
- **数据目录缓存**：摘要更新会触发状态缓存清除，确保后续节点获取最新数据
- **完整数据存储**：full_action_data 中存储完整的执行历史，摘要仅作为索引使用

## 版本特性

### 优化版本特点：
- **语义驱动**：完全依赖 reflection 的语义理解能力
- **无硬编码**：移除了工具特定的处理逻辑
- **向后兼容**：保留 tool_input 参数但不使用，确保接口稳定性
- **数据精简**：生成轻量级摘要，完整数据存储在其他位置

### 与旧版本的差异：
- 旧版本：基于工具名称的硬编码逻辑分支
- 新版本：统一的语义分析驱动处理流程
"""

from typing import Dict, Any, TYPE_CHECKING
from datetime import datetime

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import ActionSummary, ReflectionOutput


def generate_action_summary(
    tool_name: str,
    tool_input: Dict[str, Any],  # 保留以保持接口兼容性
    tool_output: Dict[str, Any],
    reflection: 'ReflectionOutput'
) -> 'ActionSummary':
    """
    从工具执行结果和反思生成动作摘要。
    
    完全依赖 reflection 节点的语义理解能力，不再有任何硬编码逻辑。
    reflection 负责理解工具输出的语义并生成高质量的摘要。
    
    参数:
        tool_name (str): 执行的工具名称。
        tool_input (Dict[str, Any]): 工具的输入参数（保留用于接口兼容，实际不使用）。
        tool_output (Dict[str, Any]): 工具的输出结果（统一格式）。
        reflection (ReflectionOutput): 反思结果（包含语义摘要）。
    
    返回:
        ActionSummary: 生成的行动摘要。
    """
    from ...core.schemas import ActionSummary
    
    # tool_input 参数保留但不使用（向后兼容）
    _ = tool_input
    
    # 生成唯一的 action_id
    timestamp = datetime.now()
    action_id = f"action_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
    
    # 状态判定：基于工具执行状态和 reflection 评估
    tool_status = tool_output.get("status", "success")
    if tool_status == "success" and not reflection.is_sufficient:
        final_status = "partial"  # 执行成功但结果不充分
    elif tool_status != "success":
        final_status = "failed"  # 执行失败
    else:
        final_status = "success"  # 执行成功且结果充分
    
    # 使用 reflection 的语义摘要作为简要描述
    # reflection 应该已经理解了工具的实际作用
    brief_description = reflection.summary if reflection.summary else f"执行 {tool_name}"
    
    # 限制长度
    if len(brief_description) > 50:
        brief_description = brief_description[:47] + "..."
    
    # 使用 reflection 的关键发现作为关键结果
    # 这些发现是 reflection 通过语义理解提取出来的
    key_results = []
    if reflection.key_findings:
        # 取前5个发现，每个限制20字符
        for finding in reflection.key_findings[:5]:
            if isinstance(finding, str):
                result = finding if len(finding) <= 20 else finding[:17] + "..."
                key_results.append(result)
    
    # 如果没有关键发现，至少提供一个状态描述
    if not key_results:
        if final_status == "success":
            key_results.append("任务完成")
        elif final_status == "partial":
            key_results.append("部分完成")
        else:
            key_results.append("执行失败")
    
    # 返回精简的动作摘要
    # 完整的工具输入已经存储在 full_action_data 中，这里不需要重复
    return ActionSummary(
        action_id=action_id,
        timestamp=timestamp.isoformat(),
        tool_name=tool_name,
        brief_description=brief_description,
        key_results=key_results,
        status=final_status,
        full_data_ref=action_id,
        is_sufficient=reflection.is_sufficient
    )

