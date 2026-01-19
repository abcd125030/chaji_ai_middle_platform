"""
主处理器: PDF文档完整处理流程

串联所有处理步骤，完成从PDF到Markdown的完整转换
"""
import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, List
import fitz  # PyMuPDF
from PIL import Image
import numpy as np

from .step1_text_extractor import TextExtractor
# from .step2_page_renderer import PageRenderer  # 已废弃，Step1已保存full_page.png
from .step3_semantic_segmentor import SemanticSegmentor, ImageRegion
from .step4_markdown_reconstructor import MarkdownReconstructor

logger = logging.getLogger('django')


class PDFProcessor:
    """PDF文档处理器 - 主控制器"""

    # 空间优化开关: 启用后使用bbox坐标进行重复锚点的位置选择
    USE_SPATIAL_OPTIMIZATION = os.getenv('USE_SPATIAL_OPTIMIZATION', 'true').lower() == 'true'

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = "qwen3-vl-plus",
        dpi: int = 144
    ):
        """
        初始化PDF处理器

        Args:
            api_key: DashScope API密钥
            base_url: API基础URL
            model: 模型名称
            dpi: PDF渲染DPI
        """
        # 从环境变量获取配置
        self.api_key = api_key or os.getenv('DASHSCOPE_API_KEY')
        self.base_url = base_url or os.getenv(
            'QWEN_BASE_URL',
            'https://dashscope.aliyuncs.com/compatible-mode/v1'
        )
        self.model = model
        self.dpi = dpi

        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

        # 初始化各个步骤的处理器
        # Step1: OCR文本提取器（使用DeepSeek-OCR）
        self.text_extractor = TextExtractor(
            ocr_dpi=self.dpi,
            ocr_mode='convert_to_markdown',
            ocr_max_tokens=8192,
            ocr_temperature=0.0
        )
        # Step2: 已废弃，不再重新渲染（Step1已保存full_page.png）
        # self.page_renderer = PageRenderer(dpi=dpi)
        # Step3: 语义分割器（使用qwen3-vl-plus识别图像区域）
        self.segmentor = SemanticSegmentor(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model
        )
        # Step4: Markdown重构器（使用qwen3-vl-plus插入图片）
        self.reconstructor = MarkdownReconstructor(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model
        )

        logger.info("PDF处理器初始化完成")

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """
        获取PDF总页数

        Args:
            pdf_path: PDF文件路径

        Returns:
            总页数
        """
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        doc.close()
        return page_count

    def _update_task_progress(self, task_id: str, total_pages: int, processed_pages: int):
        """
        更新数据库中的任务进度

        Args:
            task_id: 任务UUID
            total_pages: 总页数
            processed_pages: 已处理页数
        """
        try:
            from webapps.toolkit.models import PDFExtractorTask
            task = PDFExtractorTask.objects.get(id=task_id)
            task.total_pages = total_pages
            task.processed_pages = processed_pages
            task.save(update_fields=['total_pages', 'processed_pages', 'updated_at'])
        except Exception as e:
            logger.warning(f"更新任务进度失败: {task_id}, 错误: {str(e)}")

    def process_single_page(
        self,
        pdf_path: str,
        page_number: int,
        task_dir: Path,
        task_id: str = None,
        previous_page_content: str = None
    ) -> Dict[str, Any]:
        """
        处理单个PDF页面（4个步骤）

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            task_dir: 任务根目录
            task_id: 任务UUID（用于生成完整media路径）
            previous_page_content: 前一页的格式化内容（可选，用于上下文参考）

        Returns:
            页面处理结果
        """
        try:
            logger.info(f"开始处理第 {page_number} 页")

            # 标记为processing状态
            self.update_page_status(task_dir, page_number, 'processing')

            # 创建页面目录
            page_dir = task_dir / f"page_{page_number}"
            page_dir.mkdir(parents=True, exist_ok=True)

            # ==================== 步骤1: OCR提取文本并生成截图 ====================
            logger.info(f"[步骤1/4] OCR提取文本（DPI 144）并保存页面截图...")
            result = self.text_extractor.extract_page(
                pdf_path=pdf_path,
                page_number=page_number,
                output_dir=page_dir,
                save_debug=True  # 保存调试信息和full_page.png
            )

            if not result['success']:
                raise RuntimeError(f"页面 {page_number} OCR识别失败: {result.get('error')}")

            page_text = result['markdown_cleaned']  # 使用清理后的Markdown文本
            text_path = page_dir / f"page_{page_number}_step1_final.md"

            # ==================== 翻译step1的结果（如果需要） ====================
            # 从数据库获取任务翻译配置
            from webapps.toolkit.models import PDFExtractorTask
            task = PDFExtractorTask.objects.get(id=task_id)

            if task.translate:
                logger.info(f"[翻译] 翻译第 {page_number} 页的step1结果，目标语言: {task.target_language}")
                page_text = self._translate_page_content(
                    page_text,
                    task.target_language,
                    page_number
                )
                # 保存翻译后的内容覆盖原文件
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(page_text)
                logger.info(f"[翻译] 第 {page_number} 页翻译完成")

            # ==================== 步骤2: 读取截图（跳过重新渲染） ====================
            logger.info(f"[步骤2/4] 读取Step1生成的页面截图...")
            image_path = page_dir / "full_page.png"

            if not image_path.exists():
                raise FileNotFoundError(f"页面截图不存在: {image_path}")

            # 读取图片为numpy数组（供Step3使用）
            full_page_image = np.array(Image.open(image_path))
            logger.info(f"页面截图已读取 - 尺寸: {full_page_image.shape}")

            # ==================== 步骤3: 语义分割 ====================
            logger.info(f"[步骤3/4] 语义分割...")
            regions, region_paths = self.segmentor.segment_and_save(
                full_page_image,
                page_dir,
                page_number
            )

            # 读取分割图片（过滤掉visualization.png和metadata.json）
            region_images = []
            for region_path in region_paths:
                # 只读取image_*.png文件
                if region_path.name.startswith('image_') and region_path.suffix == '.png':
                    region_img = Image.open(region_path)
                    region_images.append(np.array(region_img))

            # 提取region bbox坐标列表
            region_bboxes = [region.bbox for region in regions]

            # ==================== 步骤4: Markdown重构 ====================
            logger.info(f"[步骤4/4] Markdown重构...")

            # 所有页面都统一经过Step4处理，无论是否有图片
            # 根据配置决定是否启用空间优化（传递bbox坐标）
            bbox_param = region_bboxes if self.USE_SPATIAL_OPTIMIZATION else None
            reconstructed_md, final_md_path = self.reconstructor.reconstruct_and_save(
                page_text,
                full_page_image,
                region_images,  # 可能为空列表（无图片页面）
                page_number,
                page_dir,
                task_id,
                bbox_param
            )

            if not region_images:
                logger.info(f"第 {page_number} 页无图片区域，直接使用OCR文本")

            logger.info(f"第 {page_number} 页处理完成")

            page_result = {
                'page': page_number,
                'status': 'completed',
                'text_length': len(page_text),
                'regions_count': len(regions),
                'text_file': str(text_path.relative_to(task_dir)),
                'full_image': str(image_path.relative_to(task_dir)),
                'region_files': [str(p.relative_to(task_dir)) for p in region_paths],
                'final_markdown': str(final_md_path.relative_to(task_dir)),
                'regions': [r.to_dict() for r in regions]
            }

            # 更新task.json中该页面的状态
            self.update_page_status(task_dir, page_number, 'completed', page_result)

            return page_result

        except Exception as e:
            logger.error(f"处理第 {page_number} 页失败: {str(e)}", exc_info=True)

            error_result = {
                'page': page_number,
                'status': 'error',
                'error': str(e)
            }

            # 更新task.json中该页面的错误状态
            self.update_page_status(task_dir, page_number, 'error', error_result)

            return error_result

    def _normalize_heading_levels(self, markdown_text: str) -> str:
        """
        规范化Markdown标题层级，确保全文档一致性

        规则：
        - 移除单独的 # 一级标题（保留为文档标题）
        - 将所有标题统一调整：章(##) → 节(###) → 子节(####)
        - 保持相对层级关系不变

        Args:
            markdown_text: 原始markdown文本

        Returns:
            规范化后的markdown文本
        """
        import re

        lines = markdown_text.split('\n')
        normalized_lines = []

        for line in lines:
            # 检测标题行
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                title_content = heading_match.group(2)

                # 跳过页面标题格式"第 X 页"
                if level == 1 and re.match(r'^第\s*\d+\s*页', title_content):
                    # 完全跳过页面标题，不输出
                    continue

                # 其他一级标题降级为二级标题
                if level == 1:
                    normalized_lines.append(f"## {title_content}")
                    continue

                normalized_lines.append(line)
            else:
                normalized_lines.append(line)

        return '\n'.join(normalized_lines)

    def merge_page_markdowns(
        self,
        task_dir: Path,
        page_count: int,
        task_id: str,
        start_page: int = 1,
        end_page: int = None
    ) -> Path:
        """
        合并所有页面的markdown文档，并确保标题层级一致性

        Args:
            task_dir: 任务目录
            page_count: 总页数
            task_id: 任务UUID
            start_page: 起始页码
            end_page: 结束页码

        Returns:
            最终markdown文件路径
        """
        try:
            if end_page is None:
                end_page = start_page + page_count - 1

            logger.info(f"合并页码范围 {start_page}-{end_page} 的markdown...")

            merged_content = []

            for page_num in range(start_page, end_page + 1):
                # 统一读取page_{num}_final.md（所有页面都由Step4生成）
                final_md_path = task_dir / f"page_{page_num}" / f"page_{page_num}_final.md"

                if final_md_path.exists():
                    with open(final_md_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 规范化标题层级
                    content = self._normalize_heading_levels(content)

                    # 直接添加内容，不添加页面分隔符
                    # 如果需要页面间的间隔，只添加适当的空行
                    if page_num > 1:
                        merged_content.append("\n\n")

                    merged_content.append(content)
                else:
                    logger.warning(f"第 {page_num} 页markdown不存在: {final_md_path}，跳过")

            # 保存最终文档
            final_path = task_dir / f"{task_id}_result.md"
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(''.join(merged_content))

            logger.info(f"Markdown合并完成（已规范化标题层级）: {final_path}")

            return final_path

        except Exception as e:
            logger.error(f"合并markdown失败: {str(e)}", exc_info=True)
            raise

    def _translate_page_content(
        self,
        content: str,
        target_language: str,
        page_number: int
    ) -> str:
        """
        使用qwen3-max模型翻译单页的markdown内容

        Args:
            content: markdown内容字符串
            target_language: 目标语言（'zh'或'en'）
            page_number: 页码（用于日志）

        Returns:
            翻译后的markdown内容字符串
        """
        try:
            # 准备翻译提示词
            language_map = {
                'zh': '中文',
                'en': '英文'
            }
            target_lang_name = language_map.get(target_language, '中文')

            system_prompt = f"""你是一个专业的文档翻译助手。请将用户提供的Markdown文档翻译成{target_lang_name}。

要求：
1. 保持Markdown格式完全不变（包括标题、列表、代码块、图片链接等）
2. 仅翻译文本内容，不要翻译代码、公式、图片路径
3. **严格保持LaTeX公式的格式**：
   - 块级公式（$$...$$）必须保持为块级公式，不要改为行内公式（$...$）
   - 行内公式（$...$）必须保持为行内公式
   - 包含 \\begin{{array}}、\\begin{{cases}} 等环境的公式必须使用块级公式 $$...$$
   - 公式内部的命令（如 \\mathrm、\\hat、\\left、\\right 等）不要翻译
4. 保持专业术语的准确性
5. 保持原文的段落结构和排版
6. 直接输出翻译后的Markdown内容，不要添加任何说明文字"""

            user_prompt = f"请将以下Markdown文档翻译成{target_lang_name}：\n\n{content}"

            # 调用qwen3-max模型进行翻译
            from llm.core_service import CoreLLMService
            from llm.config_manager import ModelConfigManager

            core_service = CoreLLMService()
            config_manager = ModelConfigManager()

            # 获取qwen3-max的模型配置
            model_config = config_manager.get_model_config('qwen3-max')

            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 调用LLM
            response = core_service.call_llm(
                messages=messages,
                temperature=0.3,
                max_tokens=8192,
                source_app='pdf_extractor',
                source_function='translate_page',
                **model_config
            )

            translated_content = response['choices'][0]['message']['content'].strip()

            logger.info(f"第 {page_number} 页翻译成功")

            return translated_content

        except Exception as e:
            logger.error(f"第 {page_number} 页翻译失败: {str(e)}", exc_info=True)
            # 翻译失败时返回原内容
            return content

    def init_task_json(
        self,
        task_dir: Path,
        total_pages: int
    ) -> None:
        """
        初始化task.json，创建pending状态

        Args:
            task_dir: 任务目录
            total_pages: 总页数
        """
        try:
            # 初始化所有页面为pending状态
            pages = [
                {
                    'page': i,
                    'status': 'pending'
                }
                for i in range(1, total_pages + 1)
            ]

            task_data = {
                'status': 'pending',
                'total_pages': total_pages,
                'processed_pages': 0,
                'pages': pages
            }

            # 保存
            task_json_path = task_dir / 'task.json'
            with open(task_json_path, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)

            logger.info(f"任务初始化完成，创建task.json: {task_json_path}")

        except Exception as e:
            logger.error(f"初始化task.json失败: {str(e)}", exc_info=True)

    def update_page_status(
        self,
        task_dir: Path,
        page_number: int,
        status: str,
        page_data: Dict[str, Any] = None
    ) -> None:
        """
        更新单个页面的状态

        Args:
            task_dir: 任务目录
            page_number: 页码
            status: 状态（processing/completed/error）
            page_data: 页面处理结果数据（可选）
        """
        try:
            task_json_path = task_dir / 'task.json'

            # 读取现有数据
            with open(task_json_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)

            # 更新对应页面的状态
            for page_info in task_data['pages']:
                if page_info['page'] == page_number:
                    page_info['status'] = status
                    # 如果提供了详细数据，更新到页面信息中
                    if page_data:
                        page_info.update(page_data)
                    break

            # 重新计算整体状态和已处理页数
            task_data['processed_pages'] = sum(
                1 for p in task_data['pages'] if p.get('status') == 'completed'
            )

            # 更新整体状态
            if task_data['status'] == 'pending':
                # 第一次开始处理，改为processing
                task_data['status'] = 'processing'
            elif all(p.get('status') == 'completed' for p in task_data['pages']):
                # 全部完成
                task_data['status'] = 'completed'
            elif any(p.get('status') == 'error' for p in task_data['pages']):
                # 有错误
                task_data['status'] = 'error'

            # 保存
            with open(task_json_path, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"更新页面 {page_number} 状态为 {status}")

        except Exception as e:
            logger.error(f"更新页面状态失败: {str(e)}", exc_info=True)

    def process_pdf_document(
        self,
        pdf_path: str,
        task_id: str,
        task_dir: Path
    ) -> Dict[str, Any]:
        """
        处理完整PDF文档

        Args:
            pdf_path: PDF文件路径
            task_id: 任务UUID
            task_dir: 任务目录

        Returns:
            处理结果
        """
        try:
            logger.info(f"开始处理PDF文档: {pdf_path}")

            # 获取总页数
            page_count = self.get_pdf_page_count(pdf_path)
            logger.info(f"PDF总页数: {page_count}")

            # 从数据库获取任务信息,检查页码范围
            from webapps.toolkit.models import PDFExtractorTask
            task = PDFExtractorTask.objects.get(id=task_id)

            # 处理页码范围
            start_page = task.page_range_start or 1
            end_page = task.page_range_end or page_count

            # 验证并调整页码范围
            if start_page > page_count:
                # 起始页超出文档范围，终止处理
                error_msg = f"指定的起始页 {start_page} 超出文档页数 {page_count}"
                logger.error(error_msg)
                task.status = 'error'
                task.save()
                return {
                    'status': 'error',
                    'task_id': task_id,
                    'error': error_msg
                }

            # 调整结束页（如果超出范围，则调整为最后一页）
            if end_page > page_count:
                logger.warning(f"结束页 {end_page} 超出文档页数 {page_count}，调整为最后一页")
                end_page = page_count

            # 确保起始页不大于结束页
            if start_page > end_page:
                start_page = end_page

            actual_page_count = end_page - start_page + 1
            logger.info(f"处理页码范围: {start_page}-{end_page}，共 {actual_page_count} 页")

            # 初始化进度：总页数已知，已处理0页
            self._update_task_progress(task_id, total_pages=actual_page_count, processed_pages=0)

            # 初始化task.json，所有页面状态为pending
            self.init_task_json(task_dir, actual_page_count)

            # 处理每一页，传递前页内容作为上下文，实现跨页格式一致性
            page_results = []
            previous_page_content = None  # 用于存储前一页的格式化内容

            for page_num in range(start_page, end_page + 1):
                page_result = self.process_single_page(
                    pdf_path,
                    page_num,
                    task_dir,
                    task_id,
                    previous_page_content=previous_page_content  # 传入前页内容
                )
                page_results.append(page_result)

                # 如果处理成功，读取当前页的格式化内容作为下一页的参考
                if page_result.get('status') == 'completed':
                    try:
                        final_md_path = task_dir / page_result.get('final_markdown', '')
                        if final_md_path.exists():
                            with open(final_md_path, 'r', encoding='utf-8') as f:
                                previous_page_content = f.read()
                                logger.debug(f"已缓存第 {page_num} 页内容作为下一页的格式参考")
                    except Exception as e:
                        logger.warning(f"读取第 {page_num} 页内容失败，下一页将无上下文参考: {str(e)}")
                        previous_page_content = None

                # 实时更新数据库进度
                processed_count = sum(1 for r in page_results if r.get('status') == 'completed')
                self._update_task_progress(task_id, total_pages=actual_page_count, processed_pages=processed_count)
                logger.info(f"进度更新: {processed_count}/{actual_page_count} 页已完成")

            # 合并所有页面（已经是翻译后的内容）
            final_md_path = self.merge_page_markdowns(
                task_dir,
                actual_page_count,
                task_id,
                start_page,
                end_page
            )

            # 最终结果
            result = {
                'status': 'success',
                'task_id': task_id,
                'total_pages': actual_page_count,
                'processed_pages': sum(
                    1 for r in page_results if r.get('status') == 'completed'
                ),
                'final_markdown': str(final_md_path),
                'page_results': page_results
            }

            logger.info(f"PDF文档处理完成: {task_id}")

            return result

        except Exception as e:
            logger.error(f"处理PDF文档失败: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'task_id': task_id,
                'error': str(e)
            }
