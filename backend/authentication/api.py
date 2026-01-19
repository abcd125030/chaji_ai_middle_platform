from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import User, UserAccount
from .serializers import UserSerializer
import logging

logger = logging.getLogger(__name__)

class UserSyncAPI(APIView):
    """
    用户数据同步API，供Web项目后端使用
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取当前用户信息"""
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)

class WebUserProfileAPI(APIView):
    """
    供Web前端获取用户信息的API
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """通过JWT Token获取用户信息"""
        user = request.user
        logger.info(f"WebUserProfileAPI called for user: {user.username} (id={user.id})")
        logger.info(f"User is_staff: {user.is_staff}, is_superuser: {user.is_superuser}")
        
        # 更新最后登录时间
        user.last_login = timezone.now()
        user.save()
        
        serialized_data = UserSerializer(user).data
        logger.info(f"Serialized user data: {serialized_data}")
        
        # 获取飞书 open_id（从 UserAccount 获取）
        feishu_open_id = None
        feishu_account = UserAccount.objects.filter(user=user, provider='feishu').first()
        if feishu_account:
            feishu_open_id = feishu_account.provider_account_id
        
        response_data = {
            'user': serialized_data,
            'feishu': {
                'open_id': feishu_open_id
            },
            'last_login': user.last_login.isoformat()
        }
        logger.info(f"Response data: {response_data}")
        
        return Response(response_data)

class WebUserSyncAPI(APIView):
    """
    供Web前端直接调用的用户同步API
    """
    def post(self, request):
        """根据Django用户ID同步用户信息到Web数据库"""
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': '缺少user_id参数'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
            # 更新最后登录时间
            user.last_login = timezone.now()
            user.save()
            
            # 获取飞书 open_id（从 UserAccount 获取）
            feishu_open_id = None
            feishu_account = UserAccount.objects.filter(user=user, provider='feishu').first()
            if feishu_account:
                feishu_open_id = feishu_account.provider_account_id
            
            # 这里返回用户数据，Web后端可以存储到自己的数据库
            return Response({
                'user': UserSerializer(user).data,
                'feishu': {
                    'open_id': feishu_open_id
                },
                'last_login': user.last_login.isoformat()
            })
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)