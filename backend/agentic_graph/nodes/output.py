"""
输出节点
"""
from typing import Dict, Any
import logging

from .base import BaseNode
from ..core.schemas import RuntimeState

logger = logging.getLogger('django')


class OutputNode(BaseNode):
    """输出节点，负责生成最终输出"""
    
    def execute(self, state: RuntimeState) -> Dict[str, Any]:
        """
        执行输出节点逻辑
        
        主要工作：
        1. 根据规划要求选择输出工具
        2. 整合所有上下文信息
        3. 调用输出工具生成最终结果
        4. 格式化输出
        """
        logger.info(f"执行输出节点: {self.name}")
        
        # 确定输出类型
        output_type = self._determine_output_type(state)
        
        # 整合上下文
        context = self._prepare_output_context(state)
        
        # 生成输出
        output = self._generate_output(output_type, context, state)
        
        # 格式化输出
        formatted_output = self._format_output(output, output_type)
        
        result = {
            "status": "success",
            "output_type": output_type,
            "output": formatted_output
        }
        
        # 保存到最终输出
        state.final_output = formatted_output
        
        # 设置下一个节点为结束
        state.next_node = "end"
        
        return result
    
    def _determine_output_type(self, state: RuntimeState) -> str:
        """确定输出类型"""
        # 从配置或规划中获取输出类型
        if self.config.get("output_type"):
            return self.config["output_type"]
        
        if state.planner_output and state.planner_output.get("output_type"):
            return state.planner_output["output_type"]
        
        # 根据场景推断
        if state.scenario == "code_generation":
            return "code"
        elif state.scenario == "file_analysis":
            return "report"
        else:
            return "text"
    
    def _prepare_output_context(self, state: RuntimeState) -> Dict[str, Any]:
        """准备输出上下文"""
        context = {
            "query": state.user_query,
            "scenario": state.scenario,
            "user_context": state.user_context,
            "planner_output": state.planner_output,
            "tool_results": [],
            "key_findings": []
        }
        
        # 提取工具结果
        for action in state.action_history:
            if action.get("type") == "tool" and action.get("result"):
                context["tool_results"].append({
                    "tool": action.get("tool_name"),
                    "result": action.get("result")
                })
        
        # 提取关键发现
        if state.memory.get("reflections"):
            for reflection in state.memory["reflections"]:
                if reflection.get("effectiveness", {}).get("information_gathered"):
                    context["key_findings"].append(reflection)
        
        return context
    
    def _generate_output(self, output_type: str, context: Dict[str, Any], state: RuntimeState) -> Dict[str, Any]:
        """
        生成输出
        
        TODO: 实现与输出工具的集成
        """
        logger.info(f"生成 {output_type} 类型的输出")
        
        if output_type == "code":
            return self._generate_code_output(context)
        elif output_type == "report":
            return self._generate_report_output(context)
        else:
            return self._generate_text_output(context)
    
    def _generate_code_output(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成代码输出"""
        return {
            "type": "code",
            "language": "python",
            "code": "# 生成的代码\nprint('Hello, World!')",
            "explanation": "这是根据您的需求生成的代码"
        }
    
    def _generate_report_output(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成报告输出"""
        return {
            "type": "report",
            "title": "分析报告",
            "sections": [
                {"title": "概述", "content": "基于提供的文件进行了分析"},
                {"title": "主要发现", "content": "发现了以下要点..."},
                {"title": "建议", "content": "建议采取以下措施..."}
            ]
        }
    
    def _generate_text_output(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成文本输出"""
        answer = "基于您的问题，我的回答是..."
        
        # 如果有规划器的最终答案，使用它
        if context.get("planner_output", {}).get("final_answer"):
            answer = context["planner_output"]["final_answer"]
        
        return {
            "type": "text",
            "answer": answer,
            "confidence": context.get("planner_output", {}).get("confidence", 0.8)
        }
    
    def _format_output(self, output: Dict[str, Any], output_type: str) -> Dict[str, Any]:
        """格式化输出"""
        formatted = {
            "type": output_type,
            "content": output,
            "metadata": {
                "generated_at": state.updated_at.isoformat() if hasattr(state, 'updated_at') else None,
                "confidence": output.get("confidence", 1.0)
            }
        }
        
        return formatted