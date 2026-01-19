from django.urls import path
from . import views
from . import admin_views

app_name = 'chat'

urlpatterns = [
    # 会话管理
    path('sessions/', views.sessions_view, name='sessions'),
    path('sessions/<uuid:session_id>/', views.session_detail_view, name='session-detail'),
    path('sessions/<uuid:session_id>/messages/', views.messages_view, name='messages'),
    path('sessions/by-conversation/<str:conversation_id>/', views.session_by_conversation_id_view, name='session-by-conversation'),
    
    # 任务检查
    path('check-incomplete-tasks/', views.check_incomplete_tasks_view, name='check-incomplete-tasks'),
    path('tasks/<str:task_id>/status/', views.check_task_status_view, name='task-status'),
    path('tasks/<str:task_id>/stream/', views.task_stream_view, name='task-stream'),  # SSE流式接口
    
    # 会话快照
    path('sessions/<uuid:session_id>/snapshot/', views.session_snapshot_view, name='session-snapshot'),
    
    # Admin管理接口
    path('admin/statistics/', admin_views.admin_statistics_view, name='admin-statistics'),
    path('admin/users/', admin_views.admin_users_view, name='admin-users'),
    path('admin/messages/', admin_views.admin_chat_messages_view, name='admin-messages'),
    path('admin/sessions/', admin_views.admin_chat_sessions_view, name='admin-sessions'),
]