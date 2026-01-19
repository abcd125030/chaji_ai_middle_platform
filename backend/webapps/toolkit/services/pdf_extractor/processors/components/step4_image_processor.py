"""
Step4 图像处理器

负责图像的格式转换、缩放和保存操作
"""
import logging
import base64
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image

logger = logging.getLogger('django')


class ImageProcessor:
    """图像处理器 - 处理图像的转换、缩放和保存"""

    @staticmethod
    def image_to_base64(image: np.ndarray) -> str:
        """
        将numpy图像转换为base64编码

        Args:
            image: numpy数组格式的图像 (RGB)

        Returns:
            base64编码的字符串
        """
        pil_image = Image.fromarray(image)
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    @staticmethod
    def resize_image_for_vl(
        image: np.ndarray,
        max_dimension: int = 1440
    ) -> np.ndarray:
        """
        等比例缩小图像到指定最大尺寸

        Args:
            image: numpy数组格式的图像 (RGB)
            max_dimension: 宽高最大值限制（像素）

        Returns:
            缩小后的图像
        """
        height, width = image.shape[:2]

        # 检查是否需要缩小
        if width <= max_dimension and height <= max_dimension:
            logger.debug(f"图像尺寸 {width}x{height} 无需缩小")
            return image

        # 计算缩放比例
        if width > height:
            scale = max_dimension / width
        else:
            scale = max_dimension / height

        new_width = int(width * scale)
        new_height = int(height * scale)

        # 使用PIL进行高质量缩放
        pil_image = Image.fromarray(image)
        resized_pil = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        resized_array = np.array(resized_pil)

        logger.info(f"完整页面图像已缩放: {width}x{height} -> {new_width}x{new_height} (缩放比例: {scale:.2f})")

        return resized_array

    @staticmethod
    def save_resized_image(
        image: np.ndarray,
        output_dir: Path,
        filename: str = "full_page_resized.png"
    ) -> Path:
        """
        保存缩放后的图像

        Args:
            image: numpy数组格式的图像
            output_dir: 输出目录
            filename: 文件名

        Returns:
            保存的文件路径
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename

            pil_image = Image.fromarray(image)
            pil_image.save(output_path, format='PNG')

            logger.debug(f"缩放图像已保存: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"保存缩放图像失败: {str(e)}", exc_info=True)
            raise
