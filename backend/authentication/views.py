import logging
import os
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from django.utils import timezone
from urllib.parse import urlencode
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponseRedirect # 新增导入
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenVerifyView

from .models import OAuthState, UserAccount
from .serializers import UserSerializer, FeishuLoginSerializer, TokenSerializer
from .auth_services import MultiAuthService

logger = logging.getLogger(__name__)
User = get_user_model()

class FeishuLoginView(APIView):
    """飞书登录视图"""
    permission_classes = [AllowAny]  # 允许匿名访问
    
    def generate_code_verifier(self):
        """生成PKCE验证码"""
        code_verifier = secrets.token_urlsafe(32)
        return code_verifier

    def generate_code_challenge(self, code_verifier):
        """生成PKCE挑战码"""
        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
        code_challenge = code_challenge.replace('=', '')  # 移除填充
        return code_challenge

    def get(self, request):
        """生成飞书授权URL"""
        # 生成并存储state
        state = secrets.token_urlsafe(16)
        redirect_url = request.query_params.get('redirect_url', '')
        redirect_uri = request.query_params.get('redirect_uri', settings.FEISHU['OAUTH']['REDIRECT_URI'])
        
        # 存储state和redirect_url
        # 生成PKCE参数
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)

        OAuthState.objects.create(
            state=state,
            redirect_url=redirect_url or redirect_uri,
            code_verifier=code_verifier  # 将 code_verifier 存储到数据库
        )

        # 构建授权参数
        scopes = ' '.join(settings.FEISHU['OAUTH']['SCOPES'])
        logger.info(f"飞书授权请求的 scopes: {scopes}")
        params = {
            'client_id': settings.FEISHU['APP_ID'],
            'response_type': 'code',
            'state': state,
            'redirect_uri': redirect_uri,
            'scope': scopes,
        }
        
        # 如果启用了PKCE，添加相关参数
        if settings.FEISHU['OAUTH'].get('PKCE_ENABLED', True):
            params.update({
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256'
            })

        auth_url = f"{settings.FEISHU['OAUTH']['AUTHORIZATION_URL']}?{urlencode(params)}"
        # return Response({'auth_url': auth_url, 'state': state}) # 原来的返回JSON
        return HttpResponseRedirect(auth_url) # 修改为重定向

    @staticmethod
    def _get_feishu_token(code, code_verifier=None, redirect_uri=None):
        """获取飞书访问令牌 (变为静态方法)"""
        data = {
            'grant_type': 'authorization_code',
            'client_id': settings.FEISHU['APP_ID'],
            'client_secret': settings.FEISHU['APP_SECRET'],
            'code': code,
            'redirect_uri': redirect_uri or settings.FEISHU['OAUTH']['REDIRECT_URI'],
            'scope': ' '.join(settings.FEISHU['OAUTH']['SCOPES']),  # 明确包含 scope
        }
        logger.info(f"飞书 token 请求参数: grant_type={data['grant_type']}, client_id={data['client_id']}, scope={data['scope']}")
        
        # 如果启用了PKCE且存在code_verifier，添加到请求中
        if settings.FEISHU['OAUTH'].get('PKCE_ENABLED', True) and code_verifier:
            data['code_verifier'] = code_verifier

        try:
            response = requests.post(settings.FEISHU['OAUTH']['ACCESS_TOKEN_URL'], data=data)
            if not response.ok:
                # 提前记录失败的响应体，因为它可能包含有用的错误信息
                logger.error(f"获取飞书token的请求失败. Status: {response.status_code}, Body: {response.text}")
            response.raise_for_status()
            token_data = response.json()
            # 添加调试日志
            logger.info(f"飞书返回的token数据: {token_data}")
            logger.info(f"是否包含refresh_token: {'refresh_token' in token_data}")
            return token_data
        except requests.exceptions.RequestException as e:
            # logger.exception 会自动附加异常信息和堆栈跟踪
            logger.exception("获取飞书token失败")
            return None

    @staticmethod
    def _get_feishu_user_info(access_token):
        """获取飞书用户信息 (变为静态方法)"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(
                settings.FEISHU['OAUTH']['USER_INFO_URL'],
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.exception("获取飞书用户信息失败")
            return None

    @staticmethod
    def _get_or_create_user(user_info, token_data):
        """创建或更新用户信息 - 使用 UserAccount 统一管理"""
        user_data = user_info['data']
        
        # 准备用户信息数据
        profile_data = {
            'email': user_data.get('email', f"{user_data['open_id']}@feishu.users"),
            'name': user_data.get('name', f"feishu_{user_data['open_id']}"),
            'avatar_url': user_data.get('avatar_url', ''),
            'nickname': user_data.get('name'),
            'open_id': user_data['open_id'],
            'union_id': user_data.get('union_id'),
            'mobile': user_data.get('mobile'),
            'department_ids': user_data.get('department_ids'),
        }
        
        # 准备令牌信息
        tokens = {
            'access_token': token_data['access_token'],
            'refresh_token': token_data.get('refresh_token', ''),
            'expires_at': timezone.now() + timedelta(seconds=token_data['expires_in']),
            'scope': token_data.get('scope'),
        }
        
        # 使用 MultiAuthService 统一处理
        user, account, created = MultiAuthService.create_or_login_oauth_user(
            provider=UserAccount.Provider.FEISHU,
            provider_account_id=user_data['open_id'],
            profile_data=profile_data,
            tokens=tokens
        )
        
        # 确保用户处于激活状态
        if not user.is_active:
            user.is_active = True
            user.save()
            logger.info(f"激活飞书用户 {user.username}")
        
        # 记录日志
        if created:
            logger.info(f"创建新飞书用户 {user.username}，refresh_token: {'有' if tokens.get('refresh_token') else '无'}")
        else:
            logger.info(f"更新飞书用户 {user.username} 的认证信息，refresh_token: {'有' if tokens.get('refresh_token') else '无'}")
        
        
        return user

    @staticmethod
    def process_feishu_authentication(code, state):
        """
        处理飞书认证的核心逻辑。
        接收 code 和 state，返回包含 token 和 user 数据的字典，或包含 error 的字典。
        """
        try:
            oauth_state = OAuthState.objects.get(state=state)
            # 从数据库中获取 code_verifier，而不是从缓存
            code_verifier = oauth_state.code_verifier

            token_data = FeishuLoginView._get_feishu_token(code, code_verifier, oauth_state.redirect_url)
            if not token_data or 'access_token' not in token_data: # 确保token_data有效且包含access_token
                logger.error(f"获取飞书访问令牌失败. Code: {code}, State: {state}, Token Data: {token_data}")
                return {'error': '获取飞书访问令牌失败', 'status': status.HTTP_400_BAD_REQUEST}

            user_info = FeishuLoginView._get_feishu_user_info(token_data['access_token'])
            if not user_info or 'data' not in user_info: # 确保user_info有效且包含data
                logger.error(f"获取用户信息失败. Access Token: {token_data.get('access_token')}, User Info: {user_info}")
                return {'error': '获取用户信息失败', 'status': status.HTTP_400_BAD_REQUEST}

            user = FeishuLoginView._get_or_create_user(user_info, token_data)

            refresh = RefreshToken.for_user(user)
            tokens = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'token_type': 'Bearer'
            }

            oauth_state.delete()
            # 不再需要从缓存中删除

            return {
                'success': True,
                'tokens': TokenSerializer(tokens).data,
                'user': UserSerializer(user).data,
                'status': status.HTTP_200_OK
            }
        except OAuthState.DoesNotExist:
            logger.warning(f"无效的state: {state}")
            return {'error': '无效的state', 'status': status.HTTP_400_BAD_REQUEST}
        except Exception as e:
            logger.exception(f"飞书登录处理失败. Code: {code}, State: {state}")
            return {'error': str(e), 'status': status.HTTP_500_INTERNAL_SERVER_ERROR}

    def post(self, request):
        """处理飞书回调，获取用户信息并完成登录"""
        serializer = FeishuLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code']
        state = serializer.validated_data['state']
        
        result = FeishuLoginView.process_feishu_authentication(code, state)
        
        if result.get('success'):
            return Response({
                'tokens': result['tokens'],
                'user': result['user']
            }, status=result['status'])
        else:
            return Response({'error': result['error']}, status=result['status'])

class GoogleLoginView(APIView):
    """Google登录视图"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """生成Google授权URL"""
        import os
        
        state = secrets.token_urlsafe(16)
        redirect_url = request.query_params.get('redirect_url', '')
        redirect_uri = request.query_params.get('redirect_uri', 
                                               os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/auth/google/callback'))
        
        # 存储state和redirect_url到数据库
        import json
        oauth_state = OAuthState.objects.create(
            provider='google',
            state=state,
            redirect_url=redirect_url,
            extra_data=json.dumps({'redirect_uri': redirect_uri})
        )
        
        # 构建Google OAuth URL
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'offline',
            'prompt': 'select_account'
        }
        
        auth_url_with_params = f"{auth_url}?{urlencode(params)}"
        
        return Response({
            'auth_url': auth_url_with_params,
            'state': state
        })
    
    def post(self, request):
        """处理Google OAuth回调"""
        from .auth_services import GoogleAuthService
        from .serializers import TokenSerializer, UserSerializer
        
        code = request.data.get('code')
        state = request.data.get('state')
        
        if not code or not state:
            return Response(
                {'error': 'Missing code or state'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 验证state
            oauth_state = OAuthState.objects.get(state=state, provider='google')
            
            # 解析 extra_data（可能是 JSON 字符串）
            import json
            try:
                extra_data = json.loads(oauth_state.extra_data) if oauth_state.extra_data else {}
            except (json.JSONDecodeError, TypeError):
                extra_data = {}
            
            redirect_uri = extra_data.get('redirect_uri', 
                                         os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/auth/google/callback'))
            
            # 处理Google认证
            user, account, created = GoogleAuthService.handle_callback(code, redirect_uri)
            
            # 生成JWT令牌
            refresh = RefreshToken.for_user(user)
            tokens = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'token_type': 'Bearer'
            }
            
            # 清理state
            oauth_state.delete()
            
            return Response({
                'tokens': TokenSerializer(tokens).data,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
            
        except OAuthState.DoesNotExist:
            return Response(
                {'error': 'Invalid state'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Google login failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CustomTokenVerifyView(TokenVerifyView):
    """自定义Token验证视图，明确指定验证AccessToken，同时确保用户有UserProfile"""
    token_class = AccessToken
    
    def post(self, request, *args, **kwargs):
        """重写post方法，在验证token成功后检查并创建UserProfile"""
        # 先调用父类的验证逻辑
        response = super().post(request, *args, **kwargs)
        
        # 如果token验证成功（返回200）
        if response.status_code == 200:
            try:
                # 从token中获取用户
                token = request.data.get('token')
                if token:
                    from django.core.cache import cache
                    from .models_extension import UserProfile
                    from .models import UserAccount
                    from .user_service import UserService
                    
                    # 解析token获取用户ID
                    access_token_obj = AccessToken(token)
                    user_id = access_token_obj.payload.get('user_id')
                    
                    if user_id:
                        # 使用缓存避免重复查询
                        cache_key = f'user_profile_checked:{user_id}'
                        
                        # 检查缓存（缓存10分钟）
                        if not cache.get(cache_key):
                            # 获取用户对象
                            user = User.objects.get(id=user_id)
                            
                            # 使用get_or_create避免并发问题
                            profile, created = UserProfile.objects.get_or_create(
                                user=user,
                                defaults={
                                    'subscription_type': UserProfile.SubscriptionType.FREE
                                }
                            )
                            
                            if created:
                                # 判断用户类型并更新订阅类型
                                # 检查 UserAccount 表
                                is_feishu_user = UserAccount.objects.filter(user=user, provider='feishu').exists()
                                
                                if is_feishu_user:
                                    profile.subscription_type = UserProfile.SubscriptionType.ENTERPRISE
                                    profile.save()
                                    
                                    # 应用enterprise_user配额模板
                                    try:
                                        UserService.apply_quota_template(user.id, 'enterprise_user')
                                        logger.info(f"Token验证时为飞书用户 {user.username} 创建UserProfile并应用企业用户配额")
                                    except Exception as e:
                                        logger.error(f"为用户 {user.username} 应用配额模板失败: {e}")
                                else:
                                    logger.info(f"Token验证时为用户 {user.username} 创建了UserProfile (订阅类型: free_user)")
                            
                            # 设置缓存，避免10分钟内重复检查
                            cache.set(cache_key, True, 600)
                            
            except Exception as e:
                # 记录错误但不影响token验证结果
                logger.error(f"Token验证时检查UserProfile失败: {e}", exc_info=True)
        
        return response


class EmailLoginView(APIView):
    """邮箱登录/注册视图"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """处理邮箱登录/注册"""
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')
        
        # 验证输入
        if not email or not password:
            return Response({
                'status': 'error',
                'message': '请输入邮箱和密码'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证邮箱格式
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            return Response({
                'status': 'error',
                'message': '邮箱格式不正确'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 查找用户
            user = User.objects.filter(email=email).first()
            
            if user:
                # 用户存在，验证密码
                if user.check_password(password):
                    # 检查用户是否有邮箱账号
                    email_account = UserAccount.objects.filter(
                        user=user,
                        provider=UserAccount.Provider.EMAIL
                    ).first()
                    
                    if not email_account:
                        # 创建邮箱账号记录
                        email_account = UserAccount.objects.create(
                            user=user,
                            type=UserAccount.AccountType.EMAIL,
                            provider=UserAccount.Provider.EMAIL,
                            provider_account_id=email,
                            is_verified=True
                        )
                    
                    # 更新最后使用时间
                    email_account.last_used_at = timezone.now()
                    email_account.save()
                    
                    # 生成JWT令牌
                    refresh = RefreshToken.for_user(user)
                    access_token = refresh.access_token
                    
                    # 返回成功响应
                    return Response({
                        'status': 'success',
                        'data': {
                            'access': str(access_token),
                            'refresh': str(refresh),
                            'user': UserSerializer(user).data,
                            'is_new_user': False
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'status': 'error',
                        'message': '密码错误'
                    }, status=status.HTTP_401_UNAUTHORIZED)
            
            else:
                # 新用户，创建账号并发送验证码
                # 生成6位验证码
                import random
                code = ''.join([str(random.randint(0, 9)) for _ in range(settings.EMAIL_VERIFICATION_CODE_LENGTH)])
                
                # 存储验证信息到缓存（10分钟有效）
                cache_key = f'email_verification:{email}'
                cache.set(cache_key, {
                    'code': code,
                    'password': password,
                    'attempts': 0
                }, settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES * 60)
                
                # 发送验证码邮件
                from django.core.mail import send_mail
                
                # 调试：打印邮件配置
                logger.info(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
                logger.info(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
                
                try:
                    # 确保from_email与EMAIL_HOST_USER完全一致
                    from_email = settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL
                    
                    send_mail(
                        subject=f'{settings.SITE_NAME or "X平台"} - 邮箱验证码',
                        message=f'''您好！
                        
您正在注册{settings.SITE_NAME or "X平台"}账号。

您的验证码是：{code}

验证码有效期为{settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES}分钟，请尽快完成验证。

如果这不是您的操作，请忽略此邮件。

祝好！
{settings.SITE_NAME or "X平台"}团队''',
                        from_email=from_email,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    
                    logger.info(f"发送验证码到邮箱 {email}")
                    
                    return Response({
                        'status': 'success',
                        'data': {
                            'require_verification': True,
                            'email': email,
                            'message': f'验证码已发送到 {email}'
                        }
                    }, status=status.HTTP_200_OK)
                    
                except Exception as e:
                    logger.error(f"发送验证码邮件失败: {e}")
                    return Response({
                        'status': 'error',
                        'message': '发送验证码失败，请稍后重试'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
        except Exception as e:
            logger.error(f"邮箱登录处理失败: {e}", exc_info=True)
            return Response({
                'status': 'error',
                'message': '系统错误，请稍后重试'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailVerifyView(APIView):
    """邮箱验证码验证视图"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """验证邮箱验证码"""
        email = request.data.get('email', '').strip().lower()
        code = request.data.get('code', '').strip()
        
        if not email or not code:
            return Response({
                'status': 'error',
                'message': '请输入邮箱和验证码'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 从缓存获取验证信息
        cache_key = f'email_verification:{email}'
        verification_data = cache.get(cache_key)
        
        if not verification_data:
            return Response({
                'status': 'error',
                'message': '验证码已过期，请重新获取'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查尝试次数
        if verification_data['attempts'] >= 5:
            cache.delete(cache_key)
            return Response({
                'status': 'error',
                'message': '验证码错误次数过多，请重新获取'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证码匹配
        if code != verification_data['code']:
            verification_data['attempts'] += 1
            cache.set(cache_key, verification_data, settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES * 60)
            return Response({
                'status': 'error',
                'message': f'验证码错误，还有{5 - verification_data["attempts"]}次机会'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 验证成功，创建用户
            username = email.split('@')[0]
            # 确保用户名唯一
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            
            # 创建用户
            user = User.objects.create_user(
                username=username,
                email=email,
                password=verification_data['password']
            )
            
            # 检查是否需要用户激活
            import os
            require_activation = os.getenv('REQUIRE_USER_ACTIVATION', 'False').lower() == 'true'
            
            if require_activation:
                # 邮箱注册用户默认为未激活状态
                user.status = User.Status.INACTIVE
                user.is_active = True  # Django的is_active字段仍保持True，用status字段控制激活状态
                logger.info(f"邮箱注册用户 {user.email} 创建成功，状态设为未激活(INACTIVE)")
            else:
                user.status = User.Status.ACTIVE
                user.is_active = True
                logger.info(f"邮箱注册用户 {user.email} 创建成功，状态设为激活(ACTIVE)")
            
            user.save()
            
            # 创建邮箱账号记录
            UserAccount.objects.create(
                user=user,
                type=UserAccount.AccountType.EMAIL,
                provider=UserAccount.Provider.EMAIL,
                provider_account_id=email,
                is_verified=True,
                is_primary=True,
                last_used_at=timezone.now()
            )
            
            # 创建UserProfile
            from .models_extension import UserProfile
            from .user_service import UserService
            
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={'subscription_type': UserProfile.SubscriptionType.FREE}
            )
            
            if created:
                # 应用免费用户配额
                try:
                    UserService.apply_quota_template(user.id, 'free_user')
                    logger.info(f"为邮箱用户 {user.username} 创建UserProfile并应用免费用户配额")
                except Exception as e:
                    logger.error(f"为用户 {user.username} 应用配额模板失败: {e}")
            
            # 删除缓存
            cache.delete(cache_key)
            
            # 生成JWT令牌
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            return Response({
                'status': 'success',
                'data': {
                    'access': str(access_token),
                    'refresh': str(refresh),
                    'user': UserSerializer(user).data,
                    'is_new_user': True
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"创建邮箱用户失败: {e}", exc_info=True)
            return Response({
                'status': 'error',
                'message': '创建账号失败，请稍后重试'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailResendCodeView(APIView):
    """重发邮箱验证码视图"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """重发验证码"""
        email = request.data.get('email', '').strip().lower()
        
        if not email:
            return Response({
                'status': 'error',
                'message': '请输入邮箱'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查是否存在待验证信息
        cache_key = f'email_verification:{email}'
        verification_data = cache.get(cache_key)
        
        if not verification_data:
            return Response({
                'status': 'error',
                'message': '请先进行登录操作'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 生成新验证码
        import random
        code = ''.join([str(random.randint(0, 9)) for _ in range(settings.EMAIL_VERIFICATION_CODE_LENGTH)])
        
        # 更新缓存
        verification_data['code'] = code
        verification_data['attempts'] = 0
        cache.set(cache_key, verification_data, settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES * 60)
        
        # 发送邮件
        from django.core.mail import send_mail
        try:
            # 确保from_email与EMAIL_HOST_USER完全一致
            from_email = settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL
            
            send_mail(
                subject=f'{settings.SITE_NAME or "X平台"} - 新的验证码',
                message=f'''您好！

您的新验证码是：{code}

验证码有效期为{settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES}分钟，请尽快完成验证。

如果这不是您的操作，请忽略此邮件。

祝好！
{settings.SITE_NAME or "X平台"}团队''',
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
            
            logger.info(f"重新发送验证码到邮箱 {email}")
            
            return Response({
                'status': 'success',
                'message': f'新验证码已发送到 {email}'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"重发验证码邮件失败: {e}")
            return Response({
                'status': 'error',
                'message': '发送验证码失败，请稍后重试'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserActivationView(APIView):
    """管理员激活/停用用户视图"""
    permission_classes = [AllowAny]  # TODO: 后续应该改为只允许管理员访问
    
    def post(self, request, user_id):
        """激活或停用用户"""
        # 验证当前用户是否为管理员
        if not request.user.is_authenticated:
            return Response({
                'status': 'error',
                'message': '请先登录'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # 检查是否为管理员
        if request.user.role not in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            return Response({
                'status': 'error', 
                'message': '您没有权限执行此操作'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 获取操作类型
        action = request.data.get('action', 'activate')  # activate 或 deactivate
        
        try:
            target_user = User.objects.get(id=user_id)
            
            if action == 'activate':
                if target_user.status == User.Status.ACTIVE:
                    return Response({
                        'status': 'info',
                        'message': '用户已经是激活状态'
                    }, status=status.HTTP_200_OK)
                
                target_user.status = User.Status.ACTIVE
                target_user.save()
                
                logger.info(f"管理员 {request.user.username} 激活了用户 {target_user.username}")
                
                return Response({
                    'status': 'success',
                    'message': f'用户 {target_user.username} 已激活',
                    'data': {
                        'user_id': target_user.id,
                        'username': target_user.username,
                        'email': target_user.email,
                        'status': 'active'
                    }
                }, status=status.HTTP_200_OK)
                
            elif action == 'deactivate':
                if target_user.status == User.Status.INACTIVE:
                    return Response({
                        'status': 'info',
                        'message': '用户已经是未激活状态'
                    }, status=status.HTTP_200_OK)
                
                target_user.status = User.Status.INACTIVE
                target_user.save()
                
                logger.info(f"管理员 {request.user.username} 停用了用户 {target_user.username}")
                
                return Response({
                    'status': 'success',
                    'message': f'用户 {target_user.username} 已停用',
                    'data': {
                        'user_id': target_user.id,
                        'username': target_user.username,
                        'email': target_user.email,
                        'status': 'inactive'
                    }
                }, status=status.HTTP_200_OK)
                
            else:
                return Response({
                    'status': 'error',
                    'message': '无效的操作类型，请使用 activate 或 deactivate'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({
                'status': 'error',
                'message': '用户不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"激活/停用用户失败: {e}", exc_info=True)
            return Response({
                'status': 'error',
                'message': '操作失败，请稍后重试'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserListView(APIView):
    """管理员查看用户列表视图"""
    permission_classes = [AllowAny]  # TODO: 后续应该改为只允许管理员访问
    
    def get(self, request):
        """获取用户列表，可按状态筛选"""
        # 验证当前用户是否为管理员
        if not request.user.is_authenticated:
            return Response({
                'status': 'error',
                'message': '请先登录'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # 检查是否为管理员
        if request.user.role not in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            return Response({
                'status': 'error',
                'message': '您没有权限查看用户列表'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 获取筛选参数
        status_filter = request.query_params.get('status', 'all')  # all, active, inactive, banned
        provider_filter = request.query_params.get('provider')  # email, google, feishu
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # 构建查询
        queryset = User.objects.all()
        
        # 按状态筛选
        if status_filter == 'active':
            queryset = queryset.filter(status=User.Status.ACTIVE)
        elif status_filter == 'inactive':
            queryset = queryset.filter(status=User.Status.INACTIVE)
        elif status_filter == 'banned':
            queryset = queryset.filter(status=User.Status.BANNED)
        
        # 按登录方式筛选
        if provider_filter:
            # 通过 UserAccount 表筛选
            user_ids = UserAccount.objects.filter(provider=provider_filter).values_list('user_id', flat=True)
            queryset = queryset.filter(id__in=user_ids)
        
        # 排序（最新注册的在前）
        queryset = queryset.order_by('-date_joined')
        
        # 分页
        total_count = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        users = queryset[start:end]
        
        # 构建响应数据
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
                'providers': providers,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'avatar_url': user.avatar_url
            })
        
        return Response({
            'status': 'success',
            'data': {
                'users': user_list,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            }
        }, status=status.HTTP_200_OK)