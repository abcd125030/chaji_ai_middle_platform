"""
工具集应用的URL配置
"""
from django.urls import path
from . import views
from . import ocr_views

app_name = 'toolkit'

urlpatterns = [
    # PDF分析相关接口
    path('formats/', views.get_supported_formats, name='get_supported_formats'),

    # PDF提取器接口
    path('extractor/upload/', views.upload_pdf_documents, name='upload_pdf_documents'),
    path('extractor/progress/', views.query_task_progress, name='query_task_progress'),
    path('extractor/tasks/', views.get_user_tasks, name='get_user_tasks'),
    path('extractor/content/<uuid:task_id>/', views.get_task_content, name='get_task_content'),

    # OCR服务接口
    path('ocr/health/', ocr_views.ocr_health_check, name='ocr_health_check'),
    path('ocr/image/', ocr_views.ocr_image, name='ocr_image'),
    path('ocr/images/batch/', ocr_views.ocr_images_batch, name='ocr_images_batch'),
    path('ocr/info/', ocr_views.ocr_info, name='ocr_info'),

    # 健康检查
    path('health/', views.health_check, name='health_check'),
]
