"""
PDF提取器核心组件

包含：
- Step1 文本提取组件：页面分析、策略决策、OCR处理、文档分析、Prompt构建和LLM格式化
- Step4 Markdown重构组件：图像处理、提示词构建、指令处理、文本处理
"""

# Step1 组件
from .step1_page_analyzer import PageAnalyzer, PageAnalysisResult
from .step1_extraction_strategy import ExtractionStrategy, ExtractionStrategyDecider
from .step1_ocr_handler import OCRHandler
from .step1_document_analyzer import DocumentAnalyzer
from .step1_prompt_builder import PromptBuilder
from .step1_llm_formatter import LLMFormatter

# Step4 组件
from .step4_image_processor import ImageProcessor
from .step4_prompt_builder import InsertionPromptBuilder
from .step4_instruction_handler import InstructionHandler
from .step4_text_processor import TextProcessor

__all__ = [
    # Step1 组件
    'PageAnalyzer',
    'PageAnalysisResult',
    'ExtractionStrategy',
    'ExtractionStrategyDecider',
    'OCRHandler',
    'DocumentAnalyzer',
    'PromptBuilder',
    'LLMFormatter',
    # Step4 组件
    'ImageProcessor',
    'InsertionPromptBuilder',
    'InstructionHandler',
    'TextProcessor',
]
