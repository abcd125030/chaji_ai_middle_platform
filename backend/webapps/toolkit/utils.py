"""
Toolkit应用的辅助工具函数
"""
import os
import uuid
import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from django.conf import settings

logger = logging.getLogger('django')


class FileManager:
    """文件管理工具类"""

    # PDF提取器存储目录配置
    EXTRACTOR_BASE_DIR = Path(settings.MEDIA_ROOT) / 'oss-bucket' / '_toolkit' / '_extractor'

    @classmethod
    def ensure_directory(cls, directory: Path) -> None:
        """
        确保目录存在

        Args:
            directory: 目录路径
        """
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"确保目录存在: {directory}")

    @classmethod
    def create_task_directory(cls, task_id: str) -> Path:
        """
        为任务创建专属目录

        Args:
            task_id: 任务UUID字符串

        Returns:
            任务目录路径
        """
        task_dir = cls.EXTRACTOR_BASE_DIR / task_id
        cls.ensure_directory(task_dir)
        return task_dir

    @classmethod
    def save_base64_file(cls, base64_data: str, filename: str, task_dir: Path) -> str:
        """
        保存base64编码的文件

        Args:
            base64_data: base64编码的文件数据
            filename: 文件名（应该是 {uuid}.pdf 格式）
            task_dir: 任务目录

        Returns:
            保存的文件路径

        Note:
            filename应该使用UUID命名，例如: "550e8400-e29b-41d4-a716-446655440000.pdf"
            原始文件名已经保存在数据库的original_filename字段中
        """
        try:
            # 确保任务目录存在
            cls.ensure_directory(task_dir)

            # 解码base64数据
            file_data = base64.b64decode(base64_data)

            # 构建文件路径
            file_path = task_dir / filename

            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(file_data)

            logger.info(f"文件已保存: {file_path}, 大小: {len(file_data)} 字节")

            return str(file_path)

        except Exception as e:
            logger.error(f"保存base64文件失败: {str(e)}", exc_info=True)
            raise

    @classmethod
    def get_task_json_path(cls, task_id: str) -> Path:
        """
        获取任务JSON文件路径

        Args:
            task_id: 任务UUID字符串

        Returns:
            task.json文件路径
        """
        return cls.EXTRACTOR_BASE_DIR / task_id / 'task.json'

    @classmethod
    def get_markdown_path(cls, task_id: str) -> Path:
        """
        获取任务Markdown文件路径（已废弃，请使用 get_result_markdown_path）

        Args:
            task_id: 任务UUID字符串

        Returns:
            markdown文件路径
        """
        # TODO: 可能需要动态查找.md文件，因为文件名可能包含原始文件名
        task_dir = cls.EXTRACTOR_BASE_DIR / task_id
        md_files = list(task_dir.glob('*.md'))
        if md_files:
            return md_files[0]
        return task_dir / f'{task_id}.md'

    @classmethod
    def get_result_markdown_path(cls, task_id: str) -> Path:
        """
        获取任务最终的 result.md 文件路径

        Args:
            task_id: 任务UUID字符串

        Returns:
            result.md 文件路径

        Raises:
            FileNotFoundError: 如果找不到 result.md 文件
        """
        task_dir = cls.EXTRACTOR_BASE_DIR / task_id

        # 优先查找标准命名的 result 文件
        result_file = task_dir / f'{task_id}_result.md'
        if result_file.exists():
            return result_file

        # 降级：查找任何以 _result.md 结尾的文件
        result_files = list(task_dir.glob('*_result.md'))
        if result_files:
            logger.info(f"找到 result 文件: {result_files[0]}")
            return result_files[0]

        # 最后降级：查找任何 .md 文件
        md_files = list(task_dir.glob('*.md'))
        if md_files:
            logger.warning(f"未找到 result.md，使用备用文件: {md_files[0]}")
            return md_files[0]

        raise FileNotFoundError(f"未找到任务 {task_id} 的 Markdown 文件")

    @classmethod
    def get_images_directory(cls, task_id: str) -> Path:
        """
        获取任务图片目录路径

        Args:
            task_id: 任务UUID字符串

        Returns:
            images目录路径
        """
        return cls.EXTRACTOR_BASE_DIR / task_id / 'images'

    @classmethod
    def validate_pdf_file(cls, file_data: str) -> bool:
        """
        验证PDF文件数据

        Args:
            file_data: base64编码的文件数据

        Returns:
            是否为有效的PDF文件
        """
        try:
            # 解码base64
            decoded_data = base64.b64decode(file_data)

            # 检查文件头是否为PDF格式 (PDF文件以 %PDF- 开头)
            if decoded_data[:5] != b'%PDF-':
                logger.warning("文件头不是PDF格式")
                return False

            # 检查文件大小
            file_size_mb = len(decoded_data) / (1024 * 1024)
            if file_size_mb > cls.MAX_FILE_SIZE_MB:
                logger.warning(f"文件大小超过限制: {file_size_mb:.2f}MB > {cls.MAX_FILE_SIZE_MB}MB")
                return False

            logger.debug(f"PDF文件验证通过, 大小: {file_size_mb:.2f}MB")
            return True

        except Exception as e:
            logger.error(f"验证PDF文件失败: {str(e)}", exc_info=True)
            return False

    @classmethod
    def extract_images_from_task_json(cls, task_id: str) -> List[str]:
        """
        从 task.json 提取所有图片路径

        Args:
            task_id: 任务UUID字符串

        Returns:
            图片相对路径列表，例如: ['page_1/image_1.png', 'page_1/visualization.png', ...]
        """
        import json

        task_json_path = cls.get_task_json_path(task_id)

        if not task_json_path.exists():
            logger.warning(f"task.json 不存在: {task_json_path}")
            return []

        try:
            with open(task_json_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)

            images = []
            for page in task_data.get('pages', []):
                # 收集每页的图片文件（只收集 .png 图片）
                for img_file in page.get('region_files', []):
                    if img_file.endswith('.png'):
                        images.append(img_file)

            logger.debug(f"从 task.json 提取到 {len(images)} 个图片")
            return images

        except Exception as e:
            logger.error(f"解析 task.json 失败: {str(e)}", exc_info=True)
            return []

    @classmethod
    def process_markdown_for_environment(cls, markdown: str, task_id: str) -> str:
        """
        根据运行环境处理 Markdown 中的图片路径，拼接完整URL

        开发环境 (DEBUG=True):
            拼接后端完整URL: /media/... → http://127.0.0.1:8000/media/...
            原因：前端在3000端口，后端在8000端口，需要跨域访问

        生产环境 (DEBUG=False):
            替换为 OSS 直链: /media/oss-bucket/... → https://your-bucket.oss-cn-xxx.aliyuncs.com/...
            原因：避免流量经过服务器，充分利用OSS CDN

        Args:
            markdown: 原始 Markdown 内容
            task_id: 任务UUID

        Returns:
            处理后的 Markdown 内容
        """
        from django.conf import settings

        # 开发环境：拼接后端完整URL
        if settings.DEBUG:
            dev_backend_url = getattr(settings, 'DEV_BACKEND_URL', 'http://127.0.0.1:6066')
            # 替换路径：/media/ → http://127.0.0.1:6066/media/
            processed = markdown.replace('/media/', f'{dev_backend_url}/media/')
            logger.debug(f"开发环境：已拼接后端URL ({dev_backend_url})")
            return processed

        # 生产环境：替换为 OSS 直链
        oss_domain = getattr(settings, 'OSS_PUBLIC_DOMAIN', '')
        if oss_domain:
            # 替换路径：/media/oss-bucket/ → https://your-bucket.oss-cn-xxx.aliyuncs.com/
            processed = markdown.replace('/media/oss-bucket/', f'{oss_domain}/')
            logger.info(f"生产环境：已将图片路径替换为 OSS 直链 ({oss_domain})")
            return processed
        else:
            logger.warning("生产环境但未配置 OSS_PUBLIC_DOMAIN，使用本地路径")
            return markdown

    @classmethod
    def cleanup_task_files(cls, task_id: str) -> bool:
        """
        清理任务相关的所有文件

        Args:
            task_id: 任务UUID字符串

        Returns:
            是否成功清理
        """
        try:
            import shutil

            task_dir = cls.EXTRACTOR_BASE_DIR / task_id

            if task_dir.exists():
                # 删除任务目录及其所有内容
                shutil.rmtree(task_dir)
                logger.info(f"任务文件已清理: {task_dir}")
                return True
            else:
                logger.warning(f"任务目录不存在: {task_dir}")
                return False

        except Exception as e:
            logger.error(f"清理任务文件失败: {str(e)}", exc_info=True)
            return False


class TaskProgressManager:
    """任务进度管理工具类"""

    @staticmethod
    def create_task_json(task_id: str, total_pages: int) -> Dict[str, Any]:
        """
        创建任务JSON数据结构

        Args:
            task_id: 任务UUID字符串
            total_pages: PDF总页数

        Returns:
            任务JSON数据
        """
        return {
            'task_id': task_id,
            'status': 'pending',
            'total_pages': total_pages,
            'processed_pages': 0,
            'pages': [
                {
                    'page': i + 1,
                    'status': 'pending'
                }
                for i in range(total_pages)
            ]
        }

    @staticmethod
    def update_page_status(task_json: Dict[str, Any], page_number: int, status: str) -> None:
        """
        更新页面处理状态

        Args:
            task_json: 任务JSON数据
            page_number: 页码（从1开始）
            status: 新状态（pending/processing/completed/error）
        """
        # 查找对应页面并更新状态
        for page_info in task_json.get('pages', []):
            if page_info.get('page') == page_number:
                page_info['status'] = status
                logger.debug(f"更新页面 {page_number} 状态: {status}")
                break

    @staticmethod
    def update_task_status(task_json: Dict[str, Any]) -> None:
        """
        根据页面状态更新整体任务状态

        Args:
            task_json: 任务JSON数据
        """
        pages = task_json.get('pages', [])
        if not pages:
            return

        # 统计各状态页面数量
        status_counts = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'error': 0
        }

        for page_info in pages:
            page_status = page_info.get('status', 'pending')
            status_counts[page_status] = status_counts.get(page_status, 0) + 1

        # 更新已处理页数（completed + error）
        task_json['processed_pages'] = status_counts['completed'] + status_counts['error']

        # 更新整体任务状态
        if status_counts['error'] > 0:
            # 有错误页面
            if status_counts['completed'] + status_counts['error'] == len(pages):
                # 所有页面已处理完（部分失败）
                task_json['status'] = 'completed_with_errors'
            else:
                # 仍在处理中但有错误
                task_json['status'] = 'processing'
        elif status_counts['completed'] == len(pages):
            # 全部完成
            task_json['status'] = 'completed'
        elif status_counts['processing'] > 0 or status_counts['completed'] > 0:
            # 正在处理
            task_json['status'] = 'processing'
        else:
            # 全部待处理
            task_json['status'] = 'pending'

        logger.debug(
            f"任务状态更新: {task_json['status']}, "
            f"已处理: {task_json['processed_pages']}/{len(pages)}, "
            f"完成: {status_counts['completed']}, 错误: {status_counts['error']}"
        )


class RequestValidator:
    """请求数据验证工具类"""

    MAX_FILES_PER_REQUEST = 20
    MAX_FILE_SIZE_MB = 80
    SUPPORTED_FORMATS = ['.pdf']

    @classmethod
    def validate_file_list(cls, files: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        验证上传文件列表

        Args:
            files: 文件列表

        Returns:
            (是否有效, 错误信息)
        """
        # 检查文件数量
        if not files:
            return False, '文件列表不能为空'

        if len(files) > cls.MAX_FILES_PER_REQUEST:
            return False, f'文件数量不能超过{cls.MAX_FILES_PER_REQUEST}个'

        # 验证每个文件
        for idx, file_info in enumerate(files):
            # 检查必需字段
            if 'filename' not in file_info:
                return False, f'第{idx + 1}个文件缺少filename字段'

            if 'data' not in file_info:
                return False, f'第{idx + 1}个文件缺少data字段'

            # 验证文件格式
            filename = file_info['filename']
            file_ext = Path(filename).suffix.lower()
            if file_ext not in cls.SUPPORTED_FORMATS:
                return False, f'不支持的文件格式: {filename}，仅支持: {", ".join(cls.SUPPORTED_FORMATS)}'

            # 验证base64数据
            file_data = file_info['data']
            try:
                decoded_data = base64.b64decode(file_data)
            except Exception as e:
                return False, f'第{idx + 1}个文件的base64数据无效: {str(e)}'

            # 验证文件大小
            file_size_mb = len(decoded_data) / (1024 * 1024)
            if file_size_mb > cls.MAX_FILE_SIZE_MB:
                return False, f'{filename} 文件大小超过限制: {file_size_mb:.2f}MB > {cls.MAX_FILE_SIZE_MB}MB'

            # 验证PDF文件头
            if file_ext == '.pdf' and decoded_data[:5] != b'%PDF-':
                return False, f'{filename} 不是有效的PDF文件'

        return True, ''

    @classmethod
    def validate_task_ids(cls, task_ids: List[str]) -> Tuple[bool, str]:
        """
        验证任务ID列表

        Args:
            task_ids: 任务UUID列表

        Returns:
            (是否有效, 错误信息)
        """
        # 检查列表是否为空
        if not task_ids:
            return False, '任务ID列表不能为空'

        # 检查数量限制
        if len(task_ids) > cls.MAX_FILES_PER_REQUEST:
            return False, f'任务ID数量不能超过{cls.MAX_FILES_PER_REQUEST}个'

        # 验证UUID格式
        for task_id in task_ids:
            try:
                uuid.UUID(task_id)
            except ValueError:
                return False, f'无效的任务ID格式: {task_id}'

        return True, ''
