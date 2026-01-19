"""
工具类型枚举定义

定义了工具系统中支持的所有工具类型
"""

from enum import Enum


class ToolType(Enum):
    """工具类型枚举"""
    
    # 数据分析类 - 用于数据处理、计算和分析
    DATA_ANALYSIS = "data_analysis"
    
    # 检索类 - 用于搜索、查询和获取信息
    RETRIEVAL = "retrieval"
    
    # 生成器类 - 用于创建、生成新内容、翻译转换等
    GENERATOR = "generator"
    
    # 通用类 - 提供通用功能的工具
    GENERAL = "general"
    
    @classmethod
    def from_string(cls, value: str) -> 'ToolType':
        """从字符串值创建枚举实例"""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown tool type: {value}")
    
    @property
    def description(self) -> str:
        """获取工具类型的描述"""
        descriptions = {
            self.DATA_ANALYSIS: "数据处理、计算和分析工具",
            self.RETRIEVAL: "信息搜索、查询和获取工具",
            self.GENERATOR: "内容创建、生成和转换工具",
            self.GENERAL: "提供通用功能的工具"
        }
        return descriptions.get(self, "未知类型")
    
    @property
    def directory_name(self) -> str:
        """获取该类型工具应该存放的目录名"""
        # 枚举值直接对应目录名
        return self.value