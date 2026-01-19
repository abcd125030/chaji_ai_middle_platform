"""
Toolkit应用服务层 - 提供文档处理等工具功能
"""
import os
import logging
from typing import Dict, Any, Optional
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

from tools.preprocessors.core.pdf_complexity_analyzer import (
    AdvancedPDFComplexityAnalyzer,
    PDFAnalysisResult
)
from tools.preprocessors.parsers.pdf_parser import PDFParserTool
from tools.preprocessors.parsers.docx_parser import DOCXParserTool
from webapps.toolkit.image_handler import DocumentImageHandler

logger = logging.getLogger('django')


class PDFAnalyzerService:
    """PDF文档分析服务"""
    
    def __init__(self):
        self.analyzer = AdvancedPDFComplexityAnalyzer()
    
    def analyze_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        分析PDF文档复杂度
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            分析结果字典
        """
        try:
            logger.info(f"开始分析PDF文档: {file_path}")
            
            # 调用分析器
            result: PDFAnalysisResult = self.analyzer.analyze_pdf_complexity(file_path)
            
            # 转换为字典格式
            analysis_data = {
                'file_path': result.file_path,
                'file_size': result.file_size,
                'file_size_mb': round(result.file_size / (1024 * 1024), 2),
                'page_count': result.page_count,
                
                # 基础指标
                'is_encrypted': result.is_encrypted,
                'has_embedded_fonts': result.has_embedded_fonts,
                'font_diversity': result.font_diversity,
                'total_text_length': result.total_text_length,
                'total_images': result.total_images,
                
                # 分布指标
                'avg_text_per_page': round(result.avg_text_per_page, 2),
                'text_variance': round(result.text_variance, 2),
                'text_consistency_score': round(result.text_consistency_score, 2),
                'image_density': round(result.image_density, 2),
                
                # 质量指标
                'likely_scanned_pages': result.likely_scanned_pages,
                'text_rich_pages': result.text_rich_pages,
                'mixed_content_pages': result.mixed_content_pages,
                
                # 决策支持
                'complexity_score': round(result.complexity_score, 2),
                'processing_recommendation': result.processing_recommendation,
                'confidence': round(result.confidence, 2),
                'reasons': result.reasons,
                
                # 推荐处理方式的中文描述
                'recommendation_desc': self._get_recommendation_desc(result.processing_recommendation),
                'complexity_level': self._get_complexity_level(result.complexity_score)
            }
            
            logger.info(f"PDF分析完成: 复杂度评分={analysis_data['complexity_score']}, 推荐={analysis_data['processing_recommendation']}")
            
            return {
                'status': 'success',
                'data': analysis_data
            }
            
        except FileNotFoundError as e:
            logger.error(f"PDF文件不存在: {str(e)}")
            return {
                'status': 'error',
                'message': f"文件不存在: {file_path}"
            }
        except ImportError as e:
            logger.error(f"缺少依赖库: {str(e)}")
            return {
                'status': 'error',
                'message': "系统缺少PDF处理依赖，请联系管理员"
            }
        except Exception as e:
            logger.error(f"PDF分析失败: {str(e)}")
            return {
                'status': 'error',
                'message': f"分析失败: {str(e)}"
            }
    
    def analyze_uploaded_pdf(self, uploaded_file: UploadedFile) -> Dict[str, Any]:
        """
        分析上传的PDF文件
        
        Args:
            uploaded_file: Django上传文件对象
            
        Returns:
            分析结果字典
        """
        # 创建临时目录
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'toolkit_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存临时文件
        temp_path = os.path.join(temp_dir, uploaded_file.name)
        
        try:
            # 写入临时文件
            with open(temp_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # 分析文件
            result = self.analyze_pdf(temp_path)
            
            # 添加原始文件名
            if result['status'] == 'success':
                result['data']['original_filename'] = uploaded_file.name
            
            return result
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"已清理临时文件: {temp_path}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")
    
    def _get_recommendation_desc(self, recommendation: str) -> str:
        """获取推荐处理方式的中文描述"""
        descriptions = {
            'internal': '建议使用内部处理器（PyPDF2）',
            'external': '建议使用外部API（如Adobe API）',
            'hybrid': '建议先尝试内部处理，失败后使用外部API'
        }
        return descriptions.get(recommendation, '未知')
    
    def _get_complexity_level(self, score: float) -> str:
        """获取复杂度级别描述"""
        if score >= 8:
            return '极高'
        elif score >= 6:
            return '高'
        elif score >= 4:
            return '中等'
        elif score >= 2:
            return '低'
        else:
            return '极低'


class DocumentConverterService:
    """文档转换服务 - 处理PDF和DOCX转Markdown"""
    
    def __init__(self):
        self.pdf_parser = PDFParserTool()
        self.docx_parser = DOCXParserTool()
    
    def convert_pdf_to_markdown(self, file_path: str, use_external_api: bool = False) -> Dict[str, Any]:
        """
        将PDF转换为Markdown
        
        Args:
            file_path: PDF文件路径
            use_external_api: 是否使用外部API（根据复杂度分析结果决定）
            
        Returns:
            转换结果字典
        """
        try:
            logger.info(f"开始转换PDF文档: {file_path}")
            
            # 调用PDF解析工具
            mode = "api" if use_external_api else "direct"
            result = self.pdf_parser.execute({
                "file_path": file_path,
                "mode": mode
            })
            
            if result.get("status") == "success":
                markdown_content = result.get("content", result.get("markdown", ""))
                response_data = {
                    'status': 'success',
                    'data': {
                        'markdown': markdown_content,
                        'conversion_mode': mode
                    }
                }
                
                # 如果有分页信息，添加到响应中
                if 'page_info' in result:
                    response_data['data']['page_info'] = result['page_info']
                    
                return response_data
            else:
                # 如果外部API失败，尝试降级到内部处理
                if use_external_api and "API调用失败" in result.get('message', ''):
                    logger.warning(f"外部API失败，降级到内部处理: {result.get('message')}")
                    # 递归调用，使用内部处理
                    return self.convert_pdf_to_markdown(file_path, use_external_api=False)
                
                return {
                    'status': 'error',
                    'message': result.get('message', '转换失败')
                }
                
        except Exception as e:
            logger.error(f"PDF转换失败: {str(e)}")
            # 如果是外部API异常，尝试内部处理
            if use_external_api:
                logger.warning(f"外部API异常，降级到内部处理: {str(e)}")
                try:
                    return self.convert_pdf_to_markdown(file_path, use_external_api=False)
                except Exception as inner_e:
                    logger.error(f"内部处理也失败: {str(inner_e)}")
                    return {
                        'status': 'error',
                        'message': f'转换失败（降级后）: {str(inner_e)}'
                    }
            
            return {
                'status': 'error',
                'message': f'转换失败: {str(e)}'
            }
    
    def convert_docx_to_markdown(self, file_path: str, extract_images: bool = True) -> Dict[str, Any]:
        """
        将DOCX转换为Markdown
        
        Args:
            file_path: DOCX文件路径
            extract_images: 是否提取图片
            
        Returns:
            转换结果字典
        """
        try:
            logger.info(f"开始转换DOCX文档: {file_path}")
            
            # 初始化图片处理器
            doc_id = None
            extracted_images = []
            image_handler = None
            
            if extract_images:
                try:
                    image_handler = DocumentImageHandler()
                    doc_id = image_handler.generate_document_id()
                    extracted_images = image_handler.extract_docx_images(file_path, doc_id)
                    logger.info(f"DOCX提取了 {len(extracted_images)} 张图片")
                except Exception as e:
                    logger.warning(f"DOCX图片提取失败: {str(e)}")
            
            # 调用DOCX解析工具
            result = self.docx_parser.execute({
                "file_path": file_path,
                "extract_images": False,  # 图片已经通过image_handler处理
                "include_metadata": False,
                "preserve_formatting": True
            })
            
            if result.get("status") == "success":
                markdown_content = result.get("markdown", result.get("content", ""))
                
                # 插入图片到Markdown
                if extracted_images and image_handler:
                    markdown_content = image_handler.insert_images_to_markdown(
                        markdown_content, extracted_images, 'append'
                    )
                
                response_data = {
                    'status': 'success',
                    'data': {
                        'markdown': markdown_content,
                        'original_filename': os.path.basename(file_path)
                    }
                }
                
                # 添加图片信息
                if extracted_images:
                    response_data['data']['images'] = extracted_images
                    response_data['data']['doc_id'] = doc_id
                
                return response_data
            else:
                return {
                    'status': 'error',
                    'message': result.get('message', '转换失败')
                }
                
        except Exception as e:
            logger.error(f"DOCX转换失败: {str(e)}")
            return {
                'status': 'error',
                'message': f'转换失败: {str(e)}'
            }
    
    def convert_uploaded_file(self, uploaded_file: UploadedFile) -> Dict[str, Any]:
        """
        转换上传的文件为Markdown
        
        Args:
            uploaded_file: Django上传文件对象
            
        Returns:
            转换结果字典
        """
        # 创建临时目录
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'toolkit_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存临时文件
        temp_path = os.path.join(temp_dir, uploaded_file.name)
        
        try:
            # 写入临时文件
            with open(temp_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # 根据文件类型选择转换方法
            file_name = uploaded_file.name.lower()
            
            if file_name.endswith('.pdf'):
                # 先分析PDF复杂度，决定使用哪种转换方式
                analyzer = AdvancedPDFComplexityAnalyzer()
                try:
                    analysis_result = analyzer.analyze_pdf_complexity(temp_path)
                    use_external = analysis_result.processing_recommendation in ['external', 'hybrid']
                    logger.info(f"PDF复杂度分析：评分={analysis_result.complexity_score}, 建议={analysis_result.processing_recommendation}")
                except Exception as e:
                    logger.warning(f"PDF复杂度分析失败，默认使用内部处理: {str(e)}")
                    use_external = False
                
                result = self.convert_pdf_to_markdown(temp_path, use_external)
            
            elif file_name.endswith(('.docx', '.doc')):
                result = self.convert_docx_to_markdown(temp_path)
            
            else:
                result = {
                    'status': 'error',
                    'message': f'不支持的文件格式: {uploaded_file.name}'
                }
            
            # 添加原始文件名到结果
            if result['status'] == 'success':
                result['data']['original_filename'] = uploaded_file.name
            
            return result
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"已清理临时文件: {temp_path}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")


class DocumentProcessorService:
    """文档处理服务 - 统一管理各种文档处理功能"""
    
    def __init__(self):
        self.pdf_analyzer = PDFAnalyzerService()
        self.converter = DocumentConverterService()
    
    def get_supported_formats(self) -> Dict[str, Any]:
        """获取支持的文档格式信息"""
        return {
            'formats': [
                {
                    'extension': '.pdf',
                    'name': 'PDF文档',
                    'mime_type': 'application/pdf',
                    'features': ['复杂度分析', '文本提取', '图像分析', '字体检测']
                },
                # 未来可扩展其他格式
                {
                    'extension': '.docx',
                    'name': 'Word文档',
                    'mime_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'features': ['即将支持']
                },
                {
                    'extension': '.xlsx',
                    'name': 'Excel表格',
                    'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'features': ['即将支持']
                }
            ],
            'max_file_size_mb': 100,
            'features': {
                'pdf_analysis': True,
                'text_extraction': True,
                'ocr_support': False,  # 未来支持
                'format_conversion': False  # 未来支持
            }
        }
    
    def process_document(self, file_path: str, file_type: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        统一的文档处理入口
        
        Args:
            file_path: 文件路径
            file_type: 文件类型
            options: 处理选项
            
        Returns:
            处理结果
        """
        options = options or {}
        
        if file_type.lower() in ['.pdf', 'pdf']:
            return self.pdf_analyzer.analyze_pdf(file_path)
        else:
            return {
                'status': 'error',
                'message': f'暂不支持 {file_type} 格式的文档处理'
            }