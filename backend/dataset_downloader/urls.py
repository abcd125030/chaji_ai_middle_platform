from django.urls import path
from . import views

app_name = 'dataset_downloader'
urlpatterns = [
    path('datasets/batch/', views.DatasetBatchCreateView.as_view(), name='datasets_batch'),
    path('datasets/', views.DatasetListView.as_view(), name='datasets_list'),
    path('datasets/<uuid:dataset_id>/', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path('datasets/<uuid:dataset_id>/reset/', views.DatasetResetView.as_view(), name='dataset_reset'),
    path('tasks/request/', views.TaskRequestView.as_view(), name='tasks_request'),
    path('tasks/<uuid:task_id>/heartbeat/', views.TaskHeartbeatView.as_view(), name='task_heartbeat'),
    path('tasks/<uuid:task_id>/complete/', views.TaskCompleteView.as_view(), name='task_complete'),
    path('tasks/<uuid:task_id>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('status/', views.TaskStatusView.as_view(), name='api_status'),
]