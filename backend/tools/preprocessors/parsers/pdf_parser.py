import os
import base64
import json
import logging
from typing import Dict, Any
from tools.core.base import BaseTool
from tools.core.exceptions import ToolExecutionError
try:
    # 导入MinerU服务和工具接口
    from mineru.tool_interface import extract_pdf_content
    MINERU_AVAILABLE = True
except ImportError:
    MINERU_AVAILABLE = False

logger = logging.getLogger(__name__)

class PDFParserTool(BaseTool):
    """
    PDF文档解析工具：将PDF文件内容转换为文本或Markdown格式。
    支持两种模式：
    1. 直接调用外部API服务（需要8002端口服务运行）
    2. 使用pdf_converter模块的功能（可扩展）
    """
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要解析的PDF文件路径"
                },
                "mode": {
                    "type": "string",
                    "enum": ["api", "direct"],
                    "description": "解析模式：api-调用外部API，direct-直接解析",
                    "default": "api"
                }
            },
            "required": ["file_path"]
        }

    def execute(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        file_path = tool_input.get('file_path')
        mode = tool_input.get('mode', 'api')
        
        if not file_path:
            return {"status": "error", "message": "文件路径未提供。"}
        
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"文件不存在: {file_path}"}
        
        if not file_path.lower().endswith('.pdf'):
            return {"status": "error", "message": f"不支持的文件格式，只支持.pdf: {file_path}"}
        
        try:
            if mode == 'api':
                return self._parse_pdf_via_api(file_path)
            else:
                return self._parse_pdf_direct(file_path)
                
        except Exception as e:
            logger.error(f"PDF解析失败: {str(e)}", exc_info=True)
            return {"status": "error", "message": f"PDF解析失败: {str(e)}", "file_path": file_path}
    
    def _parse_pdf_via_api(self, file_path: str) -> Dict[str, Any]:
        """通过MinerU服务或外部API解析PDF"""
        import uuid
        
        # 读取文件
        with open(file_path, 'rb') as f:
            pdf_content = f.read()
        
        # 生成唯一ID
        pdf_uuid = str(uuid.uuid4())
        
        # 优先尝试使用MinerU服务
        if MINERU_AVAILABLE:
            try:
                logger.info(f"使用MinerU服务解析PDF: {file_path}")
                
                # 将PDF内容转换为base64
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
                
                # 调用MinerU工具接口
                logger.info(f"调用extract_pdf_content，任务ID: {pdf_uuid}")
                result = extract_pdf_content(
                    pdf_base64=pdf_base64,
                    pdf_uuid=pdf_uuid
                )
                
                # 检查结果
                if result['status'] == 'success':
                    markdown_content = result.get('content', '')
                    logger.info(f"MinerU解析成功，内容长度: {len(markdown_content)}")
                    logger.info(f"图片数量: {result.get('images_count', 0)}")
                    logger.info(f"输出目录: {result.get('output_dir', '')}")
                    
                    return {
                        "status": "success",
                        "message": f"文件 '{os.path.basename(file_path)}' 已通过MinerU成功解析。",
                        "file_path": file_path,
                        "content": markdown_content,
                        "output_dir": result.get('output_dir', ''),
                        "images_count": result.get('images_count', 0)
                    }
                else:
                    # MinerU处理失败
                    logger.warning(f"MinerU处理失败: {result.get('message', '未知错误')}")
                    raise Exception(result.get('message', 'MinerU处理失败'))
                    
            except Exception as e:
                logger.error(f"MinerU解析失败: {str(e)}，尝试外部API")
        
        # 降级到外部API
        try:
            import requests
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            # 调用本地API服务
            api_url = 'http://127.0.0.1:8002/predict'
            logger.info(f"调用外部PDF解析API: {api_url}")
            
            response = requests.post(api_url, json={
                'file': pdf_base64,
                'pdf_name': pdf_uuid
            }, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"API调用失败: 状态码 {response.status_code}")
            
            result = response.json()
            output_dir = result.get('output_dir')
            
            # 读取解析结果
            parsed_content = self._read_parsed_results(output_dir)
            
            return {
                "status": "success",
                "message": f"文件 '{os.path.basename(file_path)}' 已成功解析。",
                "file_path": file_path,
                "content": parsed_content,
                "output_dir": output_dir
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API调用失败: {str(e)}")
            return {
                "status": "error", 
                "message": f"PDF解析服务不可用，请确保8002端口的服务正在运行: {str(e)}"
            }
    
    def _parse_pdf_direct(self, file_path: str) -> Dict[str, Any]:
        """直接解析PDF（备用方案，可使用PyPDF2等库）"""
        # 这里可以实现直接的PDF解析逻辑
        # 例如使用 PyPDF2, pdfplumber 等库
        try:
            import PyPDF2
            
            text_content = []
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text_content.append(f"## 第 {page_num + 1} 页\n\n{page.extract_text()}")
            
            markdown_content = "\n\n".join(text_content)
            
            return {
                "status": "success",
                "message": f"文件 '{os.path.basename(file_path)}' 已成功解析。",
                "file_path": file_path,
                "content": markdown_content
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "直接解析模式需要安装PyPDF2库: pip install PyPDF2"
            }
    
    def _read_parsed_results(self, output_dir: str) -> str:
        """读取解析后的结果文件"""
        # 这里需要根据实际的输出格式来读取
        # 假设输出目录中有文本文件
        result_content = []
        
        if os.path.exists(output_dir):
            for file_name in os.listdir(output_dir):
                if file_name.endswith(('.txt', '.md')):
                    file_path = os.path.join(output_dir, file_name)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        result_content.append(f.read())
        
        return "\n\n".join(result_content) if result_content else "未找到解析结果"