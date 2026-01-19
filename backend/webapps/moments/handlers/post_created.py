"""
公司圈发帖事件处理器

处理 moments.post.created_v1 事件
使用 SDK 的 P2MomentsPostCreatedV1 类型

注意：飞书 SDK 在 async 上下文中调用处理器，Django ORM 需要用线程执行
"""
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from lark_oapi.api.moments.v1 import P2MomentsPostCreatedV1

from webapps.moments.models import MomentsPost
from webapps.moments.services.post_fetcher import MomentsPostFetcher
from webapps.moments.services.content_parser import MomentsContentParser

logger = logging.getLogger('django')

# 线程池用于执行同步的数据库操作
_executor = ThreadPoolExecutor(max_workers=4)


def _process_post_sync(
    event_id: str,
    post_id: str,
    author_open_id: str,
    author_user_id: str,
    category_ids: list,
    create_time_str: str
) -> None:
    """
    同步处理帖子数据（在线程中执行）
    """
    try:
        # 幂等性检查
        if MomentsPost.objects.filter(post_id=post_id).exists():
            logger.info(f"帖子已存在，跳过处理: post_id={post_id}")
            return

        # 查询帖子详细内容
        post_detail = MomentsPostFetcher.fetch_post(post_id)

        if not post_detail:
            logger.error(f"查询帖子详情失败: post_id={post_id}")
            content_raw = []
            content_text = ''
        else:
            content_raw = post_detail.get('content', [])
            content_text = MomentsContentParser.parse_to_text(content_raw)

        # 解析发帖时间
        feishu_create_time = None
        if create_time_str:
            try:
                feishu_create_time = datetime.fromisoformat(create_time_str)
            except ValueError:
                logger.warning(f"无法解析发帖时间: {create_time_str}")

        # 保存帖子记录
        post = MomentsPost.objects.create(
            post_id=post_id,
            author_open_id=author_open_id,
            author_user_id=author_user_id,
            content_raw=content_raw,
            content_text=content_text,
            category_ids=category_ids or [],
            feishu_create_time=feishu_create_time,
            event_id=event_id
        )

        logger.info(f"公司圈帖子已保存: post_id={post_id}, content_length={len(content_text)}")

    except Exception as e:
        logger.error(f"处理帖子数据异常: post_id={post_id}, error={str(e)}", exc_info=True)


def handle_post_created(data: P2MomentsPostCreatedV1) -> None:
    """
    处理发布帖子事件

    Args:
        data: 飞书SDK传入的 P2MomentsPostCreatedV1 事件对象
    """
    try:
        # 从 SDK 类型化对象中提取数据
        header = data.header
        event = data.event

        event_id = header.event_id if header else ''
        post_id = event.id if event else ''
        user_info = event.user_id if event else None
        category_ids = event.category_ids if event else []
        create_time_str = event.create_time if event else ''

        logger.info(f"收到公司圈发帖事件: event_id={event_id}, post_id={post_id}")

        if not post_id:
            logger.warning(f"事件缺少帖子ID: event_id={event_id}")
            return

        # 提取用户信息
        author_open_id = ''
        author_user_id = ''
        if user_info:
            author_open_id = user_info.open_id or ''
            author_user_id = user_info.user_id or ''

        # 提交到线程池执行数据库操作
        _executor.submit(
            _process_post_sync,
            event_id,
            post_id,
            author_open_id,
            author_user_id,
            category_ids,
            create_time_str
        )

    except Exception as e:
        logger.error(f"处理发帖事件异常: {str(e)}", exc_info=True)
