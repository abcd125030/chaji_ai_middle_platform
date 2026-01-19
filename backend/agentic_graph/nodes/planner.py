"""
规划节点
"""
from typing import Dict, Any
import logging

from .base import BaseNode
from ..core.schemas import RuntimeState

logger = logging.getLogger('django')


class PlannerNode(BaseNode):
    """规划节点，负责任务规划和决策"""
    
    def execute(self, state: RuntimeState) -> Dict[str, Any]:
        """
        执行规划节点逻辑
        
        主要工作：
        1. 分析任务需求
        2. 制定执行计划
        3. 决定是否需要调用工具
        4. 判断是否完成任务
        """
        logger.info(f"执行规划节点: {self.name}")
        
        # 获取LLM配置
        llm_config = self.config.get("llm", {})
        
        # 构建规划上下文
        context = self._build_context(state)
        
        # 调用LLM进行规划
        plan = self._generate_plan(context, llm_config)
        
        # 更新状态
        state.planner_output = plan
        
        # 决定下一步动作
        next_action = self._determine_next_action(plan, state)
        
        result = {
            "status": "success",
            "plan": plan,
            "next_action": next_action
        }
        
        # 设置下一个节点
        if next_action == "call_tool":
            state.next_node = "tool"
        elif next_action == "need_reflection":
            state.next_node = "reflection"
        elif next_action == "generate_output":
            state.next_node = "output"
        elif next_action == "finish":
            state.next_node = "end"
        else:
            state.next_node = "reflection"  # 默认进入反思
        
        return result
    
    def _build_context(self, state: RuntimeState) -> Dict[str, Any]:
        """构建规划上下文"""
        context = {
            "query": state.user_query,
            "scenario": state.scenario,
            "user_context": state.user_context,
            "action_history": state.action_history[-10:],  # 最近10个动作
            "memory": state.memory
        }
        
        # 如果有文件，添加文件信息
        if state.preprocessed_files:
            context["files"] = list(state.preprocessed_files.keys())
        
        return context
    
    def _generate_plan(self, context: Dict[str, Any], llm_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成执行计划
        
        TODO: 实现与LLM的交互
        """
        # 这里应该调用LLM服务生成计划
        # 暂时返回模拟数据
        plan = {
            "understanding": "用户想要...",
            "steps": [
                {"step": 1, "action": "分析需求"},
                {"step": 2, "action": "调用工具"},
                {"step": 3, "action": "生成结果"}
            ],
            "next_tool": None,
            "confidence": 0.85,
            "should_continue": True
        }
        
        logger.debug(f"生成计划: {plan}")
        return plan
    
    def _determine_next_action(self, plan: Dict[str, Any], state: RuntimeState) -> str:
        """确定下一步动作"""
        # 如果已经执行了足够多的动作，考虑结束
        if len(state.action_history) > 30:
            return "finish"
        
        # 根据计划决定
        if not plan.get("should_continue"):
            return "finish"
        
        if plan.get("next_tool"):
            return "call_tool"
        
        if plan.get("confidence", 0) < 0.7:
            return "need_reflection"
        
        # 如果有明确的输出需求
        if "生成" in state.user_query or "输出" in state.user_query:
            return "generate_output"
        
        return "need_reflection"