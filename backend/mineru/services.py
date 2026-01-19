import os
import json
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('django')


class MinerUService:
    """MinerU PDF 解析服务 - 使用命令行接口"""
    
    def __init__(self):
        self.config = settings.MINERU_SETTINGS
        self.output_dir = Path(self.config['OUTPUT_DIR'])
        self.upload_dir = Path(self.config['UPLOAD_DIR'])
        self.temp_dir = Path(self.config['TEMP_DIR'])
        
        # 确保目录存在
        for dir_path in [self.output_dir, self.upload_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
    def check_mineru_command(self):
        """检查 mineru 命令是否可用"""
        try:
            result = subprocess.run(['mineru', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"MinerU 命令行工具可用: {result.stdout.strip()}")
                return True
            else:
                logger.error("MinerU 命令行工具不可用")
                return False
        except FileNotFoundError:
            logger.error("未找到 mineru 命令，请确保已安装并在 PATH 中")
            return False
    
    def convert_to_pdf(self, file_bytes: bytes, file_ext: str) -> bytes:
        """将其他格式转换为 PDF"""
        if file_ext == 'pdf':
            return file_bytes
        
        # 对于非 PDF 文件，MinerU 命令行工具会自动处理转换
        # 这里直接返回原始文件，让 MinerU 处理
        logger.info(f"文件类型 {file_ext} 将由 MinerU 自动转换")
        return file_bytes
    
    def parse_document(self, file_bytes: bytes, file_ext: str, 
                      task_id: str, parse_method: str = 'auto',
                      debug_enabled: bool = False,
                      enable_table_merge: bool = True,
                      use_new_table_model: bool = True) -> Dict[str, Any]:
        """通过命令行解析文档
        
        Args:
            file_bytes: 文件字节内容
            file_ext: 文件扩展名
            task_id: 任务ID
            parse_method: 解析方法 (auto/ocr/txt)
            debug_enabled: 是否启用调试模式
            enable_table_merge: 是否启用跨页表格合并 (v2.2新特性)
            use_new_table_model: 是否使用新的表格识别模型 (v2.2新特性)
        """
        temp_file = None
        output_path = None
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                dir=self.temp_dir, 
                suffix=f'.{file_ext}', 
                delete=False
            ) as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = temp_file.name
            
            # 创建输出目录
            now = datetime.now()
            output_path = self.output_dir / str(now.year) / f"{now.month:02d}" / task_id
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 构建命令
            cmd = [
                'mineru',  # 命令行工具
                'pdf',  # 子命令
                '-p', temp_file_path,  # 输入文件
                '-o', str(output_path),  # 输出目录
                '--method', parse_method,  # 解析方法
            ]
            
            # v2.2 新特性：跨页表格合并
            if enable_table_merge:
                cmd.extend(['--table-merge', 'true'])
            
            # v2.2 新特性：使用新的表格识别模型
            if use_new_table_model:
                cmd.extend(['--table-model', 'new'])
            
            if debug_enabled:
                cmd.append('--debug')
            
            # 执行命令
            logger.info(f"执行 MinerU 命令: {' '.join(cmd)}")
            start_time = datetime.now()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f"MinerU 执行失败: {result.stderr}")
                raise RuntimeError(f"MinerU 执行失败: {result.stderr}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"MinerU 执行成功，耗时: {processing_time:.2f}秒")
            
            # 收集结果
            return self._collect_results(output_path, processing_time)
            
        except subprocess.TimeoutExpired:
            logger.error(f"MinerU 执行超时，任务ID: {task_id}")
            raise RuntimeError("PDF 解析超时")
            
        except Exception as e:
            logger.error(f"文档解析失败，任务ID: {task_id}, 错误: {str(e)}")
            # 清理输出目录
            if output_path and output_path.exists():
                shutil.rmtree(output_path, ignore_errors=True)
            raise
            
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def _collect_results(self, output_path: Path, processing_time: float) -> Dict[str, Any]:
        """收集解析结果"""
        result = {
            'output_dir': str(output_path),
            'processing_time': processing_time,
            'files': {},
            'stats': {
                'total_text_blocks': 0,
                'total_images': 0,
                'total_tables': 0,
                'total_formulas': 0,
            }
        }
        
        # 查找生成的文件
        for file_path in output_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(output_path)
                result['files'][str(relative_path)] = str(file_path)
                
                # 特殊处理 markdown 和 json 文件
                if file_path.suffix == '.md':
                    result['markdown_path'] = str(file_path)
                elif file_path.suffix == '.json' and 'layout' not in file_path.name:
                    result['json_path'] = str(file_path)
        
        # 提取文本预览（从 markdown 文件）
        if 'markdown_path' in result and Path(result['markdown_path']).exists():
            try:
                with open(result['markdown_path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 提取前 500 个字符作为预览
                    result['text_preview'] = content[:500] + '...' if len(content) > 500 else content
                    
                    # 简单统计
                    result['stats']['total_text_blocks'] = content.count('\n\n')
                    result['stats']['total_images'] = content.count('![')
                    result['stats']['total_tables'] = content.count('|---|')
                    
                    # v2.2 新增：检测跨页表格
                    result['stats']['cross_page_tables'] = content.count('<!-- table continues -->')
                    
            except Exception as e:
                logger.warning(f"读取 Markdown 文件失败: {e}")
        
        # 统计图片文件
        if 'files' in result:
            image_count = sum(1 for f in result['files'] 
                            if any(f.endswith(ext) for ext in ['.png', '.jpg', '.jpeg']))
            result['stats']['total_images'] = max(result['stats']['total_images'], image_count)
        
        return result
    
    def get_output_files(self, task_id: str, year: int, month: int) -> Dict[str, Any]:
        """获取任务的输出文件"""
        output_path = self.output_dir / str(year) / f"{month:02d}" / task_id
        
        if not output_path.exists():
            raise FileNotFoundError(f"任务输出目录不存在: {task_id}")
        
        return self._collect_results(output_path, 0)
    
    def clean_memory(self):
        """清理内存（命令行版本不需要特殊清理）"""
        pass
    
    def save_uploaded_file(self, file_bytes: bytes, filename: str, 
                          task_id: str) -> str:
        """保存上传的文件"""
        now = datetime.now()
        file_dir = self.upload_dir / str(now.year) / f"{now.month:02d}" / task_id
        file_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = file_dir / filename
        file_path.write_bytes(file_bytes)
        
        return str(file_path)
    
    def validate_file(self, file_bytes: bytes) -> Tuple[bool, str, str]:
        """验证文件类型和大小"""
        import filetype
        
        # 检查文件大小
        file_size = len(file_bytes)
        max_size = self.config['MAX_FILE_SIZE']
        if file_size > max_size:
            return False, f"文件大小超过限制（最大 {max_size // (1024*1024)}MB）", ""
        
        # 检查文件类型
        file_type = filetype.guess(file_bytes)
        if not file_type:
            return False, "无法识别的文件类型", ""
        
        file_ext = file_type.extension
        if file_ext not in self.config['ALLOWED_FILE_TYPES']:
            return False, f"不支持的文件类型: {file_ext}", ""
        
        return True, "OK", file_ext