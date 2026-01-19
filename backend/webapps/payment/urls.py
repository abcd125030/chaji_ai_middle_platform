from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PaymentOrderViewSet,
    PaymentCallbackView,
    PaymentConfigViewSet,
    PaymentLogViewSet
)

app_name = 'payment'

router = DefaultRouter()
router.register('orders', PaymentOrderViewSet, basename='order')
router.register('configs', PaymentConfigViewSet, basename='config')
router.register('logs', PaymentLogViewSet, basename='log')

# 回调视图使用单独的router
callback_router = DefaultRouter()
callback_router.register('callback', PaymentCallbackView, basename='callback')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(callback_router.urls)),
]