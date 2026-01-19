class ToolError(Exception):
    """工具系统基础异常"""
    pass

class ToolConfigError(ToolError):
    """工具配置错误"""
    pass

class ToolExecutionError(ToolError):
    """工具执行错误"""
    pass

class ToolNotFoundError(ToolError):
    """工具未找到错误"""
    pass

class ToolValidationError(ToolError):
    """工具输入验证错误"""
    pass