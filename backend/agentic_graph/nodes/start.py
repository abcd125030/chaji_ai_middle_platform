"""
起始节点
"""
from typing import Dict, Any
import logging

from .base import BaseNode
from ..core.schemas import RuntimeState

logger = logging.getLogger('django')


class StartNode(BaseNode):
    """起始节点，负责初始化和数据预处理"""
    
    def execute(self, state: RuntimeState) -> Dict[str, Any]:
        """
        执行起始节点逻辑
        
        主要工作：
        1. 用户数据提取
        2. 数据预处理
        3. 历史挖掘
        4. 确定场景
        """
        logger.info(f"执行起始节点: {self.name}")
        
        result = {
            "status": "success",
            "message": "初始化完成"
        }
        
        # 1. 提取用户上下文
        if state.user_query:
            state.user_context["query"] = state.user_query
            result["user_context_extracted"] = True
        
        # 2. 处理预处理文件
        if state.preprocessed_files:
            self._process_files(state)
            result["files_processed"] = len(state.preprocessed_files)
        
        # 3. 分析历史记忆
        if state.conversation_history:
            self._analyze_history(state)
            result["history_analyzed"] = True
        
        # 4. 确定场景和起点
        scenario = self._determine_scenario(state)
        state.scenario = scenario
        result["scenario"] = scenario
        
        # 5. 设置下一个节点
        state.next_node = "planner"  # 默认进入规划节点
        
        return result
    
    def _process_files(self, state: RuntimeState):
        """处理文件数据"""
        logger.debug(f"处理 {len(state.preprocessed_files)} 个文件")
        # TODO: 实现文件处理逻辑
        pass
    
    def _analyze_history(self, state: RuntimeState):
        """分析对话历史"""
        logger.debug(f"分析 {len(state.conversation_history)} 条历史记录")
        # TODO: 实现历史分析逻辑
        pass
    
    def _determine_scenario(self, state: RuntimeState) -> str:
        """确定执行场景"""
        # TODO: 实现场景判断逻辑
        # 根据用户查询、文件类型等确定场景
        if state.preprocessed_files:
            return "file_analysis"
        elif "代码" in state.user_query or "编程" in state.user_query:
            return "code_generation"
        else:
            return "general_qa"