from django.urls import path
from . import views

urlpatterns = [
    # 工具管理端点
    path('', views.tool_list, name='tool-list'),
    path('execute/<str:tool_name>/', views.execute_tool_endpoint, name='tool-execute'),
    path('health/', views.health_check, name='tool-health'),
]