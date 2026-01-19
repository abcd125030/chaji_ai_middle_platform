"""
飞书块插入组件

职责：批量插入飞书块到文档，处理表格merge_info清理和1000块限制
"""
import logging
import requests
from typing import Dict, Any, List

logger = logging.getLogger('django')


class FeishuBlockInserter:
    """飞书块插入器"""

    @staticmethod
    def clean_table_merge_info(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        清理表格属性中的merge_info字段（飞书API要求）

        Args:
            blocks: 块列表

        Returns:
            List[Dict[str, Any]]: 清理后的块列表
        """
        cleaned_blocks = []
        cleaned_count = 0

        for block in blocks:
            # 检查是否为表格块（block_type=31）
            if block.get('block_type') == 31 and block.get('table') and block['table'].get('property'):
                prop = block['table']['property']
                if 'merge_info' in prop:
                    prop.pop('merge_info', None)
                    cleaned_count += 1

            cleaned_blocks.append(block)

        if cleaned_count > 0:
            logger.info(f"清理了{cleaned_count}个表格块的merge_info字段")

        return cleaned_blocks

    @staticmethod
    def insert_blocks_batch(
        token: str,
        document_id: str,
        blocks: List[Dict[str, Any]],
        first_level_block_ids: List[str],
        batch_size: int = 200
    ) -> Dict[str, str]:
        """
        批量插入块到飞书文档（支持1000块限制）

        Args:
            token: 飞书租户访问令牌
            document_id: 文档ID
            blocks: 要插入的块列表
            first_level_block_ids: 一级块ID列表
            batch_size: 每批最多块数（默认200，避免请求体过大）

        Returns:
            Dict[str, str]: 临时块ID到真实块ID的映射

        Raises:
            RuntimeError: 插入失败时抛出异常
        """
        # 清理表格merge_info
        processed_blocks = FeishuBlockInserter.clean_table_merge_info(blocks)
        block_id_relations = {}

        url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/descendant'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        total_blocks = len(processed_blocks)
        logger.info(f"开始插入块，总块数: {total_blocks}，批次大小: {batch_size}")

        # 分批插入
        for batch_idx, i in enumerate(range(0, total_blocks, batch_size), start=1):
            batch_blocks = processed_blocks[i:i + batch_size]
            payload = {
                'children_id': first_level_block_ids,
                'index': i,
                'descendants': batch_blocks
            }

            try:
                logger.info(f"插入第{batch_idx}批块，范围: {i}-{i + len(batch_blocks) - 1}，块数: {len(batch_blocks)}")
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                resp.raise_for_status()

                data = resp.json().get('data', {})
                relations = data.get('block_id_relations', [])

                # 记录ID映射
                for rel in relations:
                    tmp_id = rel.get('temporary_block_id')
                    new_id = rel.get('block_id')
                    if tmp_id and new_id:
                        block_id_relations[tmp_id] = new_id

                logger.info(f"第{batch_idx}批块插入成功，ID映射数: {len(relations)}")

            except requests.exceptions.Timeout as e:
                error_msg = f"第{batch_idx}批块插入超时: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg)
            except requests.exceptions.HTTPError as e:
                status_code = getattr(e.response, 'status_code', 'unknown')
                try:
                    response_text = e.response.text if e.response is not None else 'no response'
                except Exception:
                    response_text = 'failed to read response'
                error_msg = f"飞书API调用失败: url={url}, batch={batch_idx}, status={status_code}, response={response_text}"
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg)
            except Exception as e:
                error_msg = f"第{batch_idx}批块插入失败（未知错误）: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg)

        logger.info(f"所有块插入完成，总ID映射数: {len(block_id_relations)}")
        return block_id_relations
