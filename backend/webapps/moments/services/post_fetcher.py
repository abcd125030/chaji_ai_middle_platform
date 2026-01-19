"""
飞书公司圈帖子查询服务

调用 GET /open-apis/moments/v1/posts/:post_id 获取帖子详情
"""
import logging
import requests
from typing import Optional, Dict, Any

from webapps.toolkit.services.feishu_document.components.feishu_token_manager import FeishuTokenManager

logger = logging.getLogger('django')


class MomentsPostFetcher:
    """公司圈帖子查询器"""

    BASE_URL = 'https://open.feishu.cn/open-apis/moments/v1/posts'

    @classmethod
    def fetch_post(cls, post_id: str, user_id_type: str = 'open_id') -> Optional[Dict[str, Any]]:
        """
        查询帖子详细内容

        Args:
            post_id: 帖子ID（从事件中获取）
            user_id_type: 用户ID类型 (open_id/union_id/user_id)

        Returns:
            帖子详情字典，失败返回None
        """
        try:
            token = FeishuTokenManager.get_tenant_access_token()

            url = f'{cls.BASE_URL}/{post_id}'
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json; charset=utf-8'
            }
            params = {'user_id_type': user_id_type}

            logger.info(f"查询公司圈帖子: post_id={post_id}")

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get('code') != 0:
                logger.error(f"查询帖子失败: code={data.get('code')}, msg={data.get('msg')}")
                return None

            logger.info(f"帖子查询成功: post_id={post_id}")
            return data.get('data', {}).get('post')

        except requests.exceptions.RequestException as e:
            logger.error(f"查询帖子网络错误: post_id={post_id}, error={str(e)}")
            return None
        except RuntimeError as e:
            logger.error(f"获取Token失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"查询帖子未知错误: post_id={post_id}, error={str(e)}")
            return None
