"""
OCR模型配置管理
"""
import os
from typing import Dict, Any


class OCRModelConfig:
    """OCR模型API配置类"""

    # API配置
    API_URL = os.getenv('OCR_API_URL', 'http://172.22.217.66:9123')
    API_TIMEOUT = int(os.getenv('OCR_API_TIMEOUT', '300'))  # 请求超时时间（秒）

    # OCR模式配置
    OCR_MODES = {
        'convert_to_markdown': 'Markdown格式',
    }

    # 默认参数
    DEFAULT_MAX_TOKENS = 8192
    DEFAULT_TEMPERATURE = 0.0

    # 支持的图像格式
    SUPPORTED_IMAGE_FORMATS = [
        '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.pdf'
    ]

    # 图片标记配置
    IMAGE_MARKER = '[[[!image]]]'  # 用于替换OCR结果中的图片标记

    # 正则表达式模式
    PATTERNS = {
        # DeepSeek-OCR的图片标记格式: <|ref|>image<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
        'image_marker': r'<\|ref\|>image<\|/ref\|><\|det\|>\[\[(\d+,\s*\d+,\s*\d+,\s*\d+)\]\]<\|/det\|>',
        'ref_tag': r'<\|ref\|>.*?<\|/ref\|>',
        'det_tag': r'<\|det\|>\[\[.*?\]\]<\|/det\|>',
    }

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """
        获取完整配置

        Returns:
            Dict: 包含所有配置项的字典
        """
        return {
            'api_url': cls.API_URL,
            'api_timeout': cls.API_TIMEOUT,
            'ocr_modes': cls.OCR_MODES,
            'default_max_tokens': cls.DEFAULT_MAX_TOKENS,
            'default_temperature': cls.DEFAULT_TEMPERATURE,
            'supported_image_formats': cls.SUPPORTED_IMAGE_FORMATS,
            'image_marker': cls.IMAGE_MARKER,
            'patterns': cls.PATTERNS,
        }

    @classmethod
    def validate_image_format(cls, file_path: str) -> bool:
        """
        验证图像格式是否支持

        Args:
            file_path: 图像文件路径

        Returns:
            bool: 是否支持该格式
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.SUPPORTED_IMAGE_FORMATS

    @classmethod
    def validate_mode(cls, mode: str) -> bool:
        """
        验证OCR模式是否支持

        Args:
            mode: OCR处理模式

        Returns:
            bool: 是否支持该模式
        """
        return mode in cls.OCR_MODES
