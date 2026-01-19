"""
Recipe 服务模块

提供 Recipe 市场的核心业务逻辑:
- search_recipes: 搜索 Recipe
- get_recipe_detail: 获取详情
- download_recipe: 下载并增加计数
- check_premium_access: 检查 Premium 权限
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from django.db.models import Q, F
from django.db import transaction
from django.contrib.auth import get_user_model

from ..models import Recipe, RecipeVersion, RecipeRating

logger = logging.getLogger('django')
User = get_user_model()


class RecipeServiceError(Exception):
    """Recipe 服务错误"""

    def __init__(self, message: str, code: str = 'recipe_error'):
        super().__init__(message)
        self.message = message
        self.code = code


class RecipeNotFoundError(RecipeServiceError):
    """Recipe 不存在"""

    def __init__(self, message: str = 'Recipe 不存在'):
        super().__init__(message, code='recipe_not_found')


class VersionNotFoundError(RecipeServiceError):
    """版本不存在"""

    def __init__(self, message: str = '指定版本不存在'):
        super().__init__(message, code='version_not_found')


class PremiumRequiredError(RecipeServiceError):
    """需要订阅"""

    def __init__(self, message: str = '此 Recipe 需要订阅才能下载'):
        super().__init__(message, code='premium_required')


class RecipeService:
    """Recipe 服务类"""

    # Premium 订阅类型（可下载 Premium Recipe）
    PREMIUM_SUBSCRIPTION_TYPES = ['vip_user', 'enterprise_user', 'max_user']

    @staticmethod
    def search_recipes(
        query: Optional[str] = None,
        author: Optional[str] = None,
        runtime: Optional[str] = None,
        min_rating: Optional[float] = None,
        is_premium: Optional[bool] = None,
        ordering: str = '-download_count',
        page: int = 1,
        page_size: int = 20,
        include_private: bool = False,
        user: Optional[User] = None
    ) -> Tuple[List[Recipe], int]:
        """
        搜索 Recipe

        Args:
            query: 关键词（匹配名称、描述）
            author: 作者用户名
            runtime: 运行时类型
            min_rating: 最低评分
            is_premium: 是否为 Premium
            ordering: 排序字段
            page: 页码
            page_size: 每页数量
            include_private: 是否包含私有 Recipe（仅作者可见）
            user: 当前用户（用于查看自己的私有 Recipe）

        Returns:
            (Recipe 列表, 总数)
        """
        # 基础查询：公开 Recipe
        queryset = Recipe.objects.select_related('author')

        if include_private and user:
            # 公开的 + 自己的私有
            queryset = queryset.filter(
                Q(is_public=True) | Q(author=user)
            )
        else:
            queryset = queryset.filter(is_public=True)

        # 关键词搜索
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )

        # 作者筛选
        if author:
            queryset = queryset.filter(author__username=author)

        # 运行时筛选
        if runtime:
            queryset = queryset.filter(runtime=runtime)

        # 评分筛选
        if min_rating is not None:
            queryset = queryset.filter(average_rating__gte=min_rating)

        # Premium 筛选
        if is_premium is not None:
            queryset = queryset.filter(is_premium=is_premium)

        # 验证排序字段
        valid_orderings = ['-download_count', '-average_rating', '-created_at',
                          'download_count', 'average_rating', 'created_at', 'name']
        if ordering not in valid_orderings:
            ordering = '-download_count'

        queryset = queryset.order_by(ordering)

        # 计算总数
        total_count = queryset.count()

        # 分页
        page_size = min(page_size, 100)  # 最大 100
        offset = (page - 1) * page_size
        recipes = list(queryset[offset:offset + page_size])

        return recipes, total_count

    @staticmethod
    def get_recipe_detail(
        recipe_id: int,
        user: Optional[User] = None
    ) -> Recipe:
        """
        获取 Recipe 详情

        Args:
            recipe_id: Recipe ID
            user: 当前用户

        Returns:
            Recipe 对象

        Raises:
            RecipeNotFoundError: Recipe 不存在或无权访问
        """
        try:
            recipe = Recipe.objects.select_related('author').prefetch_related(
                'versions', 'ratings'
            ).get(pk=recipe_id)
        except Recipe.DoesNotExist:
            raise RecipeNotFoundError()

        # 检查访问权限
        if not recipe.is_public:
            if not user or recipe.author != user:
                raise RecipeNotFoundError('Recipe 不存在或无权访问')

        return recipe

    @staticmethod
    def download_recipe(
        recipe_id: int,
        version: Optional[str] = None,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        下载 Recipe

        Args:
            recipe_id: Recipe ID
            version: 指定版本号（默认最新）
            user: 当前用户

        Returns:
            包含 Recipe 内容的字典

        Raises:
            RecipeNotFoundError: Recipe 不存在
            VersionNotFoundError: 版本不存在
            PremiumRequiredError: 需要订阅
        """
        # 获取 Recipe
        try:
            recipe = Recipe.objects.select_related('author').get(pk=recipe_id)
        except Recipe.DoesNotExist:
            raise RecipeNotFoundError()

        # 检查访问权限
        if not recipe.is_public:
            if not user or recipe.author != user:
                raise RecipeNotFoundError('Recipe 不存在或无权访问')

        # 检查 Premium 权限
        if recipe.is_premium:
            if not RecipeService.check_premium_access(recipe, user):
                raise PremiumRequiredError()

        # 获取指定版本
        if version:
            try:
                recipe_version = recipe.versions.get(version=version)
            except RecipeVersion.DoesNotExist:
                raise VersionNotFoundError(f'版本 {version} 不存在')
        else:
            recipe_version = recipe.get_latest_version()
            if not recipe_version:
                raise VersionNotFoundError('该 Recipe 没有可用版本')

        # 增加下载计数（原子操作）
        Recipe.objects.filter(pk=recipe_id).update(
            download_count=F('download_count') + 1
        )

        logger.info(f'Recipe downloaded: {recipe.name}@{recipe_version.version} by user={user}')

        return {
            'name': recipe.name,
            'version': recipe_version.version,
            'runtime': recipe.runtime,
            'content': recipe_version.content,
            'description': recipe.description,
            'author': recipe.author.username,
            'changelog': recipe_version.changelog,
        }

    @staticmethod
    def check_premium_access(recipe: Recipe, user: Optional[User]) -> bool:
        """
        检查用户是否有权限访问 Premium Recipe

        Args:
            recipe: Recipe 对象
            user: 用户对象

        Returns:
            是否有权限
        """
        # 非 Premium Recipe 无需检查
        if not recipe.is_premium:
            return True

        # 未登录
        if not user:
            return False

        # 作者自己
        if recipe.author == user:
            return True

        # 检查订阅等级
        try:
            profile = user.profile
            subscription_type = getattr(profile, 'subscription_type', 'free_user')
            return subscription_type in RecipeService.PREMIUM_SUBSCRIPTION_TYPES
        except Exception:
            return False

    @staticmethod
    def get_recipe_by_name(name: str) -> Optional[Recipe]:
        """
        通过名称获取 Recipe

        Args:
            name: Recipe 名称

        Returns:
            Recipe 对象或 None
        """
        try:
            return Recipe.objects.select_related('author').get(name=name)
        except Recipe.DoesNotExist:
            return None

    # ==================== 发布功能 (US3) ====================

    @staticmethod
    def publish_recipe(
        name: str,
        description: str,
        runtime: str,
        version: str,
        content: str,
        user: User,
        changelog: str = '',
        is_public: bool = True,
        is_premium: bool = False
    ) -> Dict[str, Any]:
        """
        发布新 Recipe 或新版本

        Args:
            name: Recipe 名称（只能包含小写字母、数字和连字符）
            description: Recipe 描述
            runtime: 运行时类型
            version: 语义版本号（如 1.0.0）
            content: Recipe 脚本内容
            user: 发布者用户
            changelog: 版本更新说明
            is_public: 是否公开
            is_premium: 是否需要订阅

        Returns:
            包含发布结果的字典

        Raises:
            RecipeServiceError: 发布失败
        """
        # 验证内容格式和大小
        RecipeService.validate_recipe_content(content)

        with transaction.atomic():
            # 检查是否已存在同名 Recipe
            existing_recipe = RecipeService.get_recipe_by_name(name)

            if existing_recipe:
                # 检查名称冲突（其他用户的 Recipe）
                if existing_recipe.author != user:
                    raise RecipeServiceError(
                        f'Recipe 名称 "{name}" 已被其他用户使用',
                        code='name_conflict'
                    )

                # 检查版本是否已存在
                if existing_recipe.versions.filter(version=version).exists():
                    raise RecipeServiceError(
                        f'版本 {version} 已存在，请使用新的版本号',
                        code='version_exists'
                    )

                # 更新现有 Recipe 的元信息
                existing_recipe.description = description
                existing_recipe.runtime = runtime
                existing_recipe.is_public = is_public
                existing_recipe.is_premium = is_premium
                existing_recipe.save()

                recipe = existing_recipe
                is_new_recipe = False
            else:
                # 创建新 Recipe
                recipe = Recipe.objects.create(
                    name=name,
                    description=description,
                    runtime=runtime,
                    author=user,
                    is_public=is_public,
                    is_premium=is_premium
                )
                is_new_recipe = True

            # 将之前的 is_latest 版本标记为非最新
            recipe.versions.filter(is_latest=True).update(is_latest=False)

            # 创建新版本
            recipe_version = RecipeVersion.objects.create(
                recipe=recipe,
                version=version,
                content=content,
                changelog=changelog,
                file_size=len(content.encode('utf-8')),
                is_latest=True
            )

            logger.info(
                f'Recipe published: {name}@{version} by user={user.username} '
                f'({"new" if is_new_recipe else "update"})'
            )

            return {
                'id': recipe.id,
                'name': recipe.name,
                'version': recipe_version.version,
                'is_new_recipe': is_new_recipe,
                'is_public': recipe.is_public,
                'is_premium': recipe.is_premium,
            }

    @staticmethod
    def validate_recipe_content(content: str) -> None:
        """
        验证 Recipe 内容格式和大小

        Args:
            content: Recipe 脚本内容

        Raises:
            RecipeServiceError: 内容无效
        """
        if not content or not content.strip():
            raise RecipeServiceError('Recipe 内容不能为空', code='empty_content')

        # 检查大小（最大 1MB）
        content_size = len(content.encode('utf-8'))
        max_size = 1 * 1024 * 1024  # 1MB
        if content_size > max_size:
            raise RecipeServiceError(
                f'Recipe 内容过大（{content_size / 1024:.1f}KB > 1024KB）',
                code='content_too_large'
            )

    @staticmethod
    def check_name_conflict(name: str, user: User) -> bool:
        """
        检查名称是否冲突

        Args:
            name: Recipe 名称
            user: 当前用户

        Returns:
            True 如果名称可用，False 如果冲突
        """
        existing = RecipeService.get_recipe_by_name(name)
        if existing is None:
            return True  # 名称可用
        return existing.author == user  # 如果是自己的 Recipe 则可用

    # ==================== 评分功能 (US4) ====================

    @staticmethod
    def rate_recipe(
        recipe_id: int,
        user: User,
        rating: int,
        comment: str = ''
    ) -> Dict[str, Any]:
        """
        对 Recipe 评分（创建或更新）

        Args:
            recipe_id: Recipe ID
            user: 评分用户
            rating: 评分（1-5）
            comment: 评论内容

        Returns:
            评分结果字典

        Raises:
            RecipeNotFoundError: Recipe 不存在
            RecipeServiceError: 不能给自己的 Recipe 评分
        """
        # 获取 Recipe
        try:
            recipe = Recipe.objects.get(pk=recipe_id)
        except Recipe.DoesNotExist:
            raise RecipeNotFoundError()

        # 不能给自己的 Recipe 评分
        if recipe.author == user:
            raise RecipeServiceError(
                '不能给自己的 Recipe 评分',
                code='self_rating_not_allowed'
            )

        # 检查访问权限（私有 Recipe 不可评分）
        if not recipe.is_public:
            raise RecipeNotFoundError('Recipe 不存在或无权访问')

        with transaction.atomic():
            # 创建或更新评分
            rating_obj, created = RecipeRating.objects.update_or_create(
                recipe=recipe,
                user=user,
                defaults={
                    'rating': rating,
                    'comment': comment
                }
            )

            # 更新平均评分
            RecipeService.update_average_rating(recipe_id)

        logger.info(
            f'Recipe rated: {recipe.name} by user={user.username} '
            f'rating={rating} ({"new" if created else "update"})'
        )

        return {
            'id': rating_obj.id,
            'recipe_id': recipe.id,
            'recipe_name': recipe.name,
            'rating': rating_obj.rating,
            'comment': rating_obj.comment,
            'is_new': created,
            'created_at': rating_obj.created_at.isoformat(),
            'updated_at': rating_obj.updated_at.isoformat(),
        }

    @staticmethod
    def update_average_rating(recipe_id: int) -> None:
        """
        重新计算 Recipe 的平均评分

        Args:
            recipe_id: Recipe ID
        """
        from django.db.models import Avg

        avg_rating = RecipeRating.objects.filter(
            recipe_id=recipe_id
        ).aggregate(avg=Avg('rating'))['avg']

        # 更新 Recipe 的平均评分
        Recipe.objects.filter(pk=recipe_id).update(
            average_rating=avg_rating or 0
        )
