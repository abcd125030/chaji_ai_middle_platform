"""
Xiaohongshu sentiment monitoring URL configuration
"""
from django.urls import path
from . import views

app_name = 'xiaohongshu'

urlpatterns = [
    # Keyword management
    path('keywords/', views.keywords_list_create, name='keywords_list_create'),
    path('keywords/<int:pk>/', views.keyword_detail, name='keyword_detail'),

    # Note data
    path('notes/', views.notes_list, name='notes_list'),
    path('notes/upload/', views.upload_note, name='upload_note'),
    path('notes/batch/', views.upload_notes_batch, name='upload_notes_batch'),
    path('notes/<str:note_id>/', views.note_detail, name='note_detail'),

    # Analysis
    path('notes/<str:note_id>/analysis/review/', views.analysis_review, name='analysis_review'),

    # Statistics
    path('stats/overview/', views.stats_overview, name='stats_overview'),
    path('stats/hourly/', views.stats_hourly, name='stats_hourly'),
]
