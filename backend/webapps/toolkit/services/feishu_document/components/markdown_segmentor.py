"""
Markdown分段组件

职责：将大型Markdown文件按行拆分为多个段落，避免飞书API单次插入块数限制
"""
import logging
from typing import List, Optional

logger = logging.getLogger('django')


class MarkdownSegmentor:
    """Markdown分段器"""

    @staticmethod
    def split_markdown_lines(lines: List[str], max_lines: int = 200) -> List[str]:
        """
        将Markdown按行拆分为多个段落

        算法特点：
        1. 优先在标题行（#开头）前分割
        2. 其次在空行处分割
        3. 代码块（```或~~~围栏）内允许溢出，直到代码块结束才分割
        4. 返回段落顺序为倒序（最后一段在最前），便于从文档末尾插入

        Args:
            lines: Markdown文件的行列表
            max_lines: 每段最多行数（默认200行）

        Returns:
            List[str]: 分段后的Markdown文本列表（倒序）
        """
        if not lines:
            logger.warning("Markdown分段：输入行列表为空")
            return []

        logger.info(f"开始Markdown分段，总行数: {len(lines)}，最大行数: {max_lines}")

        parts: List[List[str]] = []
        current: List[str] = []
        current_len = 0

        inside_fence = False
        current_fence: Optional[str] = None
        last_safe_idx: Optional[int] = None

        for line_num, line in enumerate(lines, start=1):
            # 检测代码块围栏
            marker = MarkdownSegmentor._fence_marker(line)
            if marker:
                if not inside_fence:
                    inside_fence = True
                    current_fence = marker
                    logger.debug(f"第{line_num}行：进入代码块（{marker}）")
                else:
                    if marker == current_fence:
                        inside_fence = False
                        current_fence = None
                        logger.debug(f"第{line_num}行：退出代码块")

            # 添加当前行
            current.append(line)
            current_len += 1

            # 更新安全分割点（仅在代码块外）
            if not inside_fence:
                if MarkdownSegmentor._is_heading(line):
                    last_safe_idx = len(current) - 1
                elif MarkdownSegmentor._is_blank(line):
                    last_safe_idx = len(current)

            # 检查是否需要分割
            if current_len > max_lines:
                if last_safe_idx is not None and last_safe_idx > 0:
                    # 在安全点分割
                    chunk = current[:last_safe_idx]
                    remainder = current[last_safe_idx:]
                    if chunk:
                        parts.append(chunk)
                        logger.info(f"分段完成：第{len(parts)}段，{len(chunk)}行（安全分割点）")

                    # 重置状态
                    current = remainder
                    current_len = len(current)
                    inside_fence, current_fence, last_safe_idx = MarkdownSegmentor._recompute_fence_state(current)
                elif inside_fence:
                    # 代码块内允许溢出，等待块结束
                    logger.debug(f"代码块内超过{max_lines}行，允许溢出")
                    pass
                else:
                    # 硬切分
                    chunk = current[:max_lines]
                    remainder = current[max_lines:]
                    parts.append(chunk)
                    logger.warning(f"分段完成：第{len(parts)}段，{len(chunk)}行（硬切分，无安全点）")

                    current = remainder
                    current_len = len(current)
                    inside_fence, current_fence, last_safe_idx = MarkdownSegmentor._recompute_fence_state(current)

        # 添加最后一段
        if current:
            parts.append(current)
            logger.info(f"分段完成：第{len(parts)}段（最后一段），{len(current)}行")

        # 转换为文本并倒序
        parts_text: List[str] = [''.join(chunk) for chunk in parts]
        parts_text.reverse()

        logger.info(f"Markdown分段完成，总段数: {len(parts_text)}")
        return parts_text

    @staticmethod
    def _is_heading(line: str) -> bool:
        """检查是否为Markdown标题行"""
        return line.lstrip().startswith("#")

    @staticmethod
    def _is_blank(line: str) -> bool:
        """检查是否为空行"""
        return line.strip() == ""

    @staticmethod
    def _fence_marker(line: str) -> Optional[str]:
        """检测代码块围栏标记（```或~~~）"""
        s = line.strip()
        if s.startswith("```"):
            return "```"
        if s.startswith("~~~"):
            return "~~~"
        return None

    @staticmethod
    def _recompute_fence_state(lines: List[str]) -> tuple:
        """重新计算代码块状态和安全分割点"""
        inside_fence = False
        current_fence = None
        last_safe_idx = None

        for idx, line in enumerate(lines):
            marker = MarkdownSegmentor._fence_marker(line)
            if marker:
                if not inside_fence:
                    inside_fence = True
                    current_fence = marker
                elif marker == current_fence:
                    inside_fence = False
                    current_fence = None

            if not inside_fence:
                if MarkdownSegmentor._is_heading(line):
                    last_safe_idx = idx
                    break
                elif MarkdownSegmentor._is_blank(line):
                    last_safe_idx = idx + 1

        return inside_fence, current_fence, last_safe_idx
