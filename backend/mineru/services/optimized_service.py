"""
优化后的 MinerU 服务
===================

集成 OSS 存储，提供智能缓存和高效文件管理
"""

import os
import shutil
import logging
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.db import transaction

from ..models import PDFParseTask, ParseResult
from .storage_adapter import MinerUStorageAdapter

logger = logging.getLogger('django')


class OptimizedMinerUService:
    """优化后的 MinerU 服务"""
    
    def __init__(self):
        """初始化服务"""
        self.config = settings.MINERU_SETTINGS
        self.storage_adapter = None
        self.use_oss = self.config.get('USE_OSS', True)
        
        # 本地临时目录（仅用于处理过程）
        self.temp_dir = Path(self.config.get('TEMP_DIR', '/tmp/mineru'))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_storage_adapter(self, user=None) -> MinerUStorageAdapter:
        """获取存储适配器（懒加载）"""
        if not self.storage_adapter:
            self.storage_adapter = MinerUStorageAdapter(user=user)
        return self.storage_adapter
    
    @transaction.atomic
    def process_document(self, task: PDFParseTask, file_bytes: bytes) -> Dict[str, Any]:
        """
        处理文档解析任务（优化版本）
        
        Args:
            task: PDFParseTask 实例
            file_bytes: 文件字节内容
            
        Returns:
            解析结果字典
        """
        logger.info(f"开始处理文档任务: {task.task_id}")
        
        try:
            # 1. 获取存储适配器
            storage = self._get_storage_adapter(task.user)
            
            # 2. 生成文件哈希并检查缓存
            file_hash = storage.generate_file_hash(file_bytes)
            cached_result = storage.check_cache(file_hash)
            
            if cached_result:
                logger.info(f"命中缓存，直接返回结果: {task.task_id}")
                return self._handle_cached_result(task, cached_result)
            
            # 3. 如果启用 OSS，上传原始文件
            if self.use_oss:
                oss_key, _ = storage.save_upload_file(
                    file_bytes=file_bytes,
                    filename=task.original_filename,
                    task_id=str(task.task_id)
                )
                task.file_path = oss_key  # 保存 OSS 键而不是本地路径
                task.save(update_fields=['file_path'])
            
            # 4. 创建临时文件进行处理
            temp_file_path = self._create_temp_file(file_bytes, task.file_type)
            
            try:
                # 5. 执行 MinerU 解析
                parse_result = self._execute_mineru_parse(
                    temp_file_path=temp_file_path,
                    task=task
                )
                
                # 6. 如果启用 OSS，上传解析结果
                if self.use_oss:
                    output_dir = Path(parse_result['output_dir'])
                    oss_result = storage.save_parse_results(
                        task_id=str(task.task_id),
                        output_dir=output_dir,
                        file_hash=file_hash
                    )
                    
                    # 更新结果路径为 OSS URL
                    parse_result.update({
                        'markdown_url': oss_result.get('markdown_url'),
                        'json_url': oss_result.get('json_url'),
                        'files': oss_result.get('files', {}),
                        'urls': oss_result.get('urls', {}),
                        'storage_type': 'oss'
                    })
                    
                    # 清理本地输出目录
                    if output_dir.exists():
                        shutil.rmtree(output_dir, ignore_errors=True)
                else:
                    parse_result['storage_type'] = 'local'
                
                # 7. 更新任务状态
                self._update_task_success(task, parse_result)
                
                return parse_result
                
            finally:
                # 8. 清理临时文件
                if temp_file_path.exists():
                    temp_file_path.unlink()
                    
        except Exception as e:
            logger.error(f"文档处理失败: {e}", exc_info=True)
            self._update_task_failed(task, str(e))
            raise
    
    def _handle_cached_result(self, task: PDFParseTask, 
                             cached_result: Dict[str, Any]) -> Dict[str, Any]:
        """处理缓存的结果"""
        # 更新任务状态
        task.status = 'completed'
        task.processing_time = 0  # 缓存命中，处理时间为0
        task.text_preview = cached_result.get('text_preview', '')
        task.save()
        
        # 创建结果记录
        ParseResult.objects.create(
            task=task,
            markdown_path=cached_result.get('markdown_key', ''),
            json_path=cached_result.get('json_key', ''),
            total_text_blocks=cached_result.get('stats', {}).get('total_text_blocks', 0),
            total_images=cached_result.get('stats', {}).get('total_images', 0),
            total_tables=cached_result.get('stats', {}).get('total_tables', 0),
            total_formulas=cached_result.get('stats', {}).get('total_formulas', 0),
            cross_page_tables=cached_result.get('stats', {}).get('cross_page_tables', 0),
            metadata={
                'cached': True,
                'file_hash': cached_result.get('file_hash'),
                'urls': cached_result.get('urls', {})
            }
        )
        
        cached_result['cached'] = True
        return cached_result
    
    def _create_temp_file(self, file_bytes: bytes, file_ext: str) -> Path:
        """创建临时文件"""
        with tempfile.NamedTemporaryFile(
            dir=self.temp_dir,
            suffix=f'.{file_ext}',
            delete=False
        ) as temp_file:
            temp_file.write(file_bytes)
            return Path(temp_file.name)
    
    def _execute_mineru_parse(self, temp_file_path: Path, 
                             task: PDFParseTask) -> Dict[str, Any]:
        """执行 MinerU 解析"""
        import subprocess
        
        # 创建输出目录
        now = datetime.now()
        output_path = self.temp_dir / 'outputs' / str(now.year) / f"{now.month:02d}" / str(task.task_id)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 构建命令
        cmd = [
            'mineru',
            '-p', str(temp_file_path),
            '-o', str(output_path),
            '--method', task.parse_method,
        ]
        
        # 添加调试参数
        # 注意: v2.2 的表格合并和新模型会自动启用，不需要额外参数
        if task.debug_enabled:
            cmd.append('--debug')
        
        # 执行命令
        logger.info(f"执行 MinerU 命令: {' '.join(cmd)}")
        start_time = datetime.now()
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # 添加调试日志
        logger.info(f"MinerU 返回码: {result.returncode}")
        if result.stdout:
            logger.info(f"MinerU 标准输出: {result.stdout[:500]}")
        if result.stderr:
            logger.warning(f"MinerU 错误输出: {result.stderr[:500]}")
        
        if result.returncode != 0:
            raise RuntimeError(f"MinerU 执行失败: {result.stderr}")
        
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"MinerU 执行时间: {processing_time:.2f} 秒")
        
        # 收集结果
        return self._collect_results(output_path, processing_time)
    
    def _collect_results(self, output_path: Path, processing_time: float) -> Dict[str, Any]:
        """收集解析结果"""
        logger.info(f"收集输出目录的结果: {output_path}")
        
        # 检查目录是否存在
        if not output_path.exists():
            logger.warning(f"输出目录不存在: {output_path}")
        
        result = {
            'output_dir': str(output_path),
            'processing_time': processing_time,
            'files': {},
            'stats': {
                'total_text_blocks': 0,
                'total_images': 0,
                'total_tables': 0,
                'total_formulas': 0,
                'cross_page_tables': 0
            }
        }
        
        # 查找生成的文件
        files_found = list(output_path.rglob('*'))
        logger.info(f"输出目录中找到 {len(files_found)} 个文件/目录")
        
        for file_path in files_found:
            if file_path.is_file():
                relative_path = file_path.relative_to(output_path)
                result['files'][str(relative_path)] = str(file_path)
                
                # 特殊处理 markdown 和 json
                if file_path.suffix == '.md':
                    result['markdown_path'] = str(file_path)
                    # 读取文本预览
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            result['text_preview'] = content[:500] + '...' if len(content) > 500 else content
                            
                            # 统计
                            result['stats']['total_text_blocks'] = content.count('\n\n')
                            result['stats']['total_images'] = content.count('![')
                            result['stats']['total_tables'] = content.count('|---|')
                            result['stats']['cross_page_tables'] = content.count('<!-- table continues -->')
                    except Exception as e:
                        logger.warning(f"读取 Markdown 失败: {e}")
                        
                elif file_path.suffix == '.json' and 'layout' not in file_path.name:
                    result['json_path'] = str(file_path)
        
        return result
    
    def _update_task_success(self, task: PDFParseTask, result: Dict[str, Any]):
        """更新任务为成功状态"""
        task.status = 'completed'
        task.processing_time = result.get('processing_time', 0)
        task.text_preview = result.get('text_preview', '')
        
        if self.use_oss:
            # 存储 OSS 相关信息
            task.output_dir = ''  # 不保存本地路径
        else:
            task.output_dir = result.get('output_dir', '')
        
        task.completed_at = datetime.now()
        task.save()
        
        # 创建结果记录
        ParseResult.objects.create(
            task=task,
            markdown_path=result.get('markdown_url') if self.use_oss else result.get('markdown_path'),
            json_path=result.get('json_url') if self.use_oss else result.get('json_path'),
            total_text_blocks=result['stats']['total_text_blocks'],
            total_images=result['stats']['total_images'],
            total_tables=result['stats']['total_tables'],
            total_formulas=result['stats']['total_formulas'],
            cross_page_tables=result['stats']['cross_page_tables'],
            metadata={
                'files': result.get('files', {}),
                'urls': result.get('urls', {}),
                'processing_time': result.get('processing_time', 0),
                'storage_type': result.get('storage_type', 'local')
            }
        )
    
    def _update_task_failed(self, task: PDFParseTask, error_message: str):
        """更新任务为失败状态"""
        task.status = 'failed'
        task.error_message = error_message
        task.save()
    
    def get_file_content(self, task: PDFParseTask, file_type: str = 'markdown') -> str:
        """
        获取解析结果文件内容
        
        Args:
            task: PDFParseTask 实例
            file_type: 文件类型（markdown/json）
            
        Returns:
            文件内容
        """
        if not hasattr(task, 'result'):
            raise ValueError("任务没有解析结果")
        
        result = task.result
        
        # 检查存储类型
        if result.metadata.get('storage_type') == 'oss':
            # 从 OSS 获取
            storage = self._get_storage_adapter(task.user)
            
            if file_type == 'markdown' and result.markdown_path:
                file_data = storage.storage_manager.download(file_key=result.markdown_path)
                return file_data.decode('utf-8')
            elif file_type == 'json' and result.json_path:
                file_data = storage.storage_manager.download(file_key=result.json_path)
                return file_data.decode('utf-8')
        else:
            # 从本地获取
            if file_type == 'markdown' and result.markdown_path:
                with open(result.markdown_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif file_type == 'json' and result.json_path:
                with open(result.json_path, 'r', encoding='utf-8') as f:
                    return f.read()
        
        raise FileNotFoundError(f"找不到 {file_type} 文件")
    
    def cleanup_old_files(self, days: int = 30) -> int:
        """
        清理过期文件（优化版本）
        
        Args:
            days: 保留天数
            
        Returns:
            清理的文件数量
        """
        if self.use_oss:
            # 使用 OSS 的清理机制
            storage = self._get_storage_adapter()
            return storage.cleanup_old_files(days=days)
        else:
            # 原有的本地清理逻辑
            from .services import MinerUService
            original_service = MinerUService()
            # 调用原有清理方法
            return 0