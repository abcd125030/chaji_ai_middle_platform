"""
PDF提取器服务层
基于Qwen3-VL-Plus的智能语义分割系统

本模块提供PDF文档处理的门面接口，内部委托给processors模块实现。
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from .processors import PDFProcessor

logger = logging.getLogger('django')


class PDFExtractorService:
    """
    PDF文档智能提取服务（门面类）

    核心功能：
    - 委托给processors.PDFProcessor处理实际的PDF提取工作
    - 提供简洁的服务层接口
    - 负责配置初始化和错误处理

    架构说明：
    本类是一个门面（Facade），所有具体实现都在processors模块中：
    - TextExtractor: 文本提取
    - PageRenderer: 页面渲染
    - SemanticSegmentor: 语义分割
    - MarkdownReconstructor: Markdown重构
    - PDFProcessor: 主流程控制器
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "qwen3-vl-plus",
        dpi: int = 144
    ):
        """
        初始化PDF提取服务

        Args:
            api_key: DashScope API密钥（默认从环境变量读取）
            base_url: API基础URL（默认从环境变量读取）
            model: 使用的模型名称
            dpi: PDF渲染DPI
        """
        # 配置初始化
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or os.getenv(
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model
        self.dpi = dpi

        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

        # 初始化底层处理器
        self.processor = PDFProcessor(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            dpi=self.dpi
        )

        logger.info(
            f"PDF提取服务初始化完成 - "
            f"模型: {self.model}, DPI: {self.dpi}"
        )

    def process_pdf_document(
        self,
        pdf_path: str,
        task_id: str,
        task_dir: Path
    ) -> Dict[str, Any]:
        """
        处理完整PDF文档（主入口方法）

        Args:
            pdf_path: PDF文件路径
            task_id: 任务UUID
            task_dir: 任务目录

        Returns:
            处理结果字典，包含：
            - status: 处理状态（success/error）
            - task_id: 任务UUID
            - total_pages: 总页数
            - processed_pages: 已处理页数
            - final_markdown: 最终markdown文件路径
            - page_results: 各页面处理结果列表
        """
        try:
            logger.info(f"开始处理PDF文档: {pdf_path}")

            # 委托给底层处理器
            result = self.processor.process_pdf_document(
                pdf_path=pdf_path,
                task_id=task_id,
                task_dir=task_dir
            )

            logger.info(f"PDF文档处理完成: {task_id}")
            return result

        except Exception as e:
            logger.error(f"处理PDF文档失败: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'task_id': task_id,
                'error': str(e)
            }

    def process_single_page(
        self,
        pdf_path: str,
        page_number: int,
        task_dir: Path,
        task_id: str = None
    ) -> Dict[str, Any]:
        """
        处理单个PDF页面

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）
            task_dir: 任务根目录
            task_id: 任务UUID（可选）

        Returns:
            页面处理结果字典
        """
        return self.processor.process_single_page(
            pdf_path=pdf_path,
            page_number=page_number,
            task_dir=task_dir,
            task_id=task_id
        )

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """
        获取PDF总页数

        Args:
            pdf_path: PDF文件路径

        Returns:
            总页数
        """
        return self.processor.get_pdf_page_count(pdf_path)

    def merge_page_markdowns(
        self,
        task_dir: Path,
        page_count: int,
        task_id: str
    ) -> Path:
        """
        合并所有页面的markdown文档

        Args:
            task_dir: 任务目录
            page_count: 总页数
            task_id: 任务UUID

        Returns:
            最终markdown文件路径
        """
        return self.processor.merge_page_markdowns(
            task_dir=task_dir,
            page_count=page_count,
            task_id=task_id
        )
