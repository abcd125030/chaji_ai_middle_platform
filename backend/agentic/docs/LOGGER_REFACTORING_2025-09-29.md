# Agentic模块日志重构报告

日期：2025-09-29  
作者：Claude

## 概述

本次重构的目标是重建agentic模块的日志系统，确保在以下关键时刻记录完整的日志信息：
1. LLM调用请求和响应
2. State中字段值发生变化
3. 工具调用和执行结果

## 完成的工作

### 1. 创建统一的日志配置模块

创建了 `/backend/agentic/utils/logger_config.py`，提供了以下日志记录函数：
- `log_llm_request()` - 记录LLM调用请求，包含完整的system prompt和user prompt
- `log_llm_response()` - 记录LLM响应结果的完整内容
- `log_state_change()` - 记录State字段值变化，包含旧值和新值
- `log_tool_call()` - 记录工具调用，包含工具名称和输入参数
- `log_tool_result()` - 记录工具执行结果
- `log_execution_step()` - 记录关键执行步骤

### 2. 移除旧的日志代码

从以下文件中移除了原有的零散日志代码：
- `agentic/services.py`
- `agentic/tasks.py` 
- `agentic/core/processor.py`
- `agentic/nodes/planner.py`
- `agentic/nodes/reflection.py`
- `agentic/nodes/output.py`
- `agentic/utils/processor_tool_executor.py`

### 3. 在关键位置添加完整日志记录

#### 3.1 LLM调用日志
在以下节点添加了LLM请求和响应的完整记录：
- **planner节点** (`nodes/planner.py`)
  - 记录完整的system prompt和user prompt
  - 记录LLM返回的PlannerOutput结果
  
- **reflection节点** (`nodes/reflection.py`)
  - 记录反思评估的提示词
  - 记录LLM返回的ReflectionOutput结果
  
- **output节点** (`nodes/output.py`)
  - 记录输出工具选择的提示词
  - 记录LLM选择的输出工具决策

#### 3.2 State变化日志
在以下位置记录state字段变化：
- **processor.py**
  - 记录TODO列表状态变化（创建、更新、完成）
  - 记录current_plan变化
  - 记录action_history变化
  
- **processor_tool_executor.py**
  - 记录工具执行后action_history的变化

#### 3.3 工具调用日志
- 在`processor_tool_executor.py`中记录：
  - 工具调用前的完整输入参数
  - 工具执行后的完整结果
  
- 在`processor.py`中记录：
  - 输出工具的调用和结果

#### 3.4 执行流程日志
在`processor.py`和相关模块中记录：
- 图执行开始和结束
- 任务创建（新任务或基于历史）
- 任务状态变化（超时、失败等）

## 日志格式示例

### LLM请求日志
```
=============== LLM REQUEST [planner] ===============
Model: gpt-4
System Prompt Length: 2000 chars
User Prompt Length: 500 chars

--- System Prompt ---
[完整的系统提示词内容]

--- User Prompt ---
[完整的用户提示词内容]
=========================================================
```

### LLM响应日志
```
=============== LLM RESPONSE [planner] ===============
{
  "thought": "需要分析用户需求",
  "action": "CALL_TOOL",
  "tool_name": "WebSearcher",
  "tool_input": {...}
}
==========================================================
```

### State变化日志
```
=============== STATE CHANGE [todo] ===============
Context: planner node

--- Old Value ---
[{"id": "1", "status": "pending", ...}]

--- New Value ---
[{"id": "1", "status": "processing", ...}]
============================================================
```

## 遇到的问题及解决方案

### 循环导入问题
在重构过程中遇到了循环导入问题：
- `processor.py` → `utils/__init__.py` → `processor_tool_executor.py` → `core.schemas` → `core/__init__.py` → `processor.py`

**解决方案**：
1. 在`utils/__init__.py`中使用延迟导入
2. 在`processor.py`的`_tool_executor_node`方法中使用局部导入
3. 避免在模块级别导入可能造成循环的模块

## 使用说明

### 基本使用
```python
from agentic.utils.logger_config import logger, log_llm_request, log_llm_response

# 记录LLM请求
log_llm_request("planner", system_prompt, user_prompt, model_name)

# 记录LLM响应
log_llm_response("planner", llm_result)

# 记录状态变化
log_state_change("todo", old_value, new_value, "context info")
```

### 日志级别配置
日志使用`logging.getLogger('agentic')`，可以通过Django的LOGGING配置进行管理：
```python
LOGGING = {
    'loggers': {
        'agentic': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}
```

## 测试验证

创建了测试脚本 `test_logger.py` 用于验证logger功能，包括：
- LLM请求和响应日志记录
- State变化记录
- 工具调用和结果记录
- 执行步骤记录

## 后续建议

1. **日志存储优化**
   - 考虑将关键日志存储到数据库，便于查询和分析
   - 实现日志轮转，避免日志文件过大

2. **日志分析工具**
   - 开发日志分析脚本，统计LLM调用次数、响应时间等
   - 实现日志可视化，便于监控系统运行状态

3. **性能优化**
   - 对于大型对象的序列化，考虑异步处理
   - 实现日志缓冲，批量写入

4. **安全考虑**
   - 添加敏感信息过滤（API密钥、个人信息等）
   - 实现日志访问控制

## 总结

本次重构成功建立了统一的日志系统，能够完整记录LLM调用、State变化和工具执行的全过程。这将极大地帮助开发调试和生产环境的问题排查。所有关键的执行步骤都有详细的日志记录，满足了要求的记录标准。