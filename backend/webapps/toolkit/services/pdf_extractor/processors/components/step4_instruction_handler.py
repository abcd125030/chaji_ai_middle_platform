"""
Step4 指令处理器

负责调用VL模型获取图片插入指令，并解析返回结果
"""
import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from openai import OpenAI

from .step4_image_processor import ImageProcessor
from .step4_prompt_builder import InsertionPromptBuilder
from .step4_data_models import InsertionInstruction

logger = logging.getLogger('django')


class InstructionHandler:
    """插入指令处理器 - 调用VL模型获取和解析插入指令"""

    def __init__(self, llm_client: OpenAI, model: str = "qwen3-vl-plus"):
        """
        初始化指令处理器

        Args:
            llm_client: OpenAI客户端实例
            model: 模型名称
        """
        self.client = llm_client
        self.model = model
        self.image_processor = ImageProcessor()
        self.prompt_builder = InsertionPromptBuilder()

        logger.info(f"初始化指令处理器，模型: {model}")

    def get_insertion_instructions(
        self,
        page_text: str,
        full_page_image: np.ndarray,
        region_images: List[np.ndarray],
        page_number: int,
        output_dir: Path = None,
        region_bboxes: List[List[int]] = None
    ) -> List[InsertionInstruction]:
        """
        调用VL模型获取图片插入指令

        Args:
            page_text: 页面原始文本
            full_page_image: 完整页面截图
            region_images: 分割区域图片列表
            page_number: 页码
            output_dir: 输出目录（用于保存缩放后的图像）
            region_bboxes: 分割区域bbox坐标列表 [[x1,y1,x2,y2], ...], 与region_images对应

        Returns:
            InsertionInstruction对象列表
        """
        try:
            # 缩放完整页面图像（发送给VL模型）
            resized_full_page = self.image_processor.resize_image_for_vl(
                full_page_image,
                max_dimension=1440
            )

            # 保存缩放后的图像（如果指定了输出目录）
            if output_dir:
                self.image_processor.save_resized_image(resized_full_page, output_dir)

            # 将缩放后的完整页面图像转为base64
            full_page_base64 = self.image_processor.image_to_base64(resized_full_page)

            # 将分割图片转为base64（保持原始尺寸）
            region_base64_list = []
            for region_img in region_images:
                region_base64_list.append(
                    self.image_processor.image_to_base64(region_img)
                )

            # 构建消息内容
            message_content = [
                {
                    "type": "text",
                    "text": f"待处理的Markdown文本：\n\n{page_text}"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{full_page_base64}"
                    }
                }
            ]

            # 添加所有分割图片
            for region_base64 in region_base64_list:
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{region_base64}"
                    }
                })

            # 添加分析提示词
            insertion_prompt = self.prompt_builder.build_insertion_prompt(
                page_number,
                len(region_images)
            )

            message_content.append({
                "type": "text",
                "text": insertion_prompt
            })

            logger.info(
                f"调用{self.model}分析图片插入位置，"
                f"文本长度: {len(page_text)}, "
                f"分割图片数: {len(region_images)}"
            )

            # 调用API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": message_content
                    }
                ],
                temperature=0.1,
                stream=False
            )

            response_text = completion.choices[0].message.content
            logger.info(f"收到VL响应: {len(response_text)} 字符")

            # 保存模型响应到文件
            if output_dir:
                response_path = output_dir / "step4_model_response.json"
                with open(response_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "page_number": page_number,
                        "model": self.model,
                        "response": response_text,
                        "text_length": len(page_text),
                        "region_count": len(region_images)
                    }, f, indent=2, ensure_ascii=False)
                logger.info(f"保存模型响应: {response_path}")

            # 解析JSON响应，创建InsertionInstruction对象
            instructions = self._parse_instructions(response_text, region_bboxes)
            logger.info(f"解析到 {len(instructions)} 条插入指令")

            return instructions

        except json.JSONDecodeError as e:
            logger.error(f"解析VL返回的JSON失败: {str(e)}", exc_info=True)
            logger.error(f"原始响应: {response_text[:500]}")
            return []
        except Exception as e:
            logger.error(f"获取插入指令失败: {str(e)}", exc_info=True)
            return []

    def _parse_instructions(
        self,
        response_text: str,
        region_bboxes: List[List[int]] = None
    ) -> List[InsertionInstruction]:
        """
        解析VL模型返回的JSON指令，创建InsertionInstruction对象

        Args:
            response_text: 模型返回的原始文本
            region_bboxes: 分割区域bbox坐标列表，与image_index对应

        Returns:
            InsertionInstruction对象列表

        Raises:
            json.JSONDecodeError: JSON解析失败
        """
        # 尝试提取JSON部分（可能包含markdown代码块）
        json_match = re.search(r'```json\s*(\[.*?\])\s*```', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # 直接尝试解析整个响应
            json_text = response_text.strip()

        raw_instructions = json.loads(json_text)

        # 创建InsertionInstruction对象列表
        instructions = []
        for inst_dict in raw_instructions:
            image_index = inst_dict.get('image_index')

            # 获取对应的bbox坐标
            bbox = [0, 0, 0, 0]  # 默认值
            if region_bboxes and image_index and image_index <= len(region_bboxes):
                bbox = region_bboxes[image_index - 1]  # image_index从1开始

            # 创建InsertionInstruction对象
            instruction = InsertionInstruction(
                image_index=image_index,
                image_type=inst_dict.get('image_type', 'image'),
                description=inst_dict.get('description', f'图片{image_index}'),
                anchor_text=inst_dict.get('anchor_text', ''),
                bbox=bbox,
                operation=inst_dict.get('operation', 'insert_after'),
                reason=inst_dict.get('reason', '')
            )

            # 验证指令合法性
            if not instruction.validate():
                logger.warning(
                    f"图片 {image_index} 指令验证失败: "
                    f"bbox={instruction.bbox}, anchor_len={len(instruction.anchor_text)}, "
                    f"operation={instruction.operation}"
                )
                # 仍然添加，由后续逻辑处理

            instructions.append(instruction)

        return instructions
