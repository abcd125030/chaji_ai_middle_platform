# TODO: Planner节点链式拆分重构
**创建时间**: 2025-09-08 20:30:00  
**优先级**: 中  
**预计工时**: 4-6小时

## 背景信息

### 问题发现
通过分析 `/backend/agentic/graph_nodes.py` 的 planner_node 函数和相关提示词构建系统发现：
1. Planner职能过于庞大，承担了分析、规划、决策、评估等多重职责
2. System prompt过长（包含9大职能模块），导致token消耗大、响应延迟高
3. 单次决策复杂度过高，容易出现判断错误或遗漏
4. 提示词中包含大量冗余信息，每次调用都传递完整上下文

### 当前架构分析
- **提示词管理**: 使用PromptManager进行YAML模板管理（`/backend/agentic/prompt_manager.py`）
- **提示词构建**: 通过`context_builders/prompt_builder.py`动态构建
- **执行流程**: planner → tool_executor → reflection → planner (循环)
- **System Prompt规模**: 包含核心能力、思考框架、工具映射、数据引用、TODO管理、决策指南等9大模块

### 当前环境
- **运行环境**: macOS开发环境
- **Python环境**: 使用`.venv`虚拟环境
- **后端路径**: `/Users/chagee/Repos/X/backend`
- **激活虚拟环境**: `cd /Users/chagee/Repos/X/backend && source .venv/bin/activate`

## 目标

### 主要目标
1. **职责拆分**: 将planner拆分为3-4个专注的子组件
2. **提示词精简**: 每个组件的提示词控制在200 tokens以内
3. **保持兼容**: 对外接口不变，内部重构
4. **性能优化**: 减少token消耗，提高响应速度

### 具体指标
- 单个决策组件的prompt不超过200 tokens
- 总体token消耗降低50%
- 决策准确率提升（通过单一职责降低复杂度）
- 保持现有API接口完全兼容

## 设计方案

### 链式组件架构
```
Analyzer (状态分析器) 
   ↓
Strategist (策略制定器)
   ↓  
Executor (执行决策器)
   ↓
   → tool_executor → reflection (保持现有)
```

### 各组件职责定义

#### 1. Analyzer（状态分析器）
- **输入**: 用户需求、执行历史摘要、TODO状态
- **职责**: 分析当前状态，识别未满足需求
- **输出**: `{needs_met: bool, missing_info: [], can_finish: bool}`
- **Prompt规模**: ~100 tokens

#### 2. Strategist（策略制定器）
- **输入**: Analyzer结果、TODO任务列表、工具类别
- **职责**: 决定行动策略，选择任务
- **输出**: `{action_type: str, target_task_id: str, tool_category: str}`
- **Prompt规模**: ~100 tokens

#### 3. Executor（执行器）
- **输入**: Strategist策略、工具参数要求、数据目录
- **职责**: 构建具体工具调用或FINISH
- **输出**: 标准PlannerOutput格式
- **Prompt规模**: ~150 tokens

## 做事的顺序

### 第一阶段：准备工作
1. 备份现有planner_node实现
2. 创建链式组件基础框架文件
3. 设计各组件的Pydantic模型

### 第二阶段：实现链式组件
4. 实现Analyzer组件及其精简prompt
5. 实现Strategist组件及其精简prompt
6. 实现Executor组件及其精简prompt
7. 创建组件间的数据传递机制

### 第三阶段：集成测试
8. 在planner_node内部集成链式调用
9. 保持对外接口不变
10. 添加性能监控和日志

### 第四阶段：提示词优化
11. 为每个组件创建YAML模板
12. 移除冗余信息传递
13. 实现组件级别的缓存机制

### 第五阶段：验证和回滚准备
14. 对比测试新旧实现的效果
15. 准备回滚方案和开关

## 需要阅读作为上下文的文件

### 核心实现文件
- `/backend/agentic/graph_nodes.py` - planner_node函数（37-286行）
- `/backend/agentic/context_builders/prompt_builder.py` - 提示词构建逻辑（105-455行）
- `/backend/agentic/prompt_manager.py` - 提示词管理器（285-349行）
- `/backend/agentic/schemas.py` - RuntimeState和PlannerOutput定义
- `/backend/agentic/prompts/templates/planner/` - 现有提示词模板

### 相关配置文件
- `/backend/agentic/prompts/templates/planner/core.yaml` - 核心定义
- `/backend/agentic/prompts/templates/planner/framework.yaml` - 思考框架
- `/backend/agentic/prompts/templates/planner/guides.yaml` - 决策指南
- `/backend/agentic/prompts/templates/planner/formats.yaml` - 输出格式

## 涉及到要修改的文件

### 新建文件

1. **`/backend/agentic/chain_components/__init__.py`**
   - 链式组件模块初始化

2. **`/backend/agentic/chain_components/analyzer.py`**
   - Analyzer组件实现
   - 精简的分析prompt

3. **`/backend/agentic/chain_components/strategist.py`**
   - Strategist组件实现
   - 精简的策略prompt

4. **`/backend/agentic/chain_components/executor.py`**
   - Executor组件实现
   - 精简的执行prompt

5. **`/backend/agentic/chain_components/schemas.py`**
   - 组件间数据传递的Pydantic模型

### 修改文件

6. **`/backend/agentic/graph_nodes.py`**
   - planner_node函数改造（37-286行）
   - 集成链式组件调用
   - 添加兼容性开关

7. **`/backend/agentic/prompts/templates/planner/`**
   - 创建精简版prompt模板
   - analyzer.yaml、strategist.yaml、executor.yaml

### 可选修改文件

8. **`/backend/agentic/model_config_service.py`**
   - 支持为不同组件配置不同模型
   - 如analyzer使用gpt-4o-mini，strategist使用gpt-4o

## 危险事项 ⚠️

### 严禁操作
1. **❌ 不要删除原有planner实现**
2. **❌ 不要修改对外API接口**
3. **❌ 不要破坏现有的reflection机制**

### 需要特别注意
4. **⚠️ 保持完全向后兼容**
   - 确保current_plan输出格式不变
   - 保持与tool_executor和reflection的接口一致

5. **⚠️ 渐进式重构**
   - 先在内部实现，不改变外部行为
   - 添加功能开关，可快速切换新旧实现

6. **⚠️ 充分测试**
   - 对比新旧实现的输出
   - 监控token消耗和响应时间

## 验收标准

1. **功能保持**
   - 所有现有功能正常工作
   - 输出格式完全兼容

2. **性能提升**
   - 单次planner调用token消耗降低50%
   - 响应时间缩短30%

3. **代码质量**
   - 每个组件职责单一明确
   - 提示词简洁清晰
   - 充分的日志和监控

4. **可维护性**
   - 组件可独立测试和优化
   - 提示词模板化管理
   - 清晰的文档说明

## 风险评估

- **低风险**: 新建组件文件、添加精简prompt
- **中风险**: planner_node内部重构、组件集成
- **高风险**: 改变决策逻辑可能影响任务执行效果

## 回滚方案

如果新实现出现问题：
1. 通过功能开关切回原实现
2. 监控日志确认恢复正常
3. 分析问题原因，逐步优化

## 实施示例

### 精简Analyzer提示词示例
```yaml
# analyzer.yaml
system_prompt: |
  分析当前执行状态。
  
  输入：任务目标和已完成操作
  输出：需求是否满足，还缺什么

output_format: |
  {
    "needs_met": bool,
    "missing": ["缺失项"],
    "can_finish": bool
  }
```

### 链式调用伪代码
```python
def planner_node_v2(state: RuntimeState):
    # Step 1: 快速分析
    analysis = analyzer.analyze(
        task=state._original_task_goal,
        history=state.action_summaries
    )
    
    if analysis.can_finish:
        return build_finish_action(state)
    
    # Step 2: 制定策略
    strategy = strategist.plan(
        analysis=analysis,
        todos=state.todo
    )
    
    # Step 3: 构建执行
    execution = executor.build(
        strategy=strategy,
        tools=available_tools
    )
    
    return {"current_plan": execution}
```

## 预期收益

1. **降低复杂度**: 每个决策点更简单，错误率降低
2. **提升性能**: Token消耗减少，响应更快
3. **易于维护**: 组件独立，可单独优化
4. **灵活配置**: 可为不同组件使用不同模型
5. **更好的可测试性**: 每个组件可独立测试