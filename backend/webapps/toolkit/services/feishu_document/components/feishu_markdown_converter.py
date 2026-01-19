"""
飞书Markdown转换组件

职责：将Markdown文本转换为飞书块结构
"""
import logging
import requests
from typing import Dict, Any, List, Tuple

logger = logging.getLogger('django')


class FeishuMarkdownConverter:
    """飞书Markdown转换器"""

    @staticmethod
    def convert_markdown_to_blocks(token: str, markdown: str) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
        """
        将Markdown转换为飞书块结构

        Args:
            token: 飞书租户访问令牌
            markdown: Markdown文本内容

        Returns:
            Tuple[blocks, first_level_block_ids, block_id_to_image_urls]:
                - blocks: 块结构列表
                - first_level_block_ids: 一级块ID列表
                - block_id_to_image_urls: 块ID到图片URL的映射

        Raises:
            RuntimeError: 转换失败时抛出异常
        """
        url = 'https://open.feishu.cn/open-apis/docx/v1/documents/blocks/convert'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        payload = {
            'content': markdown,
            'content_type': 'markdown'
        }

        try:
            logger.info(f"正在转换Markdown，内容长度: {len(markdown)}字符")
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()

            data = resp.json().get('data')
            if data is None:
                error_msg = "飞书API未返回data字段"
                logger.error(f"Markdown转换失败: {error_msg}")
                raise RuntimeError(error_msg)

            blocks = data.get('blocks', [])
            first_level_block_ids = data.get('first_level_block_ids', [])
            block_id_to_image_urls = data.get('block_id_to_image_urls', [])

            logger.info(f"Markdown转换成功，块数: {len(blocks)}，一级块数: {len(first_level_block_ids)}，图片数: {len(block_id_to_image_urls)}")
            return blocks, first_level_block_ids, block_id_to_image_urls

        except requests.exceptions.Timeout as e:
            error_msg = f"Markdown转换超时: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
        except requests.exceptions.HTTPError as e:
            error_msg = f"飞书API调用失败: url={url}, status={e.response.status_code if e.response else 'unknown'}, response={e.response.text if e.response else 'no response'}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Markdown转换失败（未知错误）: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)
