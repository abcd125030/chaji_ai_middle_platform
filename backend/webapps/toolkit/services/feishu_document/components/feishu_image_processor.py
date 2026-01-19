"""
飞书图片处理组件

职责：下载图片、上传到飞书、替换文档中的图片块
"""
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import unquote

logger = logging.getLogger('django')


class FeishuImageProcessor:
    """飞书图片处理器"""

    @staticmethod
    def download_image(url: str, timeout: int = 10) -> Optional[bytes]:
        """
        下载图片

        支持三种路径格式：
        1. 本地文件系统路径（如 /media/oss-bucket/...）- 直接读取文件
        2. 本地开发环境URL（如 http://127.0.0.1:6066/media/...）- 转换为文件路径读取
        3. OSS直链（如 https://xxx.aliyuncs.com/...）- HTTP下载

        Args:
            url: 图片URL或本地路径
            timeout: 超时时间（秒）

        Returns:
            Optional[bytes]: 图片字节流，失败返回None
        """
        from pathlib import Path
        from django.conf import settings

        try:
            # 解码 URL 编码的路径（处理中文路径等）
            url = unquote(url)

            # 策略1: 检查是否为本地文件路径（以 /media/ 开头）
            if url.startswith('/media/'):
                # 拼接为完整的文件系统路径
                # /media/oss-bucket/... → {MEDIA_ROOT}/oss-bucket/...
                relative_path = url.replace('/media/', '', 1)
                file_path = Path(settings.MEDIA_ROOT) / relative_path

                if file_path.exists():
                    logger.info(f"从本地文件系统读取图片: {file_path}")
                    image_bytes = file_path.read_bytes()
                    logger.info(f"图片读取成功，大小: {len(image_bytes)}字节")
                    return image_bytes
                else:
                    logger.warning(f"本地图片文件不存在: {file_path}")
                    return None

            # 策略2: 检查是否为开发环境URL（包含 /media/）
            if '/media/' in url:
                # 提取 /media/ 后面的路径部分
                # http://127.0.0.1:6066/media/oss-bucket/... → /media/oss-bucket/...
                media_index = url.find('/media/')
                local_path = url[media_index:]

                # 递归调用自己，使用策略1处理
                return FeishuImageProcessor.download_image(local_path, timeout)

            # 策略3: HTTP/HTTPS URL - 正常下载
            logger.info(f"正在从URL下载图片: {url}")
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            logger.info(f"图片下载成功，大小: {len(resp.content)}字节")
            return resp.content

        except requests.exceptions.Timeout:
            logger.warning(f"图片下载超时，跳过: {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"图片下载失败（HTTP {e.response.status_code if e.response else 'unknown'}），跳过: {url}")
            return None
        except Exception as e:
            logger.warning(f"图片处理失败（{type(e).__name__}），跳过: {url}, 错误: {str(e)}")
            return None

    @staticmethod
    def upload_image_to_feishu(
        token: str,
        document_id: str,
        block_id: str,
        image_bytes: bytes
    ) -> Optional[str]:
        """
        上传图片到飞书

        Args:
            token: 飞书租户访问令牌
            document_id: 文档ID
            block_id: 块ID
            image_bytes: 图片字节流

        Returns:
            Optional[str]: 飞书file_token，失败返回None
        """
        url = 'https://open.feishu.cn/open-apis/drive/v1/medias/upload_all'
        headers = {'Authorization': f'Bearer {token}'}

        data = {
            'file_name': 'image.png',
            'extra': json.dumps({'drive_route_token': document_id}),
            'parent_type': 'docx_image',
            'parent_node': block_id,
            'size': str(len(image_bytes))
        }
        files = {'file': ('image.png', image_bytes)}

        try:
            logger.info(f"正在上传图片到飞书，块ID: {block_id}，大小: {len(image_bytes)}字节")
            resp = requests.post(url, data=data, files=files, headers=headers, timeout=30)
            resp.raise_for_status()

            upload_data = resp.json()
            file_token = upload_data.get('data', {}).get('file_token')

            if not file_token:
                logger.warning(f"图片上传成功但未获取到file_token，块ID: {block_id}，响应: {upload_data}")
                return None

            logger.info(f"图片上传成功，file_token: {file_token}")
            return file_token

        except requests.exceptions.Timeout:
            logger.warning(f"图片上传超时，块ID: {block_id}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"图片上传失败，块ID: {block_id}, status={e.response.status_code if e.response else 'unknown'}, response={e.response.text if e.response else 'no response'}")
            return None
        except Exception as e:
            logger.warning(f"图片上传失败（{type(e).__name__}），块ID: {block_id}, 错误: {str(e)}")
            return None

    @staticmethod
    def replace_image_in_block(
        token: str,
        document_id: str,
        block_id: str,
        file_token: str
    ) -> bool:
        """
        替换文档块中的图片

        Args:
            token: 飞书租户访问令牌
            document_id: 文档ID
            block_id: 块ID
            file_token: 飞书文件token

        Returns:
            bool: 是否替换成功
        """
        url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        payload = {'replace_image': {'token': file_token}}

        try:
            logger.info(f"正在替换图片块，块ID: {block_id}")
            resp = requests.patch(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info(f"图片块替换成功，块ID: {block_id}")
            return True

        except requests.exceptions.Timeout:
            logger.warning(f"图片块替换超时，块ID: {block_id}")
            return False
        except requests.exceptions.HTTPError as e:
            logger.warning(f"图片块替换失败，块ID: {block_id}, status={e.response.status_code if e.response else 'unknown'}, response={e.response.text if e.response else 'no response'}")
            return False
        except Exception as e:
            logger.warning(f"图片块替换失败（{type(e).__name__}），块ID: {block_id}, 错误: {str(e)}")
            return False

    @staticmethod
    def process_images(
        token: str,
        document_id: str,
        blocks: List[Dict[str, Any]],
        image_url_map: List[Dict[str, Any]],
        block_id_map: Dict[str, str]
    ) -> int:
        """
        处理文档中的所有图片块（下载、上传、替换）

        Args:
            token: 飞书租户访问令牌
            document_id: 文档ID
            blocks: 块列表
            image_url_map: 块ID到图片URL的映射
            block_id_map: 临时块ID到真实块ID的映射

        Returns:
            int: 成功处理的图片数量
        """
        if not image_url_map:
            logger.info("没有需要处理的图片")
            return 0

        logger.info(f"开始处理图片，总数: {len(image_url_map)}")
        success_count = 0

        for block in blocks:
            # 检查是否为图片块（block_type=27）
            if block.get('block_type') != 27 or not block.get('image'):
                continue

            old_block_id = block.get('block_id')
            new_block_id = block_id_map.get(old_block_id, old_block_id)

            # 查找图片URL
            match = next((item for item in image_url_map if item.get('block_id') == old_block_id), None)
            image_url = match.get('image_url') if match else None
            if not image_url:
                logger.warning(f"未找到图片URL，块ID: {old_block_id}")
                continue

            # 下载图片
            image_bytes = FeishuImageProcessor.download_image(image_url)
            if not image_bytes:
                continue

            # 上传到飞书
            file_token = FeishuImageProcessor.upload_image_to_feishu(
                token, document_id, new_block_id, image_bytes
            )
            if not file_token:
                continue

            # 替换块中的图片
            if FeishuImageProcessor.replace_image_in_block(
                token, document_id, new_block_id, file_token
            ):
                success_count += 1

        logger.info(f"图片处理完成，成功: {success_count}/{len(image_url_map)}")
        return success_count
