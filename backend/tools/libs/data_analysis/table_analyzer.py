"""
表格分析工具模块 (TableAnalyzer)

本模块提供JSON格式表格数据的统计分析功能，用于数据质量检查、初步数据探索和表格结构理解。

## 输入输出规范

### 输入参数 (TableAnalyzerInput)
- table_json (string, 必需): JSON格式的表格数据，使用records格式
- analyze_columns (array, 可选): 需要详细分析的列名列表

### execute方法参数
- tool_input (Dict[str, Any]): 包含上述输入参数
- runtime_state (Any): 运行时状态信息
- user_id (Optional[Union[str, int]]): 用户标识符，用于个性化服务和日志记录

### 输出 (返回值)
返回标准化的Dict格式结果：
- status (string): 执行状态 - "success" | "error"
- output (string): 人类可读的分析结果文本
- type (string): 输出类型，固定为 "text"
- raw_data (dict): 结构化的原始分析数据
  - row_count: 总行数
  - column_count: 总列数
  - column_names: 列名列表
  - column_analysis: 各列详细分析结果
- metrics (list): 关键指标摘要列表
- metadata (dict): 元数据信息
- message (string): 执行结果消息

## 内部处理流程

1. **参数验证阶段**
   - 提取table_json和analyze_columns参数
   - 验证JSON格式是否正确

2. **数据解析阶段**
   - 使用pandas.read_json()解析JSON数据为DataFrame
   - 采用orient='records'格式进行解析

3. **基础统计计算**
   - 计算总行数、总列数
   - 提取所有列名

4. **详细列分析** (可选)
   - 遍历analyze_columns中指定的列
   - 对每列计算：数据类型、唯一值数量、空值数量
   - 构建column_analysis结构化数据

5. **结果组装**
   - 生成人类可读的分析报告文本
   - 构建结构化的raw_data
   - 生成metrics摘要列表
   - 封装metadata信息

## 执行逻辑

### 正常执行路径
```
输入验证 → JSON解析 → 基础统计 → 列分析 → 结果封装 → 返回成功结果
```

### 异常处理路径
```
JSON解析失败 → 捕获异常 → 返回错误结果 (包含异常信息)
数据处理异常 → 捕获异常 → 返回错误结果
```

## 函数调用关系

### 内部方法调用
- `get_input_schema()`: 定义输入参数schema，供工具注册使用
- `execute()`: 主要执行方法，实现分析逻辑

### 类继承关系
- 继承自 `BaseTool` (tools.core.base)
- 实现BaseTool定义的标准接口

## 外部函数依赖 (非Python标准库)

### Django框架依赖
- `logging.getLogger('django')`: Django日志系统

### 工具框架依赖
- `@register_tool()`: 工具注册装饰器 (tools.core.registry)
  - 参数: name, description, tool_type, category
- `ToolType.DATA_ANALYSIS`: 工具类型枚举 (tools.core.types)
- `BaseTool`: 工具基类 (tools.core.base)

### 运行时依赖
- 需要工具注册系统已初始化
- 需要Django日志配置已生效
- 输入的JSON数据必须符合pandas可解析的records格式

## 使用场景
- 数据质量检查：快速了解表格基本信息和数据质量
- 数据探索：分析表格结构和列特征
- 数据预处理：为后续处理提供数据概览
- 质量监控：检测空值、唯一值等质量指标

## 注意事项
- 工具只进行分析，不修改原始数据
- JSON数据必须是有效的表格格式 (records orient)
- analyze_columns中不存在的列名会被忽略
- 大数据集可能导致内存占用较高
"""

import logging
from tools.core.registry import register_tool
from tools.core.types import ToolType
from tools.core.base import BaseTool
from typing import Dict, Any, Optional, Union, List
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger('django')


class TableAnalyzerInput(BaseModel):
    """表格分析工具输入参数模型"""
    table_json: str = Field(description="JSON格式的表格数据")
    analyze_columns: Optional[List[str]] = Field(
        default=None,
        description="需要分析的列名列表"
    )


@register_tool(
    name="TableAnalyzer", 
    description="表格数据分析。输入：JSON格式表格数据+要分析的列名。输出：统计信息(行数/列数/数据类型/唯一值/空值等)。用途：数据质量检查、初步数据探索、表格结构理解。注意：仅分析不修改数据。",
    tool_type=ToolType.DATA_ANALYSIS,
    category="data_analysis"
)
class TableAnalyzerTool(BaseTool):
    """
    表格分析工具：对JSON格式的表格数据进行统计分析。
    输入必须包含有效的表格JSON数据。
    """
    
    def get_input_schema(self) -> Dict[str, Any]:
        return TableAnalyzerInput.model_json_schema()
    
    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        # 使用Pydantic模型验证输入
        try:
            parsed_input = TableAnalyzerInput(**tool_input)
        except Exception as e:
            return {
                "status": "error",
                "output": f"输入参数验证失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "error_type": "ValidationError"
                },
                "message": f"输入参数验证失败: {str(e)}"
            }
        
        table_json = parsed_input.table_json
        analyze_columns = parsed_input.analyze_columns or []
        
        try:
            df = pd.read_json(table_json, orient='records')
            
            # 基础统计
            row_count = len(df)
            column_count = len(df.columns)
            column_names = list(df.columns)
            
            # 构建语义化输出
            output_lines = [
                f"表格分析结果：",
                f"- 总行数: {row_count}",
                f"- 总列数: {column_count}",
                f"- 列名: {', '.join(column_names)}"
            ]
            
            # 列分析结果
            column_analysis = {}
            if analyze_columns:
                output_lines.append("\n详细列分析:")
                for col in analyze_columns:
                    if col in df.columns:
                        col_type = str(df[col].dtype)
                        unique_count = df[col].nunique()
                        null_count = df[col].isnull().sum()
                        
                        column_analysis[col] = {
                            'type': col_type,
                            'unique_count': unique_count,
                            'null_count': null_count
                        }
                        
                        output_lines.append(f"  {col}:")
                        output_lines.append(f"    - 数据类型: {col_type}")
                        output_lines.append(f"    - 唯一值数量: {unique_count}")
                        output_lines.append(f"    - 空值数量: {null_count}")
            
            output_text = "\n".join(output_lines)
            
            # 生成指标列表
            metrics = [
                f"总行数: {row_count}",
                f"总列数: {column_count}"
            ]
            
            if analyze_columns:
                analyzed_count = len([c for c in analyze_columns if c in df.columns])
                metrics.append(f"分析列数: {analyzed_count}")
                
                # 添加空值统计
                total_nulls = sum(column_analysis.get(col, {}).get('null_count', 0) for col in analyze_columns if col in df.columns)
                if total_nulls > 0:
                    metrics.append(f"总空值数: {total_nulls}")
            
            return {
                "status": "success",
                "output": output_text,
                "type": "text",
                "raw_data": {
                    "row_count": row_count,
                    "column_count": column_count,
                    "column_names": column_names,
                    "column_analysis": column_analysis
                },
                "metrics": metrics,
                "metadata": {
                    "analyzed_columns": analyze_columns,
                    "user_id": user_id
                },
                "message": "表格分析完成"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "output": f"表格分析失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                "message": f"表格分析失败: {str(e)}"
            }