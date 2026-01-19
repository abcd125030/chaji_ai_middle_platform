"""
飞书权限管理组件

职责：转移文档所有权给用户
"""
import logging
import requests
from typing import Optional

logger = logging.getLogger('django')


class FeishuPermissionManager:
    """飞书权限管理器"""

    @staticmethod
    def transfer_document_owner(
        token: str,
        document_id: str,
        open_id: str,
        member_type: str = 'openid'
    ) -> bool:
        """
        转移文档所有权给用户

        失败时不抛出异常，仅返回False并记录警告（不影响主流程）

        Args:
            token: 飞书租户访问令牌
            document_id: 文档ID
            open_id: 用户飞书Open ID
            member_type: 成员类型（默认openid）

        Returns:
            bool: 是否转移成功
        """
        url = f'https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/members/transfer_owner?type=docx'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'member_type': member_type,
            'member_id': open_id
        }

        try:
            logger.info(f"正在转移文档所有权，文档ID: {document_id}，目标用户: {open_id}")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()

            logger.info(f"文档所有权转移成功，文档ID: {document_id}")
            return True

        except requests.exceptions.Timeout:
            logger.warning(f"文档所有权转移超时，文档仍可访问: {document_id}")
            return False
        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"文档所有权转移失败，文档仍可访问: document_id={document_id}, "
                f"status={e.response.status_code if e.response else 'unknown'}, "
                f"response={e.response.text if e.response else 'no response'}"
            )
            return False
        except Exception as e:
            logger.warning(f"文档所有权转移失败（{type(e).__name__}），文档仍可访问: {document_id}, 错误: {str(e)}")
            return False
