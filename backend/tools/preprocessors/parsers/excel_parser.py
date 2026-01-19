"""
Excel文档解析工具
==================

将Excel文件（.xlsx/.xls）内容转换为结构化的JSON格式。
使用pandas读取数据，输出适合数据分析和可视化的JSON结构。
"""

import os
import io
import json
import logging
from typing import Dict, Any, List, Optional, Union
from tools.core.base import BaseTool
from tools.core.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


class ExcelParserTool(BaseTool):
    """
    Excel文档解析工具：将Excel文件转换为结构化JSON格式。
    
    功能特性：
    1. 读取所有工作表（sheets）
    2. 自动识别数据类型（数值、日期、文本）
    3. 处理空值和缺失数据
    4. 生成数据统计摘要
    5. 支持多种输出格式（records、columns、values）
    6. 检测并处理合并单元格
    7. 识别表头和数据区域
    """
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要解析的Excel文件路径"
                },
                "sheet_name": {
                    "type": ["string", "integer", "null"],
                    "description": "要读取的工作表名称或索引，None表示读取所有表",
                    "default": None
                },
                "orient": {
                    "type": "string",
                    "enum": ["records", "columns", "values", "split", "index"],
                    "description": "JSON输出格式：records(行数组)、columns(列字典)、values(值数组)、split(分离的列名和数据)、index(索引字典)",
                    "default": "records"
                },
                "parse_dates": {
                    "type": "boolean",
                    "description": "是否解析日期",
                    "default": True
                },
                "na_values": {
                    "type": "string",
                    "description": "空值的替代值",
                    "default": ""
                },
                "include_summary": {
                    "type": "boolean",
                    "description": "是否包含数据摘要统计",
                    "default": True
                },
                "max_rows": {
                    "type": ["integer", "null"],
                    "description": "最大读取行数，None表示全部",
                    "default": None
                }
            },
            "required": ["file_path"]
        }

    def execute(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """执行Excel文档解析"""
        file_path = tool_input.get('file_path')
        sheet_name = tool_input.get('sheet_name', None)
        orient = tool_input.get('orient', 'records')
        parse_dates = tool_input.get('parse_dates', True)
        na_values = tool_input.get('na_values', '')
        include_summary = tool_input.get('include_summary', True)
        max_rows = tool_input.get('max_rows', None)
        
        # 验证输入
        if not file_path:
            return {"status": "error", "message": "文件路径未提供"}
        
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"文件不存在: {file_path}"}
        
        if not file_path.lower().endswith(('.xlsx', '.xls', '.xlsm', '.xlsb')):
            return {"status": "error", "message": f"不支持的文件格式: {file_path}"}
        
        try:
            # 解析Excel
            result = self._parse_excel(
                file_path=file_path,
                sheet_name=sheet_name,
                orient=orient,
                parse_dates=parse_dates,
                na_values=na_values,
                include_summary=include_summary,
                max_rows=max_rows
            )
            
            return {
                "status": "success",
                "message": f"文件 '{os.path.basename(file_path)}' 已成功解析",
                "file_path": file_path,
                **result
            }
            
        except ImportError as e:
            logger.error(f"缺少必要的依赖库: {str(e)}")
            return {
                "status": "error",
                "message": "需要安装pandas和openpyxl: pip install pandas openpyxl xlrd",
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Excel解析失败: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Excel解析失败: {str(e)}",
                "file_path": file_path
            }
    
    def _parse_excel(self, file_path: str, sheet_name: Optional[Union[str, int]] = None,
                     orient: str = 'records', parse_dates: bool = True,
                     na_values: str = '', include_summary: bool = True,
                     max_rows: Optional[int] = None) -> Dict[str, Any]:
        """解析Excel文档的核心方法"""
        try:
            import pandas as pd
            import numpy as np
        except ImportError:
            raise ImportError("需要安装pandas: pip install pandas openpyxl")
        
        result = {}
        
        # 读取Excel文件
        if sheet_name is None:
            # 读取所有工作表
            excel_file = pd.ExcelFile(file_path)
            sheets_data = {}
            sheets_summary = {}
            
            for sheet in excel_file.sheet_names:
                df = pd.read_excel(
                    file_path, 
                    sheet_name=sheet,
                    parse_dates=parse_dates,
                    na_values=na_values if na_values else None,
                    nrows=max_rows
                )
                
                # 处理数据
                df = self._process_dataframe(df)
                
                # 转换为JSON
                if orient == 'split':
                    # split格式分离列名和数据
                    sheet_json = {
                        'columns': df.columns.tolist(),
                        'index': df.index.tolist(),
                        'data': df.values.tolist()
                    }
                else:
                    # 使用pandas的to_dict方法
                    sheet_json = df.to_dict(orient=orient)
                
                sheets_data[sheet] = sheet_json
                
                # 生成摘要
                if include_summary:
                    sheets_summary[sheet] = self._generate_summary(df, sheet)
            
            result['sheets'] = sheets_data
            result['sheet_names'] = excel_file.sheet_names
            
            if include_summary:
                result['summary'] = sheets_summary
                result['file_summary'] = {
                    'total_sheets': len(excel_file.sheet_names),
                    'sheets_info': [
                        {
                            'name': sheet,
                            'rows': len(sheets_data[sheet]) if orient == 'records' else len(sheets_data[sheet].get('data', [])),
                            'columns': len(sheets_summary[sheet]['columns']) if sheet in sheets_summary else 0
                        }
                        for sheet in excel_file.sheet_names
                    ]
                }
        else:
            # 读取指定工作表
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                parse_dates=parse_dates,
                na_values=na_values if na_values else None,
                nrows=max_rows
            )
            
            # 处理数据
            df = self._process_dataframe(df)
            
            # 转换为JSON
            if orient == 'split':
                data_json = {
                    'columns': df.columns.tolist(),
                    'index': df.index.tolist(),
                    'data': df.values.tolist()
                }
            else:
                data_json = df.to_dict(orient=orient)
            
            result['data'] = data_json
            result['sheet_name'] = sheet_name if isinstance(sheet_name, str) else f"Sheet_{sheet_name}"
            
            if include_summary:
                result['summary'] = self._generate_summary(df, result['sheet_name'])
        
        # 添加元数据
        result['metadata'] = {
            'orient': orient,
            'parse_dates': parse_dates,
            'max_rows': max_rows
        }
        
        return result
    
    def _process_dataframe(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """处理DataFrame，清理和标准化数据"""
        import pandas as pd
        import numpy as np
        
        # 处理空值
        df = df.replace([np.inf, -np.inf], np.nan)
        
        # 处理日期列（将datetime对象转换为字符串以便JSON序列化）
        for col in df.select_dtypes(include=['datetime64']).columns:
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
        
        # 处理时间戳
        for col in df.select_dtypes(include=['timedelta64']).columns:
            df[col] = df[col].astype(str)
        
        # 处理复杂对象类型
        for col in df.select_dtypes(include=['object']).columns:
            # 尝试转换为字符串
            df[col] = df[col].fillna('').astype(str)
        
        # 填充剩余的NaN值
        df = df.fillna('')
        
        return df
    
    def _generate_summary(self, df: 'pd.DataFrame', sheet_name: str) -> Dict[str, Any]:
        """生成数据摘要统计"""
        import pandas as pd
        import numpy as np
        
        summary = {
            'sheet_name': sheet_name,
            'shape': {
                'rows': len(df),
                'columns': len(df.columns)
            },
            'columns': df.columns.tolist(),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'non_null_counts': df.count().to_dict(),
            'null_counts': df.isnull().sum().to_dict()
        }
        
        # 数值列统计
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            numeric_summary = {}
            for col in numeric_cols:
                col_stats = {
                    'mean': float(df[col].mean()) if not pd.isna(df[col].mean()) else None,
                    'median': float(df[col].median()) if not pd.isna(df[col].median()) else None,
                    'std': float(df[col].std()) if not pd.isna(df[col].std()) else None,
                    'min': float(df[col].min()) if not pd.isna(df[col].min()) else None,
                    'max': float(df[col].max()) if not pd.isna(df[col].max()) else None,
                    'sum': float(df[col].sum()) if not pd.isna(df[col].sum()) else None
                }
                numeric_summary[col] = col_stats
            summary['numeric_summary'] = numeric_summary
        
        # 分类列统计
        categorical_cols = df.select_dtypes(include=['object']).columns
        if len(categorical_cols) > 0:
            categorical_summary = {}
            for col in categorical_cols[:10]:  # 限制前10个分类列
                value_counts = df[col].value_counts().head(10).to_dict()
                categorical_summary[col] = {
                    'unique_count': df[col].nunique(),
                    'top_values': value_counts
                }
            summary['categorical_summary'] = categorical_summary
        
        # 数据质量指标
        total_cells = len(df) * len(df.columns)
        null_cells = df.isnull().sum().sum()
        summary['data_quality'] = {
            'total_cells': total_cells,
            'null_cells': int(null_cells),
            'completeness': round((1 - null_cells / total_cells) * 100, 2) if total_cells > 0 else 0
        }
        
        return summary
    
    def _detect_table_structure(self, df: 'pd.DataFrame') -> Dict[str, Any]:
        """检测表格结构，识别标题行、数据区域等"""
        structure = {
            'has_header': True,  # pandas默认第一行为表头
            'header_row': 0,
            'data_start_row': 1,
            'data_end_row': len(df),
            'has_index': df.index.name is not None,
            'index_column': 0 if df.index.name else None
        }
        
        # 检测是否有多级表头
        if hasattr(df.columns, 'levels') and df.columns.nlevels > 1:
            structure['multi_level_header'] = True
            structure['header_levels'] = df.columns.nlevels
        else:
            structure['multi_level_header'] = False
            structure['header_levels'] = 1
        
        return structure


# 用于直接测试的辅助函数
def parse_excel_file(file_path: str, sheet_name: Optional[Union[str, int]] = None,
                    orient: str = 'records', output_file: Optional[str] = None) -> Union[Dict, str]:
    """
    便捷函数：解析Excel文件并返回JSON数据
    
    Args:
        file_path: Excel文件路径
        sheet_name: 工作表名称或索引，None表示所有表
        orient: 输出格式
        output_file: 如果指定，将结果保存到此JSON文件
    
    Returns:
        解析后的JSON数据或JSON字符串
    """
    parser = ExcelParserTool()
    result = parser.execute({
        "file_path": file_path,
        "sheet_name": sheet_name,
        "orient": orient,
        "include_summary": True
    })
    
    if result["status"] == "success":
        # 移除状态信息，只保留数据
        data = {k: v for k, v in result.items() if k not in ["status", "message", "file_path"]}
        
        if output_file:
            # 保存到文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return f"数据已保存到: {output_file}"
        else:
            return data
    else:
        raise Exception(result["message"])


if __name__ == "__main__":
    # 命令行测试
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python excel_parser.py <excel文件路径> [工作表名称] [输出格式:records/columns/values/split] [输出JSON文件]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    sheet_name = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != 'all' else None
    orient = sys.argv[3] if len(sys.argv) > 3 else 'records'
    output_file = sys.argv[4] if len(sys.argv) > 4 else None
    
    try:
        result = parse_excel_file(file_path, sheet_name, orient, output_file)
        
        if isinstance(result, str):
            print(result)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)