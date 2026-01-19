"""moments.views
飞书公司圈帖子 REST API 视图层
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncHour
from datetime import timedelta

from .models import MomentsPost
import logging

logger = logging.getLogger('django')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def posts_list(request):
    """
    获取公司圈帖子列表

    支持分页参数:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20, 最大 100)
    """
    try:
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)

        # 查询所有帖子，按发帖时间倒序
        queryset = MomentsPost.objects.all().order_by('-feishu_create_time')

        # 分页
        paginator = Paginator(queryset, page_size)
        posts = paginator.get_page(page)

        # 序列化数据
        data = []
        for post in posts:
            data.append({
                'id': post.id,
                'post_id': post.post_id,
                'author_open_id': post.author_open_id,
                'author_user_id': post.author_user_id,
                'content_text': post.content_text,
                'content_raw': post.content_raw,
                'category_ids': post.category_ids,
                'feishu_create_time': post.feishu_create_time.isoformat() if post.feishu_create_time else None,
                'created_at': post.created_at.isoformat() if post.created_at else None,
            })

        return Response({
            'status': 'success',
            'data': {
                'items': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': posts.has_next(),
                    'has_previous': posts.has_previous(),
                }
            },
            'message': '获取帖子列表成功',
            'code': 200
        })
    except Exception as e:
        logger.error(f'获取帖子列表失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'获取帖子列表失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def post_detail(request, post_id):
    """
    获取单个帖子详情
    """
    try:
        post = MomentsPost.objects.get(post_id=post_id)
        data = {
            'id': post.id,
            'post_id': post.post_id,
            'author_open_id': post.author_open_id,
            'author_user_id': post.author_user_id,
            'content_text': post.content_text,
            'content_raw': post.content_raw,
            'category_ids': post.category_ids,
            'feishu_create_time': post.feishu_create_time.isoformat() if post.feishu_create_time else None,
            'created_at': post.created_at.isoformat() if post.created_at else None,
            'updated_at': post.updated_at.isoformat() if post.updated_at else None,
            'event_id': post.event_id,
        }

        return Response({
            'status': 'success',
            'data': data,
            'message': '获取帖子详情成功',
            'code': 200
        })
    except MomentsPost.DoesNotExist:
        return Response({
            'status': 'error',
            'data': None,
            'message': '帖子不存在',
            'code': 404
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'获取帖子详情失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'获取帖子详情失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def posts_hourly_stats(request):
    """
    获取24小时内每小时的发帖量统计
    返回24个小时的数据点，从24小时前到现在
    """
    try:
        # 使用本地时区
        local_tz = timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), local_tz)
        # 当前小时取整
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        # 从23小时前开始，到当前小时结束，共24个小时
        start_time = current_hour - timedelta(hours=23)

        # 按小时分组统计，指定时区
        hourly_counts = (
            MomentsPost.objects
            .filter(feishu_create_time__gte=start_time)
            .annotate(hour=TruncHour('feishu_create_time', tzinfo=local_tz))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

        # 构建完整的24小时数据，没有数据的小时填0
        # 将 hour 转换为本地时间后作为 key
        stats_dict = {}
        for item in hourly_counts:
            hour_local = timezone.localtime(item['hour'], local_tz)
            stats_dict[hour_local.replace(tzinfo=None)] = item['count']

        hourly_data = []
        for i in range(24):
            hour_start = start_time + timedelta(hours=i)
            # 用于匹配的 key（不带时区信息）
            hour_key = hour_start.replace(tzinfo=None)
            count = stats_dict.get(hour_key, 0)
            hourly_data.append({
                'hour': hour_start.isoformat(),
                'label': hour_start.strftime('%H:00'),
                'count': count
            })

        return Response({
            'status': 'success',
            'data': {
                'hourly_stats': hourly_data,
                'total_24h': sum(item['count'] for item in hourly_data)
            },
            'message': '获取统计数据成功',
            'code': 200
        })
    except Exception as e:
        logger.error(f'获取统计数据失败: {e}')
        return Response({
            'status': 'error',
            'data': None,
            'message': f'获取统计数据失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
