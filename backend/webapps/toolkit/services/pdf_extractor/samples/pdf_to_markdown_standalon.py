#!/usr/bin/env python
"""
独立的PDF转Markdown脚本
使用Django OCR API进行文档识别和图像检测
输出完整的markdown文件和images目录
"""
import os
import sys
import json
import base64
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Tuple
import argparse

import fitz  # PyMuPDF
from PIL import Image
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFToMarkdownConverter:
    """PDF转Markdown转换器（使用Django OCR API）"""
    
    def __init__(
        self,
        ocr_api_url: str = None,
        dpi: int = 144
    ):
        """
        初始化转换器
        
        Args:
            ocr_api_url: OCR API URL（默认从环境变量DJANGO_OCR_API_URL读取）
            dpi: 渲染DPI
        """
        self.ocr_api_url = ocr_api_url or os.getenv(
            "DJANGO_OCR_API_URL",
            "https://aigc.chagee.com/_X/api/webapps/toolkit/ocr"
        )
        self.dpi = dpi
        
        logger.info(f"转换器初始化完成")
        logger.info(f"OCR API URL: {self.ocr_api_url}")
        logger.info(f"DPI: {self.dpi}")
    
    def render_pdf_page(
        self,
        pdf_path: str,
        page_number: int
    ) -> Tuple[bytes, np.ndarray, Tuple[int, int]]:
        """
        渲染PDF页面为图片
        
        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            
        Returns:
            (图片字节数据, 图片numpy数组, (width, height))
        """
        doc = fitz.open(pdf_path)
        
        if page_number < 1 or page_number > doc.page_count:
            raise ValueError(f"页码无效: {page_number}，总页数: {doc.page_count}")
        
        page = doc[page_number - 1]
        
        # 设置缩放比例
        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        # 渲染页面
        pix = page.get_pixmap(matrix=mat)
        image_bytes = pix.tobytes("png")
        
        # 转换为numpy数组
        image_array = np.frombuffer(pix.samples, dtype=np.uint8)
        image_array = image_array.reshape((pix.height, pix.width, pix.n))
        
        # 如果是RGBA，转换为RGB
        if pix.n == 4:
            image_array = image_array[:, :, :3]
        
        size = (pix.width, pix.height)
        
        doc.close()
        
        logger.info(f"页面 {page_number} 渲染完成，尺寸: {size[0]}x{size[1]}")
        
        return image_bytes, image_array, size
    
    def call_ocr_api(
        self,
        image_bytes: bytes,
        mode: str = "convert_to_markdown"
    ) -> Dict[str, Any]:
        """
        调用Django OCR API
        
        Args:
            image_bytes: 图片字节数据
            mode: OCR模式
            
        Returns:
            OCR响应数据
        """
        # Base64编码
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        logger.info(f"调用OCR API，模式: {mode}")
        
        # 调用API
        response = requests.post(
            f"{self.ocr_api_url}/image/",
            json={
                'image_base64': image_base64,
                'mode': mode,
                'max_tokens': 8192,
                'temperature': 0.0
            },
            timeout=300
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"OCR API请求失败: HTTP {response.status_code}, {response.text}")
        
        result = response.json()
        
        if not result.get('success'):
            raise RuntimeError(f"OCR识别失败: {result.get('error', '未知错误')}")
        
        logger.info(f"OCR完成，检测到 {result.get('image_count', 0)} 个图片区域")
        
        return result
    
    def convert_normalized_coords(
        self,
        regions: List[List[int]],
        image_size: Tuple[int, int]
    ) -> List[List[int]]:
        """
        将归一化坐标转换为像素坐标
        
        Args:
            regions: 归一化坐标列表 [[x1, y1, x2, y2], ...]（0-999）
            image_size: 图片尺寸 (width, height)
            
        Returns:
            像素坐标列表 [[x, y, width, height], ...]
        """
        width, height = image_size
        pixel_regions = []
        
        for coords in regions:
            if len(coords) == 4:
                x1_norm, y1_norm, x2_norm, y2_norm = coords
                
                # 转换归一化坐标到像素坐标
                x1 = int(x1_norm * width / 1000)
                y1 = int(y1_norm * height / 1000)
                x2 = int(x2_norm * width / 1000)
                y2 = int(y2_norm * height / 1000)
                
                # 转换为 [x, y, width, height] 格式
                pixel_regions.append([x1, y1, x2 - x1, y2 - y1])
        
        return pixel_regions
    
    def crop_and_save_images(
        self,
        image: np.ndarray,
        regions: List[List[int]],
        page_number: int,
        images_dir: Path
    ) -> List[str]:
        """
        裁剪并保存图片区域
        
        Args:
            image: 原始图像
            regions: 像素坐标列表 [[x, y, width, height], ...]
            page_number: 页码
            images_dir: 图片输出目录
            
        Returns:
            保存的图片相对路径列表
        """
        saved_images = []
        
        for idx, bbox in enumerate(regions, 1):
            try:
                x, y, w, h = bbox
                
                # 向下增加10px高度
                h = h + 10
                
                # 确保坐标在图像范围内
                height, width = image.shape[:2]
                x = max(0, min(x, width - 1))
                y = max(0, min(y, height - 1))
                w = max(1, min(w, width - x))
                h = max(1, min(h, height - y))
                
                # 裁剪
                cropped = image[y:y+h, x:x+w]
                
                # 保存图片
                image_filename = f"page_{page_number}_image_{idx}.png"
                image_path = images_dir / image_filename
                Image.fromarray(cropped).save(image_path)
                
                saved_images.append(f"images/{image_filename}")
                logger.info(f"保存图片: {image_filename} (区域: x={x}, y={y}, w={w}, h={h})")
                
            except Exception as e:
                logger.warning(f"裁剪/保存图片 {idx} 失败: {e}")
        
        return saved_images
    
    def process_markdown_images(
        self,
        markdown: str,
        saved_images: List[str]
    ) -> str:
        """
        替换markdown中的图片占位符
        
        Args:
            markdown: 原始markdown文本
            saved_images: 保存的图片路径列表
            
        Returns:
            处理后的markdown文本
        """
        # 替换图片占位符，支持多种格式
        import re
        
        # 支持多种占位符格式: [[[!image]]], [Image: ...], [[image]], 等
        patterns = [
            r'\[\[\[!image\]\]\]',  # [[[!image]]] 格式
            r'\[Image:\s*[^\]]*\]',  # [Image: ...] 格式
            r'\[\[image\]\]',        # [[image]] 格式
            r'\[image\]'             # [image] 格式
        ]
        
        # 合并所有模式
        combined_pattern = '|'.join(f'({p})' for p in patterns)
        image_pattern = re.compile(combined_pattern)
        placeholders = image_pattern.findall(markdown)
        
        # 过滤掉空的匹配组
        placeholders = [''.join(p) for p in placeholders if any(p)]
        
        # 替换每个占位符
        for idx, placeholder in enumerate(placeholders):
            if idx < len(saved_images):
                replacement = f"![图片 {idx + 1}]({saved_images[idx]})"
                markdown = markdown.replace(placeholder, replacement, 1)
        
        return markdown
    
    def process_page(
        self,
        pdf_path: str,
        page_number: int,
        output_dir: Path
    ) -> Dict[str, Any]:
        """
        处理单个PDF页面
        
        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            output_dir: 输出目录
            
        Returns:
            处理结果
        """
        logger.info(f"处理第 {page_number} 页...")
        
        # 渲染页面
        image_bytes, image_array, image_size = self.render_pdf_page(pdf_path, page_number)
        
        # 调用OCR API
        ocr_result = self.call_ocr_api(image_bytes)
        
        # 提取结果
        markdown_text = ocr_result.get('result_cleaned', ocr_result.get('result', ''))
        image_regions = ocr_result.get('image_regions', [])
        
        # 创建pages目录并保存原始markdown
        pages_dir = output_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存原始markdown到pages目录
        page_file = pages_dir / f"page_{page_number:03d}.md"
        with open(page_file, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        logger.info(f"保存原始markdown到: {page_file.name}")
        
        # 创建images目录
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # 转换坐标并裁剪图片
        saved_images = []
        if image_regions:
            # 转换归一化坐标到像素坐标
            pixel_regions = self.convert_normalized_coords(image_regions, image_size)
            
            # 裁剪并保存图片
            saved_images = self.crop_and_save_images(
                image_array,
                pixel_regions,
                page_number,
                images_dir
            )
        
        # 处理markdown中的图片占位符
        final_markdown = self.process_markdown_images(markdown_text, saved_images)
        
        return {
            "page": page_number,
            "markdown": final_markdown,
            "images": saved_images,
            "image_regions": len(image_regions)
        }
    
    def convert(
        self,
        pdf_path: str,
        output_dir: str = None,
        start_page: int = None,
        end_page: int = None
    ) -> str:
        """
        转换PDF为Markdown
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（默认为PDF同目录）
            start_page: 起始页码（默认1）
            end_page: 结束页码（默认最后一页）
            
        Returns:
            输出markdown文件路径
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        # 设置输出目录
        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_output"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取页数
        doc = fitz.open(str(pdf_path))
        total_pages = doc.page_count
        doc.close()
        
        # 设置页码范围
        start_page = start_page or 1
        end_page = end_page or total_pages
        start_page = max(1, min(start_page, total_pages))
        end_page = max(start_page, min(end_page, total_pages))
        
        logger.info(f"开始转换 {pdf_path.name}")
        logger.info(f"页码范围: {start_page}-{end_page}，共 {end_page - start_page + 1} 页")
        logger.info(f"输出目录: {output_dir}")
        
        # 处理每一页
        all_markdown = []
        total_images = 0
        
        for page_num in range(start_page, end_page + 1):
            try:
                result = self.process_page(str(pdf_path), page_num, output_dir)
                
                # 只添加markdown内容，不添加页面标记（页码会在合并时处理）
                all_markdown.append(result['markdown'])
                
                total_images += len(result["images"])
                
                logger.info(f"第 {page_num} 页完成，包含 {len(result['images'])} 张图片")
                
            except Exception as e:
                logger.error(f"处理第 {page_num} 页失败: {e}")
                all_markdown.append(f"[处理失败: {str(e)}]")
        
        # 合并所有markdown，在每页之间添加页码和分隔符
        markdown_parts = []
        for idx, page_markdown in enumerate(all_markdown):
            page_num = start_page + idx
            if idx > 0:  # 第一页之前不需要分隔符
                markdown_parts.append(f"<center>第 {page_num - 1} 页</center>\n\n---\n")
            markdown_parts.append(page_markdown)
        
        # 在最后一页后添加页码标记
        if all_markdown:
            markdown_parts.append(f"\n<center>第 {end_page} 页</center>")
        
        final_markdown = "\n".join(markdown_parts)
        
        # 添加文档标题（使用冒号格式的论文编号）
        doc_title = f"论文编号: {pdf_path.stem}\n\n"
        final_markdown = doc_title + final_markdown
        
        # 保存markdown文件
        output_file = output_dir / f"{pdf_path.stem}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_markdown)
        
        logger.info(f"\n✅ 转换完成！")
        logger.info(f"📄 Markdown文件: {output_file}")
        logger.info(f"📁 各页原始MD: {output_dir}/pages/")
        logger.info(f"🖼️  图片总数: {total_images}")
        
        return str(output_file)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将PDF转换为Markdown格式，包含图片提取"
    )
    parser.add_argument(
        "pdf_path",
        help="PDF文件路径"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出目录（默认为PDF同目录）"
    )
    parser.add_argument(
        "-s", "--start-page",
        type=int,
        help="起始页码（默认1）"
    )
    parser.add_argument(
        "-e", "--end-page",
        type=int,
        help="结束页码（默认最后一页）"
    )
    parser.add_argument(
        "--api-url",
        help="OCR API URL（默认从环境变量DJANGO_OCR_API_URL读取）"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=144,
        help="渲染DPI（默认144）"
    )
    
    args = parser.parse_args()
    
    try:
        # 创建转换器
        converter = PDFToMarkdownConverter(
            ocr_api_url=args.api_url,
            dpi=args.dpi
        )
        
        # 执行转换
        output_file = converter.convert(
            pdf_path=args.pdf_path,
            output_dir=args.output,
            start_page=args.start_page,
            end_page=args.end_page
        )
        
        print(f"\n✅ 转换成功！")
        print(f"📄 输出文件: {output_file}")
        
    except Exception as e:
        print(f"\n❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()