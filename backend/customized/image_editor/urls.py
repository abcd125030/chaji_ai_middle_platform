from django.urls import path
from . import views

app_name = 'image_editor'

urlpatterns = [
    # 提交单个任务
    path('submit/', views.SubmitTaskView.as_view(), name='submit_task'),
    
    # 查询单个任务结果
    path('result/', views.QueryTaskResultView.as_view(), name='query_task'),
    
    # 批量提交任务
    path('batch_submit/', views.BatchSubmitTaskView.as_view(), name='batch_submit'),
    
    # 批量查询结果
    path('batch_result/', views.BatchQueryTaskResultView.as_view(), name='batch_query'),
    
    # API状态查询
    path('status/', views.TaskStatusView.as_view(), name='status'),
    
    # 任务查看器页面
    path('viewer/', views.task_viewer, name='task_viewer'),
]