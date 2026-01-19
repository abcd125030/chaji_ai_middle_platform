import copy
import jwt
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from llm.check_utils.utils import check_token_and_get_llm
from llm.llm_service import LLMServiceProvider
import logging
logger = logging.getLogger(__name__)


class LLMServiceView(APIView):
    """外部服务鉴权接口 - 重构后使用新架构"""

    # 禁用 DRF 默认的认证和权限检查，因为这个接口使用自定义的外部服务认证
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        logger.info("api/llm/v1/chat_completion/开始执行")
        
        try:
            # 使用新的外部API处理器
            from .external_api import ExternalLLMAPI
            api_handler = ExternalLLMAPI()
            
            response_data, status_code = api_handler.handle_external_request(request)
            
            # 检查返回的是否是StreamingHttpResponse（流式响应）
            if isinstance(response_data, StreamingHttpResponse):
                logger.info("检测到流式响应，返回 StreamingHttpResponse")
                return response_data
            
            # 对于非流式响应，返回JsonResponse
            logger.info("api/llm/v1/chat_completion/结束执行")
            
            # 记录成功日志
            if status_code == 200:
                ip_address = request.META.get('REMOTE_ADDR')
                logger.info(f"大模型调用成功的客户端IP地址: {ip_address}")

            # 打印要返回的结果
            logger.info(f"要返回的结果: {response_data}")

            return JsonResponse(response_data, status=status_code)
            
        except Exception as e:
            logger.error(f"调用大模型服务时发生异常: {e}")
            logger.info("api/llm/v1/chat_completion/结束执行")
            return JsonResponse(
                {"error": "调用大模型服务时发生内部错误"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
