from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_generate import generate_page
from . import views_storage

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet, basename='project')
router.register(r'share', views.ShareViewSet, basename='share')

urlpatterns = [
    path('', include(router.urls)),
    # 新的生成接口 - 与旧项目兼容
    path('generate/', generate_page, name='generate-page'),
    # 保留原有的生成接口（如果需要）
    path('generate-old/', views.GenerateViewSet.as_view({'post': 'generate'}), name='generate-old'),
    path('generate/outline/', views.GenerateViewSet.as_view({'post': 'outline'}), name='generate-outline'),
    
    # 文件存储相关接口（使用OSS）
    path('storage/upload/', views_storage.upload_file, name='storage-upload'),
    path('storage/upload/<uuid:project_id>/', views_storage.upload_file, name='storage-upload-project'),
    path('storage/files/', views_storage.list_files, name='storage-list'),
    path('storage/files/<uuid:project_id>/', views_storage.list_files, name='storage-list-project'),
    path('storage/file/<str:file_key>/delete/', views_storage.delete_file, name='storage-delete'),
    path('storage/file/<path:file_key>/download/', views_storage.download_file, name='storage-download'),
]