import secrets
from urllib.parse import urlencode
import requests
import json
import base64
from django.urls import reverse
from django.http import JsonResponse
from django.shortcuts import redirect # 确保导入 redirect
# Create your views here.
from rest_framework.response import Response
from django.shortcuts import redirect, render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from authentication.models import OAuthState, User
from authentication.serializers import FeishuLoginSerializer, TokenSerializer, UserSerializer
from authentication.views import FeishuLoginView # 导入 FeishuLoginView 以便调用其静态方法
from backend import settings
from access_control.models import UserLoginAuth  # 修改导入
from router.models import LLMModel
from service_api.models import ExternalService
from datetime import datetime, timedelta
import logging
logger = logging.getLogger('django')


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

class UserApplyView(APIView):
    permission_classes = [IsAuthenticated] # 确保只有登录用户才能访问

    def get(self, request, *args, **kwargs):
        """
        提供申请页面所需的数据，如可用的LLM模型列表。
        """
        # llm_models = LLMModel.objects.all()
        # options = [model.name for model in llm_models]
        # return Response({'available_llm_models': options}, status=status.HTTP_200_OK)

        # --- 调试代码：返回固定的模拟数据以验证前端渲染 ---
        # 这个模拟数据是为了匹配用户提供的UI截图（图1）。
        # 如果前端能正确渲染这个列表，说明问题出在数据库中的LLMModel数据不完整。
        mock_options = [
            "阿里百炼qwen3-235b-a22b", "茶姬私有化部署qwq-32b", "阿里百炼DeepSeek-R1",
            "OpenRouter DS-R1 免费版", "OpenRouter Claude 3.5 Haiku", "OpenRouter Claude 3.7 Sonnet 昂贵慎用",
            "OpenRouter Gemini2.0Flash", "阿里百炼qwen-plus", "阿里百炼qwq-32b",
            "阿里百炼qwen-vl-max-latest", "阿里百炼qwen3-32b"
        ]
        return Response({'available_llm_models': mock_options}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """
        处理用户的服务申请提交。
        """
        user = request.user # 直接从请求中获取认证过的用户
        user_address = request.data.get('address')
        user_reason = request.data.get('reason')
        selected_options = request.data.get('selected_options', [])

        if not user_reason:
            return Response({"error": "没有填写使用原因,请重新填写"}, status=status.HTTP_400_BAD_REQUEST)
        if not selected_options:
            return Response({"error": "没有选择要使用的模型,请重新选择"}, status=status.HTTP_400_BAD_REQUEST)

        # 判断是否已存在申请
        if UserLoginAuth.objects.filter(user=user).exists():
            logger.info(f"用户 {user.username} 已提交过申请, 无需重复提交。")
            return Response({"message": "您已经提交过申请了, 请等待审核。"}, status=status.HTTP_409_CONFLICT)

        # 创建申请记录
        llm_models = LLMModel.objects.filter(name__in=selected_options)
        user_login_auth = UserLoginAuth.objects.create(
            user=user,
            address=user_address,
            reason=user_reason
        )
        user_login_auth.llm_models.set(llm_models)
        
        logger.info(f"用户 {user.username} 的服务申请已成功提交。")
        return Response({"message": "申请成功, 审核完毕后将通过飞书通知您。"}, status=status.HTTP_201_CREATED)


def user_apply_page_view(request):
    """
    渲染用户申请页面。
    """
    return render(request, 'login/user_apply.html')


def login_view(request):
    """
    此视图现在仅作为一个引导页面，或提供给前端认证所需的信息。
    它不再处理POST请求或重定向到飞书。
    实际的登录请求应由前端直接发往 authentication App 的端点。
    """
    logger.info("引导用户前往前端登录页面。")
    # 这里可以向模板传递前端路由地址或认证中心URL等信息
    # 根据 docs/plans/2025-06-10_后端认证授权职责分离重构.md 的规划
    context = {
        'frontend_login_url': '/login', # 假设前端登录页面的路由是 /login
        'auth_center_url': '/api/auth/feishu/login/', # 指向 authentication App 的认证入口
        'callback_url': request.GET.get('callback_url', ''), # 保留原有的 callback_url 和 action
        'action': request.GET.get('action', '')
    }
    return render(request, 'login/login.html', context)

def feishu_callback_handler(request):
    """
    处理飞书OAuth回调。
    1. 从URL获取code和state。
    2. 将code和state POST到真正的认证回调API (/api/auth/feishu/callback/)。
    3. 渲染一个模板，该模板将JWT存储在localStorage并重定向。
    """
    logger.info("Access Control: feishu_callback_handler received request.")
    code = request.GET.get('code')
    state = request.GET.get('state')

    if not code or not state:
        logger.error("Access Control: Code or state missing in feishu_callback_handler.")
        return render(request, 'login/auth_callback_handler.html', {'error': 'Code or state missing'})

    try:
        logger.info("Access Control: Calling authentication logic directly.")
        
        # 直接调用认证模块的核心逻辑函数，避免HTTP请求
        auth_result = FeishuLoginView.process_feishu_authentication(code, state)

        if not auth_result.get('success'):
            logger.error(f"Access Control: Authentication logic failed. Error: {auth_result.get('error')}")
            return render(request, 'login/auth_callback_handler.html', {'error': auth_result.get('error')})

        logger.info(f"Access Control: Feishu authentication successful. Tokens received：{auth_result.get('tokens')}")
        
        # 认证成功，渲染模板，将token传递给前端
        context = {
            'success': True,
            'tokens': json.dumps(auth_result.get('tokens')), # 将tokens转为JSON字符串
            'redirect_url': '/api/access/apply-page/' # 使用新配置的页面路由
        }
        return render(request, 'login/auth_callback_handler.html', context)

    except Exception as e:
        logger.exception(f"Access Control: An unexpected error occurred in feishu_callback_handler.")
        return render(request, 'login/auth_callback_handler.html', {'error': 'An unexpected server error occurred.'})

