"""
agentic_graph Celery 任务
负责异步执行 Graph 任务
"""
import logging
from typing import Dict, Optional
from backend.celery import app
from backend.utils.db_connection import ensure_db_connection_safe
from django.utils import timezone

logger = logging.getLogger('django')


@app.task(bind=True)
def execute_graph_task(self,
                       task_id: str,
                       graph_id: str,
                       initial_state: Dict,
                       user_id: Optional[int] = None,
                       session_id: Optional[str] = None):
    """
    Celery 异步任务，用于执行 Graph
    
    Args:
        self: Celery task 实例
        task_id: 任务执行ID (TaskExecution.id)
        graph_id: 图定义ID (GraphDefinition.id)
        initial_state: 初始 RuntimeState 数据
        user_id: 用户ID
        session_id: 会话ID
    """
    from .models import TaskExecution, GraphDefinition, StepRecord
    from .core.schemas import RuntimeState
    
    try:
        # 确保数据库连接有效
        ensure_db_connection_safe()
        
        logger.info(f"开始执行 Graph 任务: task_id={task_id}, graph_id={graph_id}")
        
        # 1. 获取任务和图定义
        try:
            task = TaskExecution.objects.get(id=task_id)
            graph = GraphDefinition.objects.get(id=graph_id)
        except TaskExecution.DoesNotExist:
            logger.error(f"任务不存在: {task_id}")
            return
        except GraphDefinition.DoesNotExist:
            logger.error(f"图定义不存在: {graph_id}")
            _mark_task_failed(task_id, f"图定义不存在: {graph_id}")
            return
        
        # 2. 更新任务状态为运行中
        task.status = 'running'
        task.started_at = timezone.now()
        task.save(update_fields=['status', 'started_at', 'updated_at'])
        
        # 3. 初始化 RuntimeState
        runtime_state = RuntimeState.from_dict(initial_state)
        
        # 4. 填充用户上下文（如果有用户）
        if user_id:
            user_context = _get_user_context(user_id)
            runtime_state.user_context = user_context
            task.runtime_state['user_context'] = user_context
            task.save(update_fields=['runtime_state', 'updated_at'])
        
        # 5. 获取相关历史记忆（如果配置了向量数据库）
        if session_id:
            memory = _retrieve_memory(session_id, initial_state.get('prompts', [''])[0])
            runtime_state.memory = memory
            task.runtime_state['memory'] = memory
            task.save(update_fields=['runtime_state', 'updated_at'])
        
        # 6. 执行 Graph 处理流程
        try:
            # 获取 Graph 处理器
            from .services.graph_processor import GraphProcessor
            
            processor = GraphProcessor(
                graph_definition=graph,
                task_execution=task,
                runtime_state=runtime_state
            )
            
            # 执行处理流程
            final_state = processor.execute()
            
            # 7. 更新最终状态
            task.runtime_state = final_state.to_dict()
            task.status = 'completed'
            task.completed_at = timezone.now()
            
            # 提取最终结果
            if final_state.action_history and len(final_state.action_history) > 0:
                last_round = final_state.action_history[-1]
                if last_round:
                    # 查找输出节点的结果
                    for action in reversed(last_round):
                        if action.get('node', '').startswith('output'):
                            task.result = action.get('result', {})
                            break
            
            # 统计总 token 使用量
            total_tokens = 0
            for usage_round in final_state.usage:
                total_tokens += usage_round.get('total_tokens', 0)
            task.total_tokens = total_tokens
            
            task.save(update_fields=[
                'runtime_state', 'status', 'completed_at', 
                'result', 'total_tokens', 'updated_at'
            ])
            
            logger.info(f"任务执行成功: {task_id}, 总Token: {total_tokens}")
            
        except Exception as process_error:
            logger.error(f"Graph 处理失败: {process_error}", exc_info=True)
            _mark_task_failed(task_id, f"处理失败: {str(process_error)}")
            raise
        
    except Exception as e:
        logger.error(f"异步任务执行失败 - task_id: {task_id}, 错误: {e}", exc_info=True)
        _mark_task_failed(task_id, str(e))
        raise


def _mark_task_failed(task_id: str, error_message: str):
    """
    标记任务失败
    
    Args:
        task_id: 任务ID
        error_message: 错误信息
    """
    from .models import TaskExecution
    
    try:
        ensure_db_connection_safe()
        task = TaskExecution.objects.get(id=task_id)
        task.mark_failed(error_message)
        logger.info(f"任务标记为失败: {task_id}")
    except TaskExecution.DoesNotExist:
        logger.error(f"无法找到任务以更新失败状态: {task_id}")
    except Exception as db_error:
        logger.error(f"无法更新任务失败状态 - task_id: {task_id}, 错误: {db_error}")


def _get_user_context(user_id: int) -> Dict:
    """
    获取用户上下文信息
    
    Args:
        user_id: 用户ID
        
    Returns:
        用户上下文字典
    """
    try:
        from authentication.user_service import UserService
        
        # 使用 UserService 获取完整的用户上下文
        user_context = UserService.get_user_context(user_id)
        
        # 补充 agentic_graph 特定的字段（如果需要）
        if user_context:
            # 确保 user_id 是字符串格式
            user_context['user_id'] = str(user_context.get('user_id', user_id))
            
            # 这些是原代码中有但 UserService 可能没有的字段
            if 'knowledge_domains' not in user_context:
                user_context['knowledge_domains'] = user_context.get('tags', [])
            
            if 'interaction_history' not in user_context:
                user_context['interaction_history'] = {
                    'total_sessions': 0,
                    'favorite_tools': [],
                    'common_topics': []
                }
        
        return user_context or {}
        
    except Exception as e:
        logger.error(f"获取用户上下文失败 user_id={user_id}: {e}")
        return {}


def _retrieve_memory(session_id: str, prompt: str, limit: int = 5) -> list:
    """
    从向量数据库检索相关历史记忆
    
    Args:
        session_id: 会话ID
        prompt: 当前提示词
        limit: 返回记忆条数限制
        
    Returns:
        相关记忆列表
    """
    try:
        # TODO: 实现向量数据库检索逻辑
        # 这里需要：
        # 1. 连接向量数据库（Qdrant/mem0ai）
        # 2. 使用 prompt 进行相似度搜索
        # 3. 过滤同一会话的历史记录
        # 4. 返回相关记忆
        
        logger.info(f"检索会话 {session_id} 的相关记忆")
        
        # 临时返回空列表，等待向量数据库集成
        return []
        
    except Exception as e:
        logger.error(f"检索记忆失败: {e}")
        return []



@app.task
def update_task_statistics(task_id: str):
    """
    更新任务统计信息
    
    Args:
        task_id: 任务ID
    """
    from .models import TaskExecution, StepRecord
    
    try:
        ensure_db_connection_safe()
        
        task = TaskExecution.objects.get(id=task_id)
        
        # 统计步骤信息
        steps = StepRecord.objects.filter(task_execution=task)
        
        total_tokens = sum(step.total_tokens for step in steps)
        total_duration = sum(step.duration_ms for step in steps)
        
        # 更新任务统计
        task.total_tokens = total_tokens
        task.metadata['statistics'] = {
            'total_steps': steps.count(),
            'total_duration_ms': total_duration,
            'average_step_duration_ms': total_duration / steps.count() if steps.count() > 0 else 0,
            'steps_by_type': {}
        }
        
        # 按节点类型统计
        for step in steps:
            node_type = step.node_type
            if node_type not in task.metadata['statistics']['steps_by_type']:
                task.metadata['statistics']['steps_by_type'][node_type] = 0
            task.metadata['statistics']['steps_by_type'][node_type] += 1
        
        task.save(update_fields=['total_tokens', 'metadata', 'updated_at'])
        
        logger.info(f"更新任务统计: {task_id}, 总步骤: {steps.count()}, 总Token: {total_tokens}")
        
    except TaskExecution.DoesNotExist:
        logger.error(f"任务不存在: {task_id}")
    except Exception as e:
        logger.error(f"更新任务统计失败: {e}", exc_info=True)