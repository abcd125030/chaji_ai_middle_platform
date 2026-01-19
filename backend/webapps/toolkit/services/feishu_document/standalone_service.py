"""
独立的飞书文档服务 - 不依赖任何Task对象

职责：协调各组件完成Markdown转飞书文档的完整流程，
      支持通过命令行批量创建飞书文档
"""
import logging
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .components.feishu_token_manager import FeishuTokenManager
from .components.markdown_segmentor import MarkdownSegmentor
from .components.feishu_document_creator import FeishuDocumentCreator
from .components.feishu_markdown_converter import FeishuMarkdownConverter
from .components.feishu_image_processor import FeishuImageProcessor
from .components.feishu_block_inserter import FeishuBlockInserter
from .components.feishu_permission_manager import FeishuPermissionManager

logger = logging.getLogger('django')


@dataclass
class ConversionResult:
    """转换结果数据类"""
    success: bool
    document_id: Optional[str] = None
    document_url: Optional[str] = None
    owner_transferred: bool = False
    error_message: Optional[str] = None

    @property
    def feishu_url(self) -> Optional[str]:
        """返回飞书文档URL"""
        if self.document_id:
            return f"https://feishu.cn/docx/{self.document_id}"
        return None


class StandaloneFeishuDocumentService:
    """独立飞书文档服务 - 不依赖Task对象"""

    def __init__(self):
        """初始化服务"""
        self._token: Optional[str] = None

    def _ensure_token(self) -> str:
        """确保token有效，懒加载"""
        if not self._token:
            self._token = FeishuTokenManager.get_tenant_access_token()
        return self._token

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，替换空格和特殊字符为下划线

        Args:
            filename: 原始文件名

        Returns:
            str: 清理后的文件名
        """
        name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
        sanitized = name_without_ext.replace(' ', '_')
        sanitized = re.sub(r'[^\w\u4e00-\u9fff-]', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_')
        return sanitized if sanitized else 'untitled'

    def convert_markdown_file(
        self,
        markdown_path: str,
        document_title: Optional[str] = None,
        owner_open_id: Optional[str] = None
    ) -> ConversionResult:
        """
        将单个Markdown文件转换为飞书文档

        Args:
            markdown_path: Markdown文件的绝对路径
            document_title: 文档标题（可选，默认使用文件名）
            owner_open_id: 文档所有者的飞书Open ID（可选）

        Returns:
            ConversionResult: 转换结果对象
        """
        try:
            # 1. 验证文件存在
            md_path = Path(markdown_path)
            if not md_path.exists():
                return ConversionResult(
                    success=False,
                    error_message=f"文件不存在: {markdown_path}"
                )

            if not md_path.is_file():
                return ConversionResult(
                    success=False,
                    error_message=f"路径不是文件: {markdown_path}"
                )

            # 2. 读取文件内容
            markdown_content = md_path.read_text(encoding='utf-8')
            logger.info(f"读取Markdown文件: {markdown_path}, 大小: {len(markdown_content)} 字节")

            # 3. 获取飞书令牌
            token = self._ensure_token()

            # 4. 确定文档标题
            title = document_title or self.sanitize_filename(md_path.name)
            logger.info(f"文档标题: {title}")

            # 5. 分割Markdown内容
            lines = markdown_content.splitlines(keepends=True)
            segments = MarkdownSegmentor.split_markdown_lines(lines, max_lines=200)
            logger.info(f"Markdown分割为 {len(segments)} 段")

            # 6. 创建飞书文档
            document_id = FeishuDocumentCreator.create_document(token, title)
            logger.info(f"飞书文档创建成功，ID: {document_id}")

            # 7. 处理每个分段
            for idx, segment_lines in enumerate(segments, start=1):
                segment_text = ''.join(segment_lines)
                logger.info(f"处理第 {idx}/{len(segments)} 段，长度: {len(segment_text)} 字符")

                # 转换为飞书Block
                blocks, first_level_block_ids, image_url_map = \
                    FeishuMarkdownConverter.convert_markdown_to_blocks(token, segment_text)

                # 清理表格merge_info
                blocks = FeishuBlockInserter.clean_table_merge_info(blocks)

                # 插入Block
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

                # 处理图片
                if image_url_map and block_id_map:
                    success_count = FeishuImageProcessor.process_images(
                        token=token,
                        document_id=document_id,
                        blocks=blocks,
                        image_url_map=image_url_map,
                        block_id_map=block_id_map
                    )
                    logger.info(f"段落 {idx} 处理了 {success_count} 张图片")

            # 8. 转移文档所有权（如果提供了open_id）
            owner_transferred = False
            if owner_open_id:
                owner_transferred = FeishuPermissionManager.transfer_document_owner(
                    token=token,
                    document_id=document_id,
                    open_id=owner_open_id
                )
                if owner_transferred:
                    logger.info(f"文档所有权已转移给: {owner_open_id}")
                else:
                    logger.warning(f"文档所有权转移失败，目标用户: {owner_open_id}")

            # 9. 返回成功结果
            return ConversionResult(
                success=True,
                document_id=document_id,
                document_url=f"https://feishu.cn/docx/{document_id}",
                owner_transferred=owner_transferred
            )

        except FileNotFoundError as e:
            return ConversionResult(success=False, error_message=f"文件不存在: {str(e)}")
        except RuntimeError as e:
            return ConversionResult(success=False, error_message=f"飞书API错误: {str(e)}")
        except Exception as e:
            logger.error(f"转换失败: {str(e)}", exc_info=True)
            return ConversionResult(success=False, error_message=f"未知错误: {str(e)}")
