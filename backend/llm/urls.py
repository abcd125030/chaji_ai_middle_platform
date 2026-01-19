from django.urls import path
from .views import LLMServiceView

urlpatterns = [
    path('v1/chat/completions/', LLMServiceView.as_view(), name='llm_chat_completion'),  # 接受用户输入的大模型指令，返回结果
]