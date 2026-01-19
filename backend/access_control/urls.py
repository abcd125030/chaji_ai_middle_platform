# backend/access_control/urls.py
from django.urls import path
from access_control import views

app_name = 'access_control'

urlpatterns = [
    path('login/', views.login_view, name='login-page'),
    path('apply/', views.UserApplyView.as_view(), name='user-apply'),  # API 路由
    path('apply-page/', views.user_apply_page_view, name='user-apply-page'), # 渲染申请页面的路由
    path('callback/', views.feishu_callback_handler, name='feishu-callback-handler'),
]
