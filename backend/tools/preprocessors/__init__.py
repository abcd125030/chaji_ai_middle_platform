"""
预处理工具包
包含用于文件预处理的工具，这些工具不会暴露给 Agent，仅在 services.py 中内部使用。

目录结构：
- core/: 核心分析和配置模块
- parsers/: 具体文件格式的解析器
- processors/: 高级处理器，提供统一接口
"""

# 从processors目录导入高级处理器（主要入口）
from .processors.document_parser import DocumentParserTool
from .processors.excel_processor import ExcelProcessorTool

# 从parsers目录导入特定解析器
from .parsers.docx_parser import DOCXParserTool
from .parsers.excel_parser import ExcelParserTool
from .parsers.text_parser import TextParserTool
from .parsers.pdf_parser import PDFParserTool
from .parsers.pdf_parser_internal import PDFParserInternalTool

# 从core目录导入核心功能
from .core.pdf_complexity_analyzer import analyze_pdf_complexity

__all__ = [
    # 处理器
    'DocumentParserTool',
    'ExcelProcessorTool',
    # 解析器
    'DOCXParserTool', 
    'ExcelParserTool',
    'TextParserTool',
    'PDFParserTool',
    'PDFParserInternalTool',
    # 核心功能
    'analyze_pdf_complexity'
]