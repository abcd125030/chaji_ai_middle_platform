"""
生成器工具的共享工具函数包
"""

from .context_extractor import (
    extract_context_from_state,
    format_tool_outputs_as_text,
    format_tool_outputs_as_json,
    get_preprocessed_documents,
    get_preprocessed_tables
)

__all__ = [
    'extract_context_from_state',
    'format_tool_outputs_as_text', 
    'format_tool_outputs_as_json',
    'get_preprocessed_documents',
    'get_preprocessed_tables'
]