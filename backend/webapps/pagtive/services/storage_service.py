"""
存储服务
========

封装文件上传、下载、管理等存储相关功能。
使用本地文件系统存储到 media/oss-bucket 目录。
"""

import logging
import mimetypes
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List, BinaryIO
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

from ..models import Project

logger = logging.getLogger(__name__)


class StorageService:
    """存储服务类"""
    
    # 支持的文件类型
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg', 'image/jpg', 'image/png', 
        'image/gif', 'image/svg+xml', 'image/webp'
    ]
    
    ALLOWED_DOCUMENT_TYPES = [
        'application/pdf', 
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'text/markdown'
    ]
    
    # 文件大小限制（字节）
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
    
    def __init__(self, user: Optional[AbstractBaseUser] = None):
        """
        初始化存储服务
        
        Args:
            user: 用户对象（可选）
        """
        self.user = user
        self.base_dir = os.path.join(settings.MEDIA_ROOT, 'oss-bucket')
    
    def upload_file(
        self, 
        file: UploadedFile,
        project: Optional[Project] = None,
        file_type: str = 'general',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        上传文件到本地存储
        
        Args:
            file: 上传的文件对象
            project: 关联的项目（可选）
            file_type: 文件类型（'image', 'document', 'general'）
            metadata: 文件元数据
            
        Returns:
            文件信息字典
            
        Raises:
            ValueError: 文件验证失败
            Exception: 上传失败
        """
        # 验证文件
        self._validate_file(file, file_type)
        
        # 准备存储路径
        date_path = datetime.now().strftime('%Y/%m/%d')
        app_path = 'pagtive'
        if project:
            app_path = f'pagtive/project_{project.id}'
        
        save_dir = os.path.join(self.base_dir, app_path, date_path)
        os.makedirs(save_dir, exist_ok=True)
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime('%H%M%S%f')
        file_ext = os.path.splitext(file.name)[1]
        unique_filename = f"{timestamp}_{file.name}"
        file_path = os.path.join(save_dir, unique_filename)
        
        try:
            # 保存文件
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            # 生成相对路径
            relative_path = os.path.relpath(file_path, self.base_dir)
            
            # 返回文件信息
            file_info = {
                'id': timestamp,
                'file_key': relative_path,
                'original_name': file.name,
                'url': f"/media/oss-bucket/{relative_path}",
                'size': file.size,
                'content_type': file.content_type or mimetypes.guess_type(file.name)[0],
                'created_at': datetime.now().isoformat(),
                'metadata': metadata or {}
            }
            
            logger.info(f"文件上传成功: {file.name} -> {relative_path}")
            return file_info
            
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            # 清理失败的文件
            if os.path.exists(file_path):
                os.remove(file_path)
            raise
    
    def _validate_file(self, file: UploadedFile, file_type: str):
        """
        验证上传的文件
        
        Args:
            file: 上传的文件
            file_type: 文件类型
            
        Raises:
            ValueError: 验证失败
        """
        # 检查文件大小
        if file_type == 'image' and file.size > self.MAX_IMAGE_SIZE:
            raise ValueError(f"图片文件大小不能超过{self.MAX_IMAGE_SIZE / 1024 / 1024}MB")
        elif file.size > self.MAX_FILE_SIZE:
            raise ValueError(f"文件大小不能超过{self.MAX_FILE_SIZE / 1024 / 1024}MB")
        
        # 检查文件类型
        content_type = file.content_type or mimetypes.guess_type(file.name)[0]
        
        if file_type == 'image' and content_type not in self.ALLOWED_IMAGE_TYPES:
            raise ValueError(f"不支持的图片格式: {content_type}")
        elif file_type == 'document' and content_type not in self.ALLOWED_DOCUMENT_TYPES:
            raise ValueError(f"不支持的文档格式: {content_type}")
    
    def delete_file(self, file_key: str) -> bool:
        """
        删除文件
        
        Args:
            file_key: 文件相对路径
            
        Returns:
            是否删除成功
        """
        try:
            file_path = os.path.join(self.base_dir, file_key)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"文件删除成功: {file_key}")
                return True
            else:
                logger.warning(f"文件不存在: {file_key}")
                return False
        except Exception as e:
            logger.error(f"文件删除失败: {e}")
            return False
    
    def get_file_url(self, file_key: str) -> str:
        """
        获取文件访问URL
        
        Args:
            file_key: 文件相对路径
            
        Returns:
            文件访问URL
        """
        return f"/media/oss-bucket/{file_key}"
    
    def list_project_files(self, project: Project) -> List[Dict[str, Any]]:
        """
        列出项目的所有文件
        
        Args:
            project: 项目对象
            
        Returns:
            文件信息列表
        """
        files = []
        project_dir = os.path.join(self.base_dir, 'pagtive', f'project_{project.id}')
        
        if not os.path.exists(project_dir):
            return files
        
        try:
            for root, dirs, filenames in os.walk(project_dir):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, self.base_dir)
                    
                    # 获取文件信息
                    stat = os.stat(file_path)
                    files.append({
                        'file_key': relative_path,
                        'original_name': filename,
                        'url': f"/media/oss-bucket/{relative_path}",
                        'size': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat()
                    })
        except Exception as e:
            logger.error(f"列出项目文件失败: {e}")
        
        return files