"""
Step1 提取策略决策器

根据页面分析结果，决定使用何种提取策略
"""
import logging
from enum import Enum
from typing import Dict, Any
from .step1_page_analyzer import PageAnalysisResult

logger = logging.getLogger('django')


class ExtractionStrategy(Enum):
    """提取策略枚举"""

    # 直接文本提取（适用于文本丰富的页面）
    DIRECT_TEXT = "direct_text"

    # OCR提取（适用于图片或扫描页面）
    OCR = "ocr"

    # 混合策略（先提取文本，质量不佳时使用OCR）
    HYBRID = "hybrid"

    # 仅表格提取（适用于纯表格页面）
    TABLE_ONLY = "table_only"


class ExtractionStrategyDecider:
    """提取策略决策器"""

    # 决策阈值配置
    DEFAULT_THRESHOLDS = {
        # 文本提取阈值
        'text_length_min': 50,  # 最小文本长度
        'word_count_min': 10,  # 最小单词数
        'text_density_min': 0.001,  # 最小文本密度（字符数/页面面积）

        # OCR触发阈值
        'ocr_image_threshold': 1,  # 图片数量阈值
        'ocr_drawing_threshold': 100,  # 绘图元素数量阈值
        'ocr_complexity_threshold': 0.4,  # 复杂度分数阈值

        # 混合策略阈值
        'hybrid_text_quality_threshold': 0.3,  # 文本质量阈值（用于判断是否需要OCR辅助）

        # 表格提取阈值
        'table_dominant_threshold': 2,  # 表格占主导的阈值
    }

    def __init__(self, thresholds: Dict[str, float] = None):
        """
        初始化决策器

        Args:
            thresholds: 自定义阈值配置（可选）
        """
        self.thresholds = {**self.DEFAULT_THRESHOLDS}
        if thresholds:
            self.thresholds.update(thresholds)

        logger.info(f"提取策略决策器初始化完成，阈值配置: {self.thresholds}")

    def decide_strategy(self, analysis_result: PageAnalysisResult) -> Dict[str, Any]:
        """
        根据页面分析结果决定提取策略

        Args:
            analysis_result: 页面分析结果

        Returns:
            Dict包含:
                - strategy: ExtractionStrategy 提取策略
                - confidence: float 决策置信度 (0-1)
                - reason: str 决策理由
                - metrics: Dict 决策依据的指标
        """
        logger.info(f"开始为页面 {analysis_result.page_number} 决策提取策略")

        # 计算各项指标
        text_density = self._calculate_text_density(analysis_result)
        text_quality_score = self._calculate_text_quality(analysis_result)
        complexity_score = analysis_result.get_complexity_score()

        # 决策逻辑
        strategy, confidence, reason = self._apply_decision_rules(
            analysis_result,
            text_density,
            text_quality_score,
            complexity_score
        )

        # 构建决策结果
        decision = {
            'strategy': strategy,
            'confidence': confidence,
            'reason': reason,
            'metrics': {
                'text_length': analysis_result.text_length,
                'word_count': analysis_result.word_count,
                'text_density': text_density,
                'text_quality_score': text_quality_score,
                'complexity_score': complexity_score,
                'image_count': analysis_result.image_count,
                'drawing_count': analysis_result.drawing_count,
                'table_count': analysis_result.table_count
            }
        }

        logger.info(
            f"页面 {analysis_result.page_number} 策略决策完成: "
            f"{strategy.value} (置信度: {confidence:.2f}) - {reason}"
        )

        return decision

    def _calculate_text_density(self, analysis_result: PageAnalysisResult) -> float:
        """
        计算文本密度

        Args:
            analysis_result: 页面分析结果

        Returns:
            文本密度（字符数/页面面积）
        """
        page_area = analysis_result.width * analysis_result.height
        if page_area == 0:
            return 0.0

        return analysis_result.text_length / page_area

    def _calculate_text_quality(self, analysis_result: PageAnalysisResult) -> float:
        """
        计算文本质量分数（0-1）

        考虑因素：
        - 文本长度
        - 单词数量
        - 文本结构（是否有合理的单词分布）
        - 文本完整性

        Args:
            analysis_result: 页面分析结果

        Returns:
            文本质量分数 (0-1)
        """
        scores = []

        # 1. 文本长度分数
        text_length_score = min(analysis_result.text_length / 500, 1.0)  # 500字符为满分
        scores.append(text_length_score)

        # 2. 单词数量分数
        word_count_score = min(analysis_result.word_count / 100, 1.0)  # 100词为满分
        scores.append(word_count_score)

        # 3. 平均词长分数（正常英文词长约5-6字符）
        if analysis_result.word_count > 0:
            avg_word_length = analysis_result.text_length / analysis_result.word_count
            # 理想词长在4-10之间
            if 4 <= avg_word_length <= 10:
                word_length_score = 1.0
            elif avg_word_length < 2 or avg_word_length > 20:
                word_length_score = 0.3  # 异常词长
            else:
                word_length_score = 0.7
            scores.append(word_length_score)
        else:
            scores.append(0.0)

        # 4. 文本块分布分数
        if analysis_result.text_blocks_count > 0:
            # 文本块数量适中为佳（1-10个）
            block_score = min(analysis_result.text_blocks_count / 10, 1.0)
            if analysis_result.text_blocks_count > 50:
                block_score *= 0.5  # 过多文本块可能表示碎片化严重
            scores.append(block_score)
        else:
            scores.append(0.0)

        # 计算加权平均
        if scores:
            quality_score = sum(scores) / len(scores)
        else:
            quality_score = 0.0

        return quality_score

    def _apply_decision_rules(
        self,
        analysis_result: PageAnalysisResult,
        text_density: float,
        text_quality_score: float,
        complexity_score: float
    ) -> tuple[ExtractionStrategy, float, str]:
        """
        应用决策规则

        Returns:
            (strategy, confidence, reason) 元组
        """
        # 规则0（最高优先级）: 检测到CID字体 -> 强制使用OCR
        # CID字体（特别是Identity-H编码）会导致文本提取乱码，必须使用OCR
        if analysis_result.has_cid_fonts:
            confidence = 0.95
            return (
                ExtractionStrategy.OCR,
                confidence,
                "检测到CID字体（Identity-H编码），直接文本提取会产生乱码，强制使用OCR"
            )

        # 规则1: 文本丰富且质量高 -> 直接文本提取
        if (analysis_result.text_length >= self.thresholds['text_length_min'] and
            analysis_result.word_count >= self.thresholds['word_count_min'] and
            text_quality_score >= 0.6):

            confidence = min(text_quality_score + 0.2, 1.0)
            return (
                ExtractionStrategy.DIRECT_TEXT,
                confidence,
                f"文本丰富（{analysis_result.text_length}字符，{analysis_result.word_count}词），"
                f"质量高（{text_quality_score:.2f}），适合直接提取"
            )

        # 规则2: 图片占主导且文本极少 -> OCR
        if (analysis_result.image_count >= self.thresholds['ocr_image_threshold'] and
            analysis_result.text_length < self.thresholds['text_length_min']):

            confidence = min(0.7 + analysis_result.image_count * 0.1, 0.95)
            return (
                ExtractionStrategy.OCR,
                confidence,
                f"图片占主导（{analysis_result.image_count}张），"
                f"文本稀少（{analysis_result.text_length}字符），需要OCR"
            )

        # 规则3: 复杂绘图页面且文本极少 -> OCR
        if (complexity_score >= self.thresholds['ocr_complexity_threshold'] and
            analysis_result.text_length < self.thresholds['text_length_min']):

            confidence = min(0.6 + complexity_score * 0.3, 0.9)
            return (
                ExtractionStrategy.OCR,
                confidence,
                f"复杂绘图页面（复杂度{complexity_score:.2f}，"
                f"{analysis_result.drawing_count}个绘图元素），需要OCR"
            )

        # 规则4: 表格占主导 -> 表格提取策略
        if (analysis_result.table_count >= self.thresholds['table_dominant_threshold'] and
            analysis_result.text_length < 200):

            confidence = 0.75
            return (
                ExtractionStrategy.TABLE_ONLY,
                confidence,
                f"表格占主导（{analysis_result.table_count}个表格），"
                f"使用表格提取策略"
            )

        # 规则5: 有少量文本但质量不佳 -> 混合策略
        if (0 < analysis_result.text_length < self.thresholds['text_length_min'] * 2 and
            text_quality_score < self.thresholds['hybrid_text_quality_threshold']):

            confidence = 0.65
            return (
                ExtractionStrategy.HYBRID,
                confidence,
                f"文本较少（{analysis_result.text_length}字符）且质量不佳（{text_quality_score:.2f}），"
                f"使用混合策略（文本提取+OCR辅助）"
            )

        # 规则6: 有一定文本但复杂度高 -> 混合策略
        if (analysis_result.text_length >= self.thresholds['text_length_min'] and
            complexity_score >= 0.3 and
            (analysis_result.image_count > 0 or analysis_result.drawing_count > 50)):

            confidence = 0.7
            return (
                ExtractionStrategy.HYBRID,
                confidence,
                f"有文本内容（{analysis_result.text_length}字符）但页面复杂（复杂度{complexity_score:.2f}），"
                f"使用混合策略"
            )

        # 默认规则: 尝试直接文本提取，但置信度较低
        if analysis_result.text_length > 0:
            confidence = 0.5
            return (
                ExtractionStrategy.DIRECT_TEXT,
                confidence,
                f"有少量文本（{analysis_result.text_length}字符），尝试直接提取（低置信度）"
            )

        # 最终兜底: 完全无文本 -> OCR
        confidence = 0.6
        return (
            ExtractionStrategy.OCR,
            confidence,
            "页面无可提取文本，必须使用OCR"
        )

    def should_use_ocr(self, analysis_result: PageAnalysisResult) -> bool:
        """
        判断是否应该使用OCR

        这是一个快速判断方法，返回布尔值

        Args:
            analysis_result: 页面分析结果

        Returns:
            bool: 是否应该使用OCR
        """
        decision = self.decide_strategy(analysis_result)
        strategy = decision['strategy']

        return strategy in [ExtractionStrategy.OCR, ExtractionStrategy.HYBRID]

    def get_thresholds(self) -> Dict[str, float]:
        """获取当前阈值配置"""
        return self.thresholds.copy()

    def update_thresholds(self, new_thresholds: Dict[str, float]):
        """
        更新阈值配置

        Args:
            new_thresholds: 新的阈值配置（部分更新）
        """
        self.thresholds.update(new_thresholds)
        logger.info(f"阈值配置已更新: {new_thresholds}")
