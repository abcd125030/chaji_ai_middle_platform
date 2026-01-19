from tools.core.base import BaseTool
from tools.core.exceptions import ToolExecutionError
from typing import Dict, Any
import os
import base64
import logging

logger = logging.getLogger(__name__)

class ImageProcessorTool(BaseTool):
    """
    图片处理工具：使用视觉模型将图片转换为文字描述
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要处理的图片文件路径"
                },
                "model_name": {
                    "type": "string",
                    "description": "视觉模型名称，默认使用 'qwen3-vl-plus'",
                    "default": "qwen3-vl-plus"
                },
                "prompt": {
                    "type": "string",
                    "description": "图片分析提示词，默认为通用描述",
                    "default": "请详细描述这张图片的内容，包括主要元素、场景、文字信息（如果有）、颜色、布局等关键信息。"
                }
            },
            "required": ["file_path"]
        }

    def execute(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        file_path = tool_input.get('file_path')
        model_name = tool_input.get('model_name', 'qwen3-vl-plus')
        prompt = tool_input.get('prompt', '请详细描述这张图片的内容，包括主要元素、场景、文字信息（如果有）、颜色、布局等关键信息。')
        
        if not file_path:
            return {"status": "error", "message": "文件路径未提供。"}
        
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"文件不存在: {file_path}"}
        
        # 检查文件格式
        file_ext = os.path.splitext(file_path.lower())[1]
        supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        
        if file_ext not in supported_formats:
            return {
                "status": "error", 
                "message": f"不支持的文件格式 {file_ext}，支持的格式: {', '.join(supported_formats)}"
            }
        
        try:
            # 读取图片并转换为 base64
            with open(file_path, 'rb') as f:
                image_data = f.read()
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # 根据文件扩展名确定 MIME 类型
                mime_type_map = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp',
                    '.webp': 'image/webp',
                    '.svg': 'image/svg+xml'
                }
                mime_type = mime_type_map.get(file_ext, 'image/jpeg')
                
                # 构建 data URL
                base64_with_prefix = f"data:{mime_type};base64,{base64_image}"
            
            # 调用视觉模型
            from llm.llm_service import LLMService
            llm_service = LLMService()
            
            try:
                response = llm_service.call_vision_model(
                    model_name=model_name,
                    text_prompt=prompt,
                    images=[base64_with_prefix],
                    temperature=0.7,
                    max_tokens=1000
                )
                
                # 提取响应内容
                if response and 'choices' in response and len(response['choices']) > 0:
                    description = response['choices'][0]['message']['content']
                    
                    return {
                        "status": "success",
                        "message": f"图片 '{os.path.basename(file_path)}' 已成功处理",
                        "file_path": file_path,
                        "description": description,
                        "model_used": model_name
                    }
                else:
                    return {
                        "status": "error",
                        "message": "视觉模型返回了空响应",
                        "file_path": file_path
                    }
                    
            except Exception as e:
                logger.error(f"调用视觉模型失败: {str(e)}")
                return {
                    "status": "error",
                    "message": f"调用视觉模型失败: {str(e)}",
                    "file_path": file_path
                }
                
        except Exception as e:
            logger.error(f"处理图片文件失败: {str(e)}")
            return {
                "status": "error",
                "message": f"处理图片文件失败: {str(e)}",
                "file_path": file_path
            }