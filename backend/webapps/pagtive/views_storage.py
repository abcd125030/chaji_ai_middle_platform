"""
Pagtive 文件存储相关视图

使用本地文件系统处理文件上传、下载和管理
"""

import logging
import mimetypes
import os
from datetime import datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse, FileResponse
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import Project
from .serializers import FileUploadSerializer
from .services.storage_service import StorageService

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_file(request, project_id=None):
    """
    上传文件到本地存储
    
    支持的文件类型：
    - 图片：jpg, jpeg, png, gif, svg, webp
    - 文档：pdf, doc, docx, txt, md
    - 其他：由配置决定
    
    Args:
        project_id: 项目ID（可选）
    
    Returns:
        {
            "success": true,
            "file": {
                "id": "file_id",
                "url": "访问URL",
                "original_name": "原始文件名",
                "size": 文件大小,
                "content_type": "内容类型"
            }
        }
    """
    try:
        # 验证项目访问权限（如果提供了project_id）
        project = None
        if project_id:
            project = get_object_or_404(Project, id=project_id)
            if project.user != request.user:
                return Response(
                    {"error": "无权访问该项目"},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # 获取上传的文件
        if 'file' not in request.FILES:
            return Response(
                {"error": "请选择要上传的文件"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        
        # 使用StorageService上传文件
        storage_service = StorageService(user=request.user)
        
        # 准备元数据
        metadata = {
            "uploaded_by": str(request.user.id),
            "user_email": getattr(request.user, 'email', ''),
            "source": "pagtive"
        }
        
        if project:
            metadata["project_id"] = str(project.id)
            metadata["project_name"] = project.project_name
        
        # 上传文件
        try:
            file_info = storage_service.upload_file(
                file=uploaded_file,
                project=project,
                file_type='general',
                metadata=metadata
            )
            
            # 返回文件信息
            return Response({
                "success": True,
                "file": file_info
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return Response(
            {"error": f"文件上传失败: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_files(request, project_id=None):
    """
    列出项目或用户的所有文件
    
    Args:
        project_id: 项目ID（可选）
    
    Returns:
        {
            "success": true,
            "files": [
                {
                    "file_key": "相对路径",
                    "url": "访问URL",
                    "original_name": "原始文件名",
                    "size": 文件大小,
                    "created_at": "创建时间"
                }
            ]
        }
    """
    try:
        if project_id:
            # 获取项目
            project = get_object_or_404(Project, id=project_id)
            
            # 验证权限
            if project.user != request.user:
                return Response(
                    {"error": "无权访问该项目"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # 使用StorageService列出项目文件
            storage_service = StorageService(user=request.user)
            files = storage_service.list_project_files(project)
        else:
            # 列出用户的所有文件（暂时返回空列表）
            files = []
        
        return Response({
            "success": True,
            "files": files,
            "count": len(files)
        })
        
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        return Response(
            {"error": f"列出文件失败: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_file(request, file_key):
    """
    下载文件
    
    Args:
        file_key: 文件相对路径
    
    Returns:
        文件内容
    """
    try:
        # 构建文件完整路径
        base_dir = os.path.join(settings.MEDIA_ROOT, 'oss-bucket')
        file_path = os.path.join(base_dir, file_key)
        
        # 安全检查：确保路径在允许的目录内
        real_path = os.path.realpath(file_path)
        if not real_path.startswith(os.path.realpath(base_dir)):
            return Response(
                {"error": "无效的文件路径"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return Response(
                {"error": "文件不存在"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 获取文件名和MIME类型
        filename = os.path.basename(file_path)
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        
        # 返回文件
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        logger.error(f"文件下载失败: {e}")
        return Response(
            {"error": f"文件下载失败: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request, file_key):
    """
    删除文件
    
    Args:
        file_key: 文件相对路径
    
    Returns:
        {
            "success": true,
            "message": "文件删除成功"
        }
    """
    try:
        # 使用StorageService删除文件
        storage_service = StorageService(user=request.user)
        
        if storage_service.delete_file(file_key):
            return Response({
                "success": True,
                "message": "文件删除成功"
            })
        else:
            return Response(
                {"error": "文件不存在或删除失败"},
                status=status.HTTP_404_NOT_FOUND
            )
        
    except Exception as e:
        logger.error(f"文件删除失败: {e}")
        return Response(
            {"error": f"文件删除失败: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )