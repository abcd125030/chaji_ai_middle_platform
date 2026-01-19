"""
用户管理服务
"""

import logging
from typing import Optional, Dict, List, Tuple
from django.contrib.auth import get_user_model
from django.db.models import Q
from authentication.models import UserAccount

logger = logging.getLogger(__name__)
User = get_user_model()


class UserManagementService:
    """用户管理服务 - 提供用户激活、查询等管理功能"""
    
    @staticmethod
    def activate_user(user_id: int, admin_user=None) -> Tuple[bool, str]:
        """
        激活用户
        
        Args:
            user_id: 用户ID
            admin_user: 执行操作的管理员用户（可选）
            
        Returns:
            tuple: (成功标志, 消息)
        """
        try:
            user = User.objects.get(id=user_id)
            
            if user.status == User.Status.ACTIVE:
                return True, '用户已经是激活状态'
            
            user.status = User.Status.ACTIVE
            user.save()
            
            if admin_user:
                logger.info(f"管理员 {admin_user.username} 激活了用户 {user.username}")
            else:
                logger.info(f"用户 {user.username} 被激活")
            
            return True, f'用户 {user.username} 已激活'
            
        except User.DoesNotExist:
            return False, '用户不存在'
        except Exception as e:
            logger.error(f"激活用户失败: {e}", exc_info=True)
            return False, '操作失败，请稍后重试'
    
    @staticmethod
    def deactivate_user(user_id: int, admin_user=None) -> Tuple[bool, str]:
        """
        停用用户
        
        Args:
            user_id: 用户ID
            admin_user: 执行操作的管理员用户（可选）
            
        Returns:
            tuple: (成功标志, 消息)
        """
        try:
            user = User.objects.get(id=user_id)
            
            if user.status == User.Status.INACTIVE:
                return True, '用户已经是未激活状态'
            
            user.status = User.Status.INACTIVE
            user.save()
            
            if admin_user:
                logger.info(f"管理员 {admin_user.username} 停用了用户 {user.username}")
            else:
                logger.info(f"用户 {user.username} 被停用")
            
            return True, f'用户 {user.username} 已停用'
            
        except User.DoesNotExist:
            return False, '用户不存在'
        except Exception as e:
            logger.error(f"停用用户失败: {e}", exc_info=True)
            return False, '操作失败，请稍后重试'
    
    @staticmethod
    def ban_user(user_id: int, admin_user=None, reason: str = None) -> Tuple[bool, str]:
        """
        封禁用户
        
        Args:
            user_id: 用户ID
            admin_user: 执行操作的管理员用户（可选）
            reason: 封禁原因（可选）
            
        Returns:
            tuple: (成功标志, 消息)
        """
        try:
            user = User.objects.get(id=user_id)
            
            if user.status == User.Status.BANNED:
                return True, '用户已经是封禁状态'
            
            user.status = User.Status.BANNED
            user.save()
            
            log_msg = f"用户 {user.username} 被封禁"
            if admin_user:
                log_msg = f"管理员 {admin_user.username} 封禁了{log_msg}"
            if reason:
                log_msg += f"，原因：{reason}"
            
            logger.info(log_msg)
            
            return True, f'用户 {user.username} 已封禁'
            
        except User.DoesNotExist:
            return False, '用户不存在'
        except Exception as e:
            logger.error(f"封禁用户失败: {e}", exc_info=True)
            return False, '操作失败，请稍后重试'
    
    @staticmethod
    def get_user_list(
        status_filter: str = 'all',
        provider_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict:
        """
        获取用户列表
        
        Args:
            status_filter: 状态筛选 ('all', 'active', 'inactive', 'banned')
            provider_filter: 登录方式筛选 ('email', 'google', 'feishu')
            search_query: 搜索关键词（用户名或邮箱）
            page: 页码
            page_size: 每页数量
            
        Returns:
            dict: 包含用户列表和分页信息的字典
        """
        # 构建查询
        queryset = User.objects.all()
        
        # 状态筛选
        if status_filter == 'active':
            queryset = queryset.filter(status=User.Status.ACTIVE)
        elif status_filter == 'inactive':
            queryset = queryset.filter(status=User.Status.INACTIVE)
        elif status_filter == 'banned':
            queryset = queryset.filter(status=User.Status.BANNED)
        
        # 登录方式筛选
        if provider_filter:
            user_ids = UserAccount.objects.filter(
                provider=provider_filter
            ).values_list('user_id', flat=True)
            queryset = queryset.filter(id__in=user_ids)
        
        # 搜索
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        
        # 排序（最新注册的在前）
        queryset = queryset.order_by('-date_joined')
        
        # 分页
        total_count = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        users = queryset[start:end]
        
        # 构建用户数据
        user_list = UserManagementService._build_user_list(users)
        
        return {
            'users': user_list,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            }
        }
    
    @staticmethod
    def get_user_detail(user_id: int) -> Optional[Dict]:
        """
        获取用户详细信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户详细信息，如果不存在返回None
        """
        try:
            user = User.objects.get(id=user_id)
            return UserManagementService._build_user_detail(user)
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def get_user_statistics() -> Dict:
        """
        获取用户统计信息
        
        Returns:
            dict: 统计信息
        """
        total = User.objects.count()
        active = User.objects.filter(status=User.Status.ACTIVE).count()
        inactive = User.objects.filter(status=User.Status.INACTIVE).count()
        banned = User.objects.filter(status=User.Status.BANNED).count()
        
        # 按登录方式统计
        providers_stats = {}
        for provider in ['email', 'google', 'feishu']:
            count = UserAccount.objects.filter(provider=provider).values('user').distinct().count()
            providers_stats[provider] = count
        
        return {
            'total': total,
            'by_status': {
                'active': active,
                'inactive': inactive,
                'banned': banned
            },
            'by_provider': providers_stats
        }
    
    @staticmethod
    def update_user_role(user_id: int, new_role: str, admin_user=None) -> Tuple[bool, str]:
        """
        更新用户角色
        
        Args:
            user_id: 用户ID
            new_role: 新角色 ('user', 'admin', 'super_admin')
            admin_user: 执行操作的管理员用户（可选）
            
        Returns:
            tuple: (成功标志, 消息)
        """
        try:
            user = User.objects.get(id=user_id)
            
            # 验证角色值
            valid_roles = [choice[0] for choice in User.Role.choices]
            if new_role not in valid_roles:
                return False, f'无效的角色: {new_role}'
            
            old_role = user.role
            user.role = new_role
            user.save()
            
            if admin_user:
                logger.info(f"管理员 {admin_user.username} 将用户 {user.username} 的角色从 {old_role} 改为 {new_role}")
            
            return True, f'用户角色已更新为 {user.get_role_display()}'
            
        except User.DoesNotExist:
            return False, '用户不存在'
        except Exception as e:
            logger.error(f"更新用户角色失败: {e}", exc_info=True)
            return False, '操作失败，请稍后重试'
    
    @staticmethod
    def _build_user_list(users) -> List[Dict]:
        """
        构建用户列表数据
        
        Args:
            users: 用户查询集
            
        Returns:
            list: 用户数据列表
        """
        user_list = []
        for user in users:
            # 获取用户的登录方式
            accounts = UserAccount.objects.filter(user=user)
            providers = [acc.provider for acc in accounts]
            
            user_list.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'status': user.get_status_display(),
                'status_code': user.status,
                'role': user.role,
                'role_display': user.get_role_display(),
                'providers': providers,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'avatar_url': user.avatar_url
            })
        
        return user_list
    
    @staticmethod
    def _build_user_detail(user) -> Dict:
        """
        构建用户详细信息
        
        Args:
            user: 用户对象
            
        Returns:
            dict: 用户详细信息
        """
        # 获取所有账号信息
        accounts = []
        for account in user.accounts.all():
            accounts.append({
                'provider': account.provider,
                'provider_display': account.get_provider_display(),
                'is_primary': account.is_primary,
                'is_verified': account.is_verified,
                'created_at': account.created_at.isoformat(),
                'last_used_at': account.last_used_at.isoformat() if account.last_used_at else None
            })
        
        # 获取UserProfile信息
        profile_data = None
        try:
            from authentication.models_extension import UserProfile
            profile = UserProfile.objects.get(user=user)
            profile_data = {
                'subscription_type': profile.subscription_type,
                'subscription_display': profile.get_subscription_type_display(),
                'daily_quota': profile.daily_quota,
                'used_quota': profile.used_quota,
                'api_quota': profile.api_quota,
                'used_api_quota': profile.used_api_quota
            }
        except UserProfile.DoesNotExist:
            pass
        
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'status': user.get_status_display(),
            'status_code': user.status,
            'role': user.role,
            'role_display': user.get_role_display(),
            'avatar_url': user.avatar_url,
            'phone': user.phone,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'accounts': accounts,
            'profile': profile_data,
            'agreed_agreement_version': user.agreed_agreement_version,
            'agreed_at': user.agreed_at.isoformat() if user.agreed_at else None
        }