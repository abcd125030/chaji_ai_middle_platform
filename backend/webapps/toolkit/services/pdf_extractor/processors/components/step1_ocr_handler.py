"""
Step1 OCR处理器

使用qwen3-vl-plus多模态模型进行PDF页面OCR识别
"""
import logging
import base64
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import fitz  # PyMuPDF
from openai import OpenAI

logger = logging.getLogger('django')


class OCRHandler:
    """OCR处理器 - 使用qwen3-vl-plus进行视觉理解和文本提取"""

    # OCR提示词
    OCR_PROMPT = """你是一个专业的PDF文档OCR识别专家。请仔细识别这张PDF页面图片中的所有文本内容。

**任务要求**：
1. **完整识别**：识别图片中的所有可见文本，包括标题、正文、图表说明、表格内容等
2. **保持结构**：尽可能保持原文的段落结构、列表格式和层次关系
3. **识别数学公式**：如果页面包含数学公式，使用LaTeX格式表示（用 $ 或 $$ 包裹）
4. **识别表格**：如果有表格，使用Markdown表格格式输出
5. **图表处理**：
   - 如果是纯图表/图片，描述图表的类型和主要内容
   - 如果图表包含文字标注，识别这些文字
   - 保留图表标题和说明文字（如 "Figure 1: ..."）

**输出格式**：
- 直接输出识别的文本内容，使用Markdown格式
- 不要添加额外的说明或注释
- 不要添加 "识别结果："、"文本内容：" 等前缀
- 如果某些文字模糊不清，用 `<?>{不确定的部分}</?>` 标记不确定的部分

**特别注意**：
- 保持原文语言（中文/英文/混合）
- 数字、符号、标点符号要准确
- 专业术语要准确识别

请开始识别："""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "qwen3-vl-plus"
    ):
        """
        初始化OCR处理器

        Args:
            api_key: API密钥
            base_url: API基础URL
            model: 模型名称（固定使用 qwen3-vl-plus）
        """
        if model != "qwen3-vl-plus":
            logger.warning(
                f"传入的模型名称为 {model}，但OCR处理器强制使用 qwen3-vl-plus"
            )
            model = "qwen3-vl-plus"

        self.api_key = api_key
        self.base_url = base_url
        self.model = model

        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        logger.info(f"OCR处理器初始化完成，模型: {self.model}")

    def extract_page_image(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 144,
        image_format: str = "png"
    ) -> bytes:
        """
        将PDF页面渲染为图片

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            dpi: 分辨率（DPI）
            image_format: 图片格式（png/jpeg）

        Returns:
            图片字节数据

        Raises:
            FileNotFoundError: PDF文件不存在
            ValueError: 页码无效或格式不支持
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        if image_format.lower() not in ['png', 'jpeg', 'jpg']:
            raise ValueError(f"不支持的图片格式: {image_format}")

        try:
            doc = fitz.open(pdf_path)

            # 验证页码
            if page_number < 1 or page_number > doc.page_count:
                raise ValueError(
                    f"页码无效: {page_number}，总页数: {doc.page_count}"
                )

            # 获取页面
            page = doc[page_number - 1]

            # 设置缩放比例（DPI转换）
            zoom = dpi / 72  # 72是PDF的默认DPI
            mat = fitz.Matrix(zoom, zoom)

            # 渲染页面为图片
            pix = page.get_pixmap(matrix=mat)

            # 转换为字节
            if image_format.lower() == 'png':
                image_bytes = pix.tobytes("png")
            else:
                image_bytes = pix.tobytes("jpeg")

            doc.close()

            logger.info(
                f"页面 {page_number} 已渲染为图片，"
                f"尺寸: {pix.width}x{pix.height}，"
                f"大小: {len(image_bytes)} 字节"
            )

            return image_bytes

        except Exception as e:
            logger.error(
                f"渲染页面 {page_number} 为图片失败: {str(e)}",
                exc_info=True
            )
            raise

    def save_page_image(
        self,
        pdf_path: str,
        page_number: int,
        output_path: Path,
        dpi: int = 144
    ) -> Path:
        """
        保存PDF页面为图片文件

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            output_path: 输出图片路径
            dpi: 分辨率

        Returns:
            保存的图片文件路径
        """
        # 根据输出路径确定格式
        suffix = output_path.suffix.lower().lstrip('.')
        if suffix not in ['png', 'jpg', 'jpeg']:
            suffix = 'png'
            output_path = output_path.with_suffix('.png')

        # 提取图片
        image_bytes = self.extract_page_image(pdf_path, page_number, dpi, suffix)

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(output_path, 'wb') as f:
            f.write(image_bytes)

        logger.info(f"页面图片已保存到: {output_path}")

        return output_path

    def ocr_from_image_bytes(
        self,
        image_bytes: bytes,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        对图片字节数据进行OCR识别

        Args:
            image_bytes: 图片字节数据
            custom_prompt: 自定义提示词（可选）

        Returns:
            (识别的文本, 调试信息字典)

        Raises:
            RuntimeError: OCR识别失败
        """
        try:
            # Base64编码图片
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # 构建消息
            prompt = custom_prompt if custom_prompt else self.OCR_PROMPT

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]

            logger.info(f"开始调用 {self.model} 进行OCR识别，图片大小: {len(image_bytes)} 字节")

            # 调用API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # 低温度以获得更准确的结果
                stream=False
            )

            # 提取识别结果
            recognized_text = completion.choices[0].message.content

            logger.info(f"OCR识别完成，输出长度: {len(recognized_text)} 字符")

            # 构建调试信息
            debug_info = {
                "model": self.model,
                "image_size_bytes": len(image_bytes),
                "output_length": len(recognized_text),
                "prompt_tokens": completion.usage.prompt_tokens if hasattr(completion, 'usage') else None,
                "completion_tokens": completion.usage.completion_tokens if hasattr(completion, 'usage') else None,
                "total_tokens": completion.usage.total_tokens if hasattr(completion, 'usage') else None
            }

            return recognized_text, debug_info

        except Exception as e:
            logger.error(f"OCR识别失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"OCR识别失败: {str(e)}")

    def ocr_pdf_page(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 144,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        对PDF页面进行OCR识别（完整流程）

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            dpi: 渲染DPI
            custom_prompt: 自定义提示词（可选）

        Returns:
            (识别的文本, 调试信息字典)
        """
        logger.info(f"开始OCR识别 PDF 页面 {page_number}")

        # 步骤1: 渲染页面为图片
        image_bytes = self.extract_page_image(pdf_path, page_number, dpi)

        # 步骤2: OCR识别
        recognized_text, debug_info = self.ocr_from_image_bytes(
            image_bytes,
            custom_prompt
        )

        # 添加额外的调试信息
        debug_info['pdf_path'] = str(pdf_path)
        debug_info['page_number'] = page_number
        debug_info['dpi'] = dpi

        logger.info(f"页面 {page_number} OCR识别完成")

        return recognized_text, debug_info

    def batch_ocr_pages(
        self,
        pdf_path: str,
        page_numbers: list[int],
        dpi: int = 144
    ) -> Dict[int, Tuple[str, Dict[str, Any]]]:
        """
        批量OCR多个页面

        Args:
            pdf_path: PDF文件路径
            page_numbers: 页码列表
            dpi: 渲染DPI

        Returns:
            Dict[page_number, (recognized_text, debug_info)]
        """
        logger.info(f"开始批量OCR识别，共 {len(page_numbers)} 页")

        results = {}
        for page_num in page_numbers:
            try:
                text, debug_info = self.ocr_pdf_page(pdf_path, page_num, dpi)
                results[page_num] = (text, debug_info)
            except Exception as e:
                logger.error(f"OCR识别页面 {page_num} 失败: {str(e)}")
                # 记录失败但继续处理其他页面
                results[page_num] = (
                    f"[OCR识别失败: {str(e)}]",
                    {"error": str(e)}
                )

        logger.info(f"批量OCR完成，成功 {len(results)} 页")

        return results
