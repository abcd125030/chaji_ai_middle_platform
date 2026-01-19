"""
Router模块URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# 创建路由器
router = DefaultRouter()
router.register(r'vendors', views.VendorViewSet, basename='vendor')
router.register(r'endpoints', views.VendorEndpointViewSet, basename='vendorendpoint')
router.register(r'apikeys', views.VendorAPIKeyViewSet, basename='vendorapikey')
router.register(r'models', views.LLMModelViewSet, basename='llmmodel')

app_name = 'router'

urlpatterns = [
    path('', include(router.urls)),
]