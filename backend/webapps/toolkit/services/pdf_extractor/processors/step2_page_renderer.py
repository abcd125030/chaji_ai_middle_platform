"""
步骤2: PDF页面渲染器

将PDF页面渲染为高质量图片
"""
import logging
from pathlib import Path
from typing import Optional
import numpy as np
import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger('django')


class PageRenderer:
    """PDF页面渲染器"""

    def __init__(self, dpi: int = 144):
        """
        初始化页面渲染器

        Args:
            dpi: 图像分辨率，默认300
        """
        self.dpi = dpi

    def render_page_to_image(
        self,
        pdf_path: str,
        page_number: int
    ) -> np.ndarray:
        """
        将PDF页面渲染为图像

        Args:
            pdf_path: PDF文件路径
            page_number: 页面编号（从1开始）

        Returns:
            numpy数组格式的图像 (RGB)

        Raises:
            FileNotFoundError: PDF文件不存在
            ValueError: 页码无效
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

            # 打开PDF文档
            doc = fitz.open(pdf_path)

            # 验证页码
            if page_number < 1 or page_number > doc.page_count:
                raise ValueError(
                    f"页码无效: {page_number}，总页数: {doc.page_count}"
                )

            # 获取页面（PyMuPDF页码从0开始）
            page = doc[page_number - 1]

            # 计算缩放比例（DPI转换）
            zoom = self.dpi / 72.0  # PDF默认72 DPI
            mat = fitz.Matrix(zoom, zoom)

            # 渲染页面为图像
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # 转换为numpy数组
            img_data = np.frombuffer(pix.samples, dtype=np.uint8)
            img_data = img_data.reshape(pix.height, pix.width, pix.n)

            # 确保是RGB格式
            if pix.n == 4:  # RGBA
                img_data = img_data[:, :, :3]
            elif pix.n == 1:  # 灰度
                img_data = np.stack([img_data] * 3, axis=-1)

            doc.close()

            logger.info(
                f"成功渲染页面 {page_number}，"
                f"尺寸: {img_data.shape[1]}x{img_data.shape[0]}"
            )

            return img_data

        except Exception as e:
            logger.error(
                f"渲染页面 {page_number} 失败: {str(e)}",
                exc_info=True
            )
            raise

    def save_image(
        self,
        image: np.ndarray,
        output_path: Path
    ) -> Path:
        """
        保存图像到文件

        Args:
            image: numpy数组格式的图像
            output_path: 输出文件路径

        Returns:
            保存的文件路径
        """
        try:
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 转换为PIL Image并保存
            pil_image = Image.fromarray(image)
            pil_image.save(output_path, 'PNG', optimize=True)

            logger.info(f"图像已保存到: {output_path}")

            return output_path

        except Exception as e:
            logger.error(
                f"保存图像到 {output_path} 失败: {str(e)}",
                exc_info=True
            )
            raise

    def render_and_save(
        self,
        pdf_path: str,
        page_number: int,
        output_dir: Path
    ) -> tuple[np.ndarray, Path]:
        """
        渲染页面并保存为完整截图

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            output_dir: 输出目录

        Returns:
            (渲染的图像, 保存的文件路径)
        """
        # 渲染页面
        image = self.render_page_to_image(pdf_path, page_number)

        # 保存为full_page.png
        output_path = output_dir / "full_page.png"
        saved_path = self.save_image(image, output_path)

        return image, saved_path
