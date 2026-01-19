"""
OCR服务API视图
提供OCR模型服务的HTTP接口
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .services import OCRModelService

logger = logging.getLogger('django')


# 初始化OCR服务（单例模式）
_ocr_service = None


def get_ocr_service():
    """获取OCR服务实例（单例）"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRModelService()
        logger.info("OCR服务实例已创建")
    return _ocr_service


@api_view(['GET'])
@permission_classes([AllowAny])
def ocr_health_check(request):
    """OCR服务健康检查"""
    try:
        ocr_service = get_ocr_service()
        result = ocr_service.health_check()

        if result.get('success'):
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"OCR健康检查失败: {str(e)}", exc_info=True)
        return Response(
            {
                'success': False,
                'error': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def ocr_image(request):
    """
    OCR识别单张图片

    请求体:
    {
        "image_base64": "base64编码的图片",
        "mode": "convert_to_markdown",  // 可选
        "max_tokens": 8192,  // 可选
        "temperature": 0.0   // 可选
    }

    返回:
    {
        "success": true,
        "result": "原始Markdown结果",
        "result_cleaned": "清理后的Markdown结果",
        "image_size": [width, height],
        "mode": "convert_to_markdown",
        "image_count": 2
    }
    """
    try:
        # 获取请求参数
        image_base64 = request.data.get('image_base64')
        mode = request.data.get('mode', 'convert_to_markdown')
        max_tokens = request.data.get('max_tokens', 8192)
        temperature = request.data.get('temperature', 0.0)

        # 参数验证
        if not image_base64:
            return Response(
                {
                    'success': False,
                    'error': 'image_base64参数不能为空'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 调用OCR服务
        ocr_service = get_ocr_service()
        result = ocr_service.ocr_image(
            image_base64=image_base64,
            mode=mode,
            max_tokens=max_tokens,
            temperature=temperature
        )

        if result.get('success'):
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"OCR识别失败: {str(e)}", exc_info=True)
        return Response(
            {
                'success': False,
                'error': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def ocr_images_batch(request):
    """
    OCR批量识别多张图片

    请求体:
    {
        "images_base64": ["base64_1", "base64_2", ...],
        "mode": "convert_to_markdown",  // 可选
        "max_tokens": 8192,  // 可选
        "temperature": 0.0   // 可选
    }

    返回:
    {
        "success": true,
        "total": 3,
        "success_count": 3,
        "failed_count": 0,
        "results": [
            {
                "result": "...",
                "result_cleaned": "...",
                "image_size": [1200, 1600],
                "mode": "convert_to_markdown",
                "image_count": 1
            },
            ...
        ]
    }
    """
    try:
        # 获取请求参数
        images_base64 = request.data.get('images_base64', [])
        mode = request.data.get('mode', 'convert_to_markdown')
        max_tokens = request.data.get('max_tokens', 8192)
        temperature = request.data.get('temperature', 0.0)

        # 参数验证
        if not images_base64:
            return Response(
                {
                    'success': False,
                    'error': 'images_base64参数不能为空'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(images_base64, list):
            return Response(
                {
                    'success': False,
                    'error': 'images_base64必须是列表类型'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 调用OCR服务
        ocr_service = get_ocr_service()
        result = ocr_service.ocr_images(
            images_base64=images_base64,
            mode=mode,
            max_tokens=max_tokens,
            temperature=temperature
        )

        if result.get('success'):
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"OCR批量识别失败: {str(e)}", exc_info=True)
        return Response(
            {
                'success': False,
                'error': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def ocr_info(request):  # pylint: disable=unused-argument
    """
    获取OCR服务信息

    返回:
    {
        "api_url": "http://172.22.217.66:9123",
        "timeout": 300,
        "supported_modes": [...],
        "supported_formats": [...],
        "features": [...]
    }
    """
    try:
        ocr_service = get_ocr_service()
        info = ocr_service.get_api_info()
        return Response(info, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"获取OCR服务信息失败: {str(e)}", exc_info=True)
        return Response(
            {
                'success': False,
                'error': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
