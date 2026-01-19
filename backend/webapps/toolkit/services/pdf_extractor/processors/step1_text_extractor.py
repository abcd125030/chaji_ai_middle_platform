"""
Step1: PDF文本提取器（OCR版）

简化的PDF文本提取流程：
1. 对每一页渲染成 DPI 144 的图片
2. 将图片转换为base64
3. 通过HTTP请求调用Django OCR视图
4. 获取识别结果（Markdown格式）

该版本移除了复杂的页面分析和策略决策，直接使用OCR模型识别。
"""
import logging
import base64
import os
import requests
import re
from pathlib import Path
from typing import Dict, Any
import fitz  # PyMuPDF
from html.parser import HTMLParser

logger = logging.getLogger('django')


class HTMLTableParser(HTMLParser):
    """HTML表格解析器，用于将HTML表格转换为Markdown表格"""

    def __init__(self):
        super().__init__()
        self.tables = []  # 存储所有表格数据
        self.current_table = None
        self.current_row = None
        self.current_cell = None
        self.in_thead = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.current_table = {'rows': []}
        elif tag == 'thead':
            self.in_thead = True
        elif tag == 'tr' and self.current_table is not None:
            self.current_row = []
        elif tag in ('td', 'th') and self.current_row is not None:
            self.current_cell = ''

    def handle_endtag(self, tag):
        if tag == 'table' and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None
        elif tag == 'thead':
            self.in_thead = False
        elif tag == 'tr' and self.current_row is not None:
            if self.current_table is not None:
                self.current_table['rows'].append({
                    'cells': self.current_row,
                    'is_header': self.in_thead
                })
            self.current_row = None
        elif tag in ('td', 'th') and self.current_cell is not None:
            if self.current_row is not None:
                self.current_row.append(self.current_cell.strip())
            self.current_cell = None

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell += data


def html_table_to_markdown(html_table: str) -> str:
    """
    将HTML表格转换为Markdown表格

    Args:
        html_table: HTML表格字符串

    Returns:
        Markdown表格字符串
    """
    parser = HTMLTableParser()
    parser.feed(html_table)

    if not parser.tables:
        return html_table

    table_data = parser.tables[0]  # 处理第一个表格
    rows = table_data['rows']

    if not rows:
        return html_table

    # 构建Markdown表格
    markdown_lines = []

    # 确定列数
    max_cols = max(len(row['cells']) for row in rows)

    # 处理表头（第一行或标记为header的行）
    header_row = rows[0]
    header_cells = header_row['cells'] + [''] * (max_cols - len(header_row['cells']))
    markdown_lines.append('| ' + ' | '.join(header_cells) + ' |')

    # 添加分隔行
    markdown_lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')

    # 处理数据行
    for row in rows[1:]:
        cells = row['cells'] + [''] * (max_cols - len(row['cells']))
        markdown_lines.append('| ' + ' | '.join(cells) + ' |')

    return '\n'.join(markdown_lines)


def convert_html_tables_to_markdown(text: str) -> str:
    """
    将文本中的所有HTML表格转换为Markdown表格

    Args:
        text: 包含HTML表格的文本

    Returns:
        转换后的文本
    """
    # 匹配HTML表格（支持多行和嵌套标签）
    table_pattern = re.compile(r'<table>.*?</table>', re.DOTALL | re.IGNORECASE)

    def replace_table(match):
        html_table = match.group(0)
        try:
            return html_table_to_markdown(html_table)
        except Exception as e:
            logger.warning(f"转换HTML表格失败: {str(e)}")
            return html_table

    result = table_pattern.sub(replace_table, text)

    # 统计转换数量
    original_count = len(table_pattern.findall(text))
    if original_count > 0:
        logger.info(f"已将 {original_count} 个HTML表格转换为Markdown格式")

    return result


def clean_html_tags(text: str) -> str:
    """
    清理OCR返回的其他HTML标签，转换为纯文本或Markdown

    Args:
        text: 包含HTML标签的文本

    Returns:
        清理后的文本
    """
    # 加粗标签 <b>, <strong> -> **text**
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.IGNORECASE | re.DOTALL)

    # 斜体标签 <i>, <em> -> *text*
    text = re.sub(r'<i>(.*?)</i>', r'*\1*', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<em>(.*?)</em>', r'*\1*', text, flags=re.IGNORECASE | re.DOTALL)

    # 删除线 <del>, <s> -> ~~text~~
    text = re.sub(r'<del>(.*?)</del>', r'~~\1~~', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<s>(.*?)</s>', r'~~\1~~', text, flags=re.IGNORECASE | re.DOTALL)

    # 居中标签 <center> -> 直接移除标签保留内容
    text = re.sub(r'<center>(.*?)</center>', r'\1', text, flags=re.IGNORECASE | re.DOTALL)

    # 段落标签 <p> -> 保留内容并添加空行
    text = re.sub(r'<p>(.*?)</p>', r'\1\n\n', text, flags=re.IGNORECASE | re.DOTALL)

    # 换行标签 <br>, <br/>, <br /> -> 换行
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)

    # 链接标签 <a href="url">text</a> -> [text](url)
    text = re.sub(r'<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE | re.DOTALL)

    # 代码标签 <code> -> `text`
    text = re.sub(r'<code>(.*?)</code>', r'`\1`', text, flags=re.IGNORECASE | re.DOTALL)

    # 通用清理：移除常见的容器标签（保留内容）
    # div, span, u, font, etc.
    container_tags = ['div', 'span', 'u', 'font', 'sup', 'sub', 'mark']
    for tag in container_tags:
        text = re.sub(rf'<{tag}[^>]*>(.*?)</{tag}>', r'\1', text, flags=re.IGNORECASE | re.DOTALL)

    # 清理多余的空行（超过2个连续换行）
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


def convert_latex_math_syntax(text: str) -> str:
    r"""
    将LaTeX原生数学公式语法转换为remarkMath支持的格式

    LaTeX原生语法:
    - 行内公式: \(...\)
    - 块级公式: \[...\]

    remarkMath支持的语法:
    - 行内公式: $...$
    - 块级公式: $$...$$

    Args:
        text: 包含LaTeX公式的文本

    Returns:
        转换后的文本
    """
    # 块级公式: \[...\] -> $$...$$
    # 需要确保公式前后有空行
    text = re.sub(r'\\\[(.*?)\\\]', r'\n\n$$\1$$\n\n', text, flags=re.DOTALL)

    # 行内公式: \(...\) -> $...$
    text = re.sub(r'\\\((.*?)\\\)', r'$\1$', text, flags=re.DOTALL)

    # 清理多余的连续空行（转换可能产生的）
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


def merge_split_latex_arrays(text: str) -> str:
    r"""
    合并被OCR错误拆分的LaTeX分段函数

    OCR可能将一个完整的分段函数拆分成多个公式块：
    $$...\left\{ \begin{array}{ll} 第一行 & 条件1,$$   ← 缺少 \end{array} \right.
    $$第二行 & 条件2 \end{array} \right.$$              ← 缺少 \left\{ \begin{array}

    Args:
        text: 包含LaTeX公式的文本

    Returns:
        合并后的文本
    """
    # 匹配模式：
    # 1. 第一个公式块：包含 \left\{ 和 \begin{array}，但没有 \end{array}
    # 2. 第二个公式块：没有 \left\{ 和 \begin{array}，但有 \end{array} 和 \right.，且开头是 } &
    pattern = re.compile(
        r'(\$\$[^\$]*?\\left\\\{[^\$]*?\\begin\{array\}[^\$]*?\$\$)'  # 第一个块：有开头标记，没有结尾
        r'(\s*)'                                                       # 中间空白
        r'(\$\$\s*[^\$]*?\}\s*&[^\$]*?\\end\{array\}\s*\\right[\.\}]\s*\$\$)',  # 第二个块：没有开头，有结尾
        re.DOTALL
    )

    def merge_blocks(match):
        """合并两个被拆分的公式块"""
        first_block = match.group(1)
        second_block = match.group(3)

        # 检查第一个块是否已经有 \end{array}（避免误匹配）
        first_content = first_block.strip('$').strip()
        if r'\end{array}' in first_content:
            # 不应该合并，这可能不是被拆分的情况
            return match.group(0)

        # 去掉第二个块的 $$ 和结尾的 \end{array} \right.
        second_content = second_block.strip('$').strip()
        second_content = re.sub(r'\s*\\end\{array\}\s*\\right[\.\}]\s*$', '', second_content)

        # 去掉第一个块末尾可能的逗号或其他标点
        first_content = first_content.rstrip(',').rstrip()

        # 合并：在第一个内容后添加 \\（LaTeX换行），然后接第二个内容，最后加上结尾标记
        # 确保公式块前后有空行（remarkMath要求）
        merged = f"\n\n$${first_content} \\\\\n{second_content} \\end{{array}} \\right.$$\n\n"

        logger.info("LaTeX公式修复: 合并了被OCR拆分的分段函数")

        return merged

    # 应用合并，可能需要多次（如果一个函数被拆成3个或更多块）
    previous_text = None
    max_iterations = 10  # 防止无限循环
    iteration = 0

    while previous_text != text and iteration < max_iterations:
        previous_text = text
        text = pattern.sub(merge_blocks, text)
        iteration += 1

    if iteration > 1:
        logger.info(f"LaTeX公式修复: 执行了 {iteration} 轮合并")

    return text


def fix_latex_syntax_for_katex(text: str) -> str:
    r"""
    修复LaTeX语法以适配KaTeX渲染器

    KaTeX比MathJax更严格，需要修复：
    1. \mathrm{} 用于多字母文本词（应该用\text{}）
    2. array/cases环境列对齐符中的空格（KaTeX不支持）

    Args:
        text: 包含LaTeX公式的文本

    Returns:
        修复后的文本
    """
    # 1. 将 \mathrm{} 中的纯文本英文单词替换为 \text{}
    # 这些是常见的文本词，不应该用 \mathrm（罗马数学字体）
    text_words = [
        'if', 'otherwise', 'where', 'for', 'and', 'or',
        'when', 'then', 'else', 'subject to', 's.t.'
    ]

    for word in text_words:
        # 使用正则替换，确保完整匹配
        pattern = r'\\mathrm\{' + re.escape(word) + r'\}'
        replacement = r'\\text{' + word + '}'
        text = re.sub(pattern, replacement, text)

    # 2. 移除 array 和 cases 环境列对齐符中的空格
    # 例如：\begin{array}{l l} -> \begin{array}{ll}
    #       \begin{cases}{c c c} -> \begin{cases}{ccc}
    text = re.sub(
        r'\\begin\{(array|cases)\}\{([lcrLCR\|])\s+([lcrLCR\|])',
        r'\\begin{\1}{\2\3',
        text
    )

    # 处理3列或更多列的情况（递归替换直到没有空格）
    prev_text = None
    while prev_text != text:
        prev_text = text
        text = re.sub(
            r'(\\begin\{(?:array|cases)\}\{[lcrLCR\|]+)\s+([lcrLCR\|])',
            r'\1\2',
            text
        )

    return text


def convert_html_to_markdown(text: str) -> str:
    """
    完整的HTML到Markdown转换流程

    Args:
        text: 包含HTML的文本

    Returns:
        转换后的Markdown文本
    """
    # 1. 先转换表格（表格最复杂，优先处理）
    text = convert_html_tables_to_markdown(text)

    # 2. 清理其他HTML标签
    text = clean_html_tags(text)

    # 3. 转换LaTeX公式语法（\[...\] -> $$...$$, \(...\) -> $...$）
    text = convert_latex_math_syntax(text)

    # 4. 合并被OCR错误拆分的LaTeX分段函数
    text = merge_split_latex_arrays(text)

    # 5. 修复LaTeX语法以适配KaTeX渲染器
    text = fix_latex_syntax_for_katex(text)

    # 6. 清理只包含空格的行（避免干扰Markdown解析）
    text = re.sub(r'^\s+$', '', text, flags=re.MULTILINE)

    return text


class TextExtractor:
    """PDF文本提取器 - 基于OCR模型"""

    def __init__(
        self,
        ocr_dpi: int = 144,
        ocr_mode: str = 'convert_to_markdown',
        ocr_max_tokens: int = 8192,
        ocr_temperature: float = 0.0,
        ocr_api_url: str = None
    ):
        """
        初始化文本提取器

        Args:
            ocr_dpi: 渲染分辨率，默认144
            ocr_mode: OCR模式，默认 'convert_to_markdown'
            ocr_max_tokens: 最大token数，默认8192
            ocr_temperature: 温度参数，默认0.0
            ocr_api_url: OCR API地址，默认从环境变量读取
        """
        self.ocr_dpi = ocr_dpi
        self.ocr_mode = ocr_mode
        self.ocr_max_tokens = ocr_max_tokens
        self.ocr_temperature = ocr_temperature

        # 从环境变量或参数获取OCR API地址
        self.ocr_api_url = ocr_api_url or os.getenv(
            'DJANGO_OCR_API_URL',
            'http://localhost:6066/api/webapps/toolkit/ocr'
        )

        logger.info(
            f"文本提取器初始化完成 - "
            f"OCR API: {self.ocr_api_url}, "
            f"DPI: {ocr_dpi}, "
            f"模式: {ocr_mode}, "
            f"max_tokens: {ocr_max_tokens}, "
            f"temperature: {ocr_temperature}"
        )

        # 健康检查
        try:
            response = requests.get(f"{self.ocr_api_url}/health/", timeout=10)
            if response.status_code == 200:
                logger.info("OCR服务健康检查通过")
            else:
                logger.warning(f"OCR服务健康检查失败: HTTP {response.status_code}")
        except Exception as e:
            logger.warning(f"OCR服务健康检查失败: {str(e)}")

    def extract_page(
        self,
        pdf_path: str,
        page_number: int,
        output_dir: Path = None,
        save_debug: bool = True
    ) -> Dict[str, Any]:
        """
        提取单个PDF页面

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            output_dir: 输出目录（可选，用于保存调试信息）
            save_debug: 是否保存调试信息

        Returns:
            Dict包含:
                - success: bool 是否成功
                - page_number: int 页码
                - markdown_raw: str 原始Markdown结果
                - markdown_cleaned: str 清理后的Markdown结果
                - image_size: List[int] 图片尺寸
                - image_count: int 检测到的图片标记数量
                - error: Optional[str] 错误信息
        """
        try:
            logger.info(f"=" * 60)
            logger.info(f"开始提取页面 {page_number}")
            logger.info(f"=" * 60)

            # 步骤1: 打开PDF并验证页码
            logger.info(f"[步骤1/4] 打开PDF文档...")
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

            doc = fitz.open(pdf_path)

            if page_number < 1 or page_number > doc.page_count:
                raise ValueError(
                    f"页码无效: {page_number}，总页数: {doc.page_count}"
                )

            # 步骤2: 渲染页面为图片
            logger.info(f"[步骤2/4] 渲染页面为图片 (DPI: {self.ocr_dpi})...")
            page = doc[page_number - 1]

            # 计算缩放矩阵（DPI转换）
            zoom = self.ocr_dpi / 72.0  # PDF默认72 DPI
            mat = fitz.Matrix(zoom, zoom)

            # 渲染页面为图片
            pix = page.get_pixmap(matrix=mat)
            image_bytes = pix.tobytes('png')  # 转换为PNG格式（与OCR测试脚本一致）

            logger.info(f"页面渲染完成 - 尺寸: {pix.width}x{pix.height}, 大小: {len(image_bytes)} bytes")

            # 步骤3: 转换为base64
            logger.info(f"[步骤3/4] 转换图片为base64...")
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            logger.info(f"Base64转换完成 - 长度: {len(image_base64)} 字符")

            # 步骤4: 通过HTTP调用OCR服务识别
            logger.info(f"[步骤4/4] 调用OCR服务识别...")
            response = requests.post(
                f"{self.ocr_api_url}/image/",
                json={
                    'image_base64': image_base64,
                    'mode': self.ocr_mode,
                    'max_tokens': self.ocr_max_tokens,
                    'temperature': self.ocr_temperature
                },
                timeout=300
            )

            if response.status_code != 200:
                raise RuntimeError(f"OCR API请求失败: HTTP {response.status_code}, {response.text}")

            ocr_result = response.json()

            # 关闭文档
            doc.close()

            # 检查识别结果
            if not ocr_result.get('success'):
                error_msg = ocr_result.get('error', '未知错误')
                logger.error(f"OCR识别失败: {error_msg}")
                return {
                    'success': False,
                    'page_number': page_number,
                    'error': error_msg
                }

            # 提取结果
            markdown_raw = ocr_result.get('result', '')
            markdown_cleaned = ocr_result.get('result_cleaned', '')
            image_size = ocr_result.get('image_size', [pix.width, pix.height])
            image_count = ocr_result.get('image_count', 0)
            image_regions = ocr_result.get('image_regions', [])  # 新增: 图片区域坐标

            # 转换HTML为Markdown（包括表格、加粗、斜体、居中等标签）
            markdown_raw = convert_html_to_markdown(markdown_raw)
            markdown_cleaned = convert_html_to_markdown(markdown_cleaned)

            logger.info(f"OCR识别完成 - 原始长度: {len(markdown_raw)}, 清理后长度: {len(markdown_cleaned)}")
            logger.info(f"检测到的图片标记数: {image_count}, 区域坐标数: {len(image_regions)}")

            # 保存调试信息和图片
            if save_debug and output_dir:
                import json
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                # 保存渲染的图片为 full_page.png（供Step3使用，跳过Step2）
                from PIL import Image
                from io import BytesIO
                image_pil = Image.open(BytesIO(image_bytes))  # 从PNG数据加载
                image_path = output_dir / "full_page.png"
                image_pil.save(image_path, 'PNG', optimize=True)
                logger.info(f"页面图片已保存: {image_path}")

                # 保存原始结果
                raw_path = output_dir / f"page_{page_number}_step1_raw.md"
                with open(raw_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_raw)
                logger.info(f"原始结果已保存: {raw_path}")

                # 保存清理后的结果（作为最终结果）
                final_path = output_dir / f"page_{page_number}_step1_final.md"
                with open(final_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_cleaned)
                logger.info(f"清理后结果已保存: {final_path}")

                # 保存图片区域坐标信息（供Step3使用）
                if image_regions:
                    regions_path = output_dir / f"page_{page_number}_image_regions.json"
                    with open(regions_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            'page_number': page_number,
                            'image_count': image_count,
                            'image_size': image_size,
                            'coordinate_system': 'normalized_1000',  # DeepSeek-OCR归一化坐标[0-999]
                            'regions': image_regions  # [[x1, y1, x2, y2], ...] 归一化坐标
                        }, f, indent=2, ensure_ascii=False)
                    logger.info(f"图片区域坐标已保存: {regions_path} (归一化坐标 0-999)")

            logger.info(f"=" * 60)
            logger.info(f"页面 {page_number} 提取完成")
            logger.info(f"=" * 60)

            return {
                'success': True,
                'page_number': page_number,
                'markdown_raw': markdown_raw,
                'markdown_cleaned': markdown_cleaned,
                'image_size': image_size,
                'image_count': image_count,
                'image_regions': image_regions  # [[x1, y1, x2, y2], ...]
            }

        except Exception as e:
            logger.error(
                f"提取页面 {page_number} 失败: {str(e)}",
                exc_info=True
            )
            return {
                'success': False,
                'page_number': page_number,
                'error': str(e)
            }

    def extract_pages_batch(
        self,
        pdf_path: str,
        page_numbers: list[int],
        output_dir: Path = None,
        save_debug: bool = True
    ) -> Dict[str, Any]:
        """
        批量提取多个PDF页面

        Args:
            pdf_path: PDF文件路径
            page_numbers: 页码列表（从1开始）
            output_dir: 输出目录（可选）
            save_debug: 是否保存调试信息

        Returns:
            Dict包含:
                - success: bool 是否成功
                - total: int 总页数
                - success_count: int 成功数
                - failed_count: int 失败数
                - results: List[Dict] 每页的结果
        """
        logger.info(f"开始批量提取 {len(page_numbers)} 个页面")

        results = []
        success_count = 0
        failed_count = 0

        for page_number in page_numbers:
            result = self.extract_page(
                pdf_path=pdf_path,
                page_number=page_number,
                output_dir=output_dir,
                save_debug=save_debug
            )

            results.append(result)

            if result.get('success'):
                success_count += 1
            else:
                failed_count += 1

        logger.info(f"批量提取完成 - 成功: {success_count}/{len(page_numbers)}, 失败: {failed_count}")

        return {
            'success': success_count > 0,
            'total': len(page_numbers),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }

    def extract_all_pages(
        self,
        pdf_path: str,
        output_dir: Path = None,
        save_debug: bool = True
    ) -> Dict[str, Any]:
        """
        提取PDF的所有页面

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（可选）
            save_debug: 是否保存调试信息

        Returns:
            Dict包含:
                - success: bool 是否成功
                - total: int 总页数
                - success_count: int 成功数
                - failed_count: int 失败数
                - results: List[Dict] 每页的结果
        """
        logger.info(f"开始提取PDF所有页面: {pdf_path}")

        # 获取总页数
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        doc.close()

        logger.info(f"PDF总页数: {total_pages}")

        # 批量提取所有页面
        page_numbers = list(range(1, total_pages + 1))
        return self.extract_pages_batch(
            pdf_path=pdf_path,
            page_numbers=page_numbers,
            output_dir=output_dir,
            save_debug=save_debug
        )

    def get_service_info(self) -> Dict[str, Any]:
        """
        获取服务信息

        Returns:
            Dict: 服务配置信息
        """
        return {
            'ocr_api_url': self.ocr_api_url,
            'ocr_dpi': self.ocr_dpi,
            'ocr_mode': self.ocr_mode,
            'ocr_max_tokens': self.ocr_max_tokens,
            'ocr_temperature': self.ocr_temperature
        }
