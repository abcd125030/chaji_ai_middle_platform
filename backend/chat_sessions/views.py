import uuid

import jwt
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from service_api.models import ExternalService
from service_api.utils import JWTManager
from .models import Session, QA  # 导入模型


# 接口1：根据用户ID创建或获取会话
@api_view(['POST'])
def create_session(request):
    user_id = request.data.get('user_id')
    # 步骤1: 检查token
    # 步骤2: 创建session
    session = Session.objects.create(
        user_id=user_id,
        session_id=uuid.uuid4()
    )
    return Response({
        'user_id': session.user_id,
        'session_id': session.session_id,
        'created': session.created_at
    }, status=status.HTTP_200_OK)


# 接口2：根据会话ID获取所有的问答记录
@api_view(['POST'])
def get_qas_by_session(request):
    session_id = request.data.get('session_id')
    qas = QA.objects.filter(session__session_id=session_id).values(
        'id', 'prompt_text', 'model', 'response', 'created_at'
    )
    return JsonResponse(list(qas), safe=False)


# # 接口3：根据用户ID获取所有的会话
@api_view(['POST'])
def get_sessions(request):
    user_id = request.data.get('user_id')
    sessions = Session.objects.filter(user_id=user_id).values(
        'session_id', 'created_at', 'updated_at', 'state'
    )
    return JsonResponse(list(sessions), safe=False)