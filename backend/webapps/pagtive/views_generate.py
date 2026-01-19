"""
Pagtive页面生成视图 - 使用服务层重构版本
处理AI生成页面内容的请求
"""

import json
import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Project, ProjectDetail, ProjectLLMLog
from .serializers import GenerateRequestSerializer

# 导入服务层
from .services import PageGenerationService, ProjectService

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_page(request):
    """
    统一的页面生成接口 - 使用服务层
    支持创建新页面(generatePageCode)和编辑现有页面(editPageCode)
    """
    # 记录请求接收
    logger.info(f"[Pagtive生成] 接收到请求 - 用户: {request.user.id}")
    
    # 验证请求数据
    serializer = GenerateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"生成页面请求验证失败: {serializer.errors}")
        return Response({
            'status': 'error',
            'error': '请求数据验证失败',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    
    # 获取请求参数
    project_id = validated_data['projectId']
    template = validated_data['template']
    prompt = validated_data['prompt']
    scenario = validated_data.get('scenario', 'generatePageCode')
    page_id_str = validated_data.get('pageId')
    
    # 处理pageId
    page_id = None
    if page_id_str:
        try:
            page_id = int(page_id_str)
        except (ValueError, TypeError):
            logger.warning(f"[Pagtive生成] pageId无法转换为整数: {page_id_str}")
    
    # 验证项目存在且用户有权限
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        logger.error(f"项目不存在或无权限: project_id={project_id}, user={request.user.id}")
        return Response({
            'status': 'error',
            'error': '项目不存在或无权限'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 准备参考内容
    references = []
    for ref in validated_data.get('references', []):
        ref_data = {
            'title': f"参考页面 {ref.get('pageId', '')}",
            'content': ''
        }
        
        # 获取参考页面内容
        ref_page_id = ref.get('pageId')
        if ref_page_id:
            try:
                ref_page_id_int = int(ref_page_id)
                detail = ProjectDetail.objects.get(
                    project=project,
                    page_id=ref_page_id_int
                )
                
                content_parts = []
                if ref.get('includeHtml') and detail.html:
                    content_parts.append(f"HTML:\n{detail.html}")
                if ref.get('includeCss') and detail.styles:
                    content_parts.append(f"CSS:\n{detail.styles}")
                if ref.get('includeJs') and detail.script:
                    content_parts.append(f"JavaScript:\n{detail.script}")
                
                ref_data['content'] = '\n\n'.join(content_parts)
                
            except (ValueError, ProjectDetail.DoesNotExist) as e:
                logger.warning(f"无法获取参考页面 {ref_page_id}: {str(e)}")
        
        if ref_data['content']:
            references.append(ref_data)
    
    # 准备图片信息
    images = []
    for img in validated_data.get('images', []):
        images.append({
            'name': img.get('name', ''),
            'url': img.get('url', ''),
            'description': img.get('description', '')
        })
    
    # 初始化服务
    page_service = PageGenerationService()
    project_service = ProjectService()
    
    # 处理current字段
    current_content = None
    if validated_data.get('current'):
        current_data = validated_data['current']
        current_content = {
            'html': current_data.get('html', ''),
            'styles': current_data.get('styles', ''),
            'script': current_data.get('script', ''),
            'mermaidContent': current_data.get('mermaid', '')
        }
    
    try:
        # 判断模式
        mode = 'edit' if (scenario == 'editPageCode' or template == 'editPageCode') and page_id else 'generate'
        logger.info(f"[Pagtive生成] {mode}页面模式 - pageId: {page_id}")
        
        # 统一调用generate_page_content方法
        result = page_service.generate_page_content(
            project=project,
            user=request.user,
            prompt=prompt,
            scenario=scenario,
            template=template,
            references=references,
            images=images,
            page_id=page_id,
            current_content=current_content
        )
        
        # 记录响应信息
        logger.info(f"[Pagtive生成] 响应结果:\n"
                   f"  - 状态: {result.get('status', 'unknown')}")
        if result.get('status') == 'success' and result.get('data'):
            data = result['data']
            content = data.get('content', {})
            logger.info(f"  - 页面ID: {data.get('pageId')}\n"
                       f"  - HTML长度: {len(content.get('html', ''))} 字符\n"
                       f"  - CSS长度: {len(content.get('styles', ''))} 字符\n"
                       f"  - JS长度: {len(content.get('script', ''))} 字符\n"
                       f"  - Mermaid长度: {len(content.get('mermaidContent', ''))} 字符")
        elif result.get('status') == 'error':
            logger.warning(f"  - 错误消息: {result.get('message', '未知错误')}")
        
        # 返回响应
        if result.get('status') == 'success':
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"[Pagtive生成] 处理失败: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'message': f'处理失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def edit_page(request):
    """
    编辑页面接口 - 使用服务层
    """
    # 验证请求数据
    project_id = request.data.get('projectId')
    page_id = request.data.get('pageId')
    prompt = request.data.get('prompt')
    
    if not all([project_id, page_id, prompt]):
        return Response({
            'status': 'error',
            'error': '缺少必要参数'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 转换pageId为整数
    try:
        page_id_int = int(page_id)
    except (ValueError, TypeError):
        return Response({
            'status': 'error',
            'error': '无效的页面ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 验证项目权限
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'status': 'error',
            'error': '项目不存在或无权限'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 使用服务层编辑页面
    page_service = PageGenerationService()
    
    try:
        result = page_service.edit_page_content(
            project=project,
            user=request.user,
            page_id=page_id_int,
            edit_prompt=prompt
        )
        
        if result.get('status') == 'success':
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"[Pagtive编辑] 处理失败: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'message': f'编辑失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_page(request):
    """
    重新生成页面接口 - 使用服务层
    """
    # 验证请求数据
    project_id = request.data.get('projectId')
    page_id = request.data.get('pageId')
    prompt = request.data.get('prompt')
    template = request.data.get('template', 'default')
    
    if not all([project_id, page_id]):
        return Response({
            'status': 'error',
            'error': '缺少必要参数'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 转换pageId为整数
    try:
        page_id_int = int(page_id)
    except (ValueError, TypeError):
        return Response({
            'status': 'error',
            'error': '无效的页面ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 验证项目权限
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'status': 'error',
            'error': '项目不存在或无权限'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 使用服务层重新生成页面
    page_service = PageGenerationService()
    
    try:
        # 如果没有提供prompt，使用页面标题作为prompt
        if not prompt:
            pages = project.pages or []
            for page in pages:
                if str(page.get('id')) == str(page_id):
                    prompt = f"生成{page.get('title', '页面')}的内容"
                    break
            
            if not prompt:
                prompt = "生成页面内容"
        
        # 重新生成页面（覆盖现有内容）
        result = page_service.generate_page_content(
            project=project,
            user=request.user,
            prompt=prompt,
            template=template,
            references=[],
            images=[],
            page_id=page_id_int
        )
        
        if result.get('status') == 'success':
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"[Pagtive重新生成] 处理失败: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'message': f'重新生成失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)