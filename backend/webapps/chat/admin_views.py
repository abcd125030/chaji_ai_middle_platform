from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from functools import wraps
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from .models import ChatSession, ChatMessage
from .serializers import ChatMessageSerializer, ChatSessionSerializer
import logging

logger = logging.getLogger(__name__)  # 使用模块名作为 logger 名称
User = get_user_model()


def admin_required(view_func):
    """
    装饰器：检查用户是否为管理员或工作人员
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({
                'status': 'error',
                'message': '需要登录',
                'code': 401
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({
                'status': 'error',
                'message': '需要管理员权限',
                'code': 403
            }, status=status.HTTP_403_FORBIDDEN)
        
        return view_func(request, *args, **kwargs)
    return wrapper


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_statistics_view(request):
    """
    获取管理后台统计数据
    
    返回:
    - user_count: 用户总数
    - chat_message_count: 聊天消息总数
    - chat_session_count: 会话总数
    """
    try:
        stats = {
            'user_count': User.objects.count(),
            'chat_message_count': ChatMessage.objects.count(),
            'chat_session_count': ChatSession.objects.count(),
        }
        
        return Response({
            'status': 'success',
            'data': stats,
            'message': '统计数据获取成功',
            'code': 200
        })
    except Exception as e:
        logger.error(f"获取统计数据失败: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'获取统计数据失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_users_view(request):
    """
    获取用户列表（管理后台）
    
    查询参数:
    - page: 页码（默认1）
    - page_size: 每页数量（默认10）
    - search: 搜索关键词（可选）
    """
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        search = request.GET.get('search', '')
        
        # 构建查询
        queryset = User.objects.all()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        # 排序
        queryset = queryset.order_by('-date_joined')
        
        # 分页
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # 构建用户数据
        users_data = []
        for user in page_obj:
            users_data.append({
                'id': user.id,
                'user_ai_id': str(user.id),  # 兼容前端的user_ai_id字段
                'username': user.username,
                'display_name': user.username,  # 兼容前端的display_name字段
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined.isoformat() if user.date_joined else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.date_joined.isoformat() if user.date_joined else None,
                'updated_at': user.last_login.isoformat() if user.last_login else None,
            })
        
        return Response({
            'status': 'success',
            'data': {
                'users': users_data,
                'total': paginator.count,
                'page': page,
                'page_size': page_size,
                'page_count': paginator.num_pages
            },
            'message': '用户列表获取成功',
            'code': 200
        })
    except Exception as e:
        logger.error(f"获取用户列表失败: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'获取用户列表失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_chat_messages_view(request):
    """
    获取聊天消息列表（管理后台）
    
    查询参数:
    - page: 页码（默认1）
    - page_size: 每页数量（默认15）
    - session_id: 会话ID（可选）
    - role: 角色筛选（可选）
    """
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 15))
        session_id = request.GET.get('session_id')
        role = request.GET.get('role')
        
        # 构建查询
        queryset = ChatMessage.objects.select_related('session', 'session__user')
        
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        if role:
            queryset = queryset.filter(role=role)
        
        # 排序
        queryset = queryset.order_by('-created_at')
        
        # 分页
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # 构建消息数据
        messages_data = []
        for message in page_obj:
            messages_data.append({
                'id': message.id,
                'session_id': str(message.session.id),
                'session_title': message.session.title,
                'user_id': message.session.user.id,
                'username': message.session.user.username,
                'role': message.role,
                'content': message.content,
                'task_id': message.task_id,
                'is_complete': message.is_complete,
                'created_at': message.created_at.isoformat() if message.created_at else None,
            })
        
        return Response({
            'status': 'success',
            'data': {
                'messages': messages_data,
                'total': paginator.count,
                'page': page,
                'page_size': page_size,
                'page_count': paginator.num_pages
            },
            'message': '消息列表获取成功',
            'code': 200
        })
    except Exception as e:
        logger.error(f"获取消息列表失败: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'获取消息列表失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_chat_sessions_view(request):
    """
    获取会话列表（管理后台）
    
    查询参数:
    - page: 页码（默认1）
    - page_size: 每页数量（默认10）
    - user_id: 用户ID（可选）
    """
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        user_id = request.GET.get('user_id')
        
        # 构建查询
        queryset = ChatSession.objects.select_related('user').annotate(
            message_count=Count('messages')
        )
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # 排序
        queryset = queryset.order_by('-last_interacted_at')
        
        # 分页
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # 构建会话数据
        sessions_data = []
        for session in page_obj:
            sessions_data.append({
                'id': str(session.id),
                'user_id': session.user.id,
                'username': session.user.username,
                'ai_conversation_id': session.ai_conversation_id,
                'title': session.title,
                'last_message_preview': session.last_message_preview,
                'message_count': session.message_count,
                'is_pinned': session.is_pinned,
                'is_archived': session.is_archived,
                'tags': session.tags,
                'last_interacted_at': session.last_interacted_at.isoformat() if session.last_interacted_at else None,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'updated_at': session.updated_at.isoformat() if session.updated_at else None,
            })
        
        return Response({
            'status': 'success',
            'data': {
                'sessions': sessions_data,
                'total': paginator.count,
                'page': page,
                'page_size': page_size,
                'page_count': paginator.num_pages
            },
            'message': '会话列表获取成功',
            'code': 200
        })
    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'获取会话列表失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)