"""
聊天服务模块
处理聊天消息、调用 AI 服务、管理任务状态
"""

import logging
from typing import Dict, Any, Optional, List

from django.utils import timezone

from .models import ChatSession, ChatMessage
from agentic.services import AgentService

logger = logging.getLogger(__name__)  # 使用模块名作为 logger 名称


class ChatService:
    """聊天服务类，处理消息和 AI 交互"""
    
    def __init__(self):
        self.agent_service = AgentService()
        
    def process_message(
        self,
        session: ChatSession,
        message: str,
        files: Optional[List] = None,
        active_mode: Optional[str] = None,
        user = None
    ) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            session: 聊天会话对象
            message: 用户消息内容
            files: 上传的文件列表
            active_mode: 激活的模式 (research/default)
            user: 用户对象
            
        Returns:
            包含任务信息的字典
        """
        try:
            # 检查是否为重连请求
            is_reconnect = message == '[RECONNECT]'
            
            if not is_reconnect:
                # 1. 保存用户消息（重连请求不保存用户消息）
                ChatMessage.objects.create(
                    session=session,
                    role='user',
                    content=message,
                    files_info=self._process_files(files) if files else None
                )
            
            if is_reconnect:
                # 重连请求：找到现有的未完成助手消息
                assistant_message = session.messages.filter(
                    role='assistant',
                    is_complete=False,
                    task_id__isnull=False
                ).last()
                
                if not assistant_message:
                    return {
                        'success': False,
                        'error': '未找到可重连的任务'
                    }
                
                logger.info(f"重连到现有任务: task_id={assistant_message.task_id}")
            else:
                # 2. 创建助手占位消息
                assistant_message = ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content='',
                    is_complete=False
                )
                
                # 3. 更新会话信息
                session.last_interacted_at = timezone.now()
                session.last_message_preview = message[:200]
                session.save()
            
            # 4. 准备消息历史
            # 重要：确保最新的用户消息在messages列表的最后
            # 这样AgentService能正确提取到当前用户的新消息作为prompt
            messages = []
            
            # 获取所有历史消息（不包括刚创建的空助手消息）
            history_messages = session.messages.filter(
                role__in=['user', 'assistant']
            ).exclude(
                id=assistant_message.id  # 排除刚创建的空助手消息
            ).order_by('created_at')
            
            # 构建历史消息列表，但要确保不包含当前的新用户消息
            for msg in history_messages:
                if msg.content:
                    # 对于非重连请求，跳过内容与当前消息相同的最后一条用户消息
                    # （避免重复，因为我们会在最后显式添加）
                    if not is_reconnect and msg.role == 'user' and msg.content == message:
                        continue
                    messages.append({
                        'role': msg.role,
                        'content': msg.content
                    })
            
            # 对于非重连请求，确保当前用户消息在最后
            # 这很重要，因为AgentService使用messages[-1]作为prompt
            if not is_reconnect and message:
                messages.append({
                    'role': 'user',
                    'content': message
                })
            
            # 调试日志：显示准备的消息列表
            logger.info(f"[ChatService] 准备的消息历史 - session_id: {session.id}, "
                       f"消息数量: {len(messages)}, "
                       f"最后一条消息角色: {messages[-1]['role'] if messages else 'None'}, "
                       f"最后一条消息预览: {messages[-1]['content'][:100] if messages else 'None'}")
            
            if is_reconnect:
                # 重连请求：使用现有的task_id
                task_id = assistant_message.task_id
                logger.info(f"重连到现有任务: {task_id}")
            else:
                # 5. 调用 AgentService 启动任务
                # 根据 active_mode 选择 graph 和 usage
                graph_name = 'Super-Router Agent'  # 默认使用 Super-Router Agent
                usage = 'deep_research' if active_mode == 'research' else None
                
                task = self.agent_service.start_agent_task(
                    session_id=str(session.id),
                    messages=messages,
                    files=files or [],
                    graph_name=graph_name,
                    usage=usage,
                    user=user
                )
                
                # 6. 更新助手消息的 task_id
                task_id = str(task.task_id)
                assistant_message.task_id = task_id
                assistant_message.save()
            
            # 7. 记录任务创建信息
            logger.info(f"Task created successfully: task_id={task_id}, session_id={session.id}")
            
            return {
                'success': True,
                'task_id': task_id,
                'assistant_message_id': assistant_message.id,
                'session_id': session.id
            }
            
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _process_files(self, files: List[Dict]) -> List[Dict]:
        """处理上传的文件，返回文件路径和元信息"""
        file_info = []
        
        for file_data in files:
            # 文件数据现在是包含路径和元信息的字典
            info = {
                'path': file_data.get('path'),  # 本地文件路径
                'name': file_data.get('name'),
                'size': file_data.get('size'),
                'type': file_data.get('type', 'unknown')
            }
            
            # 根据文件类型添加预览类型标记
            file_type = info.get('type', '')
            
            if file_type in ['image/jpeg', 'image/png', 'image/webp']:
                info['preview_type'] = 'image'
            elif file_type in ['text/plain', 'text/markdown', 'application/json']:
                info['preview_type'] = 'text'
            elif file_type == 'application/pdf':
                info['preview_type'] = 'pdf'
            elif 'word' in file_type or 'document' in file_type:
                info['preview_type'] = 'document'
            elif 'excel' in file_type or 'spreadsheet' in file_type:
                info['preview_type'] = 'spreadsheet'
            else:
                info['preview_type'] = 'file'
                
            file_info.append(info)
        
        return file_info