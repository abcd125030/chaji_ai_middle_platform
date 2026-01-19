"""
OCR模型服务 - API中转层
封装对私有化部署的OCR模型API的调用，主要用于PDF解析
支持批量多张图片base64输入
"""
import logging
import requests
import re
import base64
from typing import Dict, Optional, Any, List, Tuple
from io import BytesIO
from .config import OCRModelConfig

logger = logging.getLogger('django')


class OCRModelService:
    """
    OCR模型API中转服务类

    封装对内网部署的OCR模型API(http://172.22.217.66:9123)的调用
    支持批量多张图片处理，使用base64传输
    主要用于PDF文档的解析和文本提取
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        timeout: int = 300
    ):
        """
        初始化OCR模型API服务

        Args:
            api_url: OCR API地址，默认从配置读取
            timeout: 请求超时时间（秒），默认300秒
        """
        self.api_url = api_url or OCRModelConfig.API_URL
        self.timeout = timeout

        logger.info(f"初始化OCR模型API服务 - api_url: {self.api_url}, timeout: {timeout}s")

    def health_check(self) -> Dict[str, Any]:
        """
        检查OCR API服务健康状态

        Returns:
            Dict包含：
            - success: bool 是否成功
            - status: str 服务状态
            - error: Optional[str] 错误信息
        """
        try:
            logger.info(f"检查OCR API健康状态: {self.api_url}/health")
            response = requests.get(
                f"{self.api_url}/health",
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"OCR API健康检查成功: {result}")
            return {
                'success': True,
                'status': result.get('status', 'unknown'),
                'data': result
            }

        except Exception as e:
            error_msg = f"OCR API健康检查失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }

    def ocr_images(
        self,
        images_base64: List[str],
        mode: str = 'convert_to_markdown',
        max_tokens: int = 8192,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        批量识别多张图片（核心方法）

        Args:
            images_base64: base64编码的图片列表
            mode: 处理模式，默认'convert_to_markdown'
            max_tokens: 最大token数
            temperature: 温度参数

        Returns:
            Dict包含：
            - success: bool 是否成功
            - results: List[Dict] 每张图片的识别结果列表
                - result: str Markdown格式的原始识别结果
                - result_cleaned: str 清理后的结果（图片标记替换为[[[!image]]]）
                - image_size: List[int] 图片尺寸 [width, height]
                - mode: str 处理模式
                - image_count: int 检测到的图片标记数量
            - total: int 总图片数
            - success_count: int 成功数
            - failed_count: int 失败数
            - error: Optional[str] 错误信息
        """
        try:
            logger.info(f"开始批量OCR识别 - 图片数量: {len(images_base64)}, 模式: {mode}")

            if not images_base64:
                return {
                    'success': False,
                    'error': '图片列表不能为空'
                }

            # 准备请求数据
            data = {
                'images': images_base64,
                'mode': mode,
                'max_tokens': max_tokens,
                'temperature': temperature
            }

            # 调用OCR API批量接口
            response = requests.post(
                f"{self.api_url}/ocr/batch",
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            # 解析响应
            result_data = response.json()

            # 处理每张图片的结果
            processed_results = []
            for i, result_item in enumerate(result_data.get('results', []), 1):
                raw_result = result_item.get('result', '')

                # 清理结果（替换图片标记并提取坐标）
                cleaned_result, image_count, image_regions = self._parse_and_replace_images(raw_result)

                processed_results.append({
                    'result': raw_result,
                    'result_cleaned': cleaned_result,
                    'image_size': result_item.get('image_size', []),
                    'mode': result_item.get('mode', mode),
                    'image_count': image_count,
                    'image_regions': image_regions  # 新增: 图片区域坐标列表
                })

                logger.info(f"图片 {i}/{len(images_base64)} 识别完成 - 尺寸: {result_item.get('image_size')}, 图片标记数: {image_count}, 区域数: {len(image_regions)}")

            success_count = result_data.get('success_count', len(processed_results))
            failed_count = result_data.get('failed_count', 0)
            total = result_data.get('total', len(images_base64))

            logger.info(f"批量OCR识别完成 - 成功: {success_count}/{total}")

            return {
                'success': True,
                'results': processed_results,
                'total': total,
                'success_count': success_count,
                'failed_count': failed_count
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"OCR API请求失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"OCR处理失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }

    def ocr_image(
        self,
        image_base64: str,
        mode: str = 'convert_to_markdown',
        max_tokens: int = 8192,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        识别单张图片（便捷方法）

        Args:
            image_base64: base64编码的图片
            mode: 处理模式
            max_tokens: 最大token数
            temperature: 温度参数

        Returns:
            Dict: 单张图片的识别结果
        """
        logger.info("开始单张图片OCR识别")

        # 调用批量接口处理单张图片
        batch_result = self.ocr_images(
            images_base64=[image_base64],
            mode=mode,
            max_tokens=max_tokens,
            temperature=temperature
        )

        if not batch_result.get('success'):
            return batch_result

        # 提取第一张图片的结果
        if batch_result.get('results'):
            result = batch_result['results'][0]
            result['success'] = True
            return result
        else:
            return {
                'success': False,
                'error': '未获取到识别结果'
            }

    def ocr_image_from_bytes(
        self,
        image_bytes: bytes,
        mode: str = 'convert_to_markdown',
        max_tokens: int = 8192,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        识别图片（从字节数据）

        Args:
            image_bytes: 图片的字节数据
            mode: 处理模式
            max_tokens: 最大token数
            temperature: 温度参数

        Returns:
            Dict: 识别结果
        """
        try:
            # 将字节数据转换为base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            return self.ocr_image(
                image_base64=image_base64,
                mode=mode,
                max_tokens=max_tokens,
                temperature=temperature
            )

        except Exception as e:
            error_msg = f"图片字节转换失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }

    def ocr_images_from_bytes(
        self,
        images_bytes: List[bytes],
        mode: str = 'convert_to_markdown',
        max_tokens: int = 8192,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        批量识别图片（从字节数据）

        Args:
            images_bytes: 图片字节数据列表
            mode: 处理模式
            max_tokens: 最大token数
            temperature: 温度参数

        Returns:
            Dict: 批量识别结果
        """
        try:
            logger.info(f"转换 {len(images_bytes)} 张图片为base64")

            # 将所有字节数据转换为base64
            images_base64 = []
            for i, image_bytes in enumerate(images_bytes, 1):
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                images_base64.append(image_base64)
                logger.debug(f"图片 {i}/{len(images_bytes)} 转换完成")

            return self.ocr_images(
                images_base64=images_base64,
                mode=mode,
                max_tokens=max_tokens,
                temperature=temperature
            )

        except Exception as e:
            error_msg = f"图片批量转换失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }

    def _parse_and_replace_images(self, text: str) -> Tuple[str, int, List[List[int]]]:
        """
        解析 DeepSeek-OCR 的标记格式，将图片标记替换为 [[[!image]]]

        原始格式: <|ref|>image<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
        替换为: [[[!image]]]

        Args:
            text: 原始OCR结果文本

        Returns:
            Tuple[str, int, List[List[int]]]: (清理后的文本, 检测到的图片数量, 图片坐标列表)
            坐标格式: [[x1, y1, x2, y2], ...] (左上角, 右下角)
        """
        # 匹配图片标记: <|ref|>image<|/ref|><|det|>[[...]]<|/det|>
        image_pattern = r'<\|ref\|>image<\|/ref\|><\|det\|>\[\[(\d+,\s*\d+,\s*\d+,\s*\d+)\]\]<\|/det\|>'

        # 提取所有图片位置信息
        image_coords_raw = re.findall(image_pattern, text)
        image_count = len(image_coords_raw)

        # 解析坐标为整数列表
        image_regions = []
        if image_count > 0:
            logger.info(f"检测到 {image_count} 个图片标记")
            for i, coords_str in enumerate(image_coords_raw, 1):
                # 解析坐标字符串 "x1, y1, x2, y2" -> [x1, y1, x2, y2]
                coords = [int(c.strip()) for c in coords_str.split(',')]
                image_regions.append(coords)
                logger.info(f"  图片 {i} 坐标: {coords} (左上角: [{coords[0]}, {coords[1]}], 右下角: [{coords[2]}, {coords[3]}])")

        # 替换为 [[[!image]]]
        text = re.sub(image_pattern, '[[[!image]]]', text)

        # 清理其他标记
        # 移除 <|ref|>...<|/ref|> 和 <|det|>...<|/det|>
        text = re.sub(r'<\|ref\|>.*?<\|/ref\|>', '', text)
        text = re.sub(r'<\|det\|>\[\[.*?\]\]<\|/det\|>', '', text)

        # 清理多余的空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text, image_count, image_regions

    def get_api_info(self) -> Dict[str, Any]:
        """
        获取API服务信息

        Returns:
            Dict: API配置和状态信息
        """
        return {
            'api_url': self.api_url,
            'timeout': self.timeout,
            'supported_modes': ['convert_to_markdown', 'free_ocr', 'parse_figure', 'locate_object'],
            'supported_formats': ['jpg', 'jpeg', 'png', 'pdf'],
            'features': ['batch_processing', 'base64_input']
        }
