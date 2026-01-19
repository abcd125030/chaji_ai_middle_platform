"""
用户上下文构建工具
用于从 RuntimeState 中提取用户信息并构建 user_context
"""
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from django.contrib.auth import get_user_model
from authentication.models_extension import UserProfile

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ..schemas import RuntimeState

logger = logging.getLogger('django')
User = get_user_model()


def build_user_context(user_id: int) -> Dict[str, Any]:
    """
    根据用户ID构建用户上下文信息
    
    Args:
        user_id: 用户ID
        
    Returns:
        包含用户完整信息的字典
    """
    try:
        # 获取用户对象
        user = User.objects.get(id=user_id)
        
        # 获取或创建 UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            logger.info(f"为用户 {user.username} (ID: {user_id}) 创建了新的 UserProfile")
        
        # 构建用户上下文
        user_context = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "profile_id": str(profile.id),
            
            "role": {
                "subscription_type": profile.subscription_type,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_active": user.is_active
            },
            
            "permissions": {
                "capabilities": profile.capabilities or {},
                "quotas": profile.quotas or {}
            },
            
            "tags": profile.tags or [],
            
            "metadata": {
                "industry": profile.industry,
                "preferences": profile.preferences or {},
                "context_data": profile.context_data or {},
                "usage_stats": profile.usage_stats or {}
            },
            
            "timestamps": {
                "date_joined": user.date_joined.isoformat() if user.date_joined else None,
                "profile_created_at": profile.created_at.isoformat() if profile.created_at else None,
                "profile_updated_at": profile.updated_at.isoformat() if profile.updated_at else None
            }
        }
        
        return user_context
        
    except User.DoesNotExist:
        logger.error(f"用户 ID {user_id} 不存在")
        return {}
    except Exception as e:
        logger.error(f"构建用户上下文失败: {str(e)}", exc_info=True)
        return {}


def build_user_prompt(user_context: Dict[str, Any]) -> str:
    """
    将 user_context 数据转换为描述用户的自然语言段落
    用于在 Graph 执行过程中添加到 LLM 提示词中
    
    Args:
        user_context: 用户上下文数据字典
        
    Returns:
        描述用户的连贯段落文本
    """
    if not user_context:
        return "当前用户信息不明。"
    
    # 订阅类型映射 - 与 UserProfile.SubscriptionType 完全一致
    SUBSCRIPTION_MAP = {
        'free_user': '免费用户',
        'vip_user': 'VIP用户',
        'enterprise_user': '企业用户',
        'max_user': 'Max用户'
    }
    
    # 行业类型映射 - 与 UserProfile.IndustryType 完全一致  
    INDUSTRY_MAP = {
        'technology': '科技行业',
        'finance': '金融行业',
        'healthcare': '医疗健康行业',
        'education': '教育行业',
        'retail': '零售行业',
        'manufacturing': '制造业',
        'real_estate': '房地产行业',
        'hospitality': '酒店服务业',
        'transportation': '交通运输业',
        'energy': '能源行业',
        'media': '媒体娱乐业',
        'telecommunications': '电信行业',
        'agriculture': '农业',
        'construction': '建筑业',
        'government': '政府部门',
        'non_profit': '非营利组织',
        'consulting': '咨询行业',
        'legal': '法律行业',
        'insurance': '保险行业',
        'pharmaceutical': '制药行业',
        'automotive': '汽车行业',
        'aerospace': '航空航天业',
        'logistics': '物流供应链行业',
        'e_commerce': '电子商务行业',
        'other': '其他行业'
    }
    
    # 服务级别描述
    SERVICE_LEVEL_DESC = {
        'free_user': '基础服务，可能需要引导升级到付费版本以获得更好的体验',
        'vip_user': '优质服务，提供个性化支持和优先响应',
        'enterprise_user': '企业级服务，提供专业支持和定制化解决方案',
        'max_user': '顶级服务，无限制访问所有功能和最高优先级支持'
    }
    
    # 提取基本信息
    username = user_context.get('username', '用户')
    user_id = user_context.get('user_id', '')
    email = user_context.get('email', '')
    
    # 提取角色和订阅信息
    role = user_context.get('role', {})
    subscription_type = role.get('subscription_type', 'free_user')
    user_level = SUBSCRIPTION_MAP.get(subscription_type, '普通用户')
    service_level = SERVICE_LEVEL_DESC.get(subscription_type, '标准服务')
    is_staff = role.get('is_staff', False)
    is_superuser = role.get('is_superuser', False)
    
    # 提取元数据
    metadata = user_context.get('metadata', {})
    industry = metadata.get('industry', '')
    industry_desc = INDUSTRY_MAP.get(industry, '')
    context_data = metadata.get('context_data', {})
    preferences = metadata.get('preferences', {})
    usage_stats = metadata.get('usage_stats', {})
    
    # 提取标签
    tags = user_context.get('tags', [])
    
    # 提取权限和配额
    permissions = user_context.get('permissions', {})
    capabilities = permissions.get('capabilities', {})
    quotas = permissions.get('quotas', {})
    
    # 构建描述段落
    description_parts = []
    
    # 第一句：介绍用户基本身份
    intro = f"我们正在与{username}进行交互"
    if industry_desc:
        intro += f"，他来自{industry_desc}"
        if context_data.get('company'):
            intro += f"的{context_data['company']}"
            if context_data.get('department'):
                intro += f"{context_data['department']}"
    intro += "。"
    description_parts.append(intro)
    
    # 第二句：用户级别和服务要求
    level_desc = f"他是我们的{user_level}"
    if is_superuser:
        level_desc += "，拥有超级管理员权限"
    elif is_staff:
        level_desc += "，拥有员工权限"
    level_desc += f"，我们需要为他提供{service_level}。"
    description_parts.append(level_desc)
    
    # 第三句：使用历史和偏好（如果有）
    if usage_stats or preferences:
        usage_parts = []
        
        if usage_stats.get('total_requests'):
            usage_parts.append(f"已累计使用{usage_stats['total_requests']}次")
        
        if preferences:
            pref_items = []
            if preferences.get('language'):
                pref_items.append(f"偏好使用{preferences['language']}")
            if preferences.get('output_format'):
                pref_items.append(f"期望{preferences['output_format']}格式的输出")
            if pref_items:
                usage_parts.extend(pref_items)
        
        if usage_parts:
            description_parts.append(f"根据历史记录，他{'，'.join(usage_parts)}。")
    
    # 第四句：特殊标签和需求（如果有）
    if tags:
        tag_desc = f"他被标记为{'、'.join(tags)}，这表明他可能有特定的需求或特征。"
        description_parts.append(tag_desc)
    
    # 第五句：能力和限制（如果有特殊设置）
    special_items = []
    if capabilities:
        active_caps = [k for k, v in capabilities.items() if v]
        if active_caps:
            special_items.append(f"已开通{len(active_caps)}项特殊功能")
    
    if quotas:
        high_quotas = [f"{k}配额{v}" for k, v in quotas.items() 
                      if isinstance(v, (int, float)) and v > 10000]
        if high_quotas:
            special_items.append(f"享有较高的使用配额")
    
    if special_items:
        description_parts.append(f"需要注意的是，他{'，同时'.join(special_items)}。")
    
    # 第六句：服务建议（根据用户级别）
    if subscription_type == 'free_user':
        description_parts.append("在提供服务时，可以适当介绍付费功能的优势，引导其了解升级后的更好体验。")
    elif subscription_type == 'vip_user':
        description_parts.append("请确保提供优质、个性化的服务体验，满足其专业需求。")
    elif subscription_type == 'enterprise_user':
        description_parts.append("请提供专业、高效的企业级支持，关注其业务需求和团队协作场景。")
    elif subscription_type == 'max_user':
        description_parts.append("这是我们的顶级用户，请提供最优质的服务，充分利用所有可用资源满足其需求。")
    
    # 组合成完整段落
    return ''.join(description_parts)


def update_runtime_state_with_user_context(runtime_state: 'RuntimeState') -> 'RuntimeState':
    """
    从 RuntimeState 中提取用户信息并更新 user_context 字段
    
    Args:
        runtime_state: RuntimeState 实例
        
    Returns:
        更新后的 RuntimeState 实例
    """
    # 从 runtime_state 中获取用户ID
    user_id = None
    
    # 尝试从多个可能的位置获取用户ID
    if hasattr(runtime_state, 'user_id'):
        user_id = runtime_state.user_id
    elif hasattr(runtime_state, 'user') and runtime_state.user:
        user_id = runtime_state.user.id if hasattr(runtime_state.user, 'id') else None
    elif runtime_state.user_context and 'user_id' in runtime_state.user_context:
        user_id = runtime_state.user_context['user_id']
    
    if not user_id:
        logger.warning("无法从 RuntimeState 中提取用户ID")
        return runtime_state
    
    # 构建用户上下文
    user_context = build_user_context(user_id)
    
    if user_context:
        # 更新 RuntimeState 的 user_context 字段
        runtime_state.user_context = user_context
        logger.info(f"成功更新用户 {user_context.get('username')} 的上下文信息")
    else:
        logger.error(f"无法为用户ID {user_id} 构建上下文")
    
    return runtime_state