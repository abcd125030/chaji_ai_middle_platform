from django.urls import path

from chat_sessions.views import create_session, get_sessions, get_qas_by_session

urlpatterns = [
    path('create_or_get_session/', create_session, name='create_or_get_session'),  # 接受用户输入的大模型指令，返回结果
    path('get_sessions/', get_sessions, name='get_sessions'),  # 接受用户输入的大模型指令，返回结果
    path('get_qas_by_session/', get_qas_by_session, name='get_qas_by_session'),  # 接受用户输入的大模型指令，返回结果
]