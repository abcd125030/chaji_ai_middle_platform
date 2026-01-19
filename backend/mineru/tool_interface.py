"""
MinerU 工具接口
为 tools 应用提供与 pdf_converter 兼容的同步接口
"""
import base64
import logging
import os
from typing import Dict, Any
from pathlib import Path

from .services import OptimizedMinerUService
from pathlib import Path
import tempfile

logger = logging.getLogger('django')


def extract_pdf_content(pdf_base64: str, pdf_uuid: str) -> Dict[str, Any]:
    """
    提供与 customized.pdf_converter.pdf_content_extractor.extract_pdf_content 兼容的接口
    
    这是一个同步接口，直接调用 MinerUService 进行处理，不使用 Celery 异步任务
    
    Args:
        pdf_base64: Base64 编码的 PDF 内容
        pdf_uuid: PDF 的唯一标识符（用作任务 ID）
        
    Returns:
        {
            'status': 'success' | 'error',
            'content': str,  # Markdown 内容
            'images_count': int,
            'output_dir': str,
            'message': str  # 错误信息（仅在错误时）
        }
    """
    try:
        # 1. 解码 base64
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
        except Exception as e:
            logger.error(f"Base64 解码失败: {str(e)}")
            return {
                'status': 'error',
                'message': f'PDF 内容解码失败: {str(e)}',
                'content': '',
                'images_count': 0,
                'output_dir': ''
            }
        
        # 2. 验证文件（简单验证）
        if len(pdf_bytes) == 0:
            logger.error("PDF文件为空")
            return {
                'status': 'error',
                'message': 'PDF文件为空',
                'content': '',
                'images_count': 0,
                'output_dir': ''
            }
        
        # 检查是否是PDF文件（通过magic bytes）
        if not pdf_bytes.startswith(b'%PDF'):
            logger.error("不是有效的PDF文件")
            return {
                'status': 'error',
                'message': '不是有效的PDF文件',
                'content': '',
                'images_count': 0,
                'output_dir': ''
            }
        
        # 3. 创建临时文件并调用MinerU命令行
        logger.info(f"开始解析 PDF，任务 ID: {pdf_uuid}")
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(pdf_bytes)
                temp_file_path = temp_file.name
            
            # 创建输出目录
            from django.conf import settings
            output_base = Path(settings.MINERU_SETTINGS.get('OUTPUT_DIR', '/tmp/mineru/outputs'))
            output_dir = output_base / pdf_uuid
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 调用mineru命令行
            import subprocess
            cmd = [
                'mineru',
                '-p', temp_file_path,
                '-o', str(output_dir),
                '--method', 'auto'
            ]
            
            logger.info(f"执行MinerU命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # 清理临时文件
            os.unlink(temp_file_path)
            
            if result.returncode != 0:
                logger.error(f"MinerU执行失败: {result.stderr}")
                raise RuntimeError(f"MinerU执行失败: {result.stderr}")
            
            # 读取生成的markdown文件
            markdown_content = ""
            markdown_files = list(output_dir.rglob('*.md'))
            if markdown_files:
                with open(markdown_files[0], 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
            
            # 统计图片数量
            image_files = list(output_dir.rglob('*.png')) + list(output_dir.rglob('*.jpg'))
            images_count = len(image_files)
            
            # 返回成功结果
            return {
                'status': 'success',
                'content': markdown_content,
                'images_count': images_count,
                'output_dir': result.get('output_dir', ''),
                'message': 'PDF 解析成功'
            }
            
        except Exception as e:
            logger.error(f"PDF 解析过程出错: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'PDF 解析失败: {str(e)}',
                'content': '',
                'images_count': 0,
                'output_dir': ''
            }
            
    except Exception as e:
        logger.error(f"extract_pdf_content 出现未预期的错误: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'message': f'处理过程出现错误: {str(e)}',
            'content': '',
            'images_count': 0,
            'output_dir': ''
        }