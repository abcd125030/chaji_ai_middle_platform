"""
步骤4: Markdown重构器

简化版本：直接读取step1产生的markdown文件，替换[[[!image]]]占位符为step3产生的局部图
"""
import logging
import time
import re
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger('django')


class MarkdownReconstructor:
    """Markdown重构器 - 基于占位符替换（简化版）"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """
        初始化Markdown重构器（简化版不需要LLM）

        Args:
            api_key: 保留参数以兼容旧接口
            base_url: 保留参数以兼容旧接口
            model: 保留参数以兼容旧接口
        """
        logger.info("初始化Markdown重构器（简化版：占位符替换模式）")

    def reconstruct_markdown(
        self,
        page_text: str = None,
        full_page_image = None,
        region_images: List = None,
        page_number: int = 1,
        output_dir: Path = None,
        task_id: str = None,
        region_bboxes: List[List[int]] = None
    ) -> Tuple[str, dict]:
        """
        重构markdown（占位符替换方法）

        Args:
            page_text: 保留参数以兼容旧接口，不再使用
            full_page_image: 保留参数以兼容旧接口，不再使用
            region_images: 保留参数以兼容旧接口，不再使用
            page_number: 页码
            output_dir: 输出目录（必需，用于读取step1的md文件）
            task_id: 任务UUID（用于生成完整media路径）
            region_bboxes: 保留参数以兼容旧接口，不再使用

        Returns:
            元组(重构后的markdown内容, 统计字典)
        """
        try:
            start_time = time.time()

            if not output_dir:
                raise ValueError("output_dir 参数是必需的")

            output_dir = Path(output_dir)

            # 读取step1产生的markdown文件
            step1_md_path = output_dir / f"page_{page_number}_step1_final.md"
            if not step1_md_path.exists():
                logger.error(f"Step1 markdown文件不存在: {step1_md_path}")
                return "", {
                    'total': 0,
                    'successful': 0,
                    'failed': 0,
                    'error': f'Step1 markdown文件不存在: {step1_md_path}'
                }

            with open(step1_md_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            logger.info(f"读取Step1 markdown文件: {step1_md_path}, 长度: {len(markdown_content)}")

            # 查找所有 [[[!image]]] 占位符
            placeholder_pattern = r'\[\[\[!image\]\]\]'
            placeholders = list(re.finditer(placeholder_pattern, markdown_content))
            total_placeholders = len(placeholders)

            logger.info(f"发现 {total_placeholders} 个图片占位符")

            # 检查step3产生的局部图数量
            step3_images = sorted(output_dir.glob("image_*.png"))
            total_images = len(step3_images)

            logger.info(f"Step3产生了 {total_images} 个局部图: {[img.name for img in step3_images]}")

            # 验证数量一致性
            if total_placeholders != total_images:
                logger.warning(
                    f"占位符数量({total_placeholders})与局部图数量({total_images})不一致！"
                )

            # 替换占位符
            reconstructed_md = markdown_content
            successful_count = 0
            failed_count = 0

            # 从后往前替换，避免位置偏移
            for idx, placeholder_match in enumerate(reversed(placeholders)):
                image_idx = total_placeholders - idx  # 从后往前，所以要反转索引

                # 构建图片引用
                if task_id:
                    # 使用Django media完整路径
                    image_path = f"/media/oss-bucket/_toolkit/_extractor/{task_id}/page_{page_number}/image_{image_idx}.png"
                else:
                    # 降级为相对路径
                    image_path = f"page_{page_number}/image_{image_idx}.png"

                # 检查对应的局部图是否存在
                expected_image = output_dir / f"image_{image_idx}.png"
                if not expected_image.exists():
                    logger.warning(f"局部图不存在: {expected_image}, 跳过此占位符")
                    failed_count += 1
                    continue

                # 替换占位符为markdown图片语法
                image_ref = f"![图片 {image_idx}]({image_path})"

                start_pos = placeholder_match.start()
                end_pos = placeholder_match.end()

                reconstructed_md = (
                    reconstructed_md[:start_pos] +
                    image_ref +
                    reconstructed_md[end_pos:]
                )

                successful_count += 1
                logger.info(f"替换占位符 #{image_idx}: {image_ref}")

            # 计算处理时间
            processing_time_ms = (time.time() - start_time) * 1000

            stats = {
                'total': total_placeholders,
                'successful': successful_count,
                'failed': failed_count,
                'processing_time_ms': processing_time_ms,
                'total_images': total_images,
                'match_results': []  # 保留字段以兼容旧接口
            }

            logger.info(
                f"Markdown重构完成 - 原文 {len(markdown_content)} -> {len(reconstructed_md)} 字符，"
                f"成功替换 {successful_count}/{total_placeholders} 个占位符"
            )

            return reconstructed_md, stats

        except Exception as e:
            logger.error(f"Markdown重构失败: {str(e)}", exc_info=True)
            return "", {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'error': str(e)
            }

    def save_markdown(
        self,
        markdown_content: str,
        output_path: Path
    ) -> Path:
        """
        保存markdown内容到文件

        Args:
            markdown_content: markdown内容
            output_path: 输出文件路径

        Returns:
            保存的文件路径
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            logger.info(f"Markdown已保存到: {output_path}")

            return output_path

        except Exception as e:
            logger.error(
                f"保存Markdown到 {output_path} 失败: {str(e)}",
                exc_info=True
            )
            raise

    def reconstruct_and_save(
        self,
        page_text: str = None,
        full_page_image = None,
        region_images: List = None,
        page_number: int = 1,
        output_dir: Path = None,
        task_id: str = None,
        region_bboxes: List[List[int]] = None
    ) -> Tuple[str, Path]:
        """
        重构markdown并保存

        Args:
            page_text: 保留参数以兼容旧接口，不再使用
            full_page_image: 保留参数以兼容旧接口，不再使用
            region_images: 保留参数以兼容旧接口，不再使用
            page_number: 页码
            output_dir: 输出目录（必需）
            task_id: 任务UUID（用于生成完整media路径）
            region_bboxes: 保留参数以兼容旧接口，不再使用

        Returns:
            (重构后的markdown内容, 保存的文件路径)
        """
        # 重构markdown
        reconstructed_md, stats = self.reconstruct_markdown(
            page_text=page_text,
            full_page_image=full_page_image,
            region_images=region_images,
            page_number=page_number,
            output_dir=output_dir,
            task_id=task_id,
            region_bboxes=region_bboxes
        )

        # 统一保存为page_{num}_final.md（无论是否有图片）
        output_path = Path(output_dir) / f"page_{page_number}_final.md"
        saved_path = self.save_markdown(reconstructed_md, output_path)

        # 保存简化的统计报告
        report_path = Path(output_dir) / f"page_{page_number}_step4_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"Step4 Markdown重构报告\n")
            f.write(f"=" * 60 + "\n")
            f.write(f"页码: {page_number}\n")
            f.write(f"占位符总数: {stats.get('total', 0)}\n")
            f.write(f"成功替换: {stats.get('successful', 0)}\n")
            f.write(f"失败数: {stats.get('failed', 0)}\n")
            f.write(f"局部图总数: {stats.get('total_images', 0)}\n")
            f.write(f"处理时间: {stats.get('processing_time_ms', 0):.2f} ms\n")
            if 'error' in stats:
                f.write(f"错误信息: {stats['error']}\n")

        logger.info(f"Step4报告已保存: {report_path}")
        logger.info(
            f"Step4完成 - 替换 {stats.get('successful', 0)}/{stats.get('total', 0)} 个占位符，"
            f"耗时 {stats.get('processing_time_ms', 0):.2f} ms"
        )

        return reconstructed_md, saved_path
