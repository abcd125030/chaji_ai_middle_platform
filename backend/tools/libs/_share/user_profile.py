"""
用户画像提取函数模块

通过RuntimeState获取用户的profile信息，返回格式化的文本描述
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agentic.core.schemas import RuntimeState

logger = logging.getLogger(__name__)


def get_user_profile(state: 'RuntimeState') -> str:
    """
    从RuntimeState中提取用户profile信息
    
    Args:
        state: RuntimeState实例，包含user_context等用户信息
        
    Returns:
        str: 用户profile的文本描述
    """
    try:
        # 从state中提取用户相关信息
        user_context = state.user_context if hasattr(state, 'user_context') else {}
        
        # 尝试从不同来源获取用户信息
        user_id = user_context.get('user_id', 'unknown')
        user_name = user_context.get('user_name', '')
        user_role = user_context.get('role', '')
        user_department = user_context.get('department', '')
        
        # 获取用户偏好设置
        preferences = user_context.get('preferences', {})
        language_style = preferences.get('language_style', '正式、严谨')
        report_format = preferences.get('report_format', '专业报告')
        
        # 从历史行为分析用户关注点
        focus_areas = []
        if hasattr(state, 'action_history') and state.action_history:
            # 分析最常用的工具
            tool_usage = {}
            for action in state.action_history:
                if isinstance(action, dict):
                    tool_name = action.get('tool_name', '')
                    if tool_name:
                        tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
            
            # 根据工具使用推断关注领域
            if 'data_analysis' in tool_usage or 'pandas_data_calculator' in tool_usage:
                focus_areas.append('数据分析')
            if 'web_search' in tool_usage:
                focus_areas.append('信息搜索')
            if 'report_generator' in tool_usage:
                focus_areas.append('报告生成')
        
        # 构建profile文本
        profile_parts = []
        
        if user_id and user_id != 'unknown':
            profile_parts.append(f"用户ID: {user_id}")
        
        if user_name:
            profile_parts.append(f"用户名称: {user_name}")
        
        if user_role:
            profile_parts.append(f"用户角色: {user_role}")
            
        if user_department:
            profile_parts.append(f"所属部门: {user_department}")
        
        profile_parts.append(f"语言风格: {language_style}")
        profile_parts.append(f"报告偏好: {report_format}")
        
        if focus_areas:
            profile_parts.append(f"关注领域: {', '.join(focus_areas)}")
        
        # 添加默认关注重点
        profile_parts.append("关注重点: 数据准确性、逻辑清晰、结果可靠")
        
        profile_text = "\n".join(profile_parts)
        
        logger.debug(f"Generated user profile: {len(profile_text)} chars")
        return profile_text
        
    except Exception as e:
        logger.error(f"Failed to extract user profile from state: {str(e)}")
        # 返回默认用户画像
        return """用户信息: 标准用户
语言风格: 正式、严谨
报告偏好: 专业报告
关注重点: 数据准确性、逻辑清晰"""