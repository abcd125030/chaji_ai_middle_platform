from django.contrib import admin
from django.urls import path, include

# 配置admin站点
admin.site.site_header = "X AI中台管理系统"
admin.site.site_title = "X AI中台"
admin.site.index_title = "控制面板"

# 使用默认的admin.site以保持Jazzmin功能
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),  # 已有的认证路由
    path('api/service/', include('service_api.urls')),  # 新增的服务 API 路由
    path('api/llm/', include('llm.urls')),  # 新增的服务 LLM 路由
    path('api/access/', include('access_control.urls')),  # 移动access_control路由到api路径下
    path('api/customization/', include('customized.customization.urls')),
    # path('api/customization/', include('customized.delivery_performance.urls')),  # 应用已移除
    # path('api/customization/', include('customized.pdf_converter.urls')),  # 应用已移除
    path('api/customized/image_editor/', include('customized.image_editor.urls')),
    path('api/knowledge/', include('knowledge.urls')),  # 新增knowledge应用的路由
    path('api/agentic/', include('agentic.urls')),  # 新增agentic应用的路由
    path('api/tools/', include('tools.urls')),      # 新增的tools路由
    path('api/mineru/', include('mineru.urls')),    # MinerU PDF解析服务路由
    path('api/router/', include('router.urls')),    # Router模型配置路由
    path('api/dataset-downloader/', include('dataset_downloader.urls')),  # 数据集下载任务路由

    # 面向前端的应用处理模块
    path('api/webapps/pagtive/', include('webapps.pagtive.urls')),  # Pagtive应用路由
    path('api/webapps/chat/', include('webapps.chat.urls')),  # Chat应用路由
    path('api/webapps/toolkit/', include('webapps.toolkit.urls')),  # 工具集应用路由
    path('api/webapps/moments/', include('webapps.moments.urls')),  # Moments公司圈路由
    path('api/webapps/xiaohongshu/', include('webapps.xiaohongshu.urls')),  # 小红书舆情监控路由
    path('api/market/', include('webapps.market.urls')),  # frago Cloud 市场路由
    path('api/payment/', include('webapps.payment.urls')),  # Payment支付模块路由
    path('api/test/', include('test_app.urls')),  # 测试应用路由
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)