"""
结束节点
"""
from typing import Dict, Any
import logging

from .base import BaseNode
from ..core.schemas import RuntimeState

logger = logging.getLogger('django')


class EndNode(BaseNode):
    """结束节点，负责整理信息和归档"""
    
    def execute(self, state: RuntimeState) -> Dict[str, Any]:
        """
        执行结束节点逻辑
        
        主要工作：
        1. 整理最终输出
        2. 归档重要信息
        3. 更新用户记忆
        """
        logger.info(f"执行结束节点: {self.name}")
        
        result = {
            "status": "success",
            "message": "任务完成"
        }
        
        # 1. 整理最终输出
        final_output = self._prepare_final_output(state)
        state.final_output = final_output
        result["final_output"] = final_output
        
        # 2. 归档动作历史
        if state.action_history:
            result["total_actions"] = len(state.action_history)
            result["key_actions"] = self._extract_key_actions(state)
        
        # 3. 更新用户记忆
        if state.memory:
            self._update_memory(state)
            result["memory_updated"] = True
        
        # 4. 生成总结
        summary = self._generate_summary(state)
        result["summary"] = summary
        
        logger.info(f"结束节点执行完成 - 总动作数: {len(state.action_history)}")
        
        return result
    
    def _prepare_final_output(self, state: RuntimeState) -> Dict[str, Any]:
        """准备最终输出"""
        output = {
            "query": state.user_query,
            "scenario": state.scenario,
            "result": state.planner_output.get("final_answer") if state.planner_output else None,
            "actions_taken": len(state.action_history),
            "success": True
        }
        
        # 如果有工具输出，包含在最终结果中
        tool_outputs = [
            action["result"] 
            for action in state.action_history 
            if action.get("type") == "tool"
        ]
        if tool_outputs:
            output["tool_outputs"] = tool_outputs
        
        return output
    
    def _extract_key_actions(self, state: RuntimeState) -> list:
        """提取关键动作"""
        key_actions = []
        for action in state.action_history:
            if action.get("type") in ["planner", "tool", "output"]:
                key_actions.append({
                    "node": action.get("node"),
                    "type": action.get("type"),
                    "timestamp": action.get("timestamp")
                })
        return key_actions
    
    def _update_memory(self, state: RuntimeState):
        """更新用户记忆"""
        # TODO: 实现记忆更新逻辑
        logger.debug("更新用户记忆")
        pass
    
    def _generate_summary(self, state: RuntimeState) -> str:
        """生成执行总结"""
        actions_count = len(state.action_history)
        tools_used = len([a for a in state.action_history if a.get("type") == "tool"])
        
        summary = f"任务完成。执行了 {actions_count} 个动作"
        if tools_used > 0:
            summary += f"，调用了 {tools_used} 个工具"
        
        return summary