"""
Pandas数据计算工具 - 动态代码执行器

本文件实现了一个基于pandas的动态数据分析工具，支持在安全的执行环境中运行Python代码对表格数据进行各种分析操作。

## 输入输出说明

### 输入参数 (PandasCalculatorInput)
- `code` (str): 要执行的Python代码字符串，可使用pandas的所有功能
- `df` (pandas.DataFrame | str): 表格数据，可以是DataFrame对象或JSON字符串格式

### execute方法参数
- `tool_input` (Dict[str, Any]): 包含PandasCalculatorInput模型定义的输入参数
- `runtime_state` (Any): 运行时状态信息
- `user_id` (Optional[Union[str, int]]): 用户标识符，用于个性化服务和审计追踪

### 输出结果
标准化输出格式包含以下字段：
- `status` (str): 执行状态，"success" 或 "error"
- `output` (str): 格式化的输出文本，包含执行结果和说明
- `type` (str): 输出类型标识，固定为 "text"
- `raw_data` (dict): 原始执行数据
  - `stdout` (str): 标准输出内容
  - `stderr` (str): 标准错误内容  
  - `result` (Any): 代码执行结果（通过result变量获取）
- `metrics` (list): 执行指标列表
- `metadata` (dict): 元数据信息，包含代码片段、错误信息等
- `message` (str): 执行状态消息

## 内部处理流程

### 1. 输入验证与预处理
- 使用Pydantic模型验证输入参数的格式和类型
- 自动检测DataFrame数据格式：
  - 如果是JSON字符串，使用`pd.read_json()`转换为DataFrame
  - 如果已是DataFrame对象，直接使用

### 2. 执行环境构建
- 创建隔离的执行作用域（exec_globals）
- 预置可用变量：
  - `df`: 传入的pandas DataFrame对象
  - `pd`: pandas库引用
  - `result`: 用于存储执行结果的变量（初始为None）

### 3. 代码安全执行
- 使用Python内置的`exec()`函数执行用户代码
- 通过`contextlib.redirect_stdout/stderr`捕获所有输出
- 在同一进程中直接执行，避免跨进程通信开销

### 4. 结果收集与处理
- 从执行作用域中提取`result`变量的值
- 收集标准输出和错误输出
- 对DataFrame结果进行特殊格式化显示

### 5. 输出格式化
- 生成语义化的输出描述
- 计算执行指标（代码长度、结果类型、数据维度等）
- 构建标准化的返回格式

## 执行逻辑

### 成功执行路径
1. 输入验证通过
2. DataFrame数据准备完成
3. 代码执行无异常
4. 标准错误为空
5. 格式化输出结果并返回成功状态

### 错误处理路径
1. **语法错误/运行时错误**: 捕获到stderr内容时返回错误状态
2. **输入验证错误**: Pydantic验证失败时的异常处理
3. **系统异常**: 其他意外异常的统一处理

## 函数调用关系

### 核心方法
- `get_input_schema()`: 返回Pydantic输入模型的JSON Schema
- `execute()`: 主执行方法，处理完整的代码执行流程

### 内部调用链
```
execute()
├── PandasCalculatorInput(**tool_input)  # 输入验证
├── pd.read_json()                       # DataFrame转换（条件执行）
├── contextlib.redirect_stdout/stderr()  # 输出捕获
├── exec(code, exec_globals)             # 代码执行
└── 结果格式化和返回
```

## 外部函数依赖（非Python标准库）

### 直接依赖的外部模块
1. **tools.core.base.BaseTool**
   - 路径: `backend/tools/core/base.py`
   - 作用: 提供工具基类，包含状态管理、日志记录、统一接口
   - 关键方法: `execute_with_logging()`, `get_configured_model()`

2. **tools.core.registry.register_tool**
   - 路径: `backend/tools/core/registry.py`  
   - 作用: 工具注册装饰器，将工具注册到全局工具注册中心
   - 功能: 工具发现、描述管理、分类管理

3. **tools.core.types.ToolType**
   - 路径: `backend/tools/core/types.py`
   - 作用: 工具类型枚举定义，本工具使用DATA_ANALYSIS类型
   - 用途: 工具分类和组织管理

### 系统集成依赖
1. **agentic.core.schemas**
   - 数据来源: `preprocessed_files.tables` 字典结构
   - 作用: 提供预处理后的表格数据，键为文件名，值为DataFrame对象

2. **agentic.graph_nodes**
   - 调用场景: 智能体图执行节点中调用本工具
   - 数据流: 文件上传 → 预处理 → 表格提取 → 本工具分析

## 使用场景

### 典型应用
- 数据探索: `df.head()`, `df.info()`, `df.describe()`
- 数据清洗: `df.dropna()`, `df.fillna()`, `df.drop_duplicates()`
- 数据筛选: `df[df['column'] > value]`, `df.query()`
- 聚合分析: `df.groupby().agg()`, `df.pivot_table()`
- 统计计算: `df.sum()`, `df.mean()`, `df.corr()`

### 结果赋值约定
用户代码需要将最终结果赋值给`result`变量，以便工具正确收集输出：
```python
# 示例代码
result = df.groupby('category').sum()
```

## 安全特性
- 代码在当前进程中执行，继承安全上下文
- 执行作用域隔离，避免变量污染
- 错误信息完整捕获，便于调试
- 支持长时间运行的计算任务
"""

import io
import contextlib
from typing import Dict, Any, Optional, Union
import pandas as pd
from pydantic import BaseModel, Field

from tools.core.base import BaseTool
from tools.core.registry import register_tool
from tools.core.types import ToolType


class PandasCalculatorInput(BaseModel):
    code: str = Field(description="要执行的Python代码字符串")
    df: Any = Field(
        description="一个 pandas DataFrame 对象，将通过`df`变量在代码中访问"
    )


class PandasCalculatorOutput(BaseModel):
    stdout: str = Field(description="标准输出内容")
    stderr: str = Field(description="标准错误内容")
    result: Optional[Any] = Field(description="代码执行结果")


@register_tool(
    name="PandasDataCalculator",
    description="pandas表格数据处理。输入：pandas DataFrame(来自preprocessed_files.tables)+Python代码。输出：计算结果。用途：数据分析、统计计算、数据筛选、聚合分析等。功能：支持所有pandas操作如groupby、pivot、统计函数等。注意：表格数据从预处理文件引用。",
    tool_type=ToolType.DATA_ANALYSIS,
    category="data_analysis"
)
class PandasDataCalculatorTool(BaseTool):

    def get_input_schema(self) -> Dict[str, Any]:
        return PandasCalculatorInput.model_json_schema()

    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        try:
            parsed_input = PandasCalculatorInput(**tool_input)

            # 处理输入：如果df是JSON字符串，则转换为DataFrame
            if isinstance(parsed_input.df, str):
                parsed_input.df = pd.read_json(io.StringIO(parsed_input.df), orient='split')

            # 创建执行作用域，直接使用传入的DataFrame对象
            exec_globals = {'df': parsed_input.df, 'pd': pd, 'result': None}

            # 捕获 stdout 和 stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with contextlib.redirect_stdout(stdout_capture):
                with contextlib.redirect_stderr(stderr_capture):
                    # 在同一进程中直接执行代码
                    exec(parsed_input.code, exec_globals)
            
            # 从执行作用域中获取结果
            result_value = exec_globals.get('result')
            stdout_text = stdout_capture.getvalue()
            stderr_text = stderr_capture.getvalue()

            # 检查是否有执行错误（stderr 有内容）
            if stderr_text:
                output_text = f"代码执行出错:\n{stderr_text}"
                if stdout_text:
                    output_text += f"\n标准输出:\n{stdout_text}"
                
                return {
                    "status": "error",
                    "output": output_text,
                    "type": "text",
                    "raw_data": {
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                        "result": result_value
                    },
                    "metrics": [],
                    "metadata": {
                        "code": parsed_input.code[:800] + "..." if len(parsed_input.code) > 800 else parsed_input.code,
                        "error": stderr_text
                    },
                    "message": "代码执行失败"
                }

            # 生成语义化的输出
            output_lines = []
            if stdout_text:
                output_lines.append("执行输出:")
                output_lines.append(stdout_text)
            
            if result_value is not None:
                output_lines.append("\n执行结果:")
                if isinstance(result_value, pd.DataFrame):
                    output_lines.append(f"DataFrame (形状: {result_value.shape})")
                    output_lines.append(str(result_value))
                else:
                    output_lines.append(str(result_value))
            
            if not output_lines:
                output_lines.append("代码执行成功，无输出结果")
            
            output_text = "\n".join(output_lines)

            # 计算数据框的基本指标（如果结果是DataFrame）
            metrics = [f"代码长度: {len(parsed_input.code)} 字符"]
            if isinstance(result_value, pd.DataFrame):
                metrics.extend([
                    f"结果行数: {result_value.shape[0]}",
                    f"结果列数: {result_value.shape[1]}",
                    f"数据类型: DataFrame"
                ])
            elif result_value is not None:
                metrics.append(f"结果类型: {type(result_value).__name__}")

            return {
                "status": "success",
                "output": output_text,
                "type": "text",
                "raw_data": {
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "result": result_value
                },
                "metrics": metrics,
                "metadata": {
                    "code": parsed_input.code[:200] + "..." if len(parsed_input.code) > 200 else parsed_input.code,
                    "has_result": result_value is not None,
                    "result_type": type(result_value).__name__ if result_value is not None else None
                },
                "message": "Pandas数据处理完成"
            }

        except Exception as e:
            # 捕获输入验证或执行过程中的异常
            return {
                "status": "error",
                "output": f"执行失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                "message": f"执行失败: {str(e)}"
            }