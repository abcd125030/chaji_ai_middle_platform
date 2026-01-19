"""
聊天模块工具函数
"""
import json
import gzip
import base64
from typing import List, Dict, Any
from datetime import datetime


def filter_action_for_frontend(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    过滤 action_history 中的数据，只保留前端需要的字段
    严格按照前端实际使用的字段进行过滤
    
    参数:
        action: 原始的 action 数据
        
    返回:
        过滤后的 action 数据，如果返回 None 则不保存到 task_steps
    """
    action_type = action.get('type', '')
    
    # 过滤掉不需要的类型
    if action_type in ['task_classification', 'reflection']:
        return None
    
    # 基础字段（所有类型都需要）
    filtered = {
        'type': action_type
    }
    
    if action_type == 'plan':
        # 前端使用: thought 和 tool_name
        data = action.get('data', {})
        filtered['data'] = {
            'thought': data.get('output', '')  # planner 节点实际存储的是 output 字段
        }
        # 前端 TaskStepsDisplay 第45行需要 tool_name
        if 'tool_name' in data:
            filtered['data']['tool_name'] = data['tool_name']
            
    elif action_type == 'tool_output':
        # 前端使用: tool_name（显示工具名）
        tool_name = action.get('tool_name') or action.get('data', {}).get('tool_name', '')
        filtered['data'] = {
            'tool_name': tool_name
        }
        # 为了兼容性，也在顶层保留 tool_name
        if tool_name:
            filtered['tool_name'] = tool_name
        
        # 对于 WebSearchTool，只保留 citations 用于显示链接数
        if tool_name in ['WebSearchTool', 'web_search']:
            data = action.get('data', {})
            
            # 尝试从多个位置提取 citations（前端 TaskStepsDisplay 使用）
            citations = None
            
            # 新格式: raw_data.citations
            if 'raw_data' in data:
                raw_data = data['raw_data']
                if isinstance(raw_data, dict) and 'citations' in raw_data:
                    citations = raw_data['citations']
                    filtered['data']['raw_data'] = {
                        'citations': citations
                    }
            
            # 兼容旧格式: primary_result.citations
            if not citations and 'primary_result' in data:
                primary_result = data['primary_result']
                if isinstance(primary_result, dict) and 'citations' in primary_result:
                    citations = primary_result['citations']
                    filtered['data']['primary_result'] = {
                        'citations': citations
                    }
            
            # 兼容旧格式: result.citations  
            if not citations and 'result' in data:
                result = data['result']
                if isinstance(result, dict) and 'citations' in result:
                    citations = result['citations']
                    filtered['data']['result'] = {
                        'citations': citations
                    }
        
    elif action_type == 'final_answer':
        # 前端使用: final_answer 作为消息内容
        data = action.get('data', {})
        filtered['data'] = {}
        
        # 使用 output 字段（与 processor.py 保持一致）
        if 'output' in data:
            filtered['data']['output'] = data['output']
        
        # 保留标题字段
        if 'title' in data:
            filtered['data']['title'] = data['title']
    
    elif action_type == 'error':
        # 错误类型：保留错误信息
        data = action.get('data', {})
        filtered['data'] = {}
        
        # 保留错误相关字段
        if 'error_type' in data:
            filtered['data']['error_type'] = data['error_type']
        if 'message' in data:
            filtered['data']['message'] = data['message']
        if 'details' in data:
            filtered['data']['details'] = data['details']
        if 'error' in data:
            filtered['data']['error'] = data['error']
    
    elif action_type in ['todo_created', 'todo_updated', 'todo_update']:
        # todo_update 事件：前端需要完整的 todo 数据
        data = action.get('data', {})
        filtered['data'] = {}
        
        # 保留前端需要的字段
        if 'total_count' in data:
            filtered['data']['total_count'] = data['total_count']
        if 'completed_count' in data:
            filtered['data']['completed_count'] = data['completed_count']
        if 'todo_list' in data:
            # 保留完整的 todo_list，前端需要显示
            filtered['data']['todo_list'] = data['todo_list']
        if 'todo_count' in data:
            filtered['data']['todo_count'] = data['todo_count']
        if 'todos' in data:
            filtered['data']['todos'] = data['todos']
        if 'operation' in data:
            filtered['data']['operation'] = data['operation']
        if 'task_ids' in data:
            filtered['data']['task_ids'] = data['task_ids']
    
    else:
        # 其他未知类型，保留最小数据
        filtered['data'] = {}
    
    return filtered



def validate_task_step(step: Dict[str, Any]) -> bool:
    """
    验证单个 task_step 的数据完整性
    
    参数:
        step: 要验证的步骤数据
        
    返回:
        是否有效
    """
    if not isinstance(step, dict):
        return False
    
    # 必须有 type 字段
    if 'type' not in step:
        return False
    
    step_type = step.get('type')
    
    # 根据类型验证必要字段
    if step_type == 'plan':
        return 'data' in step and 'thought' in step.get('data', {})
    elif step_type == 'tool_output':
        # tool_name 可能在顶层或 data 中
        return ('data' in step and 'tool_name' in step.get('data', {})) or 'tool_name' in step
    elif step_type == 'final_answer':
        # 使用 output 字段
        return 'data' in step and 'output' in step.get('data', {})
    elif step_type in ['todo_created', 'todo_updated', 'todo_update']:
        # TODO 类型至少要有 data 字段
        return 'data' in step
    
    # 未知类型，至少要有 data 字段
    return 'data' in step


def compress_data(data: Any) -> str:
    """
    压缩数据并返回 base64 编码的字符串
    
    参数:
        data: 要压缩的数据（通常是 dict 或 list）
        
    返回:
        base64 编码的压缩数据
    """
    json_str = json.dumps(data, ensure_ascii=False)
    compressed = gzip.compress(json_str.encode('utf-8'))
    return base64.b64encode(compressed).decode('ascii')


def decompress_data(compressed_str: str) -> Any:
    """
    解压缩 base64 编码的数据
    
    参数:
        compressed_str: base64 编码的压缩数据
        
    返回:
        原始数据
    """
    compressed = base64.b64decode(compressed_str.encode('ascii'))
    json_str = gzip.decompress(compressed).decode('utf-8')
    return json.loads(json_str)


def prepare_file_info_for_storage(files_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    准备文件信息用于存储，添加预览信息
    
    参数:
        files_info: 原始文件信息列表
        
    返回:
        增强后的文件信息列表
    """
    enhanced_files = []
    
    for file_info in files_info:
        enhanced = file_info.copy()
        
        # 根据文件类型添加预览信息
        file_type = file_info.get('type', '')
        
        if file_type in ['image/jpeg', 'image/png', 'image/webp']:
            # 图片类型：可以考虑生成缩略图
            enhanced['preview_type'] = 'image'
            # 这里可以添加缩略图生成逻辑
            
        elif file_type in ['text/plain', 'text/markdown', 'application/json']:
            # 文本类型：保存前几行作为预览
            if 'content' in file_info:
                content = file_info['content']
                if isinstance(content, str):
                    lines = content.split('\n')
                    preview = '\n'.join(lines[:10])
                    if len(lines) > 10:
                        preview += f'\n... (还有 {len(lines) - 10} 行)'
                    enhanced['preview'] = preview
                    enhanced['preview_type'] = 'text'
        
        elif file_type == 'application/pdf':
            # PDF：记录页数等元信息
            enhanced['preview_type'] = 'pdf'
            # 这里可以添加 PDF 元信息提取逻辑
        
        enhanced_files.append(enhanced)
    
    return enhanced_files


def create_session_snapshot(session_id: str) -> Dict[str, Any]:
    """
    创建会话快照，用于断点恢复
    
    参数:
        session_id: 会话 ID
        
    返回:
        会话快照数据
    """
    from .models import ChatSession, ChatMessage
    
    try:
        session = ChatSession.objects.get(id=session_id)
        
        # 获取最近的消息（最多保存最近 50 条）
        recent_messages = session.messages.order_by('-created_at')[:50]
        
        snapshot = {
            'session_id': str(session.id),
            'title': session.title,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'last_interacted_at': session.last_interacted_at.isoformat() if session.last_interacted_at else None,
            'messages': [],
            'snapshot_time': datetime.now().isoformat(),
        }
        
        for msg in reversed(recent_messages):
            msg_data = {
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
            }
            
            # 只保存必要的元数据
            if msg.task_id:
                msg_data['task_id'] = msg.task_id
            
            if msg.files_info:
                # 简化文件信息，只保存元数据
                msg_data['files_info'] = [
                    {
                        'name': f.get('name'),
                        'type': f.get('type'),
                        'size': f.get('size'),
                    }
                    for f in msg.files_info
                    if isinstance(f, dict)
                ]
            
            # 对 task_steps 进行压缩（数据已经是过滤后的，直接压缩）
            if msg.task_steps:
                msg_data['task_steps_compressed'] = compress_data(msg.task_steps)
            
            snapshot['messages'].append(msg_data)
        
        return snapshot
        
    except ChatSession.DoesNotExist:
        return None