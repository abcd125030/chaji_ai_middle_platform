"""
MinerU 存储适配器
====================

为 MinerU 提供本地文件系统存储能力
"""

import os
import logging
import hashlib
import json
import shutil
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from django.conf import settings

logger = logging.getLogger('django')


class MinerUStorageAdapter:
    """MinerU 存储适配器"""
    
    def __init__(self, user=None):
        """
        初始化存储适配器
        
        Args:
            user: 用户对象
        """
        self.user = user
        self.base_dir = Path(settings.MEDIA_ROOT) / 'oss-bucket' / 'mineru'
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.local_temp_dir = Path(settings.MINERU_SETTINGS.get('TEMP_DIR', '/tmp/mineru'))
        self.local_temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 缓存目录
        self.cache_dir = self.base_dir / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_file_hash(self, file_bytes: bytes) -> str:
        """
        生成文件哈希值（用于去重和缓存）
        
        Args:
            file_bytes: 文件字节内容
            
        Returns:
            文件的 SHA256 哈希值
        """
        return hashlib.sha256(file_bytes).hexdigest()
    
    def check_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        检查是否有缓存的解析结果
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            缓存的结果信息，如果没有返回 None
        """
        try:
            cache_file_path = self.cache_dir / f"{file_hash}.json"
            
            if cache_file_path.exists():
                with open(cache_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return None
            
        except Exception as e:
            logger.error(f"检查缓存失败: {e}")
            return None
    
    def save_cache(self, file_hash: str, result_data: Dict[str, Any]) -> bool:
        """
        保存解析结果到缓存
        
        Args:
            file_hash: 文件哈希值
            result_data: 解析结果数据
            
        Returns:
            是否保存成功
        """
        try:
            cache_file_path = self.cache_dir / f"{file_hash}.json"
            
            # 添加元数据
            result_data['cached_at'] = datetime.now().isoformat()
            result_data['file_hash'] = file_hash
            
            with open(cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"缓存已保存: {cache_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False
    
    def upload_file(
        self, 
        file_path: str,
        file_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        上传文件到存储
        
        Args:
            file_path: 本地文件路径
            file_name: 文件名（可选，默认使用原文件名）
            metadata: 元数据
            
        Returns:
            文件信息
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 生成目标路径
            date_path = datetime.now().strftime('%Y/%m/%d')
            save_dir = self.base_dir / date_path
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            if not file_name:
                file_name = os.path.basename(file_path)
            
            timestamp = datetime.now().strftime('%H%M%S%f')
            unique_filename = f"{timestamp}_{file_name}"
            dest_path = save_dir / unique_filename
            
            # 复制文件
            shutil.copy2(file_path, dest_path)
            
            # 生成相对路径
            relative_path = dest_path.relative_to(self.base_dir.parent.parent)
            
            file_info = {
                'file_key': str(relative_path),
                'file_path': str(dest_path),
                'original_name': file_name,
                'url': f"/media/{relative_path}",
                'size': os.path.getsize(dest_path),
                'created_at': datetime.now().isoformat(),
                'metadata': metadata or {}
            }
            
            logger.info(f"文件已上传: {file_name} -> {dest_path}")
            return file_info
            
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            raise
    
    def download_file(self, file_key: str, dest_path: Optional[str] = None) -> str:
        """
        下载文件到本地
        
        Args:
            file_key: 文件相对路径
            dest_path: 目标路径（可选）
            
        Returns:
            下载后的本地文件路径
        """
        try:
            # 源文件路径
            source_path = self.base_dir.parent.parent / file_key
            
            if not source_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_key}")
            
            # 如果没有指定目标路径，复制到临时目录
            if not dest_path:
                dest_path = self.local_temp_dir / os.path.basename(file_key)
            
            # 复制文件
            shutil.copy2(source_path, dest_path)
            
            logger.info(f"文件已下载: {file_key} -> {dest_path}")
            return str(dest_path)
            
        except Exception as e:
            logger.error(f"文件下载失败: {e}")
            raise
    
    def save_result(
        self,
        task_id: str,
        result_type: str,
        result_data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        保存解析结果
        
        Args:
            task_id: 任务ID
            result_type: 结果类型（markdown, images, etc）
            result_data: 结果数据
            metadata: 元数据
            
        Returns:
            保存的文件信息
        """
        try:
            # 创建结果目录
            result_dir = self.base_dir / 'results' / task_id
            result_dir.mkdir(parents=True, exist_ok=True)
            
            # 根据结果类型保存
            if result_type == 'markdown':
                file_name = f"{task_id}_output.md"
                file_path = result_dir / file_name
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(result_data)
                    
            elif result_type == 'json':
                file_name = f"{task_id}_result.json"
                file_path = result_dir / file_name
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                    
            elif result_type == 'images':
                # 如果是图片目录，直接移动或复制
                file_name = f"{task_id}_images"
                file_path = result_dir / file_name
                
                if os.path.isdir(result_data):
                    shutil.copytree(result_data, file_path, dirs_exist_ok=True)
                else:
                    file_path.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(result_data, file_path)
            else:
                # 其他类型，直接复制
                file_name = os.path.basename(result_data) if isinstance(result_data, str) else f"{task_id}_{result_type}"
                file_path = result_dir / file_name
                
                if isinstance(result_data, str) and os.path.exists(result_data):
                    shutil.copy2(result_data, file_path)
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(str(result_data))
            
            # 生成相对路径
            relative_path = file_path.relative_to(self.base_dir.parent.parent)
            
            return {
                'file_key': str(relative_path),
                'file_path': str(file_path),
                'file_name': file_name,
                'result_type': result_type,
                'url': f"/media/{relative_path}",
                'created_at': datetime.now().isoformat(),
                'metadata': metadata or {}
            }
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            raise
    
    def cleanup_temp_files(self, task_id: str):
        """
        清理临时文件
        
        Args:
            task_id: 任务ID
        """
        try:
            # 清理临时目录中的任务文件
            temp_task_dir = self.local_temp_dir / task_id
            if temp_task_dir.exists():
                shutil.rmtree(temp_task_dir)
                logger.info(f"临时文件已清理: {temp_task_dir}")
                
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")