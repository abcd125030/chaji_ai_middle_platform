"""
Join Wish 相关视图
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from authentication.services.join_wish_service import JoinWishService
from authentication.services.user_management_service import UserManagementService

logger = logging.getLogger(__name__)


class JoinWishSubmitView(APIView):
    """提交 Join Wish 申请"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        提交加入意愿表单
        
        Expected data:
        {
            "company": "公司名称",
            "role": "角色/职位",
            "interest": "兴趣领域",
            "message": "留言"
        }
        """
        # 检查用户状态
        if request.user.status == request.user.Status.ACTIVE:
            return Response({
                'status': 'info',
                'message': '您的账号已经激活，无需重复申请'
            }, status=status.HTTP_200_OK)
        
        # 获取表单数据
        form_data = {
            'company': request.data.get('company', ''),
            'role': request.data.get('role', ''),
            'interest': request.data.get('interest', ''),
            'message': request.data.get('message', '')
        }
        
        # 验证必填字段
        if not form_data['interest']:
            return Response({
                'status': 'error',
                'message': '请选择您的兴趣领域'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 提交申请
        result = JoinWishService.submit_join_wish(request.user, form_data)
        
        if result['success']:
            return Response({
                'status': 'success',
                'message': result['message']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': result.get('error', '提交失败')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JoinWishListView(APIView):
    """管理员查看 Join Wish 申请列表"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取待审核的申请列表"""
        # 检查权限
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if request.user.role not in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            return Response({
                'status': 'error',
                'message': '您没有权限查看申请列表'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 获取分页参数
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # 获取申请列表
        result = JoinWishService.get_pending_applications(page, page_size)
        
        return Response({
            'status': 'success',
            'data': result
        }, status=status.HTTP_200_OK)


class JoinWishApproveView(APIView):
    """批准 Join Wish 申请"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, user_id):
        """批准指定用户的申请"""
        # 检查权限
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if request.user.role not in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            return Response({
                'status': 'error',
                'message': '您没有权限批准申请'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 批准申请
        result = JoinWishService.approve_application(user_id, request.user)
        
        if result['success']:
            return Response({
                'status': 'success',
                'message': result['message']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': result.get('error', '操作失败')
            }, status=status.HTTP_400_BAD_REQUEST if 'error' in result else status.HTTP_500_INTERNAL_SERVER_ERROR)


class JoinWishBatchApproveView(APIView):
    """批量批准 Join Wish 申请"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        批量批准申请
        
        Expected data:
        {
            "user_ids": [1, 2, 3]
        }
        """
        # 检查权限
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if request.user.role not in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            return Response({
                'status': 'error',
                'message': '您没有权限批准申请'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 获取用户ID列表
        user_ids = request.data.get('user_ids', [])
        
        if not user_ids:
            return Response({
                'status': 'error',
                'message': '请选择要批准的用户'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 批量批准
        success_count = 0
        failed_count = 0
        failed_users = []
        
        for user_id in user_ids:
            result = JoinWishService.approve_application(user_id, request.user)
            if result['success']:
                success_count += 1
            else:
                failed_count += 1
                failed_users.append(user_id)
        
        # 构建响应消息
        message = f'成功激活 {success_count} 个用户'
        if failed_count > 0:
            message += f'，{failed_count} 个用户激活失败'
        
        return Response({
            'status': 'success',
            'message': message,
            'data': {
                'success_count': success_count,
                'failed_count': failed_count,
                'failed_users': failed_users
            }
        }, status=status.HTTP_200_OK)