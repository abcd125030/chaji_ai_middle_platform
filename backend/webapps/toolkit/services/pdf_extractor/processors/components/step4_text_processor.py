"""
Step4 文本处理器

负责锚点文本的查找和图片引用的插入操作
"""
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from .step4_data_models import InsertionInstruction, MatchResult

logger = logging.getLogger('django')


class TextProcessor:
    """文本处理器 - 处理锚点查找和图片插入操作"""

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """
        规范化文本中的空白字符

        将所有空白字符(空格、Tab、换行符、回车符)统一替换为单个空格

        Args:
            text: 原始文本

        Returns:
            规范化后的文本
        """
        return re.sub(r'\s+', ' ', text.strip())

    @staticmethod
    def find_anchor_position(
        text: str,
        anchor: str,
        image_index: int,
        bbox: Optional[List[int]] = None,
        page_height: Optional[int] = None
    ) -> int:
        """
        使用多层策略查找锚点文本位置（容错机制）

        策略顺序:
        1. 精确匹配(字符串完全相同)
        2. 规范化空白字符匹配(统一处理\\n、\\t、多个空格)
        3. 正则模糊匹配(允许空白字符差异)

        当锚点出现多次时,如果提供了bbox和page_height,
        会计算空间距离选择最近的位置

        Args:
            text: 待搜索的文本
            anchor: 锚点文本
            image_index: 图片索引（用于日志）
            bbox: 图片边界框坐标 [x1, y1, x2, y2] (可选,用于空间优化)
            page_height: 页面高度(像素) (可选,用于空间优化)

        Returns:
            锚点在文本中的位置，-1 表示未找到
        """
        # 策略1: 精确匹配
        pos = text.find(anchor)
        if pos >= 0:
            # 检查是否有多个匹配
            all_positions = []
            temp_pos = 0
            while True:
                temp_pos = text.find(anchor, temp_pos)
                if temp_pos == -1:
                    break
                all_positions.append(temp_pos)
                temp_pos += 1

            if len(all_positions) > 1 and bbox and page_height:
                # 有多个匹配,使用空间距离选择最近的
                best_pos = TextProcessor._select_closest_anchor(
                    all_positions, text, bbox, page_height
                )
                logger.info(
                    f"图片 {image_index}: 精确匹配成功,发现{len(all_positions)}个候选锚点,"
                    f"根据空间距离选择位置{best_pos}"
                )
                return best_pos
            else:
                logger.debug(f"图片 {image_index}: 精确匹配成功，位置 {pos}")
                return pos

        # 策略2: 规范化空白字符匹配（将连续空白替换为单个空格）
        normalized_text = TextProcessor._normalize_whitespace(text)
        normalized_anchor = TextProcessor._normalize_whitespace(anchor)

        norm_pos = normalized_text.find(normalized_anchor)
        if norm_pos >= 0:
            # 查找所有规范化匹配
            all_norm_positions = []
            temp_pos = 0
            while True:
                temp_pos = normalized_text.find(normalized_anchor, temp_pos)
                if temp_pos == -1:
                    break
                original_pos = TextProcessor._map_to_original_position(text, temp_pos)
                all_norm_positions.append(original_pos)
                temp_pos += 1

            if len(all_norm_positions) > 1 and bbox and page_height:
                # 有多个匹配,使用空间距离选择
                best_pos = TextProcessor._select_closest_anchor(
                    all_norm_positions, text, bbox, page_height
                )
                logger.info(
                    f"图片 {image_index}: 规范化匹配成功,发现{len(all_norm_positions)}个候选锚点,"
                    f"根据空间距离选择位置{best_pos}"
                )
                return best_pos
            else:
                # 单个匹配或未提供空间信息
                original_pos = TextProcessor._map_to_original_position(text, norm_pos)
                logger.info(
                    f"图片 {image_index}: 规范化匹配成功，"
                    f"原始位置 {original_pos}，锚点已规范化空白字符"
                )
                return original_pos

        # 策略3: 正则表达式模糊匹配（允许换行符被任意空白替换）
        pattern = re.escape(normalized_anchor).replace(r'\ ', r'\s+')
        matches = list(re.finditer(pattern, text))
        if matches:
            if len(matches) > 1 and bbox and page_height:
                # 多个匹配,使用空间距离
                all_regex_positions = [m.start() for m in matches]
                best_pos = TextProcessor._select_closest_anchor(
                    all_regex_positions, text, bbox, page_height
                )
                logger.info(
                    f"图片 {image_index}: 正则匹配成功,发现{len(matches)}个候选锚点,"
                    f"根据空间距离选择位置{best_pos}"
                )
                return best_pos
            else:
                logger.info(
                    f"图片 {image_index}: 正则匹配成功，"
                    f"位置 {matches[0].start()}，允许换行符差异"
                )
                return matches[0].start()

        # 所有策略失败
        logger.warning(
            f"图片 {image_index}: 所有匹配策略失败，"
            f"锚点文本: '{anchor[:100]}...'"
        )
        return -1

    @staticmethod
    def _select_closest_anchor(
        positions: List[int],
        text: str,
        bbox: List[int],
        page_height: int
    ) -> int:
        """
        从多个候选锚点位置中选择距离图片最近的一个

        Args:
            positions: 候选锚点位置列表
            text: 文本内容
            bbox: 图片边界框
            page_height: 页面高度

        Returns:
            最佳锚点位置
        """
        text_length = len(text)
        min_distance = float('inf')
        best_position = positions[0]

        for pos in positions:
            # 估算锚点的垂直位置
            estimated_y = TextProcessor._estimate_vertical_position(
                pos, text_length, page_height
            )
            # 计算与图片的距离
            distance = TextProcessor._calculate_spatial_distance(bbox, estimated_y)

            if distance < min_distance:
                min_distance = distance
                best_position = pos

        return best_position

    @staticmethod
    def _map_to_original_position(
        original_text: str,
        normalized_pos: int
    ) -> int:
        """
        将规范化文本中的位置映射回原始文本位置

        Args:
            original_text: 原始文本
            normalized_pos: 规范化文本中的位置

        Returns:
            原始文本中的对应位置
        """
        # 计算规范化文本前normalized_pos个字符
        target_chars = normalized_pos

        original_pos = 0
        normalized_count = 0
        in_whitespace = False

        for i, char in enumerate(original_text):
            # 如果是空白字符
            if char.isspace():
                if not in_whitespace:
                    # 第一个空白字符，在规范化文本中占1个位置
                    normalized_count += 1
                    in_whitespace = True
                # 后续连续空白不增加normalized_count
            else:
                # 非空白字符
                normalized_count += 1
                in_whitespace = False

            if normalized_count >= target_chars:
                original_pos = i
                break

        return original_pos

    @staticmethod
    def _estimate_vertical_position(
        anchor_index: int,
        text_length: int,
        page_height: int
    ) -> float:
        """
        基于字符索引线性估算垂直坐标

        假设: 单列布局,文本均匀分布

        Args:
            anchor_index: 锚点在文本中的字符索引
            text_length: 文本总长度
            page_height: 页面高度(像素)

        Returns:
            估算的垂直坐标(像素)
        """
        if text_length == 0:
            return 0.0
        return (anchor_index / text_length) * page_height

    @staticmethod
    def _calculate_spatial_distance(
        bbox: List[int],
        estimated_y: float
    ) -> float:
        """
        计算图片bbox中心与锚点估算位置的垂直距离

        Args:
            bbox: 图片边界框坐标 [x1, y1, x2, y2]
            estimated_y: 锚点的估算垂直坐标

        Returns:
            垂直距离(像素)
        """
        # 计算bbox垂直中心
        bbox_center_y = (bbox[1] + bbox[3]) / 2
        # 返回垂直距离的绝对值
        return abs(bbox_center_y - estimated_y)

    @staticmethod
    def _find_all_anchor_positions(
        text: str,
        anchor: str
    ) -> List[int]:
        """
        查找锚点在文本中的所有出现位置

        使用3层策略(exact/normalized/regex)查找所有匹配

        Args:
            text: 待搜索的文本
            anchor: 锚点文本

        Returns:
            所有匹配位置的列表(字符索引)
        """
        positions = []

        # 策略1: 精确匹配 - 查找所有出现
        pos = 0
        while True:
            pos = text.find(anchor, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += 1  # 继续查找下一个

        if positions:
            return positions

        # 策略2: 规范化匹配
        normalized_text = TextProcessor._normalize_whitespace(text)
        normalized_anchor = TextProcessor._normalize_whitespace(anchor)

        pos = 0
        while True:
            norm_pos = normalized_text.find(normalized_anchor, pos)
            if norm_pos == -1:
                break
            # 映射回原始文本位置
            original_pos = TextProcessor._map_to_original_position(text, norm_pos)
            positions.append(original_pos)
            pos = norm_pos + 1

        if positions:
            return positions

        # 策略3: 正则匹配 - 查找所有匹配
        pattern = re.escape(normalized_anchor).replace(r'\ ', r'\s+')
        for match in re.finditer(pattern, text):
            positions.append(match.start())

        return positions

    @staticmethod
    def _build_image_reference(
        image_index: int,
        description: str,
        page_number: int,
        task_id: Optional[str]
    ) -> str:
        """
        构建Markdown图片引用语法

        Args:
            image_index: 图片序号
            description: 图片描述(alt text)
            page_number: 页码
            task_id: 任务UUID(可选)

        Returns:
            Markdown图片引用字符串
        """
        if task_id:
            # 使用Django media完整路径
            image_path = f"/media/oss-bucket/_toolkit/_extractor/{task_id}/page_{page_number}/image_{image_index}.png"
        else:
            # 降级为相对路径
            image_path = f"page_{page_number}/image_{image_index}.png"

        return f"![{description}]({image_path})"

    @staticmethod
    def apply_insertions(
        page_text: str,
        instructions: List[InsertionInstruction],
        page_number: int,
        task_id: Optional[str] = None,
        page_height: Optional[int] = None
    ) -> Tuple[str, dict]:
        """
        根据插入指令重构markdown（带容错机制）

        Args:
            page_text: 原始文本
            instructions: InsertionInstruction对象列表
            page_number: 页码
            task_id: 任务UUID（用于生成完整media路径）
            page_height: 页面高度(像素,可选,用于空间优化)

        Returns:
            元组(重构后的markdown内容, 匹配统计字典)
        """
        if not instructions:
            logger.warning("没有插入指令，返回原始文本")
            # 返回空统计
            return page_text, {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'match_results': [],
                'skipped_indices': []
            }

        try:
            # 按锚点文本在原文中的位置排序（从后往前处理，避免位置偏移）
            sorted_instructions = []
            skipped_instructions = []
            match_results = []

            for inst in instructions:
                # 使用多层容错机制查找锚点位置(带空间优化)
                pos = TextProcessor.find_anchor_position(
                    page_text,
                    inst.anchor_text,
                    inst.image_index,
                    inst.bbox,
                    page_height
                )

                if pos >= 0:
                    sorted_instructions.append((pos, inst))
                    # 记录成功找到锚点的结果（暂时标记为成功，稍后执行插入）
                    # 策略在find_anchor_position中已经记录日志，这里暂存位置
                else:
                    skipped_instructions.append(inst)
                    # 创建失败的MatchResult
                    match_results.append(MatchResult(
                        image_index=inst.image_index,
                        success=False,
                        strategy_used="none",
                        anchor_position=-1,
                        fallback_reason="所有匹配策略失败，无法找到锚点文本"
                    ))
                    logger.warning(
                        f"图片 {inst.image_index} 跳过: 无法找到锚点文本"
                    )

            if skipped_instructions:
                logger.warning(f"共有 {len(skipped_instructions)} 张图片因找不到锚点而跳过")

            # 从后往前排序
            sorted_instructions.sort(key=lambda x: x[0], reverse=True)

            result = page_text

            # 执行插入操作
            for pos, inst in sorted_instructions:
                # 构建图片引用
                image_ref = TextProcessor._build_image_reference(
                    inst.image_index,
                    inst.description,
                    page_number,
                    task_id
                )

                # 重新定位锚点（因为result可能已被修改）
                current_pos = TextProcessor.find_anchor_position(
                    result,
                    inst.anchor_text,
                    inst.image_index,
                    inst.bbox,
                    page_height
                )
                if current_pos < 0:
                    logger.error(f"图片 {inst.image_index}: 重新定位失败，跳过此操作")
                    # 更新为失败
                    match_results.append(MatchResult(
                        image_index=inst.image_index,
                        success=False,
                        strategy_used="none",
                        anchor_position=-1,
                        fallback_reason="重新定位失败"
                    ))
                    continue

                # 执行插入操作
                operation = inst.operation
                if operation == 'replace':
                    # replace 操作已被禁用，自动转换为 insert_after
                    logger.warning(
                        f"图片 {inst.image_index}: 检测到已废弃的 'replace' 操作，"
                        f"自动转换为 'insert_after' 以保留说明文字"
                    )
                    operation = 'insert_after'

                if operation == 'insert_after':
                    # 在锚点后插入
                    normalized_anchor = TextProcessor._normalize_whitespace(inst.anchor_text)
                    pattern = re.escape(normalized_anchor).replace(r'\ ', r'\s+')
                    match = re.search(pattern, result)
                    if match:
                        anchor_end = match.end()
                        result = result[:anchor_end] + f"\n\n{image_ref}\n" + result[anchor_end:]
                        logger.debug(f"图片 {inst.image_index}: insert_after 完成")
                        # 记录成功的MatchResult（策略通过find_anchor_position的日志推断）
                        match_results.append(MatchResult(
                            image_index=inst.image_index,
                            success=True,
                            strategy_used="normalized",  # 保守估计使用normalized
                            anchor_position=pos
                        ))
                    else:
                        logger.error(f"图片 {inst.image_index}: insert_after 失败，找不到锚点")
                        match_results.append(MatchResult(
                            image_index=inst.image_index,
                            success=False,
                            strategy_used="none",
                            anchor_position=-1,
                            fallback_reason="insert_after执行失败"
                        ))

                elif operation == 'insert_before':
                    # 在锚点前插入
                    normalized_anchor = TextProcessor._normalize_whitespace(inst.anchor_text)
                    pattern = re.escape(normalized_anchor).replace(r'\ ', r'\s+')
                    match = re.search(pattern, result)
                    if match:
                        anchor_start = match.start()
                        result = result[:anchor_start] + f"\n{image_ref}\n\n" + result[anchor_start:]
                        logger.debug(f"图片 {inst.image_index}: insert_before 完成")
                        # 记录成功的MatchResult
                        match_results.append(MatchResult(
                            image_index=inst.image_index,
                            success=True,
                            strategy_used="normalized",
                            anchor_position=pos
                        ))
                    else:
                        logger.error(f"图片 {inst.image_index}: insert_before 失败，找不到锚点")
                        match_results.append(MatchResult(
                            image_index=inst.image_index,
                            success=False,
                            strategy_used="none",
                            anchor_position=-1,
                            fallback_reason="insert_before执行失败"
                        ))

            # 处理降级策略: 将所有失败的图片插入到页面末尾
            if skipped_instructions:
                fallback_section = "\n\n## 附加图片 (锚点匹配失败)\n\n"
                for inst in skipped_instructions:
                    image_ref = TextProcessor._build_image_reference(
                        inst.image_index,
                        inst.description,
                        page_number,
                        task_id
                    )
                    fallback_section += f"{image_ref}\n"

                result += fallback_section
                logger.info(f"将 {len(skipped_instructions)} 张失败图片插入到页面末尾")

                # 更新这些图片的MatchResult为fallback策略
                for mr in match_results:
                    if not mr.success and mr.image_index in [si.image_index for si in skipped_instructions]:
                        mr.strategy_used = "fallback"
                        mr.fallback_reason = "锚点匹配失败，插入到页面末尾"

            # 统计信息
            successful_count = sum(1 for mr in match_results if mr.success)
            failed_count = len(match_results) - successful_count

            stats = {
                'total': len(instructions),
                'successful': successful_count,
                'failed': failed_count,
                'match_results': match_results,
                'skipped_indices': [si.image_index for si in skipped_instructions]
            }

            logger.info(
                f"Markdown重构完成，原文 {len(page_text)} -> {len(result)} 字符，"
                f"成功插入 {successful_count}/{len(instructions)} 张图片"
            )
            return result, stats

        except Exception as e:
            logger.error(f"应用插入指令失败: {str(e)}", exc_info=True)
            # 返回原始文本和错误统计
            return page_text, {
                'total': len(instructions),
                'successful': 0,
                'failed': len(instructions),
                'match_results': [],
                'skipped_indices': [inst.image_index for inst in instructions]
            }
