import logging
from .utils.logger_config import logger, log_execution_step
from typing import List, Dict
from backend.celery import app
from backend.utils.db_connection import ensure_db_connection_safe
from .core.processor import GraphExecutor
from .models import AgentTask

@app.task(bind=True)
def run_graph_task(self, task_id: str, graph_name: str, initial_task_goal: str, preprocessed_files: dict, origin_images: List[str] = None, conversation_history: List[Dict] = None, usage: str = None, user_id: int = None, session_id: str = None):
    """
    Celery 异步任务，用于执行 Agentic Graph。
    :param user_id: 创建任务的用户ID (可选)
    """
    try:
        # 使用强力的连接恢复确保数据库连接有效
        ensure_db_connection_safe()
        # 初始化执行器
        # GraphExecutor 会自动加载或创建 AgentTask 实例
        executor = GraphExecutor(
            task_id=task_id,
            graph_name=graph_name,
            initial_task_goal=initial_task_goal,
            preprocessed_files=preprocessed_files,
            origin_images=origin_images,
            conversation_history=conversation_history,
            usage=usage, # 传递 usage 参数
            user_id=user_id,  # 传递用户ID给执行器
            session_id=session_id
        )
        
        # 运行图
        executor.run()
        

    except Exception as e:
        logger.error(f"异步 Agent 任务执行失败 - task_id: {task_id}, 错误: {e}", exc_info=True)
        # 发生异常时，更新任务状态为 FAILED
        try:
            # 在保存前确保数据库连接有效
            ensure_db_connection_safe()
            task = AgentTask.objects.get(task_id=task_id)
            task.status = AgentTask.TaskStatus.FAILED
            task.output_data = {'error': str(e)}
            task.save()
        except AgentTask.DoesNotExist:
            logger.error(f"无法找到任务以更新失败状态 - task_id: {task_id}")
        except Exception as db_error:
            logger.error(f"无法更新任务失败状态 - task_id: {task_id}, 数据库错误: {db_error}")
        # 重新抛出异常，以便 Celery 可以将其记录为任务失败
        raise