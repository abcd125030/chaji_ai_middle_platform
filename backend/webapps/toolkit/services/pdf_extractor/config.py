"""
PDF提取器配置管理
"""
import os
from pathlib import Path
from typing import Dict, Any
from django.conf import settings


class PDFExtractorConfig:
    """PDF提取器配置类"""

    # 文件存储配置
    MEDIA_ROOT = Path(settings.MEDIA_ROOT)
    BASE_DIR = MEDIA_ROOT / 'oss-bucket' / '_toolkit' / '_extractor'

    # 文件限制
    MAX_FILES_PER_REQUEST = 20
    MAX_FILE_SIZE_MB = 50
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

    # PDF处理配置
    DEFAULT_DPI = 144
    IMAGE_FORMAT = 'PNG'
    SUPPORTED_FORMATS = ['.pdf']

    # Qwen3-VL API配置
    # 这些配置应该从环境变量或数据库配置中读取
    QWEN_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
    QWEN_MODEL = 'qwen3-vl-plus'
    QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

    # 语义分割提示词配置
    SEMANTIC_ANALYSIS_PROMPT = """请分析这张PDF页面图片，识别并标注出所有重要的视觉元素区域。

对每个区域，请提供：
1. 区域类型（diagram_area/chart_area/image_text_area/table_area/formula_area）
2. 详细描述
3. 边界框坐标（像素坐标：x, y, width, height）
4. 置信度（0-1）
5. 语义标签

返回格式为JSON数组，每个元素包含：
{
    "type": "区域类型",
    "description": "详细描述",
    "bbox": [x, y, width, height],
    "confidence": 0.95,
    "semantic_label": "语义标签"
}"""

    # 任务清理配置
    TASK_RETENTION_DAYS = 30  # 任务保留天数

    # Celery任务配置
    CELERY_TASK_TIMEOUT = 3600  # 任务超时时间（秒）
    CELERY_TASK_RETRY_MAX = 3  # 最大重试次数

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """
        获取完整配置字典

        Returns:
            配置字典
        """
        return {
            'base_dir': str(cls.BASE_DIR),
            'max_files': cls.MAX_FILES_PER_REQUEST,
            'max_file_size_mb': cls.MAX_FILE_SIZE_MB,
            'dpi': cls.DEFAULT_DPI,
            'image_format': cls.IMAGE_FORMAT,
            'supported_formats': cls.SUPPORTED_FORMATS,
            'qwen_model': cls.QWEN_MODEL,
            'task_retention_days': cls.TASK_RETENTION_DAYS,
        }

    @classmethod
    def validate_config(cls) -> bool:
        """
        验证配置是否完整

        Returns:
            配置是否有效
        """
        # 检查必需的环境变量
        if not cls.QWEN_API_KEY:
            return False

        # 检查目录是否可创建
        try:
            cls.BASE_DIR.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False
