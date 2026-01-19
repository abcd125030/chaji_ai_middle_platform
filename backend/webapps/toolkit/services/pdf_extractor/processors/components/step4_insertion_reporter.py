"""
Step4插入报告生成器组件

负责生成、保存、加载和格式化InsertionReport
"""
import json
import logging
from pathlib import Path
from typing import List
from .step4_data_models import InsertionReport, MatchResult

logger = logging.getLogger('django')


class InsertionReporter:
    """插入报告生成器组件"""

    @staticmethod
    def generate_report(
        page_number: int,
        match_results: List[MatchResult],
        processing_time_ms: float
    ) -> InsertionReport:
        """
        生成页面级插入报告

        汇总所有图片的匹配结果,统计成功/失败数量,收集警告信息

        Args:
            page_number: 页码
            match_results: MatchResult对象列表
            processing_time_ms: Step4处理总耗时(毫秒)

        Returns:
            InsertionReport对象
        """
        total_images = len(match_results)
        successful_insertions = sum(1 for mr in match_results if mr.success)
        failed_insertions = total_images - successful_insertions

        # 生成警告信息
        warnings = []
        if failed_insertions > 0:
            warnings.append(
                f"第{page_number}页共{failed_insertions}张图片插入失败,已降级到页面末尾"
            )

        report = InsertionReport(
            page_number=page_number,
            total_images=total_images,
            successful_insertions=successful_insertions,
            failed_insertions=failed_insertions,
            match_results=match_results,
            warnings=warnings,
            processing_time_ms=processing_time_ms
        )

        return report

    @staticmethod
    def save_report(report: InsertionReport, output_dir: Path) -> Path:
        """
        保存插入报告为JSON文件

        文件名固定为: insertion_report.json
        文件格式: UTF-8编码, 2空格缩进, 非ASCII字符不转义

        Args:
            report: InsertionReport对象
            output_dir: 输出目录(通常为page_{N}目录)

        Returns:
            保存的文件路径
        """
        report_path = output_dir / "insertion_report.json"
        report.save_to_file(report_path)

        logger.info(f"插入报告已保存: {report_path}")
        return report_path

    @staticmethod
    def load_report(report_path: Path) -> InsertionReport:
        """
        从JSON文件加载插入报告

        用于调试或后期分析

        Args:
            report_path: insertion_report.json文件路径

        Returns:
            InsertionReport对象

        Raises:
            FileNotFoundError: 文件不存在
            json.JSONDecodeError: JSON格式错误
        """
        if not report_path.exists():
            raise FileNotFoundError(f"插入报告文件不存在: {report_path}")

        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 重建MatchResult对象列表
        match_results = [
            MatchResult(
                image_index=mr['image_index'],
                success=mr['success'],
                strategy_used=mr['strategy_used'],
                anchor_position=mr['anchor_position'],
                confidence_score=mr.get('confidence_score'),
                fallback_reason=mr.get('fallback_reason'),
                spatial_distance=mr.get('spatial_distance'),
                alternative_anchors=mr.get('alternative_anchors')
            )
            for mr in data['match_results']
        ]

        report = InsertionReport(
            page_number=data['page_number'],
            total_images=data['total_images'],
            successful_insertions=data['successful_insertions'],
            failed_insertions=data['failed_insertions'],
            match_results=match_results,
            warnings=data.get('warnings', []),
            processing_time_ms=data.get('processing_time_ms', 0.0),
            timestamp=data.get('timestamp', '')
        )

        return report

    @staticmethod
    def format_summary(report: InsertionReport) -> str:
        """
        格式化报告为人类可读的摘要文本

        用于日志输出或命令行展示

        Args:
            report: InsertionReport对象

        Returns:
            格式化的摘要文本(多行字符串)
        """
        lines = [
            f"第{report.page_number}页图片插入报告:",
            f"- 总图片数: {report.total_images}",
            f"- 成功插入: {report.successful_insertions}",
            f"- 失败插入: {report.failed_insertions}",
            f"- 处理耗时: {report.processing_time_ms:.1f}ms",
            f"- 警告: {len(report.warnings)}条",
            ""
        ]

        # 添加详细匹配结果
        if report.match_results:
            lines.append("详细匹配结果:")
            for mr in report.match_results:
                status_icon = "✓" if mr.success else "✗"
                line = f"[{mr.image_index}] 策略: {mr.strategy_used}, 位置: {mr.anchor_position} {status_icon}"

                # 添加空间距离信息(如果有)
                if mr.spatial_distance is not None:
                    line += f", 空间距离: {mr.spatial_distance:.1f}px"

                # 添加失败原因(如果有)
                if mr.fallback_reason:
                    line += f" - {mr.fallback_reason}"

                lines.append(line)

        # 添加警告信息
        if report.warnings:
            lines.append("")
            lines.append("警告信息:")
            for warning in report.warnings:
                lines.append(f"⚠️  {warning}")

        return "\n".join(lines)
