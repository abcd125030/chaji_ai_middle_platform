from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# 创建一个路由器
router = DefaultRouter()

# 注册 Graph, Node, Edge 的 ViewSet
# 这将自动生成如 /graphs/, /graphs/{pk}/ 等路由
router.register(r'graphs', views.GraphViewSet)
router.register(r'nodes', views.NodeViewSet)
router.register(r'edges', views.EdgeViewSet)
router.register(r'tasks', views.AgentTaskView, basename='task')

urlpatterns = [
    # 包含由 router 自动生成的所有 URL
    path('', include(router.urls)),
    # 添加一个用于执行特定图的自定义端点
    # POST /api/agentic/graphs/{graph_pk}/execute/
    path('graphs/<int:graph_pk>/execute/', views.execute_graph, name='graph-execute'),
]