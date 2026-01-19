"""
Join Wish 申请服务
处理用户加入意愿表单提交和通知
"""

import logging
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from authentication.models_extension import UserProfile

logger = logging.getLogger(__name__)
User = get_user_model()


class JoinWishService:
    """Join Wish 申请服务"""
    
    @staticmethod
    def submit_join_wish(user, form_data):
        """
        提交加入意愿表单
        
        Args:
            user: 用户对象
            form_data: 表单数据，包含 company, role, interest, message 等
            
        Returns:
            dict: 处理结果
        """
        try:
            # 获取或创建 UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # 准备要存储的数据
            join_wish_data = {
                'submitted_at': datetime.now().isoformat(),
                'company': form_data.get('company', ''),
                'role': form_data.get('role', ''),
                'interest': form_data.get('interest', ''),
                'message': form_data.get('message', ''),
                'status': 'pending',  # pending, approved, rejected
                'submitted_from': 'join_wish_form'
            }
            
            # 更新 context_data
            if not profile.context_data:
                profile.context_data = {}
            
            # 保存 join_wish 信息到 context_data
            profile.context_data['join_wish'] = join_wish_data
            
            # 如果有公司信息，也更新到主要字段
            if form_data.get('company'):
                profile.context_data['company'] = form_data.get('company')
            if form_data.get('role'):
                profile.context_data['department'] = form_data.get('role')
            
            profile.save()
            
            # 发送通知邮件给用户
            JoinWishService._send_user_notification(user, form_data)
            
            # 发送通知邮件给管理员
            JoinWishService._send_admin_notification(user, form_data)
            
            logger.info(f"用户 {user.email} 提交了 Join Wish 申请")
            
            return {
                'success': True,
                'message': '申请已提交，我们会尽快与您联系'
            }
            
        except Exception as e:
            logger.error(f"提交 Join Wish 申请失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': '提交失败，请稍后重试'
            }
    
    @staticmethod
    def _send_user_notification(user, form_data):
        """
        发送确认邮件给用户
        
        Args:
            user: 用户对象
            form_data: 表单数据
        """
        try:
            subject = f'{settings.SITE_NAME} - 您的加入申请已收到'
            
            message = f'''尊敬的 {user.username}，

感谢您对 {settings.SITE_NAME} 的关注！

我们已收到您的加入申请，以下是您提交的信息：
- 公司：{form_data.get('company', '未提供')}
- 角色：{form_data.get('role', '未提供')}
- 兴趣领域：{form_data.get('interest', '未提供')}
- 留言：{form_data.get('message', '无')}

我们的团队将尽快审核您的申请，并在1-2个工作日内与您联系。

如有任何问题，请随时联系我们。

祝好！
{settings.SITE_NAME} 团队'''
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True  # 邮件发送失败不影响主流程
            )
            
            logger.info(f"已向用户 {user.email} 发送确认邮件")
            
        except Exception as e:
            logger.error(f"发送用户通知邮件失败: {e}")
    
    @staticmethod
    def _send_admin_notification(user, form_data):
        """
        发送通知邮件给管理员
        
        Args:
            user: 用户对象
            form_data: 表单数据
        """
        try:
            # 获取管理员邮箱列表
            admin_emails = JoinWishService._get_admin_emails()
            if not admin_emails:
                return
            
            subject = f'{settings.SITE_NAME} - 新的加入申请'
            
            message = f'''新用户加入申请

用户信息：
- 用户名：{user.username}
- 邮箱：{user.email}
- 注册时间：{user.date_joined.strftime('%Y-%m-%d %H:%M')}

申请信息：
- 公司：{form_data.get('company', '未提供')}
- 角色：{form_data.get('role', '未提供')}
- 兴趣领域：{form_data.get('interest', '未提供')}
- 留言：{form_data.get('message', '无')}

请登录管理后台审核并激活用户账号。

{settings.SITE_NAME} 系统'''
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True
            )
            
            logger.info(f"已向管理员发送新申请通知")
            
        except Exception as e:
            logger.error(f"发送管理员通知邮件失败: {e}")
    
    @staticmethod
    def _get_admin_emails():
        """
        获取管理员邮箱列表
        
        Returns:
            list: 管理员邮箱列表
        """
        # 获取所有管理员和超级管理员
        admin_users = User.objects.filter(
            role__in=[User.Role.ADMIN, User.Role.SUPER_ADMIN],
            status=User.Status.ACTIVE
        ).values_list('email', flat=True)
        
        # 也可以从环境变量配置额外的管理员邮箱
        import os
        admin_email_env = os.getenv('ADMIN_NOTIFICATION_EMAILS', '')
        if admin_email_env:
            env_emails = [email.strip() for email in admin_email_env.split(',')]
            return list(set(list(admin_users) + env_emails))
        
        return list(admin_users)
    
    @staticmethod
    def get_pending_applications(page=1, page_size=20):
        """
        获取待审核的加入申请
        
        Args:
            page: 页码
            page_size: 每页数量
            
        Returns:
            dict: 申请列表和分页信息
        """
        try:
            # 查询所有未激活且有 join_wish 数据的用户
            profiles_with_wish = UserProfile.objects.filter(
                user__status=User.Status.INACTIVE,
                context_data__join_wish__isnull=False
            ).select_related('user')
            
            # 分页
            total_count = profiles_with_wish.count()
            start = (page - 1) * page_size
            end = start + page_size
            profiles = profiles_with_wish[start:end]
            
            # 构建申请列表
            applications = []
            for profile in profiles:
                join_wish = profile.context_data.get('join_wish', {})
                applications.append({
                    'user_id': profile.user.id,
                    'username': profile.user.username,
                    'email': profile.user.email,
                    'date_joined': profile.user.date_joined.isoformat(),
                    'company': join_wish.get('company', ''),
                    'role': join_wish.get('role', ''),
                    'interest': join_wish.get('interest', ''),
                    'message': join_wish.get('message', ''),
                    'submitted_at': join_wish.get('submitted_at', ''),
                    'status': join_wish.get('status', 'pending')
                })
            
            return {
                'applications': applications,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            }
            
        except Exception as e:
            logger.error(f"获取待审核申请失败: {e}", exc_info=True)
            return {
                'applications': [],
                'pagination': {
                    'page': 1,
                    'page_size': page_size,
                    'total_count': 0,
                    'total_pages': 0
                }
            }
    
    @staticmethod
    def approve_application(user_id, admin_user=None):
        """
        批准加入申请（激活用户）
        
        Args:
            user_id: 用户ID
            admin_user: 执行操作的管理员
            
        Returns:
            dict: 操作结果
        """
        try:
            user = User.objects.get(id=user_id)
            profile = UserProfile.objects.get(user=user)
            
            # 激活用户
            user.status = User.Status.ACTIVE
            user.save()
            
            # 更新申请状态
            if profile.context_data and 'join_wish' in profile.context_data:
                profile.context_data['join_wish']['status'] = 'approved'
                profile.context_data['join_wish']['approved_at'] = datetime.now().isoformat()
                if admin_user:
                    profile.context_data['join_wish']['approved_by'] = admin_user.username
                profile.save()
            
            # 发送激活通知邮件
            JoinWishService._send_activation_notification(user)
            
            logger.info(f"用户 {user.username} 的加入申请已批准")
            
            return {
                'success': True,
                'message': f'用户 {user.username} 已激活'
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': '用户不存在'
            }
        except Exception as e:
            logger.error(f"批准申请失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': '操作失败，请稍后重试'
            }
    
    @staticmethod
    def _send_activation_notification(user):
        """
        发送账号激活通知
        
        Args:
            user: 用户对象
        """
        try:
            subject = f'{settings.SITE_NAME} - 您的账号已激活'
            
            message = f'''尊敬的 {user.username}，

好消息！您的 {settings.SITE_NAME} 账号已成功激活。

您现在可以使用完整的平台功能了。请访问以下链接登录：
{settings.SERVER_HOST}

如有任何问题，请随时联系我们。

祝您使用愉快！
{settings.SITE_NAME} 团队'''
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
            
            logger.info(f"已向用户 {user.email} 发送激活通知")
            
        except Exception as e:
            logger.error(f"发送激活通知失败: {e}")