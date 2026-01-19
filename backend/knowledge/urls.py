from django.urls import path
from . import views

app_name = 'knowledge' # 推荐为应用URL添加命名空间

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('data/add/', views.KnowledgeAddDataView.as_view(), name='knowledge_add_data'),
    path('data/query/', views.KnowledgeQueryView.as_view(), name='knowledge_query_data'),
    path('data/search/', views.KnowledgeSearchView.as_view(), name='knowledge_search_data'),
    path('data/update/', views.KnowledgeUpdateView.as_view(), name='knowledge_update_data'),
    path('data/delete/', views.KnowledgeDeleteView.as_view(), name='knowledge_delete_data'),
    path('data/list/', views.KnowledgeListView.as_view(), name='knowledge_list_data'),
    path('data/batch/add/', views.KnowledgeBatchAddView.as_view(), name='knowledge_batch_add'),
    path('data/batch/delete/', views.KnowledgeBatchDeleteView.as_view(), name='knowledge_batch_delete'),
]