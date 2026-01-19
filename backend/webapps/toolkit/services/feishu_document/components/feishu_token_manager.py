"""
飞书Token管理组件

职责：获取飞书Tenant Access Token
"""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger('django')


class FeishuTokenManager:
    """飞书Token管理器"""

    @staticmethod
    def get_tenant_access_token() -> str:
        """
        获取飞书Tenant Access Token

        Returns:
            str: 飞书租户访问令牌（格式：t-xxxxxx）

        Raises:
            RuntimeError: Token获取失败时抛出异常
        """
        app_id = os.environ.get('FEISHU_APP_ID')
        app_secret = os.environ.get('FEISHU_APP_SECRET')

        if not app_id or not app_secret:
            error_msg = "环境变量FEISHU_APP_ID或FEISHU_APP_SECRET未配置"
            logger.error(f"飞书Token获取失败: {error_msg}")
            raise RuntimeError(error_msg)

        url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
        payload = {'app_id': app_id, 'app_secret': app_secret}

        try:
            logger.info(f"正在获取飞书Token，App ID: {app_id[:10]}...")
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            token = data.get('tenant_access_token')

            if not token:
                error_msg = f"飞书API未返回token，响应体: {data}"
                logger.error(f"飞书Token获取失败: {error_msg}")
                raise RuntimeError(error_msg)

            logger.info("飞书Token获取成功")
            return token

        except requests.exceptions.Timeout as e:
            error_msg = f"飞书Token获取超时: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"飞书API网络连接失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
        except requests.exceptions.HTTPError as e:
            error_msg = f"飞书API调用失败: url={url}, status={e.response.status_code if e.response else 'unknown'}, response={e.response.text if e.response else 'no response'}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"飞书Token获取失败（未知错误）: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
