"""
计算器工具模块 - Calculator Tool Module

文件概述 (File Overview):
    本文件实现了一个安全的数学计算工具，用于执行基本的数学表达式计算。
    该工具基于Python AST(抽象语法树)进行安全的表达式解析和计算，避免了eval()函数的安全风险。

输入输出规范 (Input/Output Specification):
    输入参数 (CalculatorInput):
        - expression (str): 数学表达式字符串，支持基本算术运算符 +, -, *, /, ^(幂运算)
    
    execute方法参数:
        - tool_input (Dict[str, Any]): 包含CalculatorInput模型定义的输入参数
        - runtime_state (Any): 运行时状态信息
        - user_id (Optional[Union[str, int]]): 用户标识符，用于个性化服务和日志记录
    
    输出 (Output):
        成功情况:
        - status: "success"
        - output: 语义化的计算结果文本
        - type: "text"
        - raw_data: 包含原始计算数据的字典
        - metrics: 计算过程的统计信息列表
        - metadata: 工具执行的元数据信息
        - message: 简洁的执行结果消息
        
        失败情况:
        - status: "error"
        - output: 语义化的错误信息
        - type: "text"
        - raw_data: null
        - metrics: 空列表
        - metadata: 错误相关的元数据
        - message: 错误描述消息

内部处理流程 (Internal Processing Flow):
    1. 表达式接收 -> 2. 输入验证 -> 3. AST解析 -> 4. 节点遍历计算 -> 5. 结果封装 -> 6. 返回响应
    
    详细流程:
    1. execute() 接收工具输入参数
    2. 使用CalculatorInput进行输入验证，提取数学表达式
    3. _evaluate_expression() 使用ast.parse()将表达式解析为抽象语法树
    4. _eval_node() 递归遍历AST节点，根据节点类型进行相应计算
    5. 将计算结果封装成标准化的工具输出格式
    6. 返回包含计算结果、元数据和执行状态的完整响应

执行逻辑 (Execution Logic):
    - 采用AST安全解析，支持的节点类型：
      * ast.Constant/ast.Num: 数值常量
      * ast.BinOp: 二元运算（加减乘除幂）
      * ast.UnaryOp: 一元运算（负号）
    - 运算符映射到Python operator模块的对应函数
    - 递归计算复合表达式，支持运算符优先级
    - 异常捕获机制，确保计算错误被妥善处理

函数调用关系 (Function Call Relationships):
    CalculatorTool (主类)
    ├── get_input_schema() -> 返回CalculatorInput模型的JSON Schema
    ├── execute() -> 主执行方法
    │   ├── CalculatorInput(**tool_input) -> 输入验证
    │   ├── _evaluate_expression() -> 表达式解析入口
    │   │   └── _eval_node() -> 递归节点计算
    │   └── [结果封装和返回]
    └── operators (类属性) -> 运算符映射字典

外部函数依赖 (External Function Dependencies):
    工具框架依赖:
    - tools.core.base.BaseTool: 工具基类，提供标准化工具接口
    - tools.core.registry.register_tool: 工具注册装饰器，用于工具发现和管理
    - tools.core.types.ToolType: 工具类型枚举，用于工具分类
    
    注意: 本模块不依赖任何外部非Python标准库的自定义函数，仅使用Python内置的ast和operator模块。

安全特性 (Security Features):
    - 使用AST替代eval()，避免代码注入风险
    - 限制支持的节点类型，防止执行危险操作
    - 完善的异常处理机制，确保计算错误不会导致系统崩溃

使用示例 (Usage Examples):
    tool = CalculatorTool()
    result = tool.execute({"expression": "2 + 3 * 4"}, runtime_state=None, user_id="user123")
    # 返回: {"status": "success", "output": "计算结果: 2 + 3 * 4 = 14", ...}
"""

import ast
import operator
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field

from tools.core.base import BaseTool
from tools.core.registry import register_tool
from tools.core.types import ToolType


class CalculatorInput(BaseModel):
    expression: str = Field(description="要计算的数学表达式，例如 '1 + 2 * 3'")


@register_tool(
    name="Calculator", 
    description="执行数学计算。输入：数学表达式字符串(如'2+3*4')。输出：计算结果数值。用途：需要精确计算数值、统计数据求和、百分比计算等场景。支持：+-*/^运算符。",
    tool_type=ToolType.DATA_ANALYSIS,
    category="data_analysis"
)
class CalculatorTool(BaseTool):
    """数学计算工具"""
    
    # 支持的运算符映射
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def get_input_schema(self) -> Dict[str, Any]:
        return CalculatorInput.model_json_schema()
    
    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        try:
            parsed_input = CalculatorInput(**tool_input)
            expression = parsed_input.expression
            
            result = self._evaluate_expression(expression)
            
            # 生成语义化的输出
            output_text = f"计算结果: {expression} = {result}"
            
            return {
                "status": "success",
                "output": output_text,  # 语义化的文本输出
                "type": "text",
                "raw_data": {
                    "expression": expression,
                    "result": result,
                    "result_type": type(result).__name__
                },
                "metrics": [
                    f"表达式长度: {len(expression)} 字符",
                    f"计算结果: {result}",
                    f"结果类型: {type(result).__name__}"
                ],
                "metadata": {
                    "tool_input": tool_input,
                    "expression": expression
                },
                "message": f"计算完成: {expression} = {result}"
            }
            
        except Exception as e:
            # 捕获输入验证或执行过程中的异常
            return {
                "status": "error",
                "output": f"计算错误: {str(e)}",  # 语义化的错误信息
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "expression": expression,
                    "error": str(e)
                },
                "message": f"计算失败: {str(e)}"
            }
    
    def _evaluate_expression(self, expression: str) -> float:
        # 使用 AST 安全地计算数学表达式
        node = ast.parse(expression, mode='eval')
        return self._eval_node(node.body)
    
    def _eval_node(self, node):
        # 在 Python 3.8+ 中，ast.Num 已被 ast.Constant 取代
        # 直接使用 ast.Constant 和 node.value
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num): # 兼容旧版本Python，如果 ast.Num 仍然存在
            return node.n
        elif isinstance(node, ast.BinOp):
            return self.operators[type(node.op)](self._eval_node(node.left), self._eval_node(node.right))
        elif isinstance(node, ast.UnaryOp):
            return self.operators[type(node.op)](self._eval_node(node.operand))
        else:
            raise TypeError(node)