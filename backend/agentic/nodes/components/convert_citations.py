"""
引用转换工具
将 Markdown 链接格式转换为数字上标格式
"""

import re
from typing import Tuple, List, Dict


def convert_citations_to_numeric(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    将文本中的 Markdown 链接格式 [label](url) 转换为数字上标格式 [1]
    
    参数:
    text: 包含 Markdown 链接的文本
    
    返回:
    (转换后的文本, 引用列表)
    """
    # 存储所有引用
    citations_list = []
    citation_map = {}  # url -> citation_number
    citation_counter = 1
    
    # 查找所有 Markdown 链接
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    
    def replace_citation(match):
        nonlocal citation_counter
        label = match.group(1)
        url = match.group(2)
        
        # 如果这个 URL 已经有编号，使用现有编号
        if url in citation_map:
            citation_num = citation_map[url]
        else:
            # 新的引用，分配新编号
            citation_num = citation_counter
            citation_map[url] = citation_num
            citations_list.append({
                'number': citation_num,
                'label': label,
                'url': url
            })
            citation_counter += 1
        
        return f'[{citation_num}]'
    
    # 替换所有引用
    converted_text = re.sub(pattern, replace_citation, text)
    
    return converted_text, citations_list