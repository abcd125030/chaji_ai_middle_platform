"""chat.views
聊天相关 REST API 视图层。

本模块提供以下能力（更详细流程与 ASCII 图示参见同目录 `FLOW_DOC.md`）：
1. 会话(Session)的创建、查询、更新、删除
2. 消息(Message)的分页获取、发送、软删除
3. 异步 Agent 任务恢复与进度检查
4. 通过 ai_conversation_id 查询会话
5. 会话快照的创建与恢复

设计要点：
* 采用 Django REST Framework 裸函数视图 + 装饰器形式，权限统一使用 IsAuthenticated。
* 绝大部分操作都限定在当前登录用户(request.user)的资源范围内，避免越权。
* 消息发送走异步任务（ChatService.process_message）并立即返回 202，随后通过回调或轮询获取进度。
* 软删除逻辑只标记 is_deleted / deleted_at，不物理删除，方便审计与恢复。
* 任务恢复(check_incomplete_tasks_view) 会拉取最近 24 小时未完成的消息并尝试从 AgentService 同步进展。
* 快照(session_snapshot_view) 用于导出当前会话（含压缩过的 task_steps）并支持恢复。

注意：
* 不在此处做权限以外的复杂校验，复杂业务放入 Service / Model 方法中。
* 前端兼容性：DELETE 消息接口同时支持旧参数(index) 与 新参数(afterIndex + isFirstMessage)。
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
import logging
import base64
import os
from typing import List, Dict, Any

from .models import ChatSession, ChatMessage
from .serializers import (
    ChatSessionSerializer,
    ChatMessageSerializer,
    SessionListSerializer
)
from .services import ChatService
from .utils import create_session_snapshot, decompress_data

logger = logging.getLogger(__name__)  # 使用模块名作为 logger 名称，自动归属到 'webapps' 命名空间


def convert_base64_to_files(files_data: List[Dict[str, Any]]) -> List[SimpleUploadedFile]:
    """
    将base64编码的文件数据转换为Django的UploadedFile对象
    
    Args:
        files_data: 包含base64文件数据的字典列表，每个字典包含:
            - name: 文件名
            - type: MIME类型
            - size: 文件大小
            - data: base64编码的文件内容
    
    Returns:
        SimpleUploadedFile对象列表
    """
    converted_files = []
    
    for file_data in files_data:
        try:
            # 提取文件信息
            file_name = file_data.get('name', 'unknown')
            file_type = file_data.get('type', 'application/octet-stream')
            base64_data = file_data.get('data', '')
            
            # 处理base64数据（可能包含data:image/png;base64,前缀）
            if ',' in base64_data:
                # 去掉data:image/png;base64,这样的前缀
                base64_data = base64_data.split(',')[1]
            
            # 解码base64数据
            file_content = base64.b64decode(base64_data)
            
            # 创建SimpleUploadedFile对象
            uploaded_file = SimpleUploadedFile(
                name=file_name,
                content=file_content,
                content_type=file_type
            )
            
            converted_files.append(uploaded_file)
            logger.info(f"成功转换base64文件: {file_name}, 类型: {file_type}, 大小: {len(file_content)} bytes")
            
        except Exception as e:
            logger.error(f"转换base64文件失败: {file_data.get('name', 'unknown')}, 错误: {str(e)}")
            continue
    
    return converted_files


def save_files_to_storage(file_paths: List[str]) -> None:
    """
    将文件保存到 media/oss-bucket 目录
    
    Args:
        file_paths: 本地文件路径列表
    
    注意：该函数会将文件复制到 media/oss-bucket 目录，
    如果复制失败，会记录错误但不会中断后续文件的复制
    """
    import shutil
    from django.conf import settings
    from datetime import datetime
    
    if not file_paths:
        logger.info("没有需要保存的文件")
        return
    
    # 确定保存目录
    base_dir = os.path.join(settings.MEDIA_ROOT, 'oss-bucket')
    # 创建子目录结构: chat/YYYY/MM/DD/
    date_path = datetime.now().strftime('%Y/%m/%d')
    save_dir = os.path.join(base_dir, 'chat', date_path)
    
    # 确保目录存在
    os.makedirs(save_dir, exist_ok=True)
    
    logger.info(f"开始保存 {len(file_paths)} 个文件到 {save_dir}")
    
    # 上传成功和失败的计数
    success_count = 0
    failed_count = 0
    
    for file_path in file_paths:
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.warning(f"文件不存在，跳过: {file_path}")
                failed_count += 1
                continue
            
            # 获取文件名
            filename = os.path.basename(file_path)
            
            # 生成唯一文件名（避免重名）
            timestamp = datetime.now().strftime('%H%M%S%f')
            unique_filename = f"{timestamp}_{filename}"
            dest_path = os.path.join(save_dir, unique_filename)
            
            # 复制文件
            shutil.copy2(file_path, dest_path)
            
            logger.info(f"文件保存成功: {filename} -> {dest_path}")
            success_count += 1
            
            # 保存成功后可以选择删除本地临时文件
            # 注意：这里暂时保留本地文件，避免影响其他逻辑
            # os.remove(file_path)
            
        except Exception as e:
            logger.error(f"文件保存失败 {file_path}: {str(e)}")
            failed_count += 1
            continue
    
    # 记录保存结果
    logger.info(f"文件保存完成: 成功 {success_count} 个, 失败 {failed_count} 个")


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def sessions_view(request):
    """
    GET: 获取用户的所有会话列表
    POST: 创建新会话

    请求方式：
    - GET  无需参数，返回用户所有会话（按最近交互时间倒序）。
    - POST body(JSON)：可选字段：title, ai_conversation_id(若不提供自动生成) 等。

    响应：
    - 200(GET)  List[SessionListSerializer]
    - 201(POST) ChatSessionSerializer
    - 400(POST) 序列化校验失败
    权限：登录用户只能看到自身会话。
    """
    if request.method == 'GET':
        # 获取用户的所有会话
        sessions = ChatSession.objects.filter(
            user=request.user
        ).prefetch_related('messages').order_by('-last_interacted_at')
        
        serializer = SessionListSerializer(sessions, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        # 创建新会话
        data = request.data.copy()
        data['user'] = request.user.id
        
        # 如果没有提供 ai_conversation_id，生成一个
        if 'ai_conversation_id' not in data:
            import uuid
            data['ai_conversation_id'] = str(uuid.uuid4())
        
        serializer = ChatSessionSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def session_detail_view(request, session_id):
    """
    GET: 获取会话详情
    PUT: 更新会话信息
    DELETE: 删除会话

    路径参数：session_id
    - GET: 返回 ChatSessionSerializer 完整信息
    - PUT: 支持局部更新(partial=True)，例如修改 title / pinned 等
    - DELETE: 物理删除该会话（若需软删除可改造此处逻辑）
    错误：404 当会话不存在或不属于当前用户
    """
    session = get_object_or_404(
        ChatSession,
        id=session_id,
        user=request.user
    )
    
    if request.method == 'GET':
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = ChatSessionSerializer(session, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def messages_view(request, session_id):
    """
    GET: 获取会话的所有消息
    POST: 发送新消息
    DELETE: 删除指定索引后的消息

        统一对当前用户所属的会话进行操作。采用软删除策略：被删除消息设置 is_deleted=True。

        GET 查询参数：
            - page (默认1, 1-based)
            - page_size (默认50)
        返回：按 created_at 正序（最早 -> 最新）。实现方式：先倒序取分页再反转以保持接口历史顺序要求。

        POST 支持两种 Content-Type：
            - multipart/form-data (包含文件上传 files[]=...)
            - application/json
        字段：
            - message / content: 用户输入文本（二择一兼容）
            - activeMode: 前端指定的执行模式（透传给 ChatService）
            - files: 上传文件列表（仅 multipart）
        返回：202 Accepted + task_id，后续通过轮询/回调获取进度。

        DELETE 软删除策略：
            支持两种调用方式：
                1) afterIndex + isFirstMessage=true 且 afterIndex == -1 => 删除全部
                2) afterIndex >=0 => 删除该 index 之后的所有消息
                3) 兼容旧格式 index => 从 index 起删除
            注意：index/afterIndex 均基于未删除消息的按时间正序列表。
        错误：
            - 400 当参数无效
    """
    session = get_object_or_404(
        ChatSession,
        id=session_id,
        user=request.user
    )
    
    if request.method == 'GET':
        # 支持分页参数；未传入时使用默认值保证接口幂等
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))

        # 计算偏移量
        offset = (page - 1) * page_size

        # 获取未删除的消息总数
        total_count = session.messages.filter(is_deleted=False).count()

        # 获取分页后的未删除消息，按创建时间倒序，然后反转以保持正确顺序
        messages = list(session.messages.filter(is_deleted=False).order_by('-created_at')[offset:offset + page_size])
        messages.reverse()

        serializer = ChatMessageSerializer(messages, many=True)

        return Response({
            'messages': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_more': offset + page_size < total_count
            }
        })

    elif request.method == 'POST':
        # 处理聊天消息：立即创建一条"进行中"任务交给异步执行
        chat_service = ChatService()

        # 从请求中获取数据
        # 支持两种格式：JSON 和 FormData
        if request.content_type and 'multipart/form-data' in request.content_type:
            # FormData 格式（包含文件）
            message = request.data.get('message', '')
            files = request.FILES.getlist('files', [])
            active_mode = request.data.get('activeMode')
        else:
            # JSON 格式
            message = request.data.get('message', '') or request.data.get('content', '')
            active_mode = request.data.get('activeMode')
            
            # 处理JSON中的base64文件
            files_data = request.data.get('files', [])
            file_paths_info = []  # 存储文件路径和元信息
            
            if files_data:
                logger.info(f"接收到 {len(files_data)} 个base64文件")
                files = convert_base64_to_files(files_data)
                
                # 保存文件到项目media目录
                from django.conf import settings
                
                # 创建目录：media/agent_uploads/
                upload_dir = os.path.join(settings.MEDIA_ROOT, 'agent_uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                for file in files:
                    # 生成唯一文件名以避免冲突
                    import uuid
                    unique_id = str(uuid.uuid4())[:8]  # 使用UUID的前8位保持文件名不会太长
                    file_name = f"{unique_id}_{file.name}"
                    file_path = os.path.join(upload_dir, file_name)
                    
                    with open(file_path, 'wb') as f:
                        f.write(file.read())
                    file.seek(0)  # 重置文件指针以供后续使用
                    
                    # 构建文件信息（包含路径和元信息）
                    file_info = {
                        'path': file_path,
                        'name': file.name,
                        'size': file.size,
                        'type': getattr(file, 'content_type', 'unknown')
                    }
                    file_paths_info.append(file_info)
                    logger.info(f"保存文件到: {file_path}")
                
                # 调用对象存储保存函数（当前只是占位）
                if file_paths_info:
                    paths_only = [f['path'] for f in file_paths_info]
                    save_files_to_storage(paths_only)
                
                # 文件已保存到media/agent_uploads目录，后续处理可以使用这些文件
                logger.info(f"文件已保存到: {upload_dir}")

        if not message:
            return Response(
                {'error': '消息内容不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 调用服务处理消息
        result = chat_service.process_message(
            session=session,
            message=message,
            files=file_paths_info,  # 传递文件路径信息而不是文件对象
            active_mode=active_mode,
            user=request.user
        )

        if result['success']:
            # 返回任务创建成功的响应
            return Response({
                'task_id': result['task_id'],
                'session_id': result['session_id'],
                'assistant_message_id': result['assistant_message_id'],
                'status': 'processing',
                'message': '消息处理中，将通过回调更新状态'
            }, status=status.HTTP_202_ACCEPTED)
        else:
            return Response(
                {'error': result.get('error', '处理消息失败')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        # 软删除指定索引后的消息（标记为已删除，不物理删除）
        # 支持两种格式：index 或 afterIndex + isFirstMessage
        after_index = request.data.get('afterIndex')
        is_first_message = request.data.get('isFirstMessage', False)
        index = request.data.get('index')
        
        # 处理不同的参数格式
        if after_index is not None:
            if is_first_message and after_index == -1:
                # 软删除所有消息（标记为已删除）
                deleted_count = session.messages.filter(is_deleted=False).update(
                    is_deleted=True,
                    deleted_at=timezone.now()
                )
                return Response({
                    'deleted': 'all', 
                    'message': f'已标记 {deleted_count} 条消息为已删除',
                    'soft_delete': True
                })
            elif after_index >= 0:
                # 软删除 afterIndex 之后的消息；需先构造未删除消息的有序列表
                messages = list(session.messages.filter(is_deleted=False).order_by('created_at'))
                delete_from = after_index + 1
                deleted_count = 0
                if 0 <= delete_from <= len(messages):
                    for msg in messages[delete_from:]:
                        msg.is_deleted = True
                        msg.deleted_at = timezone.now()
                        msg.save()
                        deleted_count += 1
                    return Response({
                        'deleted': deleted_count,
                        'soft_delete': True
                    })
        elif index is not None:
            # 旧格式兼容：index 表示从该索引起（含）全部软删除
            messages = list(session.messages.filter(is_deleted=False).order_by('created_at'))
            deleted_count = 0
            if 0 <= index < len(messages):
                for msg in messages[index:]:
                    msg.is_deleted = True
                    msg.deleted_at = timezone.now()
                    msg.save()
                    deleted_count += 1
                return Response({
                    'deleted': deleted_count,
                    'soft_delete': True
                })
        
        return Response(
            {'error': 'Invalid index or afterIndex'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_incomplete_tasks_view(request):
    """
    检查用户的未完成任务并从AgentTask恢复数据

        用途：
            前端在页面刷新 / 恢复时调用，确保之前发起但未完成的异步任务状态被同步。

        实现流程：
            1. 选取最近 24 小时、带 task_id、未完成的 ChatMessage。
            2. 调用 AgentService.get_task_progress(task_id) 获取实时进度。
            3. 若已完成：
                 * 更新 content 为 final_conclusion（或状态对应默认文案）
                 * 过滤并保存 action_history -> task_steps (前端可视化步骤)
                 * 抽取 web_search 结果（带 citations）汇总到 final_web_search_results
                 * 标记 is_complete=True
                 * 尝试补全会话标题（多级策略：output_data.title -> plan 步骤 title -> final_content 第一行）
            4. 若未完成但有 action_history：保存阶段性步骤与部分输出。
            5. 汇总返回本次更新的消息条目。

        返回：
            updated: 成功更新条数
            updated_messages: 列表[{message_id, session_id, task_id, status}]
        注意：捕获单条异常不中断整体流程。
    """
    # 查找最近24小时内的未完成任务
    from datetime import timedelta
    from agentic.services import AgentService
    from .utils import filter_action_for_frontend
    
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    
    incomplete_messages = ChatMessage.objects.filter(
        session__user=request.user,
        is_complete=False,
        task_id__isnull=False,
        created_at__gte=twenty_four_hours_ago
    ).select_related('session')
    
    logger.info(f"[TASK_RECOVERY] 检查用户 {request.user.id} 的未完成任务，找到 {incomplete_messages.count()} 个")
    
    # 初始化 AgentService
    agent_service = AgentService()
    updated_count = 0
    updated_messages = []
    
    for message in incomplete_messages:
        try:
            # 获取任务进度
            progress = agent_service.get_task_progress(message.task_id)
            
            if progress is None:
                logger.warning(f"[TASK_RECOVERY] 任务 {message.task_id} 不存在")
                continue
            
            # 检查任务是否已完成
            if progress['is_completed']:
                logger.info(f"[TASK_RECOVERY] 任务 {message.task_id} 已完成，状态: {progress['status']}")
                
                # 获取所有的action_history
                raw_action_history = progress.get('action_history', [])
                
                # 处理嵌套格式的 action_history - 扁平化所有会话的历史
                all_action_history = []
                if raw_action_history and isinstance(raw_action_history[0], list):
                    # 嵌套格式：[[session1], [session2], ...] - 扁平化
                    for session_actions in raw_action_history:
                        all_action_history.extend(session_actions)
                    logger.debug(f"[TASK_RECOVERY] Task {message.task_id} - nested format, flattened {len(raw_action_history)} sessions to {len(all_action_history)} actions")
                else:
                    # 扁平格式（向后兼容）
                    all_action_history = raw_action_history
                    logger.debug(f"[TASK_RECOVERY] Task {message.task_id} - flat format, {len(all_action_history)} actions")
                
                # 获取最终内容
                output_data = progress.get('output_data', {})
                final_content = output_data.get('final_conclusion', '任务完成' if progress['status'] == 'COMPLETED' else '任务失败')
                
                # 只在消息内容为空时更新，避免覆盖已有的详细内容
                if not message.content:
                    message.content = final_content
                
                # 过滤并保存task_steps - 只保存当前任务的 actions
                current_task_actions = []  # 初始化为空列表，避免 UnboundLocalError
                if all_action_history:
                    # 找到最后一个 final_answer 的位置
                    last_final_answer_index = -1
                    for i in range(len(all_action_history) - 1, -1, -1):
                        if all_action_history[i].get('type') == 'final_answer':
                            last_final_answer_index = i
                            break
                    
                    # 如果找到了 final_answer，从它之前最近的一个 final_answer 之后开始收集
                    if last_final_answer_index >= 0:
                        # 找到倒数第二个 final_answer 的位置
                        second_last_final_answer_index = -1
                        for i in range(last_final_answer_index - 1, -1, -1):
                            if all_action_history[i].get('type') == 'final_answer':
                                second_last_final_answer_index = i
                                break
                        
                        # 从倒数第二个 final_answer 之后开始收集，直到最后
                        start_index = second_last_final_answer_index + 1 if second_last_final_answer_index >= 0 else 0
                        current_task_actions = all_action_history[start_index:]
                    else:
                        # 没有 final_answer，说明任务还在进行中，保留所有 actions
                        current_task_actions = all_action_history
                    
                    filtered_steps = [f for f in (filter_action_for_frontend(step) for step in current_task_actions) if f is not None]
                    message.save_task_steps(filtered_steps)
                
                # 提取web搜索结果（如果有）- 只从当前任务的 actions 中提取
                web_search_results = []
                for step in current_task_actions:
                    if step.get('type') == 'tool_output':
                        tool_name = step.get('tool_name') or step.get('data', {}).get('tool_name')
                        if tool_name == 'web_search':
                            data = step.get('data', {})
                            raw_data = data.get('raw_data', {})
                            if raw_data and 'citations' in raw_data:
                                query = ''
                                # 从当前任务的 actions 中查找 query
                                for prev_step in current_task_actions:
                                    if (prev_step.get('type') == 'plan' and 
                                        prev_step.get('data', {}).get('tool_name') == 'web_search'):
                                        query = prev_step.get('data', {}).get('tool_input', {}).get('query', '')
                                        break
                                
                                web_search_results.append({
                                    'query': query,
                                    'primary_result': data.get('primary_result', ''),
                                    'citations': raw_data['citations']
                                })
                
                if web_search_results:
                    message.final_web_search_results = web_search_results
                
                # 标记为完成并保存
                message.is_complete = True
                message.save()
                
                updated_count += 1
                updated_messages.append({
                    'message_id': message.id,
                    'session_id': message.session_id,
                    'task_id': message.task_id,
                    'status': progress['status']
                })
                
                # 更新会话标题（如果需要）
                if progress['status'] == 'COMPLETED' and not message.session.title:
                    title = None
                    if 'title' in output_data:
                        title = output_data['title']
                    
                    if not title:
                        # 从当前任务的 actions 中查找 title（反向查找最新的）
                        for event in reversed(current_task_actions):
                            if event.get('type') == 'plan' and event.get('data', {}).get('title'):
                                title = event['data']['title']
                                break
                    
                    if not title and final_content:
                        lines = final_content.split('\n')
                        if lines and len(lines[0]) < 100:
                            title = lines[0].strip()
                    
                    if title:
                        message.session.title = title
                        message.session.save()
                        logger.info(f"[TASK_RECOVERY] 设置会话标题: {title}")
            
            elif progress.get('action_history'):
                # 检查任务是否真的还在运行（通过 updated_at 判断）
                from agentic.models import AgentTask
                from datetime import timedelta
                
                try:
                    task = AgentTask.objects.get(task_id=message.task_id)
                    time_since_update = timezone.now() - task.updated_at
                    
                    # 如果任务超过10分钟没有更新，认为任务已经死掉
                    if time_since_update > timedelta(minutes=10):
                        logger.warning(f"[TASK_RECOVERY] 任务 {message.task_id} 超过10分钟未更新，标记为失败")
                        
                        # 标记任务为失败
                        task.status = AgentTask.TaskStatus.FAILED
                        task.output_data['error'] = 'Task timeout - no updates for over 10 minutes'
                        task.save()
                        
                        # 更新消息（只在内容为空时）
                        if not message.content:
                            message.content = '任务执行超时，可能由于某种意外导致错误中断。请重试。'
                        message.is_complete = True
                        message.save()
                        
                        updated_count += 1
                        updated_messages.append({
                            'message_id': message.id,
                            'session_id': message.session_id,
                            'task_id': message.task_id,
                            'status': 'TIMEOUT'
                        })
                        continue
                        
                except AgentTask.DoesNotExist:
                    logger.error(f"[TASK_RECOVERY] 任务 {message.task_id} 不存在于数据库")
                    continue
                
                # 任务未完成，但有部分进度，也保存（增量同步）
                logger.info(f"[TASK_RECOVERY] 任务 {message.task_id} 仍在运行，保存部分进度")
                
                raw_action_history = progress.get('action_history', [])
                
                # 处理嵌套格式的 action_history - 扁平化所有会话的历史
                all_action_history = []
                if raw_action_history and isinstance(raw_action_history[0], list):
                    # 嵌套格式：[[session1], [session2], ...] - 扁平化
                    for session_actions in raw_action_history:
                        all_action_history.extend(session_actions)
                    logger.debug(f"[TASK_RECOVERY] Task {message.task_id} - nested format, flattened {len(raw_action_history)} sessions to {len(all_action_history)} actions")
                else:
                    # 扁平格式（向后兼容）
                    all_action_history = raw_action_history
                    logger.debug(f"[TASK_RECOVERY] Task {message.task_id} - flat format, {len(all_action_history)} actions")
                
                if all_action_history:
                    # 找到最后一个 final_answer 的位置（如果有的话，说明是历史数据）
                    last_final_answer_index = -1
                    for i in range(len(all_action_history) - 1, -1, -1):
                        if all_action_history[i].get('type') == 'final_answer':
                            last_final_answer_index = i
                            break
                    
                    # 任务还在运行，不应该有 final_answer
                    # 如果有 final_answer，从它之后开始收集（这些是当前任务的 actions）
                    current_task_actions = []
                    if last_final_answer_index >= 0:
                        # 有历史 final_answer，从它之后开始收集
                        current_task_actions = all_action_history[last_final_answer_index + 1:]
                    else:
                        # 没有历史 final_answer，所有都是当前任务的
                        current_task_actions = all_action_history
                    
                    filtered_steps = [f for f in (filter_action_for_frontend(step) for step in current_task_actions) if f is not None]
                    message.save_task_steps(filtered_steps)
                    
                    # 如果有部分输出，也保存（只在内容为空时）
                    output_data = progress.get('output_data', {})
                    partial_content = output_data.get('final_conclusion', '')
                    if partial_content and not message.content:
                        message.content = partial_content
                    
                    message.save()
                    
                    updated_count += 1
                    updated_messages.append({
                        'message_id': message.id,
                        'session_id': message.session_id,
                        'task_id': message.task_id,
                        'status': 'IN_PROGRESS'
                    })
                    
        except Exception as e:
            logger.error(f"[TASK_RECOVERY] 恢复任务 {message.task_id} 失败: {str(e)}", exc_info=True)
    
    return Response({
        'updated': updated_count,
        'message': f'Checked {incomplete_messages.count()} incomplete tasks, updated {updated_count}',
        'updated_messages': updated_messages
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_task_status_view(request, task_id):
    """
    检查指定任务的运行状态

        参数：task_id (路径参数)
        返回：
            exists: bool 是否存在该任务（若 AgentService 返回 None 视为不存在）
            status: 任务状态（枚举，如 COMPLETED / RUNNING / FAILED / NOT_FOUND / ERROR）
            is_completed: 是否已完成
            has_progress: 是否已有 action_history（用于前端决定是否展示“进度”按钮）
        错误处理：
            捕获异常返回 500，并附带 error 字段。
    """
    from agentic.services import AgentService
    
    try:
        agent_service = AgentService()
        progress = agent_service.get_task_progress(task_id)
        
        if progress is None:
            return Response({
                'exists': False,
                'status': 'NOT_FOUND'
            })
        
        return Response({
            'exists': True,
            'status': progress['status'],
            'is_completed': progress['is_completed'],
            'has_progress': bool(progress.get('action_history'))
        })
        
    except Exception as e:
        logger.error(f"检查任务状态失败: task_id={task_id}, error={str(e)}")
        return Response({
            'exists': False,
            'status': 'ERROR',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_by_conversation_id_view(request, conversation_id):
    """
    根据 AI 会话 ID 获取会话

    用于：前端仅持有 ai_conversation_id (跨端、埋点或长链路引用) 时快速定位实际 ChatSession。
    安全：仍需校验归属用户，避免他人枚举 ID 读取数据。
    """
    session = get_object_or_404(
        ChatSession,
        ai_conversation_id=conversation_id,
        user=request.user
    )
    
    serializer = ChatSessionSerializer(session)
    return Response(serializer.data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def session_snapshot_view(request, session_id):
    """
    GET: 创建会话快照
    POST: 从快照恢复会话

        GET:
            - 调用 create_session_snapshot(session_id) 生成结构化快照（含压缩 task_steps）。
            - 返回 { success, snapshot }

        POST:
            - 传入 snapshot(JSON) 字段；可选 clear_existing=True 先清空旧消息。
            - 为每条消息解压 task_steps_compressed -> task_steps 并重建 ChatMessage。
            - 不涉及权限转移，snapshot_id 必须匹配当前会话，防止误恢复入他人会话。

        注意：
            * 当前实现仅示例，未做幂等 / 版本校验 / 冲突检测。
            * 可扩展：校验 snapshot 生成时间、版本号、消息散列等。
    """
    session = get_object_or_404(
        ChatSession,
        id=session_id,
        user=request.user
    )
    
    if request.method == 'GET':
        # 创建会话快照
        snapshot = create_session_snapshot(str(session.id))
        if snapshot:
            return Response({
                'success': True,
                'snapshot': snapshot
            })
        else:
            return Response(
                {'error': 'Failed to create snapshot'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        # 从快照恢复（这里仅提供示例，实际恢复逻辑需要根据需求实现）
        snapshot_data = request.data.get('snapshot')
        if not snapshot_data:
            return Response(
                {'error': 'Snapshot data is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 验证快照数据
            if snapshot_data.get('session_id') != str(session.id):
                return Response(
                    {'error': 'Snapshot does not match session'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 恢复消息（可选：清空现有消息）
            if request.data.get('clear_existing', False):
                session.messages.all().delete()
            
            # 恢复压缩的消息
            for msg_data in snapshot_data.get('messages', []):  # 逐条恢复消息
                # 解压 task_steps
                task_steps = None
                if 'task_steps_compressed' in msg_data:
                    task_steps = decompress_data(msg_data['task_steps_compressed'])
                
                ChatMessage.objects.create(
                    session=session,
                    role=msg_data['role'],
                    content=msg_data['content'],
                    task_id=msg_data.get('task_id'),
                    files_info=msg_data.get('files_info'),
                    task_steps=task_steps
                )
            
            return Response({
                'success': True,
                'message': f'Restored {len(snapshot_data.get("messages", []))} messages'
            })
            
        except Exception as e:
            # 任何异常都返回统一错误，避免泄露内部实现细节
            logger.error(f"Failed to restore snapshot: {e}")
            return Response(
                {'error': 'Failed to restore snapshot'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponseForbidden

@csrf_exempt
def task_stream_view(request, task_id):
    """
    SSE流式接口，用于实时获取任务进度
    
    GET /tasks/<task_id>/stream/
    Accept: text/event-stream
    
    返回：SSE事件流，包含任务执行的实时进度
    
    事件类型：
    - plan: 计划步骤
    - tool_output: 工具输出
    - reflection: 反思结果
    - final_answer: 最终答案
    - error: 错误信息
    - timeout: 超时
    """
    from django.http import StreamingHttpResponse, JsonResponse
    import json
    import time
    from agentic.services import AgentService
    from .utils import filter_action_for_frontend
    
    # 手动进行认证检查
    permission = IsAuthenticated()
    if not permission.has_permission(request, None):
        return HttpResponseForbidden('Authentication credentials were not provided.')
    
    # 检查是否是重连请求
    is_reconnect = request.GET.get('reconnect') == 'true'
    logger.debug(f"[SSE] Task {task_id} - is_reconnect: {is_reconnect}")
    
    def event_stream():
        """生成SSE事件流"""
        agent_service = AgentService()
        last_action_index = 0
        max_attempts = 150  # 5分钟超时（2秒 * 150）
        attempt = 0
        all_action_history = []
        
        logger.info(f"[SSE] Starting stream for task {task_id}, user: {request.user.username}, reconnect: {is_reconnect}")
        
        # 不再发送connection_established事件，直接开始监听任务进度
        while attempt < max_attempts:
            attempt += 1
            
            try:
                # 获取任务进度
                progress = agent_service.get_task_progress(task_id, last_action_index)
                
                if progress is None:
                    # 任务不存在
                    logger.warning(f"[SSE] Task {task_id} not found")
                    error_data = {'type': 'error', 'message': f'Task {task_id} not found'}
                    logger.info(f"[SSE] Sending data: {json.dumps(error_data, ensure_ascii=False)}")
                    yield f"data: {json.dumps(error_data)}\n\n"
                    break
                
                task_status = progress['status']
                # 打印 task_status
                logger.debug(f"[SSE] Task {task_id} status: {task_status}")
                
                # 处理嵌套的 action_history 格式
                raw_action_history = progress.get('action_history', [])
                
                # 如果是嵌套格式，取最后一个子列表（当前会话）
                if raw_action_history and isinstance(raw_action_history[0], list):
                    # 嵌套格式：[[session1], [session2], ...]
                    current_session_actions = raw_action_history[-1] if raw_action_history else []
                    new_actions = current_session_actions
                    logger.debug(f"[SSE] Task {task_id} - nested format, current session has {len(current_session_actions)} actions")
                else:
                    # 扁平格式（向后兼容）
                    new_actions = raw_action_history
                    logger.debug(f"[SSE] Task {task_id} - flat format, has {len(new_actions)} actions")
                
                # 打印 new_actions 数量
                logger.debug(f"[SSE] Task {task_id} has {len(new_actions)} new actions")

                # 发送新的动作事件
                if new_actions:
                    logger.debug(f"[SSE] Task {task_id} has {len(new_actions)} new actions from index {last_action_index}")
                    
                    # 处理历史数据（无论是重连还是新消息，都需要过滤历史的final_answer）
                    skip_until_index = -1
                    if last_action_index == 0:
                        # 第一次获取actions时，可能包含从历史任务合并来的action_history
                        # 找到所有的final_answer位置
                        final_answer_indices = []
                        for i in range(len(new_actions)):
                            if new_actions[i].get('type') == 'final_answer':
                                final_answer_indices.append(i)
                        
                        # 如果有多个final_answer，说明包含历史任务的final_answer
                        # 只保留最后一个final_answer之后的actions（当前任务的actions）
                        if len(final_answer_indices) > 1:
                            # 跳过除最后一个之外的所有final_answer及其之前的内容
                            skip_until_index = final_answer_indices[-2]  # 倒数第二个final_answer的位置
                            logger.info(f"[SSE] Found {len(final_answer_indices)} final_answers, skipping historical ones up to index {skip_until_index}")
                        elif is_reconnect and len(final_answer_indices) == 1:
                            # 重连场景且只有一个final_answer，可能是历史的，需要跳过
                            skip_until_index = final_answer_indices[0]
                            logger.info(f"[SSE] Reconnect: skipping single historical final_answer at index {skip_until_index}")
                        else:
                            logger.debug(f"[SSE] New message with {len(final_answer_indices)} final_answer(s), sending all actions")
                    
                    for i, action in enumerate(new_actions):
                        all_action_history.append(action)
                        
                        # 跳过历史数据（包括历史的 final_answer）
                        if skip_until_index >= 0 and i <= skip_until_index:
                            logger.debug(f"[SSE] Skipping historical action at index {i}: {action.get('type')}")
                            continue
                        
                        # 过滤并发送事件
                        filtered_action = filter_action_for_frontend(action)
                        if filtered_action is not None:
                            logger.info(f"[SSE] Sending data: {json.dumps(filtered_action, ensure_ascii=False)}")
                            yield f"data: {json.dumps(filtered_action)}\n\n"
                    
                    last_action_index = progress['last_action_index']
                    # 打印此时的 last_action_index
                    logger.debug(f"任务：{task_id} [SSE]\nUpdated last_action_index to {last_action_index}")
                    logger.debug(f"\n\n====== 任务 {task_id} 第 {attempt} 次循环结束 ======\n\n")
                
                # 检查任务是否完成
                if task_status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    logger.info(f"[SSE] Task {task_id} finished with status: {task_status}")
                    
                    # 获取最终结果
                    try:
                        # 尝试获取关联的消息
                        message = ChatMessage.objects.filter(task_id=task_id).first()
                        
                        if message:
                            # 从最后一个 action 中提取内容（任务已完成，最后一个应该是 final_answer）
                            final_answer_content = None
                            error_type = None
                            error_message = None

                            if all_action_history:
                                last_action = all_action_history[-1]

                                if last_action.get('type') == 'final_answer':
                                    # 正常情况：最后一个是 final_answer
                                    final_answer_content = last_action.get('data', {}).get('final_answer')
                                else:
                                    # 异常情况：最后一个不是 final_answer
                                    logger.warning(f"[SSE] Task {task_id} 完成但最后一个 action 不是 final_answer，而是: {last_action.get('type')}")

                                    # 根据任务状态生成文案
                                    if task_status == 'FAILED':
                                        error_type = 'task_failed_without_answer'
                                        error_message = '任务执行失败，未能生成最终答案。请重试或调整您的问题。'
                                    elif task_status == 'CANCELLED':
                                        error_type = 'task_cancelled'
                                        error_message = '任务已被取消。'
                                    else:  # COMPLETED 但没有 final_answer
                                        error_type = 'completed_without_answer'
                                        error_message = '任务已完成，但未生成标准格式的答案。'
                                        # 尝试从 output_data 获取内容
                                        try:
                                            progress = agent_service.get_task_progress(task_id)
                                            if progress and progress.get('output_data'):
                                                output_data = progress['output_data']
                                                if output_data.get('final_conclusion'):
                                                    final_answer_content = output_data['final_conclusion']
                                                    error_type = None  # 找到了内容，清除错误标记
                                                    error_message = None
                                        except Exception as e:
                                            logger.error(f"[SSE] 尝试获取 output_data 失败: {e}")
                            else:
                                # 没有 action_history
                                logger.error(f"[SSE] Task {task_id} 完成但没有 action_history")
                                error_type = 'no_action_history'
                                error_message = '任务记录异常，无法获取执行过程。'

                            # 更新消息内容
                            if final_answer_content and not message.content:
                                message.content = final_answer_content
                                message.save()
                            elif error_message and not message.content:
                                # 使用错误文案作为内容
                                message.content = error_message
                                message.save()

                                # 发送异常事件给前端
                                error_event = {
                                    'type': 'task_abnormal',
                                    'data': {
                                        'error_type': error_type,
                                        'message': error_message,
                                        'task_status': task_status
                                    }
                                }
                                logger.info(f"[SSE] Sending data: {json.dumps(error_event, ensure_ascii=False)}")
                                yield f"data: {json.dumps(error_event)}\n\n"
                            
                            # 只保存当前任务产生的 actions，过滤掉历史任务的 actions
                            # 找到最后一个 final_answer 的位置
                            last_final_answer_index = -1
                            for i in range(len(all_action_history) - 1, -1, -1):
                                if all_action_history[i].get('type') == 'final_answer':
                                    last_final_answer_index = i
                                    break
                            
                            # 如果找到了 final_answer，从它之前最近的一个 final_answer 之后开始收集
                            current_task_actions = []
                            if last_final_answer_index >= 0:
                                # 找到倒数第二个 final_answer 的位置
                                second_last_final_answer_index = -1
                                for i in range(last_final_answer_index - 1, -1, -1):
                                    if all_action_history[i].get('type') == 'final_answer':
                                        second_last_final_answer_index = i
                                        break
                                
                                # 从倒数第二个 final_answer 之后开始收集，直到最后
                                start_index = second_last_final_answer_index + 1 if second_last_final_answer_index >= 0 else 0
                                current_task_actions = all_action_history[start_index:]
                            else:
                                # 没有 final_answer，所有都是当前任务的
                                current_task_actions = all_action_history
                            
                            # 过滤当前任务的步骤
                            filtered_steps = [f for f in (filter_action_for_frontend(s) for s in current_task_actions) if f is not None]
                            # 保存过滤后的步骤到数据库
                            message.save_task_steps(filtered_steps)
                        
                        # 发送 END 事件表示任务完成，不管是否找到消息
                        end_event = {
                            'type': 'END',
                            'data': None,
                            'status': task_status
                        }
                        logger.info(f"[SSE] Sending data: {json.dumps(end_event, ensure_ascii=False)}")
                        yield f"data: {json.dumps(end_event)}\n\n"
                            
                    except Exception as e:
                        logger.error(f"[SSE] Error getting final message for task {task_id}: {e}")
                        error_data = {'type': 'error', 'message': 'Failed to get final message'}
                        logger.info(f"[SSE] Sending data: {json.dumps(error_data, ensure_ascii=False)}")
                        yield f"data: {json.dumps(error_data)}\n\n"
                    
                    break
                
                # 等待下次轮询
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"[SSE] Error in stream for task {task_id}: {e}", exc_info=True)
                error_data = {'type': 'error', 'message': str(e)}
                logger.info(f"[SSE] Sending data: {json.dumps(error_data, ensure_ascii=False)}")
                yield f"data: {json.dumps(error_data)}\n\n"
                break
        
        if attempt >= max_attempts:
            # 超时
            logger.warning(f"[SSE] Stream timeout for task {task_id}")
            timeout_data = {'type': 'timeout', 'message': '任务监控超时，任务可能仍在后台执行'}
            logger.info(f"[SSE] Sending data: {json.dumps(timeout_data, ensure_ascii=False)}")
            yield f"data: {json.dumps(timeout_data)}\n\n"
    
    # 创建流式响应
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # 禁用nginx缓冲
    # 注意：不要设置Connection头部，它是hop-by-hop头部，在WSGI中不被允许
    
    return response