"""
飞书公司圈帖子数据模型
"""
from django.db import models


class MomentsPost(models.Model):
    """公司圈帖子记录"""

    # 飞书帖子标识
    post_id = models.CharField(max_length=64, unique=True, verbose_name='帖子ID')

    # 发帖人信息
    author_open_id = models.CharField(max_length=64, blank=True, verbose_name='发帖人OpenID')
    author_user_id = models.CharField(max_length=64, blank=True, verbose_name='发帖人UserID')

    # 帖子内容
    content_raw = models.JSONField(default=list, verbose_name='原始富文本内容')
    content_text = models.TextField(blank=True, verbose_name='解析后的纯文本')

    # 帖子元数据
    category_ids = models.JSONField(default=list, verbose_name='板块ID列表')
    feishu_create_time = models.DateTimeField(null=True, verbose_name='飞书发帖时间')

    # 事件元数据
    event_id = models.CharField(max_length=64, blank=True, verbose_name='事件ID')

    # 本地记录时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='记录更新时间')

    class Meta:
        db_table = 'moments_post'
        verbose_name = '公司圈帖子'
        verbose_name_plural = verbose_name
        ordering = ['-feishu_create_time']

    def __str__(self):
        return f'Post({self.post_id})'
