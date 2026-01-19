"""
步骤3: 语义分割器（简化版）

直接使用Step1中OCR提供的图片区域坐标，不再调用VLM模型
性能提升：去除LLM调用，降低成本，提升速度
"""
import logging
import json
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
from PIL import Image

logger = logging.getLogger('django')


@dataclass
class ImageRegion:
    """图像区域定义"""
    id: int
    type: str  # image（OCR识别的图片区域）
    description: str
    bbox: List[int]  # [x, y, width, height] 格式
    confidence: float
    semantic_label: str

    def to_dict(self) -> Dict:
        return asdict(self)


class SemanticSegmentor:
    """语义分割器 - 基于OCR坐标（简化版）"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """
        初始化语义分割器（简化版不需要VLM）

        Args:
            api_key: 保留参数以兼容旧接口
            base_url: 保留参数以兼容旧接口
            model: 保留参数以兼容旧接口
        """
        logger.info("初始化语义分割器（简化版：直接使用OCR坐标）")

    def load_ocr_regions(self, output_dir: Path, page_number: int) -> List[ImageRegion]:
        """
        从Step1保存的JSON文件加载OCR识别的图片区域

        Args:
            output_dir: 输出目录
            page_number: 页码

        Returns:
            区域列表
        """
        regions_path = output_dir / f"page_{page_number}_image_regions.json"

        if not regions_path.exists():
            logger.warning(f"OCR坐标文件不存在: {regions_path}")
            return []

        try:
            with open(regions_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            ocr_regions = data.get('regions', [])
            image_size = data.get('image_size', [0, 0])
            coordinate_system = data.get('coordinate_system', 'unknown')

            logger.info(f"从OCR加载到 {len(ocr_regions)} 个图片区域，图片尺寸: {image_size}, 坐标系统: {coordinate_system}")

            # 将OCR坐标转换为ImageRegion对象
            regions = []
            for idx, coords in enumerate(ocr_regions, 1):
                # OCR坐标格式: [left_top_x, left_top_y, right_bottom_x, right_bottom_y]
                # DeepSeek-OCR使用归一化坐标 [0-999]，需要转换为像素坐标
                x1_norm, y1_norm, x2_norm, y2_norm = coords

                # 转换归一化坐标到像素坐标
                if coordinate_system == 'normalized_1000':
                    image_width, image_height = image_size
                    x1 = int(x1_norm * image_width / 1000)
                    y1 = int(y1_norm * image_height / 1000)
                    x2 = int(x2_norm * image_width / 1000)
                    y2 = int(y2_norm * image_height / 1000)
                    logger.info(f"坐标转换: 归一化[{x1_norm}, {y1_norm}, {x2_norm}, {y2_norm}] -> 像素[{x1}, {y1}, {x2}, {y2}]")
                else:
                    # 向后兼容：假设已经是像素坐标
                    x1, y1, x2, y2 = coords
                    logger.warning(f"未知坐标系统 '{coordinate_system}'，假设为像素坐标")

                # 转换为bbox格式: [x, y, width, height]
                bbox = [x1, y1, x2 - x1, y2 - y1]

                region = ImageRegion(
                    id=idx,
                    type='image',  # OCR识别的图片区域
                    description=f'图片区域 {idx}',
                    bbox=bbox,
                    confidence=1.0,  # OCR直接识别，置信度最高
                    semantic_label='ocr_detected_image'
                )
                regions.append(region)

                logger.info(f"区域 {idx}: 像素bbox [x={bbox[0]}, y={bbox[1]}, w={bbox[2]}, h={bbox[3]}]")

            return regions

        except Exception as e:
            logger.error(f"加载OCR区域失败: {str(e)}", exc_info=True)
            return []

    def extract_region(
        self,
        image: np.ndarray,
        region: ImageRegion
    ) -> np.ndarray:
        """
        从图像中提取指定区域

        Args:
            image: 原始图像
            region: 区域定义 (bbox格式: [x, y, width, height])

        Returns:
            裁剪后的区域图像
        """
        x, y, w, h = region.bbox

        # 确保坐标在图像范围内
        height, width = image.shape[:2]
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))

        # 裁剪区域
        region_img = image[y:y+h, x:x+w]

        logger.debug(f"裁剪区域 {region.id}: ({x}, {y}) 尺寸 {w}x{h}")

        return region_img

    def save_region_images(
        self,
        image: np.ndarray,
        regions: List[ImageRegion],
        output_dir: Path
    ) -> List[Path]:
        """
        保存所有区域图片

        Args:
            image: 原始图像
            regions: 区域列表
            output_dir: 输出目录

        Returns:
            保存的文件路径列表
        """
        saved_paths = []

        for region in regions:
            # 提取区域
            region_img = self.extract_region(image, region)

            # 保存图片
            filename = f"image_{region.id}.png"
            save_path = output_dir / filename

            # 转换为PIL Image并保存
            pil_img = Image.fromarray(region_img)
            pil_img.save(save_path, 'PNG', optimize=True)

            saved_paths.append(save_path)
            logger.info(f"保存区域图片 {region.id}: {save_path} (尺寸: {region_img.shape[1]}x{region_img.shape[0]})")

        return saved_paths

    def visualize_regions(
        self,
        image: np.ndarray,
        regions: List[ImageRegion]
    ) -> np.ndarray:
        """
        在图像上可视化所有区域

        Args:
            image: 原始图像
            regions: 区域列表

        Returns:
            标注后的图像
        """
        import cv2

        # 复制图像以避免修改原图
        vis_image = image.copy()

        # 为每个区域绘制边界框和标签
        for region in regions:
            x, y, w, h = region.bbox

            # 绘制矩形框（绿色，线宽2）
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # 添加标签
            label = f"{region.id}: {region.type}"
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

            # 绘制标签背景
            cv2.rectangle(
                vis_image,
                (x, y - label_size[1] - 5),
                (x + label_size[0], y),
                (0, 255, 0),
                -1
            )

            # 绘制标签文字
            cv2.putText(
                vis_image,
                label,
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1
            )

        logger.info(f"生成可视化图像，标注了 {len(regions)} 个区域")
        return vis_image

    def segment_and_save(
        self,
        image: np.ndarray,
        output_dir: Path,
        page_number: int = 1
    ) -> Tuple[List[ImageRegion], List[Path]]:
        """
        执行语义分割并保存所有区域（简化版：直接使用OCR坐标）

        Args:
            image: 输入图像
            output_dir: 输出目录
            page_number: 页码（用于文件命名）

        Returns:
            (区域列表, 保存的文件路径列表)
        """
        # 1. 从Step1加载OCR识别的区域坐标
        regions = self.load_ocr_regions(output_dir, page_number)

        if not regions:
            logger.warning("未找到OCR识别的图片区域")
            return regions, []

        # 2. 生成并保存可视化图像
        visualization = self.visualize_regions(image, regions)
        vis_path = output_dir / "visualization.png"
        Image.fromarray(visualization).save(vis_path)
        logger.info(f"保存可视化图像: {vis_path}")

        # 3. 保存元数据JSON
        metadata = {
            'stage': 'ocr_based',
            'page_number': page_number,
            'processing_time': datetime.now().isoformat(),
            'image_size': {
                'width': image.shape[1],
                'height': image.shape[0]
            },
            'total_regions': len(regions),
            'regions': [region.to_dict() for region in regions],
            'source': 'DeepSeek-OCR coordinates'
        }

        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"保存元数据: {metadata_path}")

        # 4. 保存所有区域图片
        saved_paths = self.save_region_images(image, regions, output_dir)

        # 返回结果（包含visualization和metadata路径）
        saved_paths.extend([vis_path, metadata_path])

        logger.info(f"Step3完成：基于OCR坐标裁剪了 {len(regions)} 个图片区域")

        return regions, saved_paths
