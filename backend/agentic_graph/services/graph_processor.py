"""
Graph 处理器
连接 execute_graph_task 和 Graph 执行框架
"""
import logging
from typing import Dict, Any, Optional
from django.db import transaction

from ..core.schemas import RuntimeState
from ..models import GraphDefinition, TaskExecution, StepRecord
from ..executor.graph_executor import GraphExecutor

logger = logging.getLogger('django')


class GraphProcessor:
    """
    Graph 处理器
    桥接 execute_graph_task 任务和 GraphExecutor 执行器
    """
    
    def __init__(
        self,
        graph_definition: GraphDefinition,
        task_execution: TaskExecution,
        runtime_state: RuntimeState
    ):
        """
        初始化 Graph 处理器
        
        Args:
            graph_definition: Graph 定义
            task_execution: 任务执行实例
            runtime_state: 运行时状态
        """
        self.graph_definition = graph_definition
        self.task_execution = task_execution
        self.runtime_state = runtime_state
        
        logger.info(f"初始化 GraphProcessor - task: {task_execution.id}, graph: {graph_definition.name}")
    
    def execute(self) -> RuntimeState:
        """
        执行 Graph 处理流程
        
        Returns:
            最终的 RuntimeState
        """
        logger.info(f"开始执行 Graph - task: {self.task_execution.id}")
        
        try:
            # 从 RuntimeState 中提取必要信息
            initial_query = ""
            if hasattr(self.runtime_state, 'prompts') and self.runtime_state.prompts:
                initial_query = self.runtime_state.prompts[0]
            elif hasattr(self.runtime_state, 'prompt'):
                initial_query = self.runtime_state.prompt
            
            # 提取预处理文件
            preprocessed_files = {}
            if hasattr(self.runtime_state, 'preprocessed_files'):
                preprocessed_files = self.runtime_state.preprocessed_files
            
            # 提取对话历史
            conversation_history = []
            if hasattr(self.runtime_state, 'chat_history'):
                conversation_history = self.runtime_state.chat_history
            elif hasattr(self.runtime_state, 'conversation_history'):
                conversation_history = self.runtime_state.conversation_history
            
            # 创建 GraphExecutor 执行器
            executor = GraphExecutor(
                task_id=str(self.task_execution.id),
                graph_name=self.graph_definition.name,
                initial_query=initial_query,
                user_id=self.task_execution.user.id if self.task_execution.user else None,
                session_id=self.task_execution.session_id,
                preprocessed_files=preprocessed_files,
                conversation_history=conversation_history
            )
            
            # 如果有现有的 runtime_state，更新执行器的状态
            if hasattr(self.runtime_state, 'action_history'):
                executor.state.action_history = self.runtime_state.action_history
            if hasattr(self.runtime_state, 'memory'):
                executor.state.memory = self.runtime_state.memory
            if hasattr(self.runtime_state, 'user_context'):
                executor.state.user_context = self.runtime_state.user_context
            
            # 执行 Graph
            executor.run()
            
            # 将执行器的状态转换回 RuntimeState
            final_state = self._convert_executor_state_to_runtime_state(executor.state)
            
            # 记录执行步骤
            self._record_execution_steps(executor.state.action_history)
            
            logger.info(f"Graph 执行完成 - task: {self.task_execution.id}")
            
            return final_state
            
        except Exception as e:
            logger.error(f"Graph 执行失败 - task: {self.task_execution.id}, 错误: {e}", exc_info=True)
            raise
    
    def _convert_executor_state_to_runtime_state(self, executor_state) -> RuntimeState:
        """
        将 GraphExecutor 的状态转换为 RuntimeState
        
        Args:
            executor_state: GraphExecutor 的运行时状态
            
        Returns:
            RuntimeState 实例
        """
        # 创建新的 RuntimeState
        runtime_state_dict = {
            'prompts': [executor_state.user_query] if executor_state.user_query else [],
            'user_context': executor_state.user_context,
            'memory': executor_state.memory,
            'action_history': [],
            'usage': []
        }
        
        # 转换 action_history
        if executor_state.action_history:
            # 按轮次组织 action_history
            current_round = []
            for action in executor_state.action_history:
                action_dict = {
                    'node': action.get('node', ''),
                    'summary': action.get('type', ''),
                    'result': action.get('result', {}),
                    'usage': {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0
                    }
                }
                current_round.append(action_dict)
            
            if current_round:
                runtime_state_dict['action_history'].append(current_round)
        
        # 添加最终输出
        if executor_state.final_output:
            runtime_state_dict['final_output'] = executor_state.final_output
        
        # 计算总 token 使用量
        total_tokens = 0
        for action in executor_state.action_history:
            if 'result' in action and isinstance(action['result'], dict):
                usage = action['result'].get('usage', {})
                total_tokens += usage.get('total_tokens', 0)
        
        runtime_state_dict['usage'].append({
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': total_tokens
        })
        
        # 创建 RuntimeState 实例
        runtime_state = RuntimeState(runtime_state_dict)
        
        return runtime_state
    
    def _record_execution_steps(self, action_history: list):
        """
        记录执行步骤到 StepRecord
        
        Args:
            action_history: 动作历史列表
        """
        try:
            step_number = 0
            for action in action_history:
                step_number += 1
                
                # 创建步骤记录
                StepRecord.objects.create(
                    task_execution=self.task_execution,
                    node_id=action.get('node', 'unknown'),
                    node_type=action.get('type', 'unknown'),
                    node_name=action.get('node', 'unknown'),
                    step_number=step_number,
                    input_data={},
                    output_data=action.get('result', {}),
                    result='success',
                    total_tokens=action.get('result', {}).get('usage', {}).get('total_tokens', 0)
                )
                
            logger.info(f"记录了 {step_number} 个执行步骤")
            
        except Exception as e:
            logger.error(f"记录执行步骤失败: {e}", exc_info=True)
            # 不抛出异常，避免影响主流程