import os
import uuid
from django.conf import settings
from typing import List, Any, Dict
from .models import AgentTask # 移除 Node，因为 services.py 不直接使用 Node
from .core.processor import GraphExecutor # 导入新的 GraphExecutor
import logging
from .utils.logger_config import logger, log_state_change, log_execution_step

class AgentService:
    """
    Agent 任务服务层，负责处理 Agent 任务的业务逻辑，包括文件存储、任务启动等。
    """

    def __init__(self):
        try:
            # 确保文件上传目录存在
            self.upload_dir = os.path.join(settings.MEDIA_ROOT, 'agent_uploads')
            os.makedirs(self.upload_dir, exist_ok=True)
        except Exception as e:
            # 重新抛出异常，以便上层可以捕获到初始化失败
            raise

    def _save_file(self, file_obj):
        """
        保存上传的文件到指定目录。
        :param file_obj: 上传的文件对象
        :return: 字典包含 {'path': 保存路径, 'original_name': 原始文件名}
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
            'original_name': original_name
        }

    def _preprocess_files(self, saved_files: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        预处理上传的文件，将不同类型文件转换为结构化数据：
        - docx/pdf 转换为 markdown 文本
        - excel 转换为表格数据结构
        - 图片通过视觉模型转换为文字描述
        
        :param saved_files: 已保存的文件信息列表，每个元素包含:
            {'path': 文件路径, 'original_name': 原始文件名}
            
        :return: 预处理后的文件数据字典，结构如下:
            {
                'documents': {
                    'uuid-filename.docx': {
                        'content': 'markdown内容...',
                        'summary': '文档摘要...',
                        'name': 'report.docx'
                    },
                    'uuid-filename.pdf': {
                        'content': 'markdown内容...',
                        'summary': '文档摘要...',
                        'name': 'document.pdf'
                    }
                },
                'tables': {
                    'uuid-filename.xlsx': {
                        'data': [{'col1': 'val1', ...}, ...],
                        'row_count': 100,
                        'column_count': 5,
                        'name': 'data.xlsx'
                    }
                },
                'images': {
                    'uuid-filename.jpg': {
                        'description': '这是一张包含...的图片',
                        'name': 'photo.jpg',
                        'file_path': '/path/to/file',
                        'model_used': 'qwen3-vl-plus'
                    }
                },
                'other_files': [
                    {'path': '/path/to/file.zip', 'original_name': 'archive.zip'}
                ]
            }
        """
        from tools.preprocessors.processors.document_parser import DocumentParserTool
        from tools.preprocessors.processors.excel_processor import ExcelProcessorTool
        from tools.preprocessors.processors.image_processor import ImageProcessorTool
        
        processed_files = {
            'documents': {},  # 存储 markdown 格式的文档内容
            'tables': {},     # 存储 pandas 格式的表格数据
            'images': {},     # 存储图片的文字描述
            'other_files': [] # 存储其他类型文件的路径信息
        }
        
        if not saved_files:
            return processed_files
            
        document_parser = DocumentParserTool()
        excel_processor = ExcelProcessorTool()
        image_processor = ImageProcessorTool()
        
        for file_info in saved_files:
            if not file_info:
                continue
                
            file_path = file_info['path']
            original_name = file_info['original_name']
            file_extension = os.path.splitext(original_name)[1].lower()
            uuid_filename = os.path.basename(file_path)
            
            try:
                if file_extension in ['.docx', '.pdf']:
                    # 使用 document_parser 工具处理 docx 和 pdf 文件
                    result = document_parser.execute({'file_path': file_path})
                    
                    if result.get('status') == 'success':
                        # 对于 PDF，可能返回 'content' 或 'markdown_content'
                        content_key = 'markdown_content' if 'markdown_content' in result else 'content'
                        # 使用 UUID 文件名作为键（从文件路径中提取）
                        uuid_filename = os.path.basename(file_path)
                        # 创建包含内容、摘要和原始文件名的对象
                        processed_files['documents'][uuid_filename] = {
                            'content': result.get(content_key, ''),
                            'summary': result.get('summary', ''),
                            'name': original_name
                        }
                    else:
                        processed_files['other_files'].append(file_info)
                        
                elif file_extension in ['.xlsx', '.xls']:
                    # 使用 excel_processor 工具处理 excel 文件
                    result = excel_processor.execute({'file_path': file_path})
                    
                    if result.get('status') == 'success':
                        # 将 JSON 数据转换为可以重新构建 pandas DataFrame 的格式
                        import json
                        table_data = json.loads(result.get('table_json', '[]'))
                        # 使用 UUID 文件名作为键（从文件路径中提取）
                        uuid_filename = os.path.basename(file_path)
                        processed_files['tables'][uuid_filename] = {
                            'data': table_data,
                            'row_count': result.get('row_count', 0),
                            'column_count': result.get('column_count', 0),
                            'name': original_name
                        }
                    else:
                        processed_files['other_files'].append(file_info)
                        
                elif file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']:
                    # 使用 image_processor 工具处理图片文件
                    result = image_processor.execute({'file_path': file_path})
                    
                    if result.get('status') == 'success':
                        # 使用 UUID 文件名作为键
                        uuid_filename = os.path.basename(file_path)
                        processed_files['images'][uuid_filename] = {
                            'description': result.get('description', ''),
                            'name': original_name,
                            'file_path': file_path,
                            'model_used': result.get('model_used', 'unknown')
                        }
                    else:
                        # 如果图片处理失败，仍保留文件信息
                        processed_files['other_files'].append(file_info)
                        pass  # 图片处理失败时的处理将在后续添加日志
                        
                else:
                    # 其他类型文件暂不预处理，保留文件路径信息
                    processed_files['other_files'].append(file_info)
                    
            except Exception as e:
                processed_files['other_files'].append(file_info)
        
        
        return processed_files

    def start_agent_task(self, session_id: str, messages: List[Dict], files: List[Any], graph_name: str = 'Super-Router Agent', usage: str = None, user=None) -> AgentTask:
        """
        异步启动一个 Agent 任务。
        :param session_id: 会话ID
        :param messages: 消息列表
        :param files: 文件对象列表
        :param graph_name: 要启动的 Agent 图的名称，默认为 'Super-Router Agent'
        :param usage: 任务类型标签，用于选择特定提示词 (可选)
        :param user: 创建任务的用户对象 (可选)
        :return: AgentTask 实例
        """
        from .tasks import run_graph_task
        from .models import Graph

        # 1. 处理文件信息
        # 如果files已经是包含路径的字典列表，直接使用
        # 否则保存文件
        saved_files = []
        for f in files:
            if f:
                if isinstance(f, dict) and 'path' in f:
                    # 已经是文件路径信息，转换格式
                    saved_files.append({
                        'path': f['path'],
                        'original_name': f.get('name', os.path.basename(f['path']))
                    })
                else:
                    # 旧的文件对象格式，需要保存
                    saved_files.append(self._save_file(f))

        # 2. 预处理文件内容（注：图片文件会被放入 other_files 中）
        processed_files = self._preprocess_files(saved_files)

        # 3. 从 other_files 中提取图片路径
        origin_images = []
        # 图片文件扩展名
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
        
        # 从 other_files 中提取图片
        for file_info in processed_files.get('other_files', []):
            if file_info:
                original_name = file_info['original_name']
                file_extension = os.path.splitext(original_name)[1].lower()
                if file_extension in image_extensions:
                    # 将图片文件路径添加到 origin_images
                    origin_images.append(file_info['path'])


        # 4. 创建 AgentTask 记录，状态为 PENDING
        try:
            graph = Graph.objects.get(name=graph_name)
        except Graph.DoesNotExist:
            raise ValueError(f"Graph '{graph_name}' not found.")

        # 从messages中提取prompt和历史
        prompt = messages[-1]['content'] if messages else ''
        conversation_history = messages[:-1]
        
        # messages提取信息将在后续添加日志

        input_data = {"task_goal": prompt}
        if processed_files:
            input_data["preprocessed_files_summary"] = {
                "documents_count": len(processed_files.get('documents', {})),
                "tables_count": len(processed_files.get('tables', {})),
                "other_files_count": len(processed_files.get('other_files', [])),
                "document_names": list(processed_files.get('documents', {}).keys()),
                "table_names": list(processed_files.get('tables', {}).keys())
            }
        if usage:
            input_data["usage"] = usage

        # 5. 查找同session的历史任务（包括已完成和失败的），限制数量避免性能问题
        MAX_SESSION_HISTORY = 20
        historical_tasks = []
        if session_id and user:
            # 包含 COMPLETED 和 FAILED 状态的任务，让用户能在失败的基础上继续
            historical_task_uuids = list(AgentTask.objects.filter(
                session_id=session_id,
                user=user,
                status__in=[AgentTask.TaskStatus.COMPLETED, AgentTask.TaskStatus.FAILED]
            ).order_by('-created_at')[:MAX_SESSION_HISTORY].values_list('task_id', flat=True))
            
            # 将UUID对象转换为字符串
            historical_tasks = [str(task_id) for task_id in historical_task_uuids]
            
            # 反转顺序保持时间顺序
            historical_tasks.reverse()

        agent_task = AgentTask.objects.create(
            graph=graph,
            user=user,
            status=AgentTask.TaskStatus.PENDING,
            session_id=session_id,
            session_task_history=historical_tasks,
            input_data=input_data,
            state_snapshot={
                'preprocessed_files': processed_files,
                'conversation_history': conversation_history,
                'current_step': None,
                'execution_history': []
            }
        )
        

        # 4. 调用异步任务
        run_graph_task.delay(
            task_id=str(agent_task.task_id),
            graph_name=graph_name,
            initial_task_goal=prompt,
            preprocessed_files=processed_files,
            origin_images=origin_images,
            conversation_history=conversation_history,
            usage=usage,
            user_id=user.id if user else None,
            session_id=session_id
        )
        

        # 5. 立即返回 AgentTask 实例
        return agent_task
    
    def get_task_progress(self, task_id: str, last_action_index: int = 0):
        """
        获取任务进度，直接从 state_snapshot 获取数据
        
        功能点：
        1. 从 state_snapshot 的 action_history 获取实时进度数据
        2. 从 state_snapshot 的 full_action_data 获取完整执行数据
        3. 保持数据的原始性，不修改 state 中的字段值
        4. 支持增量获取（通过 last_action_index）
        5. 检查任务超时并自动标记为失败（超过3分钟未更新）
        
        Args:
            task_id: 任务ID
            last_action_index: 上次处理的 action 索引（从0开始）
            
        Returns:
            dict: 包含任务状态、action_history、full_action_data 等信息
                - status: 任务状态
                - action_history: 实时执行历史（增量部分）
                - full_action_data: 完整执行数据
                - last_action_index: 最新的 action 索引
                - is_completed: 任务是否已完成
                - output_data: 任务输出数据
        """
        from .models import AgentTask
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            task = AgentTask.objects.get(task_id=task_id)
            
            # 检查任务超时（仅对 RUNNING 状态的任务进行检查）
            if task.status == AgentTask.TaskStatus.RUNNING:
                # 计算任务最后更新时间与当前时间的差值
                time_since_update = timezone.now() - task.updated_at
                timeout_duration = timedelta(minutes=3)
                
                if time_since_update > timeout_duration:
                    # 任务超时，标记为失败
                    # 超时检测将在后续添加日志
                    
                    # 更新任务状态为失败
                    task.status = AgentTask.TaskStatus.FAILED
                    task.output_data = {
                        'final_conclusion': f'任务执行超时（超过3分钟未响应）。最后更新时间：{task.updated_at.strftime("%Y-%m-%d %H:%M:%S")}',
                        'task_goal': task.state_snapshot.get('task_goal', '') if task.state_snapshot else '',
                        'title': '任务超时'
                    }
                    
                    # 如果有 state_snapshot，添加超时信息到 action_history
                    if task.state_snapshot:
                        action_history = task.state_snapshot.get('action_history', [])
                        
                        timeout_action = {
                            'type': 'final_answer',
                            'data': {
                                'final_answer': f'抱歉，任务执行超时。系统检测到任务超过3分钟未响应，已自动终止。\n\n任务最后更新时间：{task.updated_at.strftime("%Y-%m-%d %H:%M:%S")}\n超时检测时间：{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n可能的原因：\n• 任务复杂度过高，需要更长处理时间\n• 系统资源暂时繁忙\n• 网络或服务暂时不可用\n\n建议您稍后重试，或者尝试简化您的问题。如果问题持续存在，请联系系统管理员。'
                            },
                            'timestamp': timezone.now().isoformat()
                        }
                        
                        # 处理嵌套格式的 action_history
                        if action_history and isinstance(action_history[0], list):
                            # 嵌套格式：添加到最后一个子列表
                            action_history[-1].append(timeout_action)
                        else:
                            # 扁平格式（向后兼容）
                            action_history.append(timeout_action)
                        
                        task.state_snapshot['action_history'] = action_history
                    
                    # 保存任务状态更新
                    from backend.utils.db_connection import ensure_db_connection_safe
                    ensure_db_connection_safe()
                    task.save(update_fields=['status', 'output_data', 'state_snapshot', 'updated_at'])
                    
                    # 任务失败标记将在后续添加日志
            
            # 检查是否有 state_snapshot
            if not task.state_snapshot:
                # 缺少state_snapshot将在后续添加日志
                return {
                    'status': task.status,
                    'action_history': [],
                    'full_action_data': {},
                    'last_action_index': 0,
                    'output_data': task.output_data,
                    'is_completed': task.status in [
                        AgentTask.TaskStatus.COMPLETED,
                        AgentTask.TaskStatus.FAILED,
                        AgentTask.TaskStatus.CANCELLED
                    ]
                }
            
            # 从 state_snapshot 获取数据
            state_snapshot = task.state_snapshot
            
            # 获取 action_history（实时进度）
            action_history = state_snapshot.get('action_history', [])
            
            # 【修复】处理嵌套列表格式的action_history
            # action_history格式: [[session1_actions], [session2_actions], ...]
            # 我们需要返回完整的嵌套格式,让SSE接口处理
            # SSE接口会自动提取最后一个子列表(当前会话)
            
            # 不进行增量过滤,直接返回完整的action_history
            # 因为SSE接口会根据last_action_index进行过滤
            new_actions = action_history
            
            # 记录action_history信息
            if new_actions:
                # 计算总的action数量(扁平化后)
                total_actions = 0
                if isinstance(new_actions, list) and new_actions:
                    if isinstance(new_actions[0], list):
                        # 嵌套格式
                        for session_actions in new_actions:
                            total_actions += len(session_actions)
                    else:
                        # 扁平格式
                        total_actions = len(new_actions)
                # 进度信息将在后续添加日志
            
            # 获取 full_action_data（完整数据）
            full_action_data = state_snapshot.get('full_action_data', {})
            
            # 计算最新的 action 索引
            new_last_index = len(action_history)
            
            return {
                'status': task.status,
                'action_history': new_actions,  # 只返回增量部分
                'full_action_history': action_history,  # 也可以返回完整历史供客户端选择
                'full_action_data': full_action_data,
                'last_action_index': new_last_index,
                'output_data': task.output_data,
                'is_completed': task.status in [
                    AgentTask.TaskStatus.COMPLETED,
                    AgentTask.TaskStatus.FAILED,
                    AgentTask.TaskStatus.CANCELLED
                ],
                # 额外信息
                'task_goal': state_snapshot.get('task_goal'),
                'usage': state_snapshot.get('usage'),
                'preprocessed_files': state_snapshot.get('preprocessed_files', {}),
                'origin_images': state_snapshot.get('origin_images', [])
            }
            
        except AgentTask.DoesNotExist:
            # 任务未找到将在后续添加日志
            return None
        except Exception as e:
            # 获取任务进度错误将在后续添加日志
            # 返回基本信息，避免完全失败
            try:
                task = AgentTask.objects.get(task_id=task_id)
                return {
                    'status': task.status,
                    'action_history': [],
                    'full_action_data': {},
                    'last_action_index': 0,
                    'output_data': task.output_data,
                    'is_completed': task.status in [
                        AgentTask.TaskStatus.COMPLETED,
                        AgentTask.TaskStatus.FAILED,
                        AgentTask.TaskStatus.CANCELLED
                    ],
                    'error': str(e)
                }
            except:
                return None