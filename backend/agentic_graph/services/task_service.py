"""
agentic_graph 任务服务层
负责处理 Graph 任务的业务逻辑，包括文件存储、任务启动等
复用 agentic 的核心逻辑，适配新的数据模型
"""
import os
import uuid
import json
import logging
from typing import List, Any, Dict, Optional
from django.conf import settings
from django.contrib.auth import get_user_model

from ..models import GraphDefinition, TaskExecution, StepRecord
from ..core.schemas import RuntimeState

logger = logging.getLogger('django')
User = get_user_model()


class TaskService:
    """
    Graph 任务服务层
    提供任务创建、执行、查询等核心服务方法
    """
    
    def __init__(self):
        """初始化服务，确保必要的目录存在"""
        try:
            # 确保文件上传目录存在
            self.upload_dir = os.path.join(settings.MEDIA_ROOT, 'graph_uploads')
            os.makedirs(self.upload_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"初始化 TaskService 失败: {e}")
            raise
    
    def _save_file(self, file_obj) -> Optional[Dict[str, str]]:
        """
        保存上传的文件到指定目录
        
        Args:
            file_obj: 上传的文件对象
            
        Returns:
            字典包含 {'path': 保存路径, 'original_name': 原始文件名}
        """
        if not file_obj:
            return None
        
        # 使用 UUID 作为文件名，保留原始扩展名
        original_name = file_obj.name
        file_extension = os.path.splitext(original_name)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file_obj.chunks():
                destination.write(chunk)
        
        return {
            'path': file_path,
            'original_name': original_name,
            'unique_name': unique_filename
        }
    
    def _preprocess_files(self, saved_files: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        预处理上传的文件
        将 docx 转换为 markdown，excel 转换为结构化数据
        
        Args:
            saved_files: 已保存的文件信息列表
            
        Returns:
            预处理后的文件数据字典
        """
        from tools.preprocessors.processors.document_parser import DocumentParserTool
        from tools.preprocessors.processors.excel_processor import ExcelProcessorTool
        
        processed_files = {
            'documents': {},      # 存储 markdown 格式的文档内容
            'tables': {},         # 存储 pandas 格式的表格数据
            'other_files': [],    # 存储其他类型文件的路径信息
            'file_mapping': {}    # 存储原始文件名到 UUID 文件名的映射
        }
        
        if not saved_files:
            return processed_files
        
        document_parser = DocumentParserTool()
        excel_processor = ExcelProcessorTool()
        
        for file_info in saved_files:
            if not file_info:
                continue
            
            file_path = file_info['path']
            original_name = file_info['original_name']
            unique_name = file_info.get('unique_name', os.path.basename(file_path))
            file_extension = os.path.splitext(original_name)[1].lower()
            
            # 记录文件名映射
            processed_files['file_mapping'][unique_name] = original_name
            
            try:
                if file_extension in ['.docx', '.pdf']:
                    # 处理文档文件
                    result = document_parser.execute({'file_path': file_path})
                    
                    if result.get('status') == 'success':
                        content_key = 'markdown_content' if 'markdown_content' in result else 'content'
                        processed_files['documents'][unique_name] = result.get(content_key, '')
                        logger.info(f"成功处理文档: {original_name}")
                    else:
                        processed_files['other_files'].append(file_info)
                        logger.warning(f"文档处理失败: {original_name}")
                        
                elif file_extension in ['.xlsx', '.xls']:
                    # 处理 Excel 文件
                    result = excel_processor.execute({'file_path': file_path})
                    
                    if result.get('status') == 'success':
                        table_data = json.loads(result.get('table_json', '[]'))
                        processed_files['tables'][unique_name] = {
                            'data': table_data,
                            'row_count': result.get('row_count', 0),
                            'column_count': result.get('column_count', 0)
                        }
                        logger.info(f"成功处理表格: {original_name}")
                    else:
                        processed_files['other_files'].append(file_info)
                        logger.warning(f"表格处理失败: {original_name}")
                        
                else:
                    # 其他类型文件暂不预处理
                    processed_files['other_files'].append(file_info)
                    
            except Exception as e:
                logger.error(f"预处理文件 {original_name} 时出错: {e}")
                processed_files['other_files'].append(file_info)
        
        return processed_files
    
    def _extract_images(self, processed_files: Dict[str, Any]) -> List[str]:
        """
        从预处理文件中提取图片路径
        
        Args:
            processed_files: 预处理后的文件数据
            
        Returns:
            图片文件路径列表
        """
        origin_images = []
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
        
        for file_info in processed_files.get('other_files', []):
            if file_info:
                original_name = file_info.get('original_name', '')
                file_extension = os.path.splitext(original_name)[1].lower()
                if file_extension in image_extensions:
                    origin_images.append(file_info['path'])
                    logger.info(f"识别图片文件: {original_name}")
        
        return origin_images
    
    def create_task(self,
                    session_id: str,
                    messages: List[Dict],
                    files: Optional[List[Any]] = None,
                    graph_name: str = 'Super-Router Agent',
                    usage: Optional[str] = None,
                    user: Optional[User] = None) -> TaskExecution:
        """
        创建并启动 Graph 任务
        
        Args:
            session_id: 会话ID
            messages: 消息列表
            files: 文件对象列表
            graph_name: 要使用的 Graph 名称
            usage: 任务类型标签
            user: 创建任务的用户
            
        Returns:
            TaskExecution 实例
        """
        from ..tasks import execute_graph_task
        
        # 1. 保存上传的文件
        saved_files = []
        if files:
            saved_files = [self._save_file(f) for f in files if f]
            saved_files = [f for f in saved_files if f]  # 过滤None值
        
        # 2. 预处理文件内容
        processed_files = self._preprocess_files(saved_files)
        
        # 3. 提取图片路径
        origin_images = self._extract_images(processed_files)
        
        # 4. 获取或创建默认 Graph
        try:
            graph = GraphDefinition.objects.filter(
                name=graph_name,
                is_active=True
            ).order_by('-version').first()
            
            if not graph:
                # 如果没有找到，尝试获取任何激活的默认图
                graph = GraphDefinition.objects.filter(
                    is_default=True,
                    is_active=True
                ).first()
                
                if not graph:
                    raise ValueError(f"未找到可用的 Graph: {graph_name}")
                
                logger.warning(f"未找到 {graph_name}，使用默认图: {graph.name}")
        except Exception as e:
            logger.error(f"获取 Graph 失败: {e}")
            raise ValueError(f"Graph '{graph_name}' 配置错误")
        
        # 5. 从 messages 中提取 prompt 和历史
        prompt = messages[-1]['content'] if messages else ''
        conversation_history = messages[:-1] if len(messages) > 1 else []
        
        # 6. 构建初始 RuntimeState
        initial_state = {
            'prompts': [prompt],  # 支持多轮对话
            'user_context': {},   # 将在任务执行时填充
            'memory': [],
            'output_style': '',
            'output_structure': [],
            'scenario': '',
            'task_goals': [],
            'origin_files': [],
            'preprocessed_files': processed_files,
            'todos': [[]],  # 多轮对话的TODO清单
            'action_history': [[]],  # 多轮对话历史
            'chat_history': conversation_history,
            'usage': [{'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}]
        }
        
        # 7. 处理文件信息到 origin_files
        for file_info in saved_files:
            initial_state['origin_files'].append({
                'name': file_info['original_name'],
                'type': os.path.splitext(file_info['original_name'])[1][1:],  # 去掉点号
                'local_path': file_info['path'],
                'mapping': {
                    'provider': 'local',
                    'path': file_info['path']
                }
            })
        
        # 8. 添加图片到 origin_files
        for image_path in origin_images:
            initial_state['origin_files'].append({
                'name': os.path.basename(image_path),
                'type': 'image',
                'local_path': image_path,
                'mapping': {
                    'provider': 'local',
                    'path': image_path
                }
            })
        
        # 9. 查找历史任务（用于多轮对话）
        MAX_SESSION_HISTORY = 20
        historical_tasks = []
        if session_id and user:
            historical_task_ids = list(
                TaskExecution.objects.filter(
                    session_id=session_id,
                    user=user,
                    status__in=['completed', 'failed']
                ).order_by('-created_at')[:MAX_SESSION_HISTORY].values_list('id', flat=True)
            )
            historical_tasks = [str(task_id) for task_id in historical_task_ids]
            historical_tasks.reverse()  # 保持时间顺序
        
        # 10. 创建 TaskExecution 记录
        metadata = {
            'usage': usage,
            'session_history': historical_tasks,
            'original_graph_name': graph_name
        }
        
        task_execution = TaskExecution.objects.create(
            graph=graph,
            user=user,
            session_id=session_id,
            status='pending',
            runtime_state=initial_state,
            metadata=metadata
        )
        
        logger.info(f"创建任务: {task_execution.id}, Graph: {graph.name} v{graph.version}")
        
        # 11. 调用异步任务
        execute_graph_task.delay(
            task_id=str(task_execution.id),
            graph_id=str(graph.id),
            initial_state=initial_state,
            user_id=user.id if user else None,
            session_id=session_id
        )
        
        return task_execution
    
    def get_task_status(self, task_id: str, user: Optional[User] = None) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            user: 请求的用户（用于权限验证）
            
        Returns:
            任务状态字典
        """
        try:
            query = TaskExecution.objects.filter(id=task_id)
            if user:
                query = query.filter(user=user)
            
            task = query.first()
            if not task:
                logger.warning(f"任务未找到或无权访问: {task_id}")
                return None
            
            return {
                'task_id': str(task.id),
                'status': task.status,
                'current_node': task.current_node,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat(),
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'result': task.result,
                'error_message': task.error_message,
                'total_tokens': task.total_tokens,
                'total_cost': str(task.total_cost)
            }
        except Exception as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return None
    
    def get_task_steps(self, task_id: str, last_step_number: int = 0, user: Optional[User] = None) -> Dict:
        """
        获取任务执行步骤（支持增量获取）
        
        Args:
            task_id: 任务ID
            last_step_number: 上次处理的步骤序号
            user: 请求的用户
            
        Returns:
            包含步骤信息的字典
        """
        try:
            # 验证任务权限
            query = TaskExecution.objects.filter(id=task_id)
            if user:
                query = query.filter(user=user)
            
            task = query.first()
            if not task:
                return {
                    'error': 'Task not found or access denied',
                    'steps': [],
                    'last_step_number': last_step_number
                }
            
            # 获取新步骤
            new_steps = StepRecord.objects.filter(
                task_execution=task,
                step_number__gt=last_step_number
            ).order_by('step_number')
            
            # 格式化步骤数据
            formatted_steps = []
            for step in new_steps:
                formatted_steps.append({
                    'step_number': step.step_number,
                    'node_id': step.node_id,
                    'node_type': step.node_type,
                    'node_name': step.node_name,
                    'result': step.result,
                    'output_data': step.output_data,
                    'error_message': step.error_message,
                    'total_tokens': step.total_tokens,
                    'duration_ms': step.duration_ms,
                    'started_at': step.started_at.isoformat(),
                    'completed_at': step.completed_at.isoformat() if step.completed_at else None
                })
            
            # 获取最新步骤序号
            new_last_step = new_steps.last().step_number if new_steps else last_step_number
            
            # 从 runtime_state 获取 action_history
            action_history = []
            if task.runtime_state:
                # 获取当前轮次的 action_history
                all_action_history = task.runtime_state.get('action_history', [[]])
                if all_action_history and len(all_action_history) > 0:
                    current_round_history = all_action_history[-1]  # 最新一轮
                    if last_step_number < len(current_round_history):
                        action_history = current_round_history[last_step_number:]
            
            return {
                'task_id': str(task.id),
                'status': task.status,
                'steps': formatted_steps,
                'action_history': action_history,
                'last_step_number': new_last_step,
                'is_completed': task.status in ['completed', 'failed', 'cancelled'],
                'result': task.result,
                'runtime_state': task.runtime_state  # 可选：返回完整状态
            }
            
        except Exception as e:
            logger.error(f"获取任务步骤失败 {task_id}: {e}", exc_info=True)
            return {
                'error': str(e),
                'steps': [],
                'last_step_number': last_step_number
            }
    
    def cancel_task(self, task_id: str, user: Optional[User] = None) -> bool:
        """
        取消任务执行
        
        Args:
            task_id: 任务ID
            user: 请求的用户
            
        Returns:
            是否成功取消
        """
        try:
            query = TaskExecution.objects.filter(id=task_id)
            if user:
                query = query.filter(user=user)
            
            task = query.first()
            if not task:
                logger.warning(f"无法取消任务 {task_id}: 未找到或无权限")
                return False
            
            if task.status in ['completed', 'failed', 'cancelled']:
                logger.info(f"任务 {task_id} 已结束，状态: {task.status}")
                return False
            
            task.status = 'cancelled'
            task.save(update_fields=['status', 'updated_at'])
            
            logger.info(f"成功取消任务: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消任务失败 {task_id}: {e}")
            return False