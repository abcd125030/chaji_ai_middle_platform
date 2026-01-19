from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PDFParseTaskViewSet, create_task_from_base64

# 创建路由器
router = DefaultRouter()
router.register(r'tasks', PDFParseTaskViewSet, basename='task')

app_name = 'mineru'

urlpatterns = [
    # ViewSet 路由
    path('', include(router.urls)),
    
    # 额外的 API 端点
    path('create-from-base64/', create_task_from_base64, name='create-from-base64'),
]

# API 端点说明：
# POST /api/mineru/tasks/upload/ - 上传文件创建任务
# GET  /api/mineru/tasks/ - 获取任务列表
# GET  /api/mineru/tasks/{id}/ - 获取任务详情
# GET  /api/mineru/tasks/{id}/status/ - 查询任务状态
# GET  /api/mineru/tasks/{id}/download/?type=markdown|json - 下载结果文件
# POST /api/mineru/tasks/{id}/reprocess/ - 重新处理任务
# POST /api/mineru/create-from-base64/ - 通过Base64创建任务