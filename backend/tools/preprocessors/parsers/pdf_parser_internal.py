"""
PDF解析器 - 内部直接调用版本
直接使用pdf_converter模块的功能，避免HTTP调用的开销
"""
import os
import base64
import uuid
import logging
from typing import Dict, Any, Optional, Tuple
from tools.core.base import BaseTool
from tools.core.exceptions import ToolExecutionError
from ..core.pdf_complexity_analyzer import analyze_pdf_complexity, should_use_external_api
try:
    from webapps.toolkit.image_handler import DocumentImageHandler
except ImportError:
    DocumentImageHandler = None

logger = logging.getLogger(__name__)

class PDFParserInternalTool(BaseTool):
    """
    PDF文档解析工具（内部版本）：直接调用pdf_converter服务。
    这个版本直接在进程内调用pdf_converter的功能，避免了HTTP调用的开销。
    """
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要解析的PDF文件路径"
                },
                "use_external_api": {
                    "type": "boolean",
                    "description": "是否使用外部API服务（需要8002端口服务）",
                    "default": True
                }
            },
            "required": ["file_path"]
        }

    def execute(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        file_path = tool_input.get('file_path')
        use_external_api = tool_input.get('use_external_api', None)  # None表示自动决策
        
        if not file_path:
            return {"status": "error", "message": "文件路径未提供。"}
        
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"文件不存在: {file_path}"}
        
        if not file_path.lower().endswith('.pdf'):
            return {"status": "error", "message": f"不支持的文件格式，只支持.pdf: {file_path}"}
        
        try:
            # 读取文件并转换为base64
            with open(file_path, 'rb') as f:
                pdf_content = f.read()
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            pdf_uuid = str(uuid.uuid4())
            
            # 自动决策是否使用外部API
            processing_mode = 'internal'  # 默认模式
            
            if use_external_api is None:
                use_external_api, processing_mode = self._should_use_external_api(file_path, len(pdf_content))
                logger.info(f"自动决策: {'使用外部API' if use_external_api else '使用内部处理'} (模式: {processing_mode})")
            else:
                # 用户指定了模式
                processing_mode = 'external' if use_external_api else 'internal'
            
            if use_external_api:
                # 尝试使用外部API服务
                try:
                    result = self._try_external_processing(pdf_base64, pdf_uuid, file_path)
                    
                    # 如果成功，直接返回
                    if result['status'] == 'success':
                        logger.info(f"外部API处理成功 (模式: {processing_mode})")
                        return result
                    else:
                        raise Exception(result.get('message', '外部API返回错误'))
                        
                except Exception as e:
                    logger.error(f"PDF解析服务调用失败: {str(e)}")
                    
                    # 根据模式决定是否降级
                    if processing_mode == 'hybrid':
                        logger.info("混合模式: 外部API失败，降级到内部处理")
                        return self._parse_pdf_fallback(file_path)
                    else:
                        # external模式下，外部API失败则返回错误
                        return {
                            "status": "error",
                            "message": f"外部PDF解析服务不可用: {str(e)}",
                            "file_path": file_path,
                            "processing_mode": processing_mode
                        }
            else:
                # 使用内部处理方案
                logger.info(f"使用内部处理 (模式: {processing_mode})")
                return self._parse_pdf_fallback(file_path)
                
        except Exception as e:
            logger.error(f"PDF解析失败: {str(e)}", exc_info=True)
            return {"status": "error", "message": f"PDF解析失败: {str(e)}", "file_path": file_path}
    
    def _parse_pdf_fallback(self, file_path: str, extract_images: bool = True) -> Dict[str, Any]:
        """备用PDF解析方案，使用PyPDF2或pdfplumber，支持分页
        
        Args:
            file_path: PDF文件路径
            extract_images: 是否提取图片
        """
        try:
            # 初始化图片处理器
            image_handler = None
            doc_id = None
            extracted_images = []
            
            if extract_images and DocumentImageHandler:
                try:
                    image_handler = DocumentImageHandler()
                    doc_id = image_handler.generate_document_id()
                    extracted_images = image_handler.extract_pdf_images(file_path, doc_id)
                    logger.info(f"提取了 {len(extracted_images)} 张图片，文档ID: {doc_id}")
                except Exception as e:
                    logger.warning(f"图片提取失败，继续处理文本: {str(e)}")
            
            # 优先尝试使用pdfplumber（更准确）
            try:
                import pdfplumber
                
                text_content = []
                page_markers = []  # 记录页面信息
                current_position = 0
                
                with pdfplumber.open(file_path) as pdf:
                    total_pages = len(pdf.pages)
                    
                    for i, page in enumerate(pdf.pages):
                        page_num = i + 1
                        
                        # 添加分页标记
                        if i > 0:  # 不在第一页前添加标记
                            text_content.append(f"\n<!-- PAGE_BREAK_{page_num} -->\n")
                        
                        # 提取页面标题（取第一行作为标题，如果有的话）
                        page_text = page.extract_text()
                        page_title = f"第 {page_num} 页"
                        
                        if page_text:
                            # 尝试提取页面的第一个有意义的标题
                            first_lines = page_text.split('\n')[:3]
                            for line in first_lines:
                                line = line.strip()
                                if line and len(line) > 2 and len(line) < 100:
                                    page_title = line
                                    break
                            
                            text_content.append(f"## {page_title}\n\n{page_text}")
                        
                        # 记录页面标记信息
                        page_markers.append({
                            "page": page_num,
                            "position": current_position,
                            "title": page_title
                        })
                        current_position += 1
                        
                        # 提取表格
                        tables = page.extract_tables()
                        for j, table in enumerate(tables):
                            if table:
                                table_md = self._table_to_markdown(table)
                                text_content.append(f"### 表格 {j + 1}\n\n{table_md}")
                
                markdown_content = "\n\n".join(text_content)
                
                # 插入图片到Markdown
                if extracted_images and image_handler:
                    markdown_content = image_handler.insert_images_to_markdown(
                        markdown_content, extracted_images, 'append'
                    )
                
            except ImportError:
                # 降级到PyPDF2
                import PyPDF2
                
                text_content = []
                page_markers = []
                current_position = 0
                
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    total_pages = len(pdf_reader.pages)
                    
                    for page_num in range(total_pages):
                        actual_page = page_num + 1
                        
                        # 添加分页标记
                        if page_num > 0:
                            text_content.append(f"\n<!-- PAGE_BREAK_{actual_page} -->\n")
                        
                        page = pdf_reader.pages[page_num]
                        page_text = page.extract_text()
                        page_title = f"第 {actual_page} 页"
                        
                        if page_text:
                            # 尝试提取页面标题
                            first_lines = page_text.split('\n')[:3]
                            for line in first_lines:
                                line = line.strip()
                                if line and len(line) > 2 and len(line) < 100:
                                    page_title = line
                                    break
                            
                            text_content.append(f"## {page_title}\n\n{page_text}")
                        
                        # 记录页面标记信息
                        page_markers.append({
                            "page": actual_page,
                            "position": current_position,
                            "title": page_title
                        })
                        current_position += 1
                
                markdown_content = "\n\n".join(text_content)
                
                # 插入图片到Markdown
                if extracted_images and image_handler:
                    markdown_content = image_handler.insert_images_to_markdown(
                        markdown_content, extracted_images, 'append'
                    )
            
            return {
                "status": "success",
                "message": f"文件 '{os.path.basename(file_path)}' 已使用内部方案解析。",
                "file_path": file_path,
                "content": markdown_content,
                "markdown_content": markdown_content,
                "processing_method": "internal_fallback",
                "page_info": {
                    "total_pages": total_pages,
                    "page_markers": page_markers
                },
                "images": extracted_images,
                "doc_id": doc_id
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "备用解析方案需要安装PDF处理库: pip install pdfplumber 或 pip install PyPDF2"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"备用PDF解析失败: {str(e)}"
            }
    
    def _read_parsed_results(self, output_dir: str) -> str:
        """读取解析后的结果文件"""
        result_content = []
        
        # pdf_converter 返回的目录结构通常是：
        # output_dir/
        #   └── auto/
        #       ├── images/
        #       │   └── *.png/jpg
        #       └── *.md
        
        auto_dir = os.path.join(output_dir, 'auto')
        search_dirs = [output_dir]  # 默认搜索根目录
        
        # 如果存在 auto 子目录，优先搜索
        if os.path.exists(auto_dir):
            search_dirs.insert(0, auto_dir)
            logger.info(f"发现 auto 子目录，优先搜索: {auto_dir}")
        
        md_files_found = False
        
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
                
            # 查找所有 .md 文件
            md_files = []
            for file_name in os.listdir(search_dir):
                if file_name.endswith('.md'):
                    md_files.append(file_name)
                    md_files_found = True
            
            if md_files:
                # 按文件名排序，确保顺序
                md_files.sort()
                logger.info(f"在 {search_dir} 找到 {len(md_files)} 个 MD 文件")
                
                for file_name in md_files:
                    file_path = os.path.join(search_dir, file_name)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 如果有多个 MD 文件，添加文件标题
                        if len(md_files) > 1:
                            result_content.append(f"### {file_name}\n\n{content}")
                        else:
                            result_content.append(content)
                            
                    except Exception as e:
                        logger.warning(f"读取文件 {file_path} 失败: {str(e)}")
                
                # 如果找到了 MD 文件就停止搜索
                if md_files_found:
                    break
        
        # 如果没有找到 MD 文件，尝试读取其他文本文件
        if not md_files_found:
            logger.warning(f"未在 {output_dir} 找到 MD 文件，尝试读取其他文本文件")
            
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                    
                files = sorted(os.listdir(search_dir))
                for file_name in files:
                    file_path = os.path.join(search_dir, file_name)
                    
                    # 跳过目录
                    if os.path.isdir(file_path):
                        continue
                    
                    # 读取文本类文件
                    if file_name.endswith(('.txt', '.json')):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            if file_name.endswith('.json'):
                                try:
                                    import json
                                    data = json.loads(content)
                                    content = json.dumps(data, ensure_ascii=False, indent=2)
                                except:
                                    pass
                            
                            result_content.append(f"### {file_name}\n\n{content}")
                            
                        except Exception as e:
                            logger.warning(f"读取文件 {file_path} 失败: {str(e)}")
        
        # 记录图片信息（如果有）
        images_dir = os.path.join(auto_dir if os.path.exists(auto_dir) else output_dir, 'images')
        if os.path.exists(images_dir):
            image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
            if image_files:
                logger.info(f"发现 {len(image_files)} 个图片文件在 {images_dir}")
                result_content.append(f"\n\n---\n注：PDF 中包含 {len(image_files)} 个图片，已提取到 images 目录")
        
        return "\n\n".join(result_content) if result_content else "未找到解析结果"
    
    def _table_to_markdown(self, table: list) -> str:
        """将表格数据转换为Markdown格式"""
        if not table or not table[0]:
            return ""
        
        markdown_lines = []
        
        # 表头
        header = [str(cell) if cell else "" for cell in table[0]]
        markdown_lines.append("| " + " | ".join(header) + " |")
        markdown_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        # 数据行
        for row in table[1:]:
            if row:  # 跳过空行
                row_data = [str(cell) if cell else "" for cell in row]
                # 确保列数一致
                while len(row_data) < len(header):
                    row_data.append("")
                markdown_lines.append("| " + " | ".join(row_data[:len(header)]) + " |")
        
        return "\n".join(markdown_lines)
    
    def _should_use_external_api(self, file_path: str, file_size: int) -> Tuple[bool, str]:
        """
        智能决策是否使用外部API服务
        使用改进的PDF复杂度分析器进行决策
        
        Returns:
            Tuple[bool, str]: (is_use_external, processing_mode)
            processing_mode: 'internal', 'external', 'hybrid'
        """
        try:
            # 使用新的复杂度分析器（已在文件头部导入）
            
            analysis = analyze_pdf_complexity(file_path)
            recommendation = analysis.processing_recommendation
            
            logger.info(
                f"PDF复杂度分析结果: 复杂度{analysis.complexity_score:.2f}/10, "
                f"建议: {recommendation} (置信度: {analysis.confidence:.2f}) - "
                f"{'; '.join(analysis.reasons)}"
            )
            
            # 根据推荐结果决定使用外部API
            if recommendation == 'external':
                return True, 'external'
            elif recommendation == 'hybrid':
                # hybrid模式：优先尝试外部API，失败则降级到内部
                return True, 'hybrid'
            else:  # internal
                return False, 'internal'
            
        except Exception as e:
            logger.warning(f"使用新分析器失败，降级到简单检查: {str(e)}")
            use_external = self._should_use_external_api_simple(file_path, file_size)
            return use_external, 'external' if use_external else 'internal'
    
    def _should_use_external_api_simple(self, file_path: str, file_size: int) -> bool:
        """
        简单的复杂度检查（备用方案）
        保留原有逻辑作为降级处理
        """
        # 文件大小阈值（5MB）
        SIZE_THRESHOLD = 5 * 1024 * 1024
        
        # 大文件建议使用外部服务
        if file_size > SIZE_THRESHOLD:
            logger.info(f"文件大小 {file_size / 1024 / 1024:.2f}MB，建议使用外部服务")
            return True
        
        # 检查PDF复杂度
        try:
            import PyPDF2
            complexity_score = 0
            
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                page_count = len(pdf_reader.pages)
                
                # 页数较多
                if page_count > 20:
                    complexity_score += 2
                    
                # 检查前几页
                for i in range(min(3, page_count)):
                    page = pdf_reader.pages[i]
                    
                    # 检查是否有图片
                    if '/XObject' in page.get('/Resources', {}):
                        complexity_score += 1
                    
                    # 检查文本长度（可能是扫描版）
                    text = page.extract_text()
                    if len(text.strip()) < 100:  # 文本很少，可能是扫描版
                        complexity_score += 2
                        
                # 检查是否加密
                if pdf_reader.is_encrypted:
                    complexity_score += 3
            
            # 复杂度高的建议使用外部服务
            if complexity_score >= 3:
                logger.info(f"PDF复杂度评分：{complexity_score}，建议使用外部服务")
                return True
            else:
                logger.info(f"PDF复杂度评分：{complexity_score}，可以使用内部处理")
                return False
                
        except Exception as e:
            logger.warning(f"PDF复杂度检查失败：{str(e)}，默认使用外部服务")
            return True
    
    def _try_external_processing(self, pdf_base64: str, pdf_uuid: str, file_path: str) -> Dict[str, Any]:
        """
        尝试使用外部API进行处理
        """
        try:
            # 使用pdf_converter的内容提取器
            from mineru.tool_interface import extract_pdf_content
            
            # 调用内容提取器
            result = extract_pdf_content(pdf_base64, pdf_uuid)
            
            if result['status'] == 'success':
                content = result['content']
                
                # 如果有图片，添加提示
                if result.get('images_count', 0) > 0:
                    content += f"\n\n---\n注：PDF 中包含 {result['images_count']} 个图片"
                
                return {
                    "status": "success",
                    "message": f"文件 '{os.path.basename(file_path)}' 已成功解析。",
                    "file_path": file_path,
                    "content": content,
                    "markdown_content": content,  # 兼容DocumentParserTool的输出格式
                    "images_count": result.get('images_count', 0),
                    "output_dir": result.get('output_dir'),
                    "processing_method": "external_api"
                }
            else:
                return {
                    "status": "error",
                    "message": result.get('message', '外部API返回错误'),
                    "file_path": file_path
                }
                
        except ImportError:
            return {
                "status": "error",
                "message": "mineru.tool_interface 模块未安装或不可用",
                "file_path": file_path
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"外部API调用失败: {str(e)}",
                "file_path": file_path
            }
    
    def _check_external_service_available(self) -> bool:
        """检查外部服务是否可用"""
        try:
            import requests
            response = requests.get('http://127.0.0.1:8002/health', timeout=1)
            return response.status_code == 200
        except:
            return False