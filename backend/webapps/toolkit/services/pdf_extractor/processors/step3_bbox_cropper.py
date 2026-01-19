"""
步骤3: BBox裁剪器（简化版）

直接使用Step1产生的image_regions坐标裁剪局部图，确保与占位符顺序一致
"""
import logging
import json
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
from PIL import Image

logger = logging.getLogger('django')


class BBoxCropper:
    """BBox裁剪器 - 基于Step1的坐标直接裁剪"""

    def __init__(self):
        """初始化BBox裁剪器"""
        logger.info("初始化BBox裁剪器（简化版：直接使用OCR坐标）")

    def crop_regions_from_step1(
        self,
        image: np.ndarray,
        output_dir: Path,
        page_number: int = 1
    ) -> Tuple[int, List[Path]]:
        """
        从Step1保存的坐标文件读取bbox并裁剪图片

        Args:
            image: 完整页面图像（numpy数组）
            output_dir: 输出目录（需要包含Step1的坐标文件）
            page_number: 页码

        Returns:
            元组(裁剪的图片数量, 保存的文件路径列表)
        """
        try:
            output_dir = Path(output_dir)

            # 读取Step1保存的坐标文件
            regions_path = output_dir / f"page_{page_number}_image_regions.json"
            if not regions_path.exists():
                logger.warning(f"Step1坐标文件不存在: {regions_path}")
                return 0, []

            with open(regions_path, 'r', encoding='utf-8') as f:
                regions_data = json.load(f)

            regions = regions_data.get('regions', [])
            image_count = len(regions)

            if image_count == 0:
                logger.warning("Step1未检测到任何图片区域")
                return 0, []

            logger.info(f"从Step1坐标文件读取到 {image_count} 个图片区域")

            # 裁剪并保存每个区域
            saved_paths = []
            image_height, image_width = image.shape[:2]

            for i, bbox in enumerate(regions, 1):
                # bbox格式: [x1, y1, x2, y2] (左上角, 右下角)
                x1, y1, x2, y2 = bbox

                # 确保坐标在图像范围内
                x1 = max(0, min(x1, image_width - 1))
                y1 = max(0, min(y1, image_height - 1))
                x2 = max(x1 + 1, min(x2, image_width))
                y2 = max(y1 + 1, min(y2, image_height))

                # 裁剪区域
                cropped = image[y1:y2, x1:x2]

                # 保存为 image_{i}.png
                filename = f"image_{i}.png"
                output_path = output_dir / filename

                pil_image = Image.fromarray(cropped)
                pil_image.save(output_path, 'PNG')

                saved_paths.append(output_path)
                logger.info(
                    f"裁剪图片 {i}/{image_count}: bbox=[{x1}, {y1}, {x2}, {y2}], "
                    f"尺寸={x2-x1}x{y2-y1}, 保存到: {output_path.name}"
                )

            # 保存裁剪报告
            report_path = output_dir / f"page_{page_number}_step3_crop_report.txt"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Step3 BBox裁剪报告\n")
                f.write(f"=" * 60 + "\n")
                f.write(f"页码: {page_number}\n")
                f.write(f"原始图像尺寸: {image_width}x{image_height}\n")
                f.write(f"裁剪区域数量: {image_count}\n\n")
                for i, bbox in enumerate(regions, 1):
                    x1, y1, x2, y2 = bbox
                    f.write(f"图片 {i}: [{x1}, {y1}, {x2}, {y2}] -> {x2-x1}x{y2-y1}\n")

            logger.info(f"Step3报告已保存: {report_path}")
            logger.info(f"Step3完成 - 裁剪 {image_count} 个区域")

            return image_count, saved_paths

        except Exception as e:
            logger.error(f"BBox裁剪失败: {str(e)}", exc_info=True)
            return 0, []

    def crop_and_save(
        self,
        image: np.ndarray,
        output_dir: Path,
        page_number: int = 1
    ) -> Tuple[int, List[Path]]:
        """
        执行裁剪并保存（别名方法，兼容旧接口）

        Args:
            image: 输入图像
            output_dir: 输出目录
            page_number: 页码

        Returns:
            (裁剪的图片数量, 保存的文件路径列表)
        """
        return self.crop_regions_from_step1(image, output_dir, page_number)
