"""
frago Cloud Market 视图

包含设备认证、Recipe 市场、会话同步的 API 视图
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .services.device_auth_service import DeviceAuthService
from .services.recipe_service import (
    RecipeService,
    RecipeServiceError,
    RecipeNotFoundError,
    VersionNotFoundError,
    PremiumRequiredError,
)
from .serializers import (
    DeviceCodeRequestSerializer,
    DeviceCodeResponseSerializer,
    TokenPollRequestSerializer,
    TokenResponseSerializer,
    DeviceAuthErrorSerializer,
    DeviceAuthorizeRequestSerializer,
    UserInfoSerializer,
    TokenRefreshRequestSerializer,
    RecipeSummarySerializer,
    RecipeDetailSerializer,
    RecipeDownloadResponseSerializer,
    RecipePublishRequestSerializer,
    RatingRequestSerializer,
    RatingResponseSerializer,
)

logger = logging.getLogger('django')


# ==================== 设备认证视图 ====================

class DeviceCodeView(APIView):
    """
    设备认证码视图

    POST /auth/device/code
    获取 device_code 和 user_code，供 CLI 进行 OAuth 设备授权流程
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """获取设备认证码"""
        serializer = DeviceCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'message': '请求参数无效',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        result = DeviceAuthService.create_device_code(
            client_id=serializer.validated_data['client_id'],
            scope=serializer.validated_data.get('scope', 'market sync')
        )

        response_serializer = DeviceCodeResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class DeviceTokenView(APIView):
    """
    设备 Token 轮询视图

    POST /auth/device/token
    CLI 使用 device_code 轮询获取 access_token
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """轮询获取 Token"""
        serializer = TokenPollRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'invalid_request',
                'error_description': '请求参数无效'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = DeviceAuthService.poll_for_token(
            device_code=serializer.validated_data['device_code'],
            client_id=serializer.validated_data['client_id']
        )

        # 判断是否成功
        if 'error' in result:
            # 根据错误类型返回不同状态码
            error_status_map = {
                'authorization_pending': status.HTTP_400_BAD_REQUEST,
                'slow_down': status.HTTP_400_BAD_REQUEST,
                'expired_token': status.HTTP_400_BAD_REQUEST,
                'access_denied': status.HTTP_400_BAD_REQUEST,
                'invalid_grant': status.HTTP_400_BAD_REQUEST,
                'invalid_client': status.HTTP_401_UNAUTHORIZED,
                'server_error': status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            http_status = error_status_map.get(result['error'], status.HTTP_400_BAD_REQUEST)
            return Response(result, status=http_status)

        # 成功返回 token
        return Response(result, status=status.HTTP_200_OK)


class DeviceAuthorizeView(APIView):
    """
    用户授权设备码视图

    POST /auth/device/authorize
    用户在浏览器中输入 user_code 并授权
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """用户授权设备码"""
        serializer = DeviceAuthorizeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'message': '请求参数无效',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        success, message = DeviceAuthService.authorize_device(
            user_code=serializer.validated_data['user_code'],
            user=request.user
        )

        if success:
            return Response({
                'status': 'success',
                'message': message
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """用户拒绝授权"""
        serializer = DeviceAuthorizeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'message': '请求参数无效',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        success, message = DeviceAuthService.deny_device(
            user_code=serializer.validated_data['user_code']
        )

        if success:
            return Response({
                'status': 'success',
                'message': message
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)


class UserInfoView(APIView):
    """
    当前用户信息视图

    GET /auth/me
    获取当前登录用户的信息
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取当前用户信息"""
        serializer = UserInfoSerializer(request.user)
        return Response({
            'status': 'success',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    """
    Token 刷新视图

    POST /auth/refresh
    使用 refresh_token 获取新的 access_token
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """刷新 Token"""
        serializer = TokenRefreshRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'invalid_request',
                'error_description': '请求参数无效'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = DeviceAuthService.refresh_access_token(
            refresh_token=serializer.validated_data['refresh_token']
        )

        if result:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'invalid_grant',
                'error_description': '刷新令牌无效或已过期'
            }, status=status.HTTP_400_BAD_REQUEST)


# ==================== Recipe 市场视图（Phase 4 实现） ====================

class RecipeListView(APIView):
    """
    Recipe 列表视图

    GET /recipes/
    搜索公开 Recipe，支持关键词、作者、评分筛选
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """搜索/列表 Recipe"""
        # 解析查询参数
        query = request.query_params.get('q')
        author = request.query_params.get('author')
        runtime = request.query_params.get('runtime')
        min_rating = request.query_params.get('min_rating')
        is_premium = request.query_params.get('is_premium')
        ordering = request.query_params.get('ordering', '-download_count')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)

        # 转换类型
        try:
            page = int(page)
            page_size = int(page_size)
        except (ValueError, TypeError):
            page = 1
            page_size = 20

        if min_rating:
            try:
                min_rating = float(min_rating)
            except (ValueError, TypeError):
                min_rating = None

        if is_premium is not None:
            is_premium = is_premium.lower() in ('true', '1', 'yes')

        # 搜索
        recipes, total_count = RecipeService.search_recipes(
            query=query,
            author=author,
            runtime=runtime,
            min_rating=min_rating,
            is_premium=is_premium,
            ordering=ordering,
            page=page,
            page_size=page_size,
            user=request.user if request.user.is_authenticated else None
        )

        # 序列化
        serializer = RecipeSummarySerializer(recipes, many=True)

        # 构建分页响应
        total_pages = (total_count + page_size - 1) // page_size
        next_page = page + 1 if page < total_pages else None
        prev_page = page - 1 if page > 1 else None

        base_url = request.build_absolute_uri(request.path)

        return Response({
            'status': 'success',
            'data': {
                'count': total_count,
                'next': f'{base_url}?page={next_page}&page_size={page_size}' if next_page else None,
                'previous': f'{base_url}?page={prev_page}&page_size={page_size}' if prev_page else None,
                'results': serializer.data
            }
        }, status=status.HTTP_200_OK)


class RecipeDetailView(APIView):
    """
    Recipe 详情视图

    GET /recipes/{id}/
    获取 Recipe 详情
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        """获取 Recipe 详情"""
        try:
            recipe = RecipeService.get_recipe_detail(
                recipe_id=pk,
                user=request.user if request.user.is_authenticated else None
            )
        except RecipeNotFoundError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = RecipeDetailSerializer(recipe, context={'request': request})
        return Response({
            'status': 'success',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class RecipeDownloadView(APIView):
    """
    Recipe 下载视图

    POST /recipes/{id}/download
    获取 Recipe 内容并增加下载计数
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """下载 Recipe"""
        version = request.query_params.get('version')

        try:
            result = RecipeService.download_recipe(
                recipe_id=pk,
                version=version,
                user=request.user
            )
        except RecipeNotFoundError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_404_NOT_FOUND)
        except VersionNotFoundError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_404_NOT_FOUND)
        except PremiumRequiredError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = RecipeDownloadResponseSerializer(result)
        return Response({
            'status': 'success',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


# ==================== Recipe 发布视图（Phase 5 US3 实现） ====================

class RecipePublishView(APIView):
    """
    Recipe 发布视图

    POST /recipes/
    发布新 Recipe 或新版本
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """发布 Recipe"""
        serializer = RecipePublishRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'message': '请求参数无效',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = RecipeService.publish_recipe(
                name=serializer.validated_data['name'],
                description=serializer.validated_data['description'],
                runtime=serializer.validated_data['runtime'],
                version=serializer.validated_data['version'],
                content=serializer.validated_data['content'],
                user=request.user,
                changelog=serializer.validated_data.get('changelog', ''),
                is_public=serializer.validated_data.get('is_public', True),
                is_premium=serializer.validated_data.get('is_premium', False)
            )
        except RecipeServiceError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_400_BAD_REQUEST)

        # 返回不同的状态码：新 Recipe 201，更新版本 200
        http_status = status.HTTP_201_CREATED if result['is_new_recipe'] else status.HTTP_200_OK
        message = '发布成功' if result['is_new_recipe'] else '新版本发布成功'

        return Response({
            'status': 'success',
            'message': message,
            'data': result
        }, status=http_status)


# ==================== Recipe 评分视图（Phase 6 US4 实现） ====================

class RecipeRateView(APIView):
    """
    Recipe 评分视图

    POST /recipes/{id}/rate
    对 Recipe 提交评分（创建或更新）
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """提交评分"""
        serializer = RatingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'message': '请求参数无效',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = RecipeService.rate_recipe(
                recipe_id=pk,
                user=request.user,
                rating=serializer.validated_data['rating'],
                comment=serializer.validated_data.get('comment', '')
            )
        except RecipeNotFoundError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_404_NOT_FOUND)
        except RecipeServiceError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_400_BAD_REQUEST)

        # 返回不同的状态码：新评分 201，更新评分 200
        http_status = status.HTTP_201_CREATED if result['is_new'] else status.HTTP_200_OK
        message = '评分成功' if result['is_new'] else '评分已更新'

        return Response({
            'status': 'success',
            'message': message,
            'data': result
        }, status=http_status)


# ==================== 会话同步视图（Phase 7 实现） ====================

# class SessionListView(APIView):
#     """会话列表视图 - GET /sync/sessions/"""
#     pass

# class SessionUploadView(APIView):
#     """会话上传视图 - POST /sync/sessions/"""
#     pass

# class SessionDownloadView(APIView):
#     """会话下载视图 - GET /sync/sessions/{id}/"""
#     pass

# class SessionDeleteView(APIView):
#     """会话删除视图 - DELETE /sync/sessions/{id}/"""
#     pass


# ==================== Claude Code 镜像视图（US6） ====================

from django.http import HttpResponseRedirect
from .services.claude_mirror_service import (
    ClaudeMirrorService,
    ClaudeMirrorServiceError,
    VersionNotFoundError as ClaudeVersionNotFoundError,
    BinaryNotFoundError,
    SUPPORTED_PLATFORM_ARCHS,
)
from .throttles import ClaudeCodeDownloadThrottle, record_download, get_rate_limit_info
from .serializers import (
    ClaudeCodeVersionSerializer,
    ClaudeCodeVersionDetailSerializer,
)


class ClaudeCodeVersionListView(APIView):
    """
    Claude Code 版本列表视图

    GET /claude-code/versions
    列出所有可用的 Claude Code 版本
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """获取版本列表"""
        include_deprecated = request.query_params.get('include_deprecated', 'false').lower() == 'true'

        versions = ClaudeMirrorService.list_available_versions(include_deprecated)

        # 序列化
        data = []
        for v in versions:
            data.append({
                'version': v.version,
                'released_at': v.released_at.isoformat(),
                'changelog': v.changelog,
                'deprecated': v.deprecated,
                'binaries_count': v.binaries.count(),
            })

        return Response({
            'status': 'success',
            'data': {
                'versions': data,
                'supported_platforms': SUPPORTED_PLATFORM_ARCHS,
            }
        }, status=status.HTTP_200_OK)


class ClaudeCodeLatestView(APIView):
    """
    Claude Code 最新版本视图

    GET /claude-code/latest
    获取最新版本信息，可指定平台架构
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """获取最新版本"""
        platform_arch = request.query_params.get('platform')

        latest_version = ClaudeMirrorService.get_latest_version()
        if not latest_version:
            return Response({
                'status': 'error',
                'message': '暂无可用版本',
                'code': 'no_version_available'
            }, status=status.HTTP_404_NOT_FOUND)

        # 获取版本信息
        result = ClaudeMirrorService.get_version_info(latest_version, platform_arch)

        # 如果指定了平台，添加下载 URL
        if platform_arch:
            try:
                binary = ClaudeMirrorService.get_binary(platform_arch)
                result['download_url'] = request.build_absolute_uri(
                    f'/api/market/claude-code/download/{platform_arch}'
                )
            except BinaryNotFoundError:
                pass

        return Response({
            'status': 'success',
            'data': result
        }, status=status.HTTP_200_OK)


class ClaudeCodeDownloadView(APIView):
    """
    Claude Code 下载视图

    GET /claude-code/download/{platform_arch}
    下载指定平台的 Claude Code 二进制（302 重定向到 R2 签名 URL）

    IP 限流：每 IP 每小时 3 次
    """
    permission_classes = [AllowAny]
    throttle_classes = [ClaudeCodeDownloadThrottle]

    def get(self, request, platform_arch):
        """下载二进制文件"""
        version = request.query_params.get('version')

        # 验证平台架构
        if platform_arch not in SUPPORTED_PLATFORM_ARCHS:
            return Response({
                'status': 'error',
                'message': f'不支持的平台架构: {platform_arch}',
                'code': 'invalid_platform',
                'supported_platforms': SUPPORTED_PLATFORM_ARCHS,
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            binary = ClaudeMirrorService.get_binary(platform_arch, version)
        except ClaudeVersionNotFoundError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_404_NOT_FOUND)
        except BinaryNotFoundError as e:
            return Response({
                'status': 'error',
                'message': e.message,
                'code': e.code
            }, status=status.HTTP_404_NOT_FOUND)

        # 获取客户端 IP
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            ip_address = xff.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')

        # 记录下载日志（用于限流统计）
        record_download(ip_address, binary)

        # 增加下载计数
        ClaudeMirrorService.increment_download_count(binary)

        # 生成下载 URL
        download_url = ClaudeMirrorService.get_download_url(binary)

        # 设置响应头
        response = HttpResponseRedirect(download_url)
        response['X-Claude-Code-Version'] = binary.version.version
        response['X-Claude-Code-SHA256'] = binary.sha256
        response['X-Claude-Code-Platform'] = platform_arch

        # 添加限流信息到响应头
        rate_info = get_rate_limit_info(ip_address)
        response['X-RateLimit-Limit'] = str(rate_info['limit'])
        response['X-RateLimit-Remaining'] = str(rate_info['remaining'])
        if rate_info['reset_at']:
            response['X-RateLimit-Reset'] = rate_info['reset_at']

        return response

    def throttled(self, request, wait):
        """限流响应"""
        return Response({
            'status': 'error',
            'message': f'请求过于频繁，请在 {int(wait)} 秒后重试',
            'code': 'rate_limit_exceeded',
            'retry_after': int(wait),
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
