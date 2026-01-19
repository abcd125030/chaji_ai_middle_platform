from tools.core.base import BaseTool
from typing import Dict, Any
import pandas as pd
import os

class ExcelProcessorTool(BaseTool):
    """
    Excel处理工具：将Excel文件读取为Pandas DataFrame，并序列化为JSON。
    输入必须包含有效的Excel文件路径。
    """
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Excel文件路径，支持.xlsx和.xls格式",
                    "pattern": r"\.xlsx?$"
                }
            },
            "required": ["file_path"]
        }
    
    def execute(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        file_path = tool_input.get('file_path')
        
        if not os.path.exists(file_path):
            return {
                "status": "error",
                "message": f"文件不存在: {file_path}",
                "file_path": file_path
            }
        
        try:
            df = pd.read_excel(file_path)
            table_json = df.to_json(orient='records', force_ascii=False)
            
            return {
                "status": "success",
                "message": f"文件 '{os.path.basename(file_path)}' 已成功处理为JSON格式的表格数据。",
                "table_json": table_json,
                "file_path": file_path,
                "row_count": len(df),
                "column_count": len(df.columns)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Excel处理失败: {str(e)}",
                "file_path": file_path
            }