"""
文本文件解析工具
================

处理各种文本格式文件，包括纯文本、Markdown、代码文件、日志文件等。
根据文件类型提供适当的格式化和元数据提取。
"""

import os
import re
import json
import csv
import io
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from tools.core.base import BaseTool
from tools.core.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


class TextParserTool(BaseTool):
    """
    文本文件解析工具：处理各种文本格式文件。
    
    功能特性：
    1. 支持多种文本格式（txt, md, log, csv, 代码文件等）
    2. 自动检测文件编码
    3. 提取文件元数据（行数、字数、编程语言等）
    4. 识别Markdown结构（标题、列表、代码块等）
    5. 处理CSV为结构化数据
    6. 识别日志文件中的错误和警告
    7. 为代码文件添加语言标记
    """
    
    # 支持的文件扩展名和对应的处理类型
    FILE_TYPE_MAPPING = {
        # 文档类
        '.txt': 'text',
        '.text': 'text',
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.rst': 'text',
        '.log': 'log',
        '.logs': 'log',
        
        # 数据类
        '.csv': 'csv',
        '.tsv': 'tsv',
        '.dat': 'text',
        
        # 代码文件
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.r': 'r',
        '.m': 'matlab',
        '.scala': 'scala',
        '.pl': 'perl',
        '.lua': 'lua',
        '.dart': 'dart',
        
        # 标记语言
        '.html': 'html',
        '.htm': 'html',
        '.xml': 'xml',
        '.svg': 'xml',
        
        # 样式表
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        
        # 配置文件
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'conf',
        '.env': 'env',
        '.properties': 'properties',
        
        # 脚本文件
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.fish': 'shell',
        '.ps1': 'powershell',
        '.bat': 'batch',
        '.cmd': 'batch',
        
        # SQL
        '.sql': 'sql',
        
        # 其他
        '.gitignore': 'gitignore',
        '.dockerignore': 'dockerignore',
        'Dockerfile': 'dockerfile',
        'Makefile': 'makefile',
        '.makefile': 'makefile',
    }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要解析的文本文件路径"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认自动检测",
                    "default": "auto"
                },
                "max_lines": {
                    "type": ["integer", "null"],
                    "description": "最大读取行数，None表示全部",
                    "default": None
                },
                "extract_structure": {
                    "type": "boolean",
                    "description": "是否提取文档结构（Markdown标题、代码块等）",
                    "default": True
                },
                "detect_patterns": {
                    "type": "boolean",
                    "description": "是否检测特殊模式（错误、警告、TODO等）",
                    "default": True
                }
            },
            "required": ["file_path"]
        }

    def execute(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """执行文本文件解析"""
        file_path = tool_input.get('file_path')
        encoding = tool_input.get('encoding', 'auto')
        max_lines = tool_input.get('max_lines', None)
        extract_structure = tool_input.get('extract_structure', True)
        detect_patterns = tool_input.get('detect_patterns', True)
        
        # 验证输入
        if not file_path:
            return {"status": "error", "message": "文件路径未提供"}
        
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"文件不存在: {file_path}"}
        
        try:
            # 检测文件类型
            file_type = self._detect_file_type(file_path)
            
            # 解析文件
            result = self._parse_text_file(
                file_path=file_path,
                file_type=file_type,
                encoding=encoding,
                max_lines=max_lines,
                extract_structure=extract_structure,
                detect_patterns=detect_patterns
            )
            
            return {
                "status": "success",
                "message": f"文件 '{os.path.basename(file_path)}' 已成功解析",
                "file_path": file_path,
                "file_type": file_type,
                **result
            }
            
        except Exception as e:
            logger.error(f"文本文件解析失败: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"文本文件解析失败: {str(e)}",
                "file_path": file_path
            }
    
    def _detect_file_type(self, file_path: str) -> str:
        """检测文件类型"""
        path = Path(file_path)
        
        # 特殊文件名处理
        if path.name == 'Dockerfile':
            return 'dockerfile'
        elif path.name == 'Makefile':
            return 'makefile'
        
        # 根据扩展名判断
        ext = path.suffix.lower()
        return self.FILE_TYPE_MAPPING.get(ext, 'text')
    
    def _parse_text_file(self, file_path: str, file_type: str,
                        encoding: str = 'auto', max_lines: Optional[int] = None,
                        extract_structure: bool = True,
                        detect_patterns: bool = True) -> Dict[str, Any]:
        """解析文本文件的核心方法"""
        
        # 读取文件内容
        content = self._read_file_content(file_path, encoding, max_lines)
        
        # 基础统计
        lines = content.splitlines()
        statistics = {
            "total_lines": len(lines),
            "total_characters": len(content),
            "total_words": len(content.split()),
            "non_empty_lines": sum(1 for line in lines if line.strip()),
            "file_type": file_type
        }
        
        # 根据文件类型进行特殊处理
        metadata = {}
        structured_content = None
        
        if file_type == 'csv':
            structured_content = self._parse_csv(content)
            metadata['format'] = 'csv'
        elif file_type == 'tsv':
            structured_content = self._parse_csv(content, delimiter='\t')
            metadata['format'] = 'tsv'
        elif file_type == 'json':
            structured_content = self._parse_json(content)
            metadata['format'] = 'json'
        elif file_type == 'markdown':
            if extract_structure:
                metadata['structure'] = self._extract_markdown_structure(content)
            metadata['format'] = 'markdown'
        elif file_type == 'log':
            if detect_patterns:
                metadata['patterns'] = self._detect_log_patterns(content)
            metadata['format'] = 'log'
        elif file_type in ['yaml', 'yml']:
            structured_content = self._parse_yaml(content)
            metadata['format'] = 'yaml'
        elif file_type in ['python', 'javascript', 'typescript', 'java', 'cpp', 'c', 
                          'go', 'rust', 'ruby', 'php', 'swift', 'kotlin']:
            metadata['language'] = file_type
            if extract_structure:
                metadata['code_structure'] = self._extract_code_structure(content, file_type)
        
        # 检测特殊模式
        if detect_patterns:
            patterns = self._detect_special_patterns(content)
            if patterns:
                metadata['detected_patterns'] = patterns
        
        result = {
            "content": content,
            "statistics": statistics,
            "metadata": metadata
        }
        
        if structured_content is not None:
            result["structured_content"] = structured_content
        
        return result
    
    def _read_file_content(self, file_path: str, encoding: str = 'auto',
                          max_lines: Optional[int] = None) -> str:
        """读取文件内容，自动检测编码"""
        if encoding == 'auto':
            # 尝试多种编码
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 
                        'big5', 'iso-8859-1', 'windows-1252']
            
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        if max_lines:
                            lines = []
                            for i, line in enumerate(f):
                                if i >= max_lines:
                                    break
                                lines.append(line)
                            return ''.join(lines)
                        else:
                            return f.read()
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            # 如果都失败，使用错误处理模式
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    return ''.join(lines)
                else:
                    return f.read()
        else:
            # 使用指定编码
            with open(file_path, 'r', encoding=encoding) as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    return ''.join(lines)
                else:
                    return f.read()
    
    def _parse_csv(self, content: str, delimiter: str = ',') -> List[Dict[str, Any]]:
        """解析CSV/TSV内容"""
        try:
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            rows = list(reader)
            return rows
        except Exception as e:
            logger.warning(f"CSV解析失败: {str(e)}")
            return []
    
    def _parse_json(self, content: str) -> Any:
        """解析JSON内容"""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {str(e)}")
            return None
    
    def _parse_yaml(self, content: str) -> Any:
        """解析YAML内容"""
        try:
            import yaml
            return yaml.safe_load(content)
        except ImportError:
            logger.warning("需要安装PyYAML: pip install pyyaml")
            return None
        except Exception as e:
            logger.warning(f"YAML解析失败: {str(e)}")
            return None
    
    def _extract_markdown_structure(self, content: str) -> Dict[str, Any]:
        """提取Markdown文档结构"""
        structure = {
            "headings": [],
            "code_blocks": [],
            "links": [],
            "images": [],
            "lists": {"ordered": 0, "unordered": 0},
            "tables": 0
        }
        
        lines = content.splitlines()
        in_code_block = False
        
        for line in lines:
            # 代码块
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                if in_code_block and len(line.strip()) > 3:
                    # 提取代码语言
                    lang = line.strip()[3:].strip()
                    if lang:
                        structure["code_blocks"].append(lang)
                continue
            
            if in_code_block:
                continue
            
            # 标题
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                structure["headings"].append({
                    "level": level,
                    "text": title
                })
            
            # 链接
            links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', line)
            for text, url in links:
                structure["links"].append({"text": text, "url": url})
            
            # 图片
            images = re.findall(r'!\[([^\]]*)\]\(([^\)]+)\)', line)
            for alt, url in images:
                structure["images"].append({"alt": alt, "url": url})
            
            # 列表
            if re.match(r'^\s*[-*+]\s+', line):
                structure["lists"]["unordered"] += 1
            elif re.match(r'^\s*\d+\.\s+', line):
                structure["lists"]["ordered"] += 1
            
            # 表格
            if '|' in line and line.count('|') >= 2:
                if re.match(r'^\s*\|?\s*:?-+:?\s*\|', line):
                    structure["tables"] += 1
        
        return structure
    
    def _extract_code_structure(self, content: str, language: str) -> Dict[str, Any]:
        """提取代码文件结构"""
        structure = {
            "language": language,
            "functions": [],
            "classes": [],
            "imports": [],
            "comments": {"single_line": 0, "multi_line": 0},
            "todos": []
        }
        
        lines = content.splitlines()
        
        # 语言特定的模式
        patterns = {
            'python': {
                'function': r'^\s*def\s+(\w+)\s*\(',
                'class': r'^\s*class\s+(\w+)',
                'import': r'^\s*(import|from)\s+',
                'single_comment': r'^\s*#',
                'multi_comment_start': r'^\s*"""',
                'multi_comment_end': r'"""'
            },
            'javascript': {
                'function': r'^\s*(function\s+(\w+)|const\s+(\w+)\s*=\s*.*=>)',
                'class': r'^\s*class\s+(\w+)',
                'import': r'^\s*(import|require)',
                'single_comment': r'^\s*//',
                'multi_comment_start': r'^\s*/\*',
                'multi_comment_end': r'\*/'
            },
            'java': {
                'function': r'^\s*(public|private|protected)?\s*\w+\s+(\w+)\s*\(',
                'class': r'^\s*(public|private|protected)?\s*class\s+(\w+)',
                'import': r'^\s*import\s+',
                'single_comment': r'^\s*//',
                'multi_comment_start': r'^\s*/\*',
                'multi_comment_end': r'\*/'
            }
        }
        
        # 获取语言模式
        lang_patterns = patterns.get(language, patterns.get('javascript'))
        
        in_multi_comment = False
        
        for line in lines:
            # 导入语句
            if re.match(lang_patterns['import'], line):
                structure["imports"].append(line.strip())
            
            # 函数定义
            func_match = re.match(lang_patterns['function'], line)
            if func_match:
                func_name = func_match.group(1) if func_match.group(1) else func_match.group(2)
                if func_name:
                    structure["functions"].append(func_name)
            
            # 类定义
            class_match = re.match(lang_patterns['class'], line)
            if class_match:
                class_name = class_match.group(1) if class_match.group(1) else class_match.group(2)
                if class_name:
                    structure["classes"].append(class_name)
            
            # 注释统计
            if re.match(lang_patterns['single_comment'], line):
                structure["comments"]["single_line"] += 1
            
            if re.search(lang_patterns['multi_comment_start'], line):
                in_multi_comment = True
            if in_multi_comment:
                structure["comments"]["multi_line"] += 1
            if re.search(lang_patterns['multi_comment_end'], line):
                in_multi_comment = False
            
            # TODO检测
            if 'TODO' in line or 'FIXME' in line or 'XXX' in line:
                structure["todos"].append(line.strip())
        
        return structure
    
    def _detect_log_patterns(self, content: str) -> Dict[str, Any]:
        """检测日志文件中的模式"""
        patterns = {
            "errors": [],
            "warnings": [],
            "info": [],
            "timestamps": [],
            "stack_traces": []
        }
        
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            # 错误
            if re.search(r'\b(ERROR|FATAL|CRITICAL)\b', line, re.IGNORECASE):
                patterns["errors"].append({"line": i + 1, "text": line[:200]})
            
            # 警告
            elif re.search(r'\b(WARN|WARNING)\b', line, re.IGNORECASE):
                patterns["warnings"].append({"line": i + 1, "text": line[:200]})
            
            # 信息
            elif re.search(r'\b(INFO|DEBUG)\b', line, re.IGNORECASE):
                if len(patterns["info"]) < 10:  # 限制数量
                    patterns["info"].append({"line": i + 1, "text": line[:200]})
            
            # 时间戳
            timestamp_match = re.search(
                r'\d{4}-\d{2}-\d{2}[\s|T]\d{2}:\d{2}:\d{2}', line
            )
            if timestamp_match and len(patterns["timestamps"]) < 5:
                patterns["timestamps"].append(timestamp_match.group())
            
            # 堆栈跟踪
            if re.match(r'^\s+at\s+', line) or re.match(r'^Traceback', line):
                if not patterns["stack_traces"] or i > patterns["stack_traces"][-1]["end_line"]:
                    patterns["stack_traces"].append({
                        "start_line": i + 1,
                        "end_line": i + 1,
                        "preview": line[:200]
                    })
                else:
                    patterns["stack_traces"][-1]["end_line"] = i + 1
        
        # 统计摘要
        patterns["summary"] = {
            "total_errors": len(patterns["errors"]),
            "total_warnings": len(patterns["warnings"]),
            "has_stack_traces": len(patterns["stack_traces"]) > 0
        }
        
        return patterns
    
    def _detect_special_patterns(self, content: str) -> Dict[str, List[str]]:
        """检测特殊模式（URL、邮箱、IP地址等）"""
        patterns = {}
        
        # URL
        urls = re.findall(r'https?://[^\s]+', content)
        if urls:
            patterns["urls"] = list(set(urls[:10]))  # 限制数量
        
        # 邮箱
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
        if emails:
            patterns["emails"] = list(set(emails[:10]))
        
        # IP地址
        ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', content)
        if ips:
            patterns["ip_addresses"] = list(set(ips[:10]))
        
        # 文件路径
        paths = re.findall(r'[/\\](?:[\w.-]+[/\\])*[\w.-]+', content)
        if paths:
            # 过滤掉太短的路径
            paths = [p for p in paths if len(p) > 5]
            patterns["file_paths"] = list(set(paths[:10]))
        
        return patterns


# 用于直接测试的辅助函数
def parse_text_file(file_path: str, output_format: str = "full") -> Union[Dict, str]:
    """
    便捷函数：解析文本文件并返回内容
    
    Args:
        file_path: 文本文件路径
        output_format: 输出格式（full/content/summary）
    
    Returns:
        解析后的内容或摘要
    """
    parser = TextParserTool()
    result = parser.execute({"file_path": file_path})
    
    if result["status"] == "success":
        if output_format == "content":
            return result.get("content", "")
        elif output_format == "summary":
            return {
                "file_type": result.get("file_type"),
                "statistics": result.get("statistics"),
                "metadata": result.get("metadata")
            }
        else:
            return result
    else:
        raise Exception(result["message"])


if __name__ == "__main__":
    # 命令行测试
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python text_parser.py <文件路径> [输出格式:full/content/summary]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    output_format = sys.argv[2] if len(sys.argv) > 2 else "full"
    
    try:
        result = parse_text_file(file_path, output_format)
        
        if isinstance(result, dict):
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result)
            
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)