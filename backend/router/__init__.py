# -*- coding: utf-8 -*-
"""
Router模块
提供模型配置查询和管理服务
"""

# 延迟导入以避免Django初始化问题
def __getattr__(name):
    if name == 'ModelConfigService':
        from .services import ModelConfigService
        return ModelConfigService
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")