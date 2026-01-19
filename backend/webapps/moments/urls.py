"""moments URL配置"""

from django.urls import path
from . import views

urlpatterns = [
    path('posts/', views.posts_list, name='moments-posts-list'),
    path('posts/stats/hourly/', views.posts_hourly_stats, name='moments-posts-hourly-stats'),
    path('posts/<str:post_id>/', views.post_detail, name='moments-post-detail'),
]
