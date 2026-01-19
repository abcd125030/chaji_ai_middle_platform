"""
Step4数据模型

定义PDF图片插入锚点匹配的核心数据结构
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import json


@dataclass
class InsertionInstruction:
    """
    插入指令 - VL模型返回的单个图片插入指令

    包含锚点文本和插入位置信息,用于指导图片插入操作
    """
    image_index: int  # 图片序号(从1开始)
    image_type: str  # 图片类型: chart, table, formula, diagram, image_text
    description: str  # 图片简短描述(用于alt text)
    anchor_text: str  # 锚点文本(从原文提取,可能包含\n换行符)
    bbox: List[int]  # 图片区域边界框坐标[x1, y1, x2, y2]
    operation: str  # 操作类型: insert_before, insert_after
    reason: str  # 插入理由说明

    def validate(self) -> bool:
        """
        验证指令合法性

        Returns:
            bool: 指令是否合法
        """
        # 检查图片序号
        if self.image_index <= 0:
            return False

        # 检查锚点文本长度
        if len(self.anchor_text) > 200:
            return False

        # 检查bbox格式和坐标合理性
        if len(self.bbox) != 4:
            return False
        if self.bbox[2] <= self.bbox[0] or self.bbox[3] <= self.bbox[1]:
            return False

        # 检查操作类型
        if self.operation not in ["insert_before", "insert_after"]:
            return False

        return True


@dataclass
class MatchResult:
    """
    匹配结果 - 记录单个图片锚点匹配的执行结果

    包含使用的策略和匹配详情,用于生成插入报告
    """
    image_index: int  # 对应的图片序号
    success: bool  # 是否成功匹配并插入
    strategy_used: str  # 使用的匹配策略: exact, normalized, regex, fallback
    anchor_position: int  # 找到的锚点在原文中的位置(字符索引,-1表示未找到)
    confidence_score: Optional[float] = None  # 匹配置信度(0-1,当前版本未使用,预留给语义匹配)
    fallback_reason: Optional[str] = None  # 若使用降级策略,说明原因
    spatial_distance: Optional[float] = None  # 图片与锚点的空间距离(像素,用于US2)
    alternative_anchors: Optional[List[dict]] = None  # 候选锚点列表(用于重复锚点,US2)

    def to_dict(self) -> dict:
        """
        序列化为字典

        Returns:
            dict: 包含所有非None字段的字典
        """
        result = {
            'image_index': self.image_index,
            'success': self.success,
            'strategy_used': self.strategy_used,
            'anchor_position': self.anchor_position
        }

        # 添加可选字段
        if self.confidence_score is not None:
            result['confidence_score'] = self.confidence_score
        if self.fallback_reason:
            result['fallback_reason'] = self.fallback_reason
        if self.spatial_distance is not None:
            result['spatial_distance'] = self.spatial_distance
        if self.alternative_anchors:
            result['alternative_anchors'] = self.alternative_anchors

        return result


@dataclass
class InsertionReport:
    """
    插入报告 - 页面级别的插入总结

    汇总所有图片的匹配结果和警告信息,保存为JSON文件
    """
    page_number: int  # 页码
    total_images: int  # 总图片数量
    successful_insertions: int  # 成功插入数量
    failed_insertions: int  # 失败插入数量
    match_results: List[MatchResult]  # 所有匹配结果列表
    warnings: List[str] = field(default_factory=list)  # 警告信息列表
    processing_time_ms: float = 0.0  # Step4处理总耗时(毫秒)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')  # 生成时间戳(ISO 8601)

    def to_dict(self) -> dict:
        """
        序列化为字典

        Returns:
            dict: 包含所有字段的字典,match_results转换为字典列表
        """
        return {
            'page_number': self.page_number,
            'total_images': self.total_images,
            'successful_insertions': self.successful_insertions,
            'failed_insertions': self.failed_insertions,
            'match_results': [mr.to_dict() for mr in self.match_results],
            'warnings': self.warnings,
            'processing_time_ms': self.processing_time_ms,
            'timestamp': self.timestamp
        }

    def save_to_file(self, output_path: Path):
        """
        保存为JSON文件

        Args:
            output_path: 输出文件路径(通常为page_{N}/insertion_report.json)
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
