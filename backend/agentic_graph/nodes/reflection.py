"""
反思节点
"""
from typing import Dict, Any
import logging

from .base import BaseNode
from ..core.schemas import RuntimeState

logger = logging.getLogger('django')


class ReflectionNode(BaseNode):
    """反思节点，负责评估执行进度和调整策略"""
    
    def execute(self, state: RuntimeState) -> Dict[str, Any]:
        """
        执行反思节点逻辑
        
        主要工作：
        1. 评估当前执行进度
        2. 分析已执行动作的效果
        3. 判断是否需要调整策略
        4. 决定是否继续或结束
        """
        logger.info(f"执行反思节点: {self.name}")
        
        # 评估执行进度
        progress = self._evaluate_progress(state)
        
        # 分析动作效果
        effectiveness = self._analyze_effectiveness(state)
        
        # 决定下一步策略
        strategy = self._determine_strategy(progress, effectiveness, state)
        
        result = {
            "status": "success",
            "progress": progress,
            "effectiveness": effectiveness,
            "strategy": strategy
        }
        
        # 根据策略设置下一个节点
        if strategy == "continue_planning":
            state.next_node = "planner"
        elif strategy == "need_more_tools":
            state.next_node = "tool"
        elif strategy == "ready_to_output":
            state.next_node = "output"
        elif strategy == "task_complete":
            state.next_node = "end"
        else:
            state.next_node = "planner"  # 默认返回规划
        
        # 更新反思结果到状态
        if "reflections" not in state.memory:
            state.memory["reflections"] = []
        state.memory["reflections"].append({
            "iteration": len(state.action_history),
            "progress": progress,
            "effectiveness": effectiveness,
            "strategy": strategy
        })
        
        return result
    
    def _evaluate_progress(self, state: RuntimeState) -> Dict[str, Any]:
        """评估执行进度"""
        action_count = len(state.action_history)
        tool_calls = len([a for a in state.action_history if a.get("type") == "tool"])
        planner_calls = len([a for a in state.action_history if a.get("type") == "planner"])
        
        progress = {
            "total_actions": action_count,
            "tool_calls": tool_calls,
            "planner_calls": planner_calls,
            "completion_estimate": min(action_count / 20.0, 0.9)  # 估计完成度
        }
        
        # 检查是否有循环
        if action_count > 5:
            recent_actions = state.action_history[-5:]
            action_types = [a.get("type") for a in recent_actions]
            if len(set(action_types)) == 1:
                progress["possible_loop"] = True
        
        return progress
    
    def _analyze_effectiveness(self, state: RuntimeState) -> Dict[str, Any]:
        """分析动作效果"""
        effectiveness = {
            "tool_success_rate": 1.0,  # 默认100%成功
            "information_gathered": False,
            "user_needs_met": False
        }
        
        # 检查工具调用结果
        tool_results = [
            a.get("result") 
            for a in state.action_history 
            if a.get("type") == "tool"
        ]
        
        if tool_results:
            # 计算成功率
            successful = len([r for r in tool_results if r and r.get("status") == "success"])
            effectiveness["tool_success_rate"] = successful / len(tool_results) if tool_results else 0
            effectiveness["information_gathered"] = successful > 0
        
        # 判断是否满足用户需求（简单判断）
        if state.planner_output and state.planner_output.get("confidence", 0) > 0.8:
            effectiveness["user_needs_met"] = True
        
        return effectiveness
    
    def _determine_strategy(self, progress: Dict, effectiveness: Dict, state: RuntimeState) -> str:
        """确定下一步策略"""
        # 如果可能陷入循环，尝试结束
        if progress.get("possible_loop"):
            logger.warning("检测到可能的执行循环")
            return "ready_to_output"
        
        # 如果执行次数过多，结束任务
        if progress["total_actions"] > 30:
            logger.info("达到最大执行次数，准备结束")
            return "task_complete"
        
        # 如果用户需求已满足
        if effectiveness["user_needs_met"] and effectiveness["information_gathered"]:
            return "ready_to_output"
        
        # 如果工具调用效果不好，重新规划
        if effectiveness["tool_success_rate"] < 0.5:
            return "continue_planning"
        
        # 如果还没有调用过工具，可能需要工具
        if progress["tool_calls"] == 0 and progress["total_actions"] > 2:
            return "need_more_tools"
        
        # 默认继续规划
        return "continue_planning"