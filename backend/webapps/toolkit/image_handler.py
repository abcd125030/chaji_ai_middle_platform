"""
文档图片处理服务
处理PDF、DOCX、PPTX等文档中的图片提取和存储
"""
import os
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image
import base64
from django.conf import settings

logger = logging.getLogger('django')

class DocumentImageHandler:
    """文档图片处理器"""
    
    def __init__(self):
        self.media_root = settings.MEDIA_ROOT
        self.media_url = settings.MEDIA_URL
        self.image_base_dir = 'document_images'
        
    def generate_document_id(self) -> str:
        """生成文档唯一ID"""
        return str(uuid.uuid4())
    
    def get_image_storage_path(self, doc_type: str, doc_id: str) -> Path:
        """
        获取图片存储路径
        
        Args:
            doc_type: 文档类型（pdf/docx/pptx等）
            doc_id: 文档唯一ID
            
        Returns:
            图片存储的完整路径
        """
        now = datetime.now()
        path = Path(self.media_root) / self.image_base_dir / str(now.year) / f"{now.month:02d}" / doc_type / doc_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def save_image_from_bytes(self, image_data: bytes, doc_type: str, doc_id: str, 
                              image_index: int, ext: str = 'png') -> Dict[str, Any]:
        """
        保存图片字节数据到文件系统
        
        Args:
            image_data: 图片字节数据
            doc_type: 文档类型
            doc_id: 文档ID
            image_index: 图片索引
            ext: 图片扩展名
            
        Returns:
            包含图片信息的字典
        """
        try:
            storage_path = self.get_image_storage_path(doc_type, doc_id)
            filename = f"image_{image_index}.{ext}"
            file_path = storage_path / filename
            
            # 保存图片文件
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            # 生成相对URL路径
            now = datetime.now()
            relative_url = f"{self.media_url}{self.image_base_dir}/{now.year}/{now.month:02d}/{doc_type}/{doc_id}/{filename}"
            
            # 获取图片尺寸
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
            except:
                width, height = None, None
            
            return {
                'index': image_index,
                'filename': filename,
                'path': str(file_path),
                'url': relative_url,
                'size': len(image_data),
                'width': width,
                'height': height,
                'format': ext
            }
            
        except Exception as e:
            logger.error(f"保存图片失败: {str(e)}")
            raise
    
    def save_image_from_base64(self, base64_data: str, doc_type: str, doc_id: str,
                                image_index: int, ext: str = 'png') -> Dict[str, Any]:
        """
        保存base64编码的图片
        
        Args:
            base64_data: base64编码的图片数据
            doc_type: 文档类型
            doc_id: 文档ID
            image_index: 图片索引
            ext: 图片扩展名
            
        Returns:
            包含图片信息的字典
        """
        try:
            # 解码base64数据
            image_data = base64.b64decode(base64_data)
            return self.save_image_from_bytes(image_data, doc_type, doc_id, image_index, ext)
        except Exception as e:
            logger.error(f"解码base64图片失败: {str(e)}")
            raise
    
    def extract_pdf_images(self, pdf_path: str, doc_id: str) -> List[Dict[str, Any]]:
        """
        从PDF文件中提取图片
        
        Args:
            pdf_path: PDF文件路径
            doc_id: 文档ID
            
        Returns:
            提取的图片信息列表
        """
        images = []
        
        try:
            # 尝试使用PyMuPDF（fitz）
            import fitz  # PyMuPDF
            
            pdf_document = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    # 获取图片引用
                    xref = img[0]
                    
                    # 提取图片数据
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # 保存图片
                    global_index = len(images) + 1
                    image_info = self.save_image_from_bytes(
                        image_bytes, 'pdf', doc_id, global_index, image_ext
                    )
                    image_info['page'] = page_num + 1
                    image_info['page_index'] = img_index + 1
                    
                    images.append(image_info)
                    
                    logger.info(f"提取PDF第{page_num + 1}页第{img_index + 1}张图片")
            
            pdf_document.close()
            
        except ImportError:
            logger.warning("PyMuPDF未安装，尝试使用pdf2image")
            
            try:
                # 尝试使用pdf2image
                from pdf2image import convert_from_path
                
                # 将PDF页面转换为图片
                pages = convert_from_path(pdf_path, dpi=150)
                
                for i, page in enumerate(pages):
                    # 保存页面为图片
                    import io
                    img_byte_arr = io.BytesIO()
                    page.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    image_info = self.save_image_from_bytes(
                        img_byte_arr, 'pdf', doc_id, i + 1, 'png'
                    )
                    image_info['page'] = i + 1
                    image_info['is_page_snapshot'] = True  # 标记这是整页截图
                    
                    images.append(image_info)
                    
                    logger.info(f"转换PDF第{i + 1}页为图片")
                    
            except ImportError:
                logger.error("pdf2image未安装，无法提取PDF图片")
                
        except Exception as e:
            logger.error(f"提取PDF图片失败: {str(e)}")
            
        return images
    
    def extract_docx_images(self, docx_path: str, doc_id: str) -> List[Dict[str, Any]]:
        """
        从DOCX文件中提取图片
        
        Args:
            docx_path: DOCX文件路径
            doc_id: 文档ID
            
        Returns:
            提取的图片信息列表
        """
        images = []
        
        try:
            from docx import Document
            import zipfile
            
            doc = Document(docx_path)
            
            # DOCX文件实际上是ZIP文件，包含图片在word/media目录下
            with zipfile.ZipFile(docx_path, 'r') as zip_file:
                media_files = [f for f in zip_file.namelist() if f.startswith('word/media/')]
                
                for idx, media_file in enumerate(media_files):
                    # 提取文件扩展名
                    ext = media_file.split('.')[-1].lower()
                    if ext not in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
                        continue
                    
                    # 读取图片数据
                    image_data = zip_file.read(media_file)
                    
                    # 保存图片
                    image_info = self.save_image_from_bytes(
                        image_data, 'docx', doc_id, idx + 1, ext
                    )
                    
                    images.append(image_info)
                    
                    logger.info(f"提取DOCX图片: {media_file}")
                    
        except Exception as e:
            logger.error(f"提取DOCX图片失败: {str(e)}")
            
        return images
    
    def insert_images_to_markdown(self, markdown_content: str, images: List[Dict[str, Any]], 
                                  insert_mode: str = 'append') -> str:
        """
        将图片链接插入到Markdown内容中
        
        Args:
            markdown_content: 原始Markdown内容
            images: 图片信息列表
            insert_mode: 插入模式（'append': 追加到末尾, 'inline': 在相应位置插入）
            
        Returns:
            包含图片链接的Markdown内容
        """
        if not images:
            return markdown_content
        
        if insert_mode == 'append':
            # 在末尾追加所有图片
            image_section = "\n\n## 文档图片\n\n"
            for img in images:
                alt_text = f"图片{img['index']}"
                if img.get('page'):
                    alt_text += f" (第{img['page']}页)"
                image_section += f"![{alt_text}]({img['url']})\n\n"
            
            return markdown_content + image_section
            
        elif insert_mode == 'inline':
            # TODO: 实现智能插入，在相应的页面位置插入图片
            # 目前先使用append模式
            return self.insert_images_to_markdown(markdown_content, images, 'append')
        
        return markdown_content
    
    def cleanup_old_images(self, days: int = 30):
        """
        清理旧的图片文件
        
        Args:
            days: 保留最近多少天的图片
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            base_path = Path(self.media_root) / self.image_base_dir
            if not base_path.exists():
                return
            
            # 遍历年份目录
            for year_dir in base_path.iterdir():
                if not year_dir.is_dir():
                    continue
                
                try:
                    year = int(year_dir.name)
                    if year < cutoff_date.year:
                        # 删除整个年份目录
                        shutil.rmtree(year_dir)
                        logger.info(f"删除旧图片目录: {year_dir}")
                    elif year == cutoff_date.year:
                        # 检查月份
                        for month_dir in year_dir.iterdir():
                            if not month_dir.is_dir():
                                continue
                            
                            try:
                                month = int(month_dir.name)
                                if month < cutoff_date.month:
                                    shutil.rmtree(month_dir)
                                    logger.info(f"删除旧图片目录: {month_dir}")
                            except ValueError:
                                continue
                                
                except ValueError:
                    continue
                    
        except Exception as e:
            logger.error(f"清理旧图片失败: {str(e)}")