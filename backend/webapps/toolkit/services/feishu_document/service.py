"""
飞书文档服务主类

职责：协调各组件完成Markdown转飞书文档的完整流程
"""
import logging
import re
from pathlib import Path
from typing import Optional
from django.contrib.auth import get_user_model

from authentication.models import UserAccount
from .components.feishu_token_manager import FeishuTokenManager
from .components.markdown_segmentor import MarkdownSegmentor
from .components.feishu_document_creator import FeishuDocumentCreator
from .components.feishu_markdown_converter import FeishuMarkdownConverter
from .components.feishu_image_processor import FeishuImageProcessor
from .components.feishu_block_inserter import FeishuBlockInserter
from .components.feishu_permission_manager import FeishuPermissionManager

User = get_user_model()
logger = logging.getLogger('django')


class FeishuDocumentService:
    """飞书文档服务 - 主编排类"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，替换空格和特殊字符为下划线

        Args:
            filename: 原始文件名

        Returns:
            str: 清理后的文件名
        """
        # 移除文件扩展名
        name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename

        # 替换空格为下划线
        sanitized = name_without_ext.replace(' ', '_')

        # 替换特殊字符为下划线（保留中文、英文、数字、下划线和连字符）
        sanitized = re.sub(r'[^\w\u4e00-\u9fff-]', '_', sanitized)

        # 压缩连续的下划线为单个下划线
        sanitized = re.sub(r'_+', '_', sanitized)

        # 移除首尾下划线
        sanitized = sanitized.strip('_')

        return sanitized if sanitized else 'untitled'

    def convert_markdown_to_feishu(
        self,
        task,
        markdown_path: str
    ) -> Optional[str]:
        """
        将Markdown文件转换为飞书文档

        Args:
            task: PDFExtractorTask对象
            markdown_path: Markdown文件路径

        Returns:
            str: 飞书文档URL（格式: https://feishu.cn/docx/{document_id}）
            None: 用户未关联飞书账号或转换失败
        """
        try:
            logger.info(f"开始飞书文档转换流程，任务ID: {task.id}")

            # 1. 检查用户是否关联飞书账号（使用UserAccount表）
            feishu_account = UserAccount.objects.filter(
                user=task.user,
                provider='feishu',
                is_verified=True
            ).first()

            if not feishu_account:
                logger.info(f"用户 {task.user.username} 未关联飞书账号，跳过飞书文档转换")
                return None

            open_id = feishu_account.provider_account_id
            logger.info(f"用户 {task.user.username} 的飞书Open ID: {open_id}")

            # 2. 读取Markdown文件内容
            markdown_content = Path(markdown_path).read_text(encoding='utf-8')
            logger.info(f"成功读取 Markdown 文件: {markdown_path}, 大小: {len(markdown_content)} 字节")

            # 3. 获取飞书令牌
            token = FeishuTokenManager.get_tenant_access_token()
            if not token:
                logger.error("获取飞书令牌失败")
                return None

            # 4. 分割Markdown内容（如果超过200行）
            lines = markdown_content.splitlines(keepends=True)
            segments = MarkdownSegmentor.split_markdown_lines(lines, max_lines=200)
            logger.info(f"Markdown内容分割为 {len(segments)} 段")

            # 5. 创建飞书文档
            # 使用清理后的原始文件名作为文档标题
            document_title = self.sanitize_filename(task.original_filename)
            logger.info(f"飞书文档标题: {document_title}（原始文件名: {task.original_filename}）")

            document_id = FeishuDocumentCreator.create_document(token, document_title)
            if not document_id:
                logger.error("创建飞书文档失败")
                return None

            logger.info(f"飞书文档创建成功，文档ID: {document_id}")

            # 6. 处理每个分段
            for idx, segment_lines in enumerate(segments, start=1):
                segment_text = ''.join(segment_lines)
                logger.info(f"处理第 {idx}/{len(segments)} 段，长度: {len(segment_text)} 字符")

                # 6.1 转换Markdown为飞书Block
                blocks, first_level_block_ids, image_url_map = FeishuMarkdownConverter.convert_markdown_to_blocks(
                    token=token,
                    markdown=segment_text
                )
                logger.info(f"段落 {idx} 转换为 {len(blocks)} 个Block")

                # 6.2 清理表格merge_info
                blocks = FeishuBlockInserter.clean_table_merge_info(blocks)

                # 6.3 插入Block到文档
                block_id_map = FeishuBlockInserter.insert_blocks_batch(
                    token=token,
                    document_id=document_id,
                    blocks=blocks,
                    first_level_block_ids=first_level_block_ids
                )

                if not block_id_map:
                    logger.warning(f"段落 {idx} 插入失败，继续处理下一段")
                    continue

                logger.info(f"段落 {idx} 插入成功，映射了 {len(block_id_map)} 个块ID")

                # 6.4 处理图片（如果有）
                if image_url_map:
                    success_count = FeishuImageProcessor.process_images(
                        token=token,
                        document_id=document_id,
                        blocks=blocks,
                        image_url_map=image_url_map,
                        block_id_map=block_id_map
                    )
                    logger.info(f"段落 {idx} 处理了 {success_count} 张图片")

            # 7. 转移文档所有权给用户
            transfer_success = FeishuPermissionManager.transfer_document_owner(
                token=token,
                document_id=document_id,
                open_id=open_id
            )

            if transfer_success:
                logger.info(f"文档所有权转移成功，目标用户: {open_id}")
            else:
                logger.warning("文档所有权转移失败，但文档已创建成功")

            # 8. 返回文档URL
            feishu_url = f"https://feishu.cn/docx/{document_id}"
            logger.info(f"飞书文档转换完成，URL: {feishu_url}")
            return feishu_url

        except FileNotFoundError:
            logger.error(f"Markdown文件不存在: {markdown_path}")
            return None
        except Exception as e:
            logger.error(f"飞书文档转换失败: {str(e)}", exc_info=True)
            return None
