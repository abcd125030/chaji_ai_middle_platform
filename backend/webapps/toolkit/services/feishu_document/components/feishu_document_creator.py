"""
飞书文档创建组件

职责：调用飞书API创建空白文档
"""
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger('django')


class FeishuDocumentCreator:
    """飞书文档创建器"""

    @staticmethod
    def create_document(token: str, title: str) -> str:
        """
        创建飞书文档

        Args:
            token: 飞书租户访问令牌
            title: 文档标题

        Returns:
            str: 文档ID（格式：doccnxxxxxx）

        Raises:
            RuntimeError: 文档创建失败时抛出异常
        """
        url = 'https://open.feishu.cn/open-apis/docx/v1/documents'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        payload = {'title': title}

        try:
            logger.info(f"正在创建飞书文档，标题: {title}")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            document_id = data.get('data', {}).get('document', {}).get('document_id')

            if not document_id:
                error_msg = f"飞书API未返回document_id，响应体: {data}"
                logger.error(f"飞书文档创建失败: {error_msg}")
                raise RuntimeError(error_msg)

            logger.info(f"飞书文档创建成功，ID: {document_id}")
            return document_id

        except requests.exceptions.Timeout as e:
            error_msg = f"飞书文档创建超时: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
        except requests.exceptions.HTTPError as e:
            error_msg = f"飞书API调用失败: url={url}, status={e.response.status_code if e.response else 'unknown'}, response={e.response.text if e.response else 'no response'}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"飞书文档创建失败（未知错误）: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
