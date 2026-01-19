"""
Step1 页面元素分析器

分析PDF页面的元素构成，生成解析指标，用于决策最佳提取策略
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any
import pdfplumber
import fitz  # PyMuPDF

logger = logging.getLogger('django')


@dataclass
class PageAnalysisResult:
    """页面分析结果"""
    page_number: int

    # 页面尺寸
    width: float
    height: float

    # pdfplumber 分析结果
    text_length: int
    word_count: int
    table_count: int
    image_count: int
    line_count: int
    rect_count: int
    curve_count: int

    # PyMuPDF 分析结果
    text_blocks_count: int
    link_count: int
    drawing_count: int

    # 原始文本内容（用于质量评估）
    raw_text: str

    # 字体编码信息
    has_cid_fonts: bool = False  # 是否包含CID字体（可能导致文本提取乱码）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'page_number': self.page_number,
            'dimensions': {
                'width': self.width,
                'height': self.height
            },
            'pdfplumber_metrics': {
                'text_length': self.text_length,
                'word_count': self.word_count,
                'table_count': self.table_count,
                'image_count': self.image_count,
                'line_count': self.line_count,
                'rect_count': self.rect_count,
                'curve_count': self.curve_count
            },
            'pymupdf_metrics': {
                'text_blocks_count': self.text_blocks_count,
                'link_count': self.link_count,
                'drawing_count': self.drawing_count
            },
            'font_encoding': {
                'has_cid_fonts': self.has_cid_fonts
            },
            'raw_text_preview': self.raw_text[:200] if self.raw_text else ""
        }

    def is_text_rich(self) -> bool:
        """判断是否文本丰富"""
        return self.text_length >= 50 and self.word_count >= 10

    def is_image_dominant(self) -> bool:
        """判断是否图片占主导"""
        return self.image_count > 0 and self.text_length < 50

    def is_complex_drawing(self) -> bool:
        """判断是否复杂绘图页面"""
        return (self.drawing_count > 100 or self.curve_count > 500) and self.text_length < 50

    def get_complexity_score(self) -> float:
        """
        计算页面复杂度分数（0-1）

        考虑因素：
        - 绘图元素数量
        - 图片数量
        - 表格数量
        - 文本密度
        """
        # 归一化各项指标
        drawing_score = min(self.drawing_count / 1000, 1.0)  # 1000+ 绘图元素为高复杂度
        image_score = min(self.image_count / 5, 1.0)  # 5+ 图片为高复杂度
        curve_score = min(self.curve_count / 2000, 1.0)  # 2000+ 曲线为高复杂度
        table_score = min(self.table_count / 3, 1.0)  # 3+ 表格为高复杂度

        # 文本密度越低，复杂度越高
        text_density = self.text_length / (self.width * self.height) if (self.width * self.height) > 0 else 0
        text_deficit_score = max(0, 1 - text_density * 10000)  # 文本密度阈值

        # 加权平均
        complexity = (
            drawing_score * 0.3 +
            image_score * 0.2 +
            curve_score * 0.2 +
            table_score * 0.1 +
            text_deficit_score * 0.2
        )

        return complexity


class PageAnalyzer:
    """PDF页面元素分析器"""

    def __init__(self):
        """初始化分析器"""
        pass

    def analyze_page(self, pdf_path: str, page_number: int) -> PageAnalysisResult:
        """
        分析PDF页面的元素构成

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）

        Returns:
            PageAnalysisResult: 页面分析结果

        Raises:
            FileNotFoundError: PDF文件不存在
            ValueError: 页码无效
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        logger.info(f"开始分析页面 {page_number} 的元素构成")

        # 初始化结果变量
        width = height = 0
        text_length = word_count = table_count = 0
        image_count = line_count = rect_count = curve_count = 0
        text_blocks_count = link_count = drawing_count = 0
        raw_text = ""

        # 方法1: 使用 pdfplumber 分析
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                if page_number < 1 or page_number > total_pages:
                    raise ValueError(f"页码无效: {page_number}，总页数: {total_pages}")

                page = pdf.pages[page_number - 1]

                # 页面尺寸
                width = float(page.width)
                height = float(page.height)

                # 提取文本
                text = page.extract_text()
                raw_text = text if text else ""
                text_length = len(raw_text)

                # 提取单词
                words = page.extract_words()
                word_count = len(words)

                # 提取表格
                tables = page.extract_tables()
                table_count = len(tables)

                # 提取图片
                images = page.images
                image_count = len(images)

                # 提取线条
                lines = page.lines
                line_count = len(lines)

                # 提取矩形
                rects = page.rects
                rect_count = len(rects)

                # 提取曲线
                curves = page.curves
                curve_count = len(curves)

                logger.debug(f"pdfplumber分析完成 - 文本长度: {text_length}, 单词数: {word_count}, "
                           f"表格: {table_count}, 图片: {image_count}")

        except Exception as e:
            logger.error(f"pdfplumber分析失败: {str(e)}", exc_info=True)
            raise

        # 方法2: 使用 PyMuPDF 补充分析
        has_cid_fonts = False
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_number - 1]

            # 提取文本块
            text_blocks = page.get_text('blocks')
            text_blocks_count = len(text_blocks)

            # 提取链接
            links = page.get_links()
            link_count = len(links)

            # 提取绘图命令
            drawings = page.get_drawings()
            drawing_count = len(drawings)

            # 检测CID字体
            has_cid_fonts = self._detect_cid_fonts(page)
            if has_cid_fonts:
                logger.warning(
                    f"页面 {page_number} 检测到CID字体（Identity-H编码），"
                    f"直接文本提取可能产生乱码"
                )

            doc.close()

            logger.debug(f"PyMuPDF分析完成 - 文本块: {text_blocks_count}, "
                       f"链接: {link_count}, 绘图: {drawing_count}, "
                       f"CID字体: {has_cid_fonts}")

        except Exception as e:
            logger.error(f"PyMuPDF分析失败: {str(e)}", exc_info=True)
            # 不抛出异常，使用默认值继续

        # 构建分析结果
        result = PageAnalysisResult(
            page_number=page_number,
            width=width,
            height=height,
            text_length=text_length,
            word_count=word_count,
            table_count=table_count,
            image_count=image_count,
            line_count=line_count,
            rect_count=rect_count,
            curve_count=curve_count,
            text_blocks_count=text_blocks_count,
            link_count=link_count,
            drawing_count=drawing_count,
            raw_text=raw_text,
            has_cid_fonts=has_cid_fonts
        )

        # 记录综合指标
        logger.info(
            f"页面 {page_number} 分析完成 - "
            f"文本: {text_length}字符/{word_count}词, "
            f"图片: {image_count}, "
            f"表格: {table_count}, "
            f"绘图: {drawing_count}, "
            f"复杂度: {result.get_complexity_score():.2f}"
        )

        return result

    def analyze_multiple_pages(
        self,
        pdf_path: str,
        start_page: int = 1,
        end_page: int = None
    ) -> Dict[int, PageAnalysisResult]:
        """
        分析多个页面

        Args:
            pdf_path: PDF文件路径
            start_page: 起始页码（从1开始）
            end_page: 结束页码（包含，None表示到最后一页）

        Returns:
            Dict[int, PageAnalysisResult]: 页码到分析结果的映射
        """
        pdf_path = Path(pdf_path)

        # 获取总页数
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

        if end_page is None:
            end_page = total_pages

        # 验证页码范围
        if start_page < 1 or end_page > total_pages or start_page > end_page:
            raise ValueError(
                f"页码范围无效: {start_page}-{end_page}，总页数: {total_pages}"
            )

        logger.info(f"开始批量分析页面 {start_page} 到 {end_page}")

        results = {}
        for page_num in range(start_page, end_page + 1):
            try:
                result = self.analyze_page(pdf_path, page_num)
                results[page_num] = result
            except Exception as e:
                logger.error(f"分析页面 {page_num} 失败: {str(e)}")
                # 继续分析下一页

        logger.info(f"批量分析完成，成功分析 {len(results)} 页")

        return results

    def _detect_cid_fonts(self, page) -> bool:
        """
        检测页面是否使用了CID字体（可能导致文本提取乱码）

        CID (Character Identifier) 字体使用字符ID映射到字形，而不是直接的Unicode编码。
        特别是使用Identity-H编码的CID字体，PyMuPDF和pdfplumber都无法正确解析其ToUnicode映射表，
        导致提取的中文文本出现乱码。

        Args:
            page: PyMuPDF page对象

        Returns:
            bool: 如果检测到CID字体返回True
        """
        try:
            fonts = page.get_fonts()
            for font in fonts:
                # font结构: (xref, type, basefont, name, encoding, ...)
                # font[1] 是字体类型，font[5] 是编码
                if len(font) >= 6:
                    font_type = font[1]  # 'cid' 表示CID字体
                    encoding = font[5]   # 'Identity-H' 是有问题的编码

                    # 检测CID字体 + Identity-H编码组合（最容易出现乱码）
                    if font_type == 'cid' and encoding == 'Identity-H':
                        logger.debug(
                            f"检测到CID字体: {font[3]}, 编码: {encoding}, "
                            f"文本提取可能出现乱码"
                        )
                        return True

            return False

        except Exception as e:
            logger.error(f"CID字体检测失败: {str(e)}", exc_info=True)
            return False
