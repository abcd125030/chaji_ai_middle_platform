"""
工具节点
"""
from typing import Dict, Any
import logging

from .base import BaseNode
from ..core.schemas import RuntimeState

logger = logging.getLogger('django')


class ToolNode(BaseNode):
    """工具节点，负责调用各种工具"""
    
    def execute(self, state: RuntimeState) -> Dict[str, Any]:
        """
        执行工具节点逻辑
        
        主要工作：
        1. 根据规划确定要调用的工具
        2. 准备工具参数
        3. 调用工具
        4. 处理工具返回结果
        """
        logger.info(f"执行工具节点: {self.name}")
        
        # 从规划输出中获取工具信息
        planner_output = state.planner_output or {}
        tool_name = planner_output.get("next_tool") or self.config.get("tool_name")
        
        if not tool_name:
            logger.warning("没有指定要调用的工具")
            return {
                "status": "skipped",
                "message": "没有工具需要调用"
            }
        
        # 准备工具参数
        tool_params = self._prepare_tool_params(state, tool_name)
        
        # 调用工具
        tool_result = self._call_tool(tool_name, tool_params, state)
        
        result = {
            "status": "success",
            "tool": tool_name,
            "result": tool_result
        }
        
        # 将工具结果写入动作历史
        state.update_action_history({
            "node": self.name,
            "type": "tool",
            "tool_name": tool_name,
            "params": tool_params,
            "result": tool_result
        })
        
        # 设置下一个节点（通常返回规划节点）
        state.next_node = "planner"
        
        return result
    
    def _prepare_tool_params(self, state: RuntimeState, tool_name: str) -> Dict[str, Any]:
        """准备工具参数"""
        params = {
            "query": state.user_query,
            "context": state.user_context
        }
        
        # 根据不同工具准备特定参数
        if tool_name == "search":
            params["keywords"] = self._extract_keywords(state.user_query)
        elif tool_name == "calculator":
            params["expression"] = self._extract_expression(state.user_query)
        elif tool_name == "file_reader":
            params["files"] = state.preprocessed_files
        
        return params
    
    def _call_tool(self, tool_name: str, params: Dict[str, Any], state: RuntimeState) -> Dict[str, Any]:
        """
        调用具体工具
        
        TODO: 实现工具注册和调用机制
        """
        logger.info(f"调用工具: {tool_name}")
        
        # 这里应该从工具注册表获取工具并调用
        # 暂时返回模拟数据
        if tool_name == "search":
            return {
                "tool": "search",
                "status": "success",
                "results": ["结果1", "结果2", "结果3"]
            }
        elif tool_name == "calculator":
            return {
                "tool": "calculator",
                "status": "success",
                "result": 42
            }
        else:
            return {
                "tool": tool_name,
                "status": "success",
                "message": f"工具 {tool_name} 执行成功"
            }
    
    def _extract_keywords(self, query: str) -> list:
        """提取搜索关键词"""
        # TODO: 实现关键词提取
        return query.split()[:3]
    
    def _extract_expression(self, query: str) -> str:
        """提取计算表达式"""
        # TODO: 实现表达式提取
        return "1 + 1"