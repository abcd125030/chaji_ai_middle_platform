#!/usr/bin/env python3
"""
基于Qwen3-VL-Plus的智能语义分割系统

文件功能：
使用通义千问VL-Plus模型对PDF页面进行智能语义分割，识别并提取页面中的图示区域。

输入：
- PDF文档路径
- 页面编号
- DPI设置（默认300）
- 可选：分割示例图片（绿色框标记需要提取的区域）

输出：
- 原始页面图像
- 初始分割可视化 + 元数据
- 校准后分割可视化 + 元数据（如果需要）
- 最终版本可视化
- 各个识别区域的独立图像文件
- 完整元数据JSON

核心特点：
- 直接使用VL模型进行语义理解，无需SAM预分割
- 精准识别图表、流程图、示意图等视觉元素
- 实验性自我校准功能：VL模型检查自己的输出并调整
- 输出结构化的区域信息，便于后续文档重构

提示词设计原理：
1. 目标明确：只提取需要以图片形式保留在Markdown中的视觉内容
2. 坐标系统：使用百分比（0-100）而非固定比例，适应任意宽高比图像
3. 示例引导：支持提供绿色框标记的示例图，让模型学习分割粒度
4. 排除纯文本：明确告知模型不提取纯文本段落（通过其他方式提取）

实验记录（2025-09-30）：
- 初版问题：全页分割，产生过多无关segments
- 改进1：明确"只提取视觉元素"，减少纯文本提取
- 改进2：从1000单位系统改为百分比系统，解决宽高比问题
- 改进3：添加自我校准流程，VL模型查看可视化结果并修正坐标
- 校准实验结果：不稳定，可能让结果变差（已默认禁用）
  问题：VL模型看到可视化后反而扩大了边界框，包含了无关内容
  原因：可能是提示词不够精确，或模型对"完整性"理解有偏差
"""

import os
import sys
import json
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import io
import fitz  # PyMuPDF
from openai import OpenAI

# 尝试加载dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

@dataclass
class ImageRegion:
    """图像区域定义"""
    id: int
    type: str  # diagram, chart, table, formula, photo, text_block, title
    description: str
    bbox: List[int]  # [x, y, width, height] in pixels
    confidence: float
    semantic_label: str  # 语义标签，如"architecture_diagram", "flow_chart"等
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_dict_with_percentage(self, image_width: int, image_height: int) -> Dict:
        """返回包含百分比坐标的字典"""
        data = asdict(self)
        # 添加百分比坐标 [左上x%, 左上y%, 右下x%, 右下y%]
        data['bbox_percentage'] = [
            round(self.bbox[0] * 100.0 / image_width, 2),  # 左上角x%
            round(self.bbox[1] * 100.0 / image_height, 2),  # 左上角y%
            round((self.bbox[0] + self.bbox[2]) * 100.0 / image_width, 2),  # 右下角x%
            round((self.bbox[1] + self.bbox[3]) * 100.0 / image_height, 2)  # 右下角y%
        ]
        return data

class Qwen3VLSegmentation:
    """基于Qwen3-VL-Plus的语义分割器"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "qwen3-vl-plus", 
                 example_image_path: Optional[str] = None):
        """
        初始化分割器
        
        Args:
            api_key: DashScope API密钥
            model: 使用的模型名称
            example_image_path: 分割示例图片路径
        """
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.model = model
        
        # 设置示例图片路径（默认路径）
        # 注意：示例图片可能会干扰某些页面的识别，建议谨慎使用
        self.example_image_path = example_image_path
        # 如果没有明确指定示例图片，默认不使用
        # self.example_image_path = example_image_path or "/Users/chagee/Repos/chagee-utils/ppt_extractor/segmentation_example.png"
        
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY not found in environment variables")
        
        # 初始化OpenAI客户端（兼容模式）
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=DASHSCOPE_BASE_URL
        )
        
        print(f"✅ Initialized Qwen3-VL Segmentation with model: {self.model}")
        
        # 检查示例图片是否存在
        if self.example_image_path and Path(self.example_image_path).exists():
            print(f"📎 Using segmentation example: {self.example_image_path}")
        elif self.example_image_path:
            print(f"ℹ️ No example image found at: {self.example_image_path}")
        else:
            print("ℹ️ No example image specified")
    
    def pdf_to_image(self, pdf_path: str, page_number: int = 1, dpi: int = 300) -> np.ndarray:
        """
        将PDF页面转换为图像
        
        Args:
            pdf_path: PDF文件路径
            page_number: 页面编号（从1开始）
            dpi: 输出图像的DPI
            
        Returns:
            图像数组
        """
        doc = fitz.open(pdf_path)
        page = doc[page_number - 1]
        
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        image = np.array(img)
        
        doc.close()
        return image
    
    def analyze_image_regions(self, image: np.ndarray) -> List[ImageRegion]:
        """
        使用Qwen3-VL-Plus分析图像并识别区域
        
        Args:
            image: 输入图像数组
            
        Returns:
            识别出的区域列表
        """
        # 将图像编码为base64
        _, buffer = cv2.imencode('.png', cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 准备消息内容
        message_content = []
        
        # 如果有示例图片，先添加示例
        if self.example_image_path and Path(self.example_image_path).exists():
            try:
                # 读取示例图片
                example_img = Image.open(self.example_image_path)
                example_np = np.array(example_img)
                
                # 编码示例图片
                _, example_buffer = cv2.imencode('.png', cv2.cvtColor(example_np, cv2.COLOR_RGB2BGR))
                example_base64 = base64.b64encode(example_buffer).decode('utf-8')
                
                # 添加示例图片和说明
                message_content.extend([
                    {
                        "type": "text",
                        "text": "参考这个分割示例图，图中仅绿色框代表符合分割的区域，理解如何识别和分割文档中的不同区域："
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{example_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "现在请按照示例图中绿色框的精确边界方式，分析下面这张图片。注意：绿色框紧密贴合内容，没有多余空白。请用同样精确的方式提取视觉元素区域："
                    }
                ])
                print("   📎 Added segmentation example to request")
            except Exception as e:
                print(f"   ⚠️ Failed to load example image: {e}")
        
        # 添加要分析的图片
        message_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img_base64}"
            }
        })
        
        # 添加提示词
        prompt = self._build_segmentation_prompt()
        message_content.append({
            "type": "text",
            "text": prompt
        })
        
        try:
            print("📡 Calling Qwen3-VL-Plus for semantic segmentation...")
            
            # 调用API进行分析
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": message_content
                    }
                ],
                temperature=0.1,  # 低温度以获得更一致的结果
                stream=False
            )
            
            response = completion.choices[0].message.content
            print(f"✅ Received response: {len(response)} characters")
            
            # 打印原始响应以便调试
            print("\n📝 Raw VL Model Response:")
            print("-" * 60)
            print(response[:1000] if len(response) > 1000 else response)  # 打印前1000个字符
            if len(response) > 1000:
                print(f"... (truncated, total {len(response)} chars)")
            print("-" * 60)
            
            # 解析响应
            regions = self._parse_vl_response(response, image.shape)
            print(f"📊 Identified {len(regions)} regions")
            
            return regions
            
        except Exception as e:
            print(f"❌ Error calling Qwen3-VL: {e}")
            return []
    
    def _build_segmentation_prompt(self) -> str:
        """构建语义分割的提示词"""
        base_prompt = """你是一个专业的文档视觉内容提取专家。你的任务是从文档页面中识别和提取有视觉价值的内容区域，用于后续的Markdown文档重构。

核心任务：
只提取包含视觉元素的内容区域，这些区域在转换为Markdown时需要以图片形式保留。

需要提取的内容（仅限以下类型）：
1. 示意图区域（diagram_area）：包含示意图、架构图、流程图及其相关说明文字
2. 图表区域（chart_area）：包含数据图表（柱状图、饼图、折线图等）及其标题说明
3. 图文混合区域（image_text_area）：包含产品图片、设备照片等与其说明文字的组合
4. 表格区域（table_area）：包含结构化表格，特别是带图标或视觉元素的表格
5. 公式区域（formula_area）：数学公式、化学式等特殊符号内容

不要提取的内容（忽略以下内容）：
- 纯文本段落（这些会通过其他方式提取）
- 单独的标题文字
- 页眉页脚
- 页码
- 单纯的文字列表（没有图标或视觉元素的）

关键原则：
- 每个区域必须是一个完整的视觉单元（图+其直接相关的说明文字）
- 紧密贴合内容边界，不要包含多余的空白或无关内容
- 如果有多个独立的视觉组，应该分别提取，而不是合并成一个大区域
- 判断标准：这个区域是否需要以图片形式保留在最终的Markdown中？
- 边界要精确：只框选实际内容，不要为了"安全"而扩大范围

输出格式要求：
请严格按照以下JSON格式返回结果，使用像素坐标：

{
    "bbox_format": "left_top_x, left_top_y, right_bottom_x, right_bottom_y",
    "regions": [
        {
            "id": 1,
            "type": "image_text_area", 
            "description": "设备介绍区域，包含6个设备图片及其功能说明",
            "bbox": [100, 200, 900, 600],
            "bbox_meaning": {
                "left_top_x": 100,
                "left_top_y": 200,
                "right_bottom_x": 900,
                "right_bottom_y": 600
            },
            "confidence": 0.95,
            "semantic_label": "equipment_showcase"
        }
    ]
}

重要的坐标系统说明：
- 使用像素坐标（绝对坐标）
- bbox格式必须是：[left_top_x, left_top_y, right_bottom_x, right_bottom_y]
  - left_top_x: 左上角的x像素坐标
  - left_top_y: 左上角的y像素坐标  
  - right_bottom_x: 右下角的x像素坐标（必须大于left_top_x）
  - right_bottom_y: 右下角的y像素坐标（必须大于left_top_y）
- 每个区域必须同时提供bbox和bbox_meaning字段，确保坐标含义清晰
- 精确性要求：
  - 边界要紧贴内容，不要包含大片空白
  - 宁可稍微紧一点，也不要框得太松
- 示例（假设图像尺寸2250x3250）：
  - 页面中央的小图：bbox=[900, 1300, 1350, 1950]，其中left_top=(900,1300), right_bottom=(1350,1950)
  - 左上角的内容块：bbox=[100, 150, 1125, 1000]，其中left_top=(100,150), right_bottom=(1125,1000)"""
        
        # 如果有示例图片，添加额外说明
        if self.example_image_path and Path(self.example_image_path).exists():
            base_prompt += """

重要参考：
   - 请仔细参考上面提供的分割示例图
   - 关键：示例图中只有绿色框标记的区域才是需要提取的视觉内容区域
   - 其他颜色（如红色框）是文档原有内容，不是分割标记
   - 学习示例中是如何识别"完整的视觉单元"的
   - 注意：只提取那些包含图片、图表、表格等视觉元素的区域，纯文本不要提取"""
        
        base_prompt += "\n\n请直接返回JSON格式的结果，不要包含其他解释文字。"
        
        return base_prompt
    
    def _parse_vl_response(self, response: str, image_shape: Tuple) -> List[ImageRegion]:
        """
        解析VL模型的响应
        
        Args:
            response: 模型响应文本
            image_shape: 原始图像尺寸
            
        Returns:
            解析后的区域列表
        """
        regions = []
        height, width = image_shape[:2]
        
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)
            
            # 首先检查是否有bbox_format字段
            bbox_format = data.get('bbox_format', '')
            print(f"   Declared bbox format: {bbox_format}" if bbox_format else "   No bbox format declared")
            
            # 解析区域数据
            for idx, region_data in enumerate(data.get('regions', [])):
                bbox = region_data.get('bbox', [0, 0, 100, 100])
                bbox_meaning = region_data.get('bbox_meaning', None)
                
                # 如果提供了bbox_meaning，使用它来确保正确理解坐标
                if bbox_meaning:
                    print(f"   Using bbox_meaning for region {idx+1}")
                    # 从bbox_meaning构建正确的bbox（总是[x,y,width,height]格式）
                    left_x = bbox_meaning.get('left_top_x', bbox[0])
                    left_y = bbox_meaning.get('left_top_y', bbox[1])
                    right_x = bbox_meaning.get('right_bottom_x', bbox[2])
                    right_y = bbox_meaning.get('right_bottom_y', bbox[3])
                    
                    # 计算宽高
                    width_calc = right_x - left_x
                    height_calc = right_y - left_y
                    
                    # 验证坐标合理性
                    if width_calc <= 0 or height_calc <= 0:
                        print(f"   ⚠️ Invalid bbox_meaning: width={width_calc}, height={height_calc}")
                        # 回退到原始bbox处理
                    else:
                        # 使用从bbox_meaning计算的值
                        bbox = [left_x, left_y, width_calc, height_calc]
                        print(f"   Calculated from meaning: x={left_x}, y={left_y}, w={width_calc}, h={height_calc}")
                
                # 智能判断坐标类型
                # 如果任何值大于100，说明模型可能返回了绝对坐标
                if any(val > 100 for val in bbox):
                    # 可能是绝对坐标
                    if any(val > 1000 for val in bbox):
                        # 肯定是绝对坐标（像素值）
                        # 判断是[x, y, width, height]还是[x1, y1, x2, y2]格式
                        is_x2y2_format = False
                        
                        # 检查第3个值是否可能是x2（右边界）
                        if bbox[2] > bbox[0] and bbox[2] <= width:
                            potential_width = bbox[2] - bbox[0]
                            if potential_width > 100 and potential_width < width:
                                is_x2y2_format = True
                        
                        # 检查第4个值是否可能是y2（下边界）
                        if bbox[3] > bbox[1] and bbox[3] <= height:
                            potential_height = bbox[3] - bbox[1]
                            if potential_height > 100 and potential_height < height:
                                is_x2y2_format = True
                        
                        if is_x2y2_format:
                            # [左上x, 左上y, 右下x, 右下y]格式（绝对坐标）
                            abs_bbox = [
                                int(bbox[0]),  # 左上角x坐标
                                int(bbox[1]),  # 左上角y坐标
                                int(bbox[2] - bbox[0]),  # 宽度 = 右下x - 左上x
                                int(bbox[3] - bbox[1])   # 高度 = 右下y - 左上y
                            ]
                            print(f"   Detected absolute [左上x,左上y,右下x,右下y]: {bbox} -> w={abs_bbox[2]}, h={abs_bbox[3]}")
                        else:
                            # [x, y, width, height]格式
                            abs_bbox = [int(v) for v in bbox]
                            print(f"   Detected absolute [x,y,w,h]: {bbox}")
                    else:
                        # 100-1000范围，可能是旧的1000单位系统
                        print(f"   Warning: coordinates in 100-1000 range, treating as 1000-unit system")
                        abs_bbox = [
                            int(bbox[0] * width / 1000),
                            int(bbox[1] * height / 1000),
                            int(bbox[2] * width / 1000),
                            int(bbox[3] * height / 1000)
                        ]
                else:
                    # 百分比坐标（0-100范围）- 虽然我们现在要求像素坐标，但仍保留对百分比的支持
                    abs_bbox = [
                        int(bbox[0] * width / 100),   # 左上角x坐标转像素
                        int(bbox[1] * height / 100),  # 左上角y坐标转像素
                        int((bbox[2] - bbox[0]) * width / 100),   # 宽度 = (右下角x - 左上角x)
                        int((bbox[3] - bbox[1]) * height / 100)   # 高度 = (右下角y - 左上角y)
                    ]
                    print(f"   Detected percentage [左上x,左上y,右下x,右下y]: {bbox}% -> w={abs_bbox[2]}, h={abs_bbox[3]}")
                
                # 确保边界框在图像范围内
                abs_bbox[0] = max(0, min(abs_bbox[0], width))
                abs_bbox[1] = max(0, min(abs_bbox[1], height))
                abs_bbox[2] = max(1, min(abs_bbox[2], width - abs_bbox[0]))
                abs_bbox[3] = max(1, min(abs_bbox[3], height - abs_bbox[1]))
                
                region = ImageRegion(
                    id=region_data.get('id', idx + 1),
                    type=region_data.get('type', 'unknown'),
                    description=region_data.get('description', ''),
                    bbox=abs_bbox,
                    confidence=region_data.get('confidence', 0.5),
                    semantic_label=region_data.get('semantic_label', 'general')
                )
                regions.append(region)
                
                print(f"  Region {region.id}: {region.type} - {region.description[:50]}...")
                
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse JSON response: {e}")
            print(f"Response preview: {response[:200]}...")
            
            # 降级处理：尝试基于启发式方法
            regions = self._fallback_segmentation(image_shape)
        
        return regions
    
    def _fallback_segmentation(self, image_shape: Tuple) -> List[ImageRegion]:
        """
        降级的启发式分割方法
        
        Args:
            image_shape: 图像尺寸
            
        Returns:
            基础的区域分割
        """
        height, width = image_shape[:2]
        
        # 简单的网格分割作为降级方案
        regions = []
        
        # 上半部分可能是标题
        regions.append(ImageRegion(
            id=1,
            type="title",
            description="Page header/title area",
            bbox=[0, 0, width, int(height * 0.15)],
            confidence=0.3,
            semantic_label="header"
        ))
        
        # 主体内容区域
        regions.append(ImageRegion(
            id=2,
            type="mixed",
            description="Main content area",
            bbox=[0, int(height * 0.15), width, int(height * 0.85)],
            confidence=0.3,
            semantic_label="content"
        ))
        
        print("⚠️ Using fallback segmentation (2 regions)")
        return regions
    
    def calibrate_regions_with_vl(self, image: np.ndarray, visualization: np.ndarray, 
                                   regions: List[ImageRegion]) -> List[ImageRegion]:
        """
        使用VL模型校准已识别的区域坐标
        
        Args:
            image: 原始图像
            visualization: 带标注框的可视化图像
            regions: 初始识别的区域列表
            
        Returns:
            校准后的区域列表
        """
        print("\n🔧 Calibrating regions with VL model...")
        
        # 将可视化图像编码为base64
        _, buffer = cv2.imencode('.png', cv2.cvtColor(visualization, cv2.COLOR_RGB2BGR))
        vis_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 构建校准提示词
        calibration_prompt = f"""请仔细查看这个带有蓝色边界框的标注图像。

当前标注的区域信息如下：
{json.dumps([{
    'id': r.id,
    'type': r.type,
    'description': r.description,
    'current_bbox_percentage': [
        round(r.bbox[0] * 100 / image.shape[1], 1),  # x%
        round(r.bbox[1] * 100 / image.shape[0], 1),  # y%
        round(r.bbox[2] * 100 / image.shape[1], 1),  # width%
        round(r.bbox[3] * 100 / image.shape[0], 1)   # height%
    ]
} for r in regions], indent=2, ensure_ascii=False)}

请检查每个蓝色框是否准确框选了对应的内容区域。如果发现偏差，请提供校正后的坐标。

任务要求：
1. 仔细观察每个蓝色框的位置和大小
2. 判断是否完整包含了描述中的内容
3. 如果边界不准确，提供调整后的百分比坐标

输出格式（使用百分比坐标0-100）：
{{
    "calibrated_regions": [
        {{
            "id": 1,
            "needs_adjustment": true/false,
            "reason": "框选范围偏大/偏小/位置偏移等",
            "new_bbox": [x%, y%, width%, height%]
        }}
    ]
}}

注意：
- 只有当边界明显不准确时才需要调整
- new_bbox使用百分比（0-100）
- 如果不需要调整，new_bbox可以省略"""
        
        try:
            # 调用VL模型进行校准
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{vis_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": calibration_prompt
                            }
                        ]
                    }
                ],
                temperature=0.1,
                stream=False
            )
            
            response = completion.choices[0].message.content
            print(f"   Received calibration response: {len(response)} chars")
            
            # 解析校准响应
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                calibration_data = json.loads(json_match.group())
                
                # 应用校准
                calibrated_regions = []
                height, width = image.shape[:2]
                
                for region in regions:
                    # 查找对应的校准信息
                    calibration = None
                    for cal in calibration_data.get('calibrated_regions', []):
                        if cal.get('id') == region.id:
                            calibration = cal
                            break
                    
                    if calibration and calibration.get('needs_adjustment', False):
                        # 需要调整
                        new_bbox_pct = calibration.get('new_bbox')
                        if new_bbox_pct:
                            # 转换百分比到绝对坐标
                            new_bbox = [
                                int(new_bbox_pct[0] * width / 100),
                                int(new_bbox_pct[1] * height / 100),
                                int(new_bbox_pct[2] * width / 100),
                                int(new_bbox_pct[3] * height / 100)
                            ]
                            
                            # 创建新的区域对象
                            calibrated_region = ImageRegion(
                                id=region.id,
                                type=region.type,
                                description=region.description,
                                bbox=new_bbox,
                                confidence=region.confidence,
                                semantic_label=region.semantic_label
                            )
                            calibrated_regions.append(calibrated_region)
                            
                            print(f"   ✅ Region {region.id} calibrated: {calibration.get('reason', 'adjusted')}")
                            print(f"      Old bbox%: [{round(region.bbox[0]*100/width,1)}, {round(region.bbox[1]*100/height,1)}, {round(region.bbox[2]*100/width,1)}, {round(region.bbox[3]*100/height,1)}]")
                            print(f"      New bbox%: {new_bbox_pct}")
                        else:
                            calibrated_regions.append(region)
                    else:
                        # 不需要调整
                        calibrated_regions.append(region)
                        print(f"   ✓ Region {region.id} - no adjustment needed")
                
                return calibrated_regions
                
        except Exception as e:
            print(f"   ⚠️ Calibration failed: {e}")
            print(f"   Using original regions without calibration")
            return regions
        
        return regions
    
    def extract_region(self, image: np.ndarray, region: ImageRegion) -> np.ndarray:
        """
        从图像中提取指定区域
        
        Args:
            image: 原始图像
            region: 区域定义
            
        Returns:
            裁剪的区域图像
        """
        x, y, w, h = region.bbox
        
        # 确保坐标在有效范围内
        x = max(0, x)
        y = max(0, y)
        x_end = min(image.shape[1], x + w)
        y_end = min(image.shape[0], y + h)
        
        # 裁剪区域
        cropped = image[y:y_end, x:x_end]
        
        return cropped
    
    def visualize_regions(self, image: np.ndarray, regions: List[ImageRegion]) -> np.ndarray:
        """
        创建区域可视化
        
        Args:
            image: 原始图像
            regions: 区域列表
            
        Returns:
            带标注的可视化图像
        """
        vis_image = image.copy()
        
        # 为每个区域类型定义颜色
        type_colors = {
            'diagram_area': (255, 100, 100),      # 红色 - 示意图区域
            'chart_area': (100, 255, 100),        # 绿色 - 图表区域
            'image_text_area': (100, 100, 255),   # 蓝色 - 图文混合区域
            'table_area': (255, 255, 100),        # 黄色 - 表格区域
            'formula_area': (255, 100, 255),      # 紫色 - 公式区域
            'unknown': (200, 200, 200)            # 浅灰 - 未知类型
        }
        
        # 绘制每个区域
        for region in regions:
            x, y, w, h = region.bbox
            color = type_colors.get(region.type, (200, 200, 200))
            
            # 绘制边界框
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 3)
            
            # 绘制半透明填充
            overlay = vis_image.copy()
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
            cv2.addWeighted(overlay, 0.2, vis_image, 0.8, 0, vis_image)
            
            # 添加标签背景
            label = f"#{region.id} {region.type} ({region.confidence:.2f})"
            font_scale = 0.6
            thickness = 2
            (text_width, text_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
            )
            
            # 标签背景框
            label_y = max(y - 5, text_height + 5)
            cv2.rectangle(vis_image, 
                         (x, label_y - text_height - 5),
                         (x + text_width + 10, label_y + 5),
                         color, -1)
            
            # 添加文字
            cv2.putText(vis_image, label,
                       (x + 5, label_y),
                       cv2.FONT_HERSHEY_SIMPLEX,
                       font_scale, (255, 255, 255), thickness)
            
            # 添加描述（如果不太长）
            if region.description and len(region.description) < 50:
                desc_y = label_y + text_height + 15
                cv2.putText(vis_image, region.description[:40],
                           (x + 5, min(desc_y, y + h - 5)),
                           cv2.FONT_HERSHEY_SIMPLEX,
                           0.4, color, 1)
        
        return vis_image
    
    def process_page(self, pdf_path: str, page_number: int = 1, 
                     output_dir: Optional[str] = None, dpi: int = 300) -> Dict[str, Any]:
        """
        处理PDF页面并进行语义分割
        
        Args:
            pdf_path: PDF文件路径
            page_number: 页面编号
            output_dir: 输出目录
            dpi: 图像DPI
            
        Returns:
            处理结果字典
        """
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_path}, Page {page_number}")
        print(f"{'='*60}\n")
        
        # 创建输出目录
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"./ppt/{timestamp}_qwen3_vl_segmentation"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {output_path}")
        
        # 1. 转换PDF为图像
        print("\n1️⃣ Converting PDF to image...")
        image = self.pdf_to_image(pdf_path, page_number, dpi)
        print(f"   Image size: {image.shape[1]} x {image.shape[0]} pixels")
        
        # 保存原始图像
        original_path = output_path / f"page{page_number:03d}_original.png"
        Image.fromarray(image).save(original_path)
        print(f"   Saved: {original_path}")
        
        # 2. 使用qwen3-vl-plus进行语义分割
        print("\n2️⃣ Performing semantic segmentation with Qwen3-VL-Plus...")
        regions = self.analyze_image_regions(image)
        
        if not regions:
            print("   ⚠️ No regions identified")
            return {
                'success': False,
                'message': 'No regions identified',
                'page_number': page_number,
                'output_dir': str(output_path)
            }
        
        # 3. 创建初始可视化
        print("\n3️⃣ Creating visualization...")
        visualization = self.visualize_regions(image, regions)
        
        # 保存初始版本
        vis_path_initial = output_path / f"page{page_number:03d}_visualization_initial.png"
        Image.fromarray(visualization).save(vis_path_initial)
        print(f"   Saved initial: {vis_path_initial}")
        
        # 保存初始元数据
        initial_metadata = {
            'stage': 'initial',
            'regions': [region.to_dict() for region in regions]
        }
        initial_metadata_path = output_path / f"page{page_number:03d}_metadata_initial.json"
        with open(initial_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(initial_metadata, f, indent=2, ensure_ascii=False)
        print(f"   Saved initial metadata: {initial_metadata_path}")
        
        # 3.5. 实验性功能：使用VL模型校准区域坐标
        # ⚠️ 实验结果（2025-09-30）：校准功能不稳定，可能让结果变差
        # 建议禁用：注释掉下面的代码块
        # print("\n3.5️⃣ Experimental: Calibrating with VL model...")
        # calibrated_regions = self.calibrate_regions_with_vl(image, visualization, regions)
        
        # 暂时禁用校准，直接使用初始结果
        calibrated_regions = regions
        
        # 检查是否有变化
        regions_changed = False
        for orig, calib in zip(regions, calibrated_regions):
            if orig.bbox != calib.bbox:
                regions_changed = True
                break
        
        if regions_changed:
            print("   📐 Regions were calibrated, saving calibrated version...")
            regions = calibrated_regions
            
            # 生成校准后的可视化
            visualization_calibrated = self.visualize_regions(image, regions)
            vis_path_calibrated = output_path / f"page{page_number:03d}_visualization_calibrated.png"
            Image.fromarray(visualization_calibrated).save(vis_path_calibrated)
            print(f"   Saved calibrated: {vis_path_calibrated}")
            
            # 保存校准后的元数据
            calibrated_metadata = {
                'stage': 'calibrated',
                'regions': [region.to_dict() for region in regions]
            }
            calibrated_metadata_path = output_path / f"page{page_number:03d}_metadata_calibrated.json"
            with open(calibrated_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(calibrated_metadata, f, indent=2, ensure_ascii=False)
            print(f"   Saved calibrated metadata: {calibrated_metadata_path}")
            
            # 使用校准后的版本作为最终版本
            visualization = visualization_calibrated
        else:
            print("   ✓ No calibration needed, regions are already accurate")
            # 使用初始版本作为最终版本
            visualization = visualization
        
        # 保存最终版本（便于使用）
        vis_path = output_path / f"page{page_number:03d}_visualization.png"
        Image.fromarray(visualization).save(vis_path)
        print(f"   Saved final: {vis_path}")
        
        # 4. 提取和保存各个区域
        print("\n4️⃣ Extracting individual regions...")
        extracted_files = []
        
        for region in regions:
            # 提取区域图像
            region_image = self.extract_region(image, region)
            
            # 生成文件名
            safe_type = region.type.replace(' ', '_').lower()
            filename = f"page{page_number:03d}_region{region.id:02d}_{safe_type}.png"
            filepath = output_path / filename
            
            # 保存区域图像
            Image.fromarray(region_image).save(filepath)
            extracted_files.append(filename)
            
            print(f"   Region {region.id}: {region.type} -> {filename}")
            if region.description:
                print(f"      Description: {region.description}")
        
        # 5. 保存元数据
        print("\n5️⃣ Saving metadata...")
        
        # 构建输出文件列表
        output_files = {
            'original': str(original_path.name),
            'visualization_initial': str(vis_path_initial.name),
            'metadata_initial': str(initial_metadata_path.name),
            'visualization_final': str(vis_path.name),
            'regions': extracted_files
        }
        
        # 如果进行了校准，添加校准文件
        if regions_changed:
            output_files['visualization_calibrated'] = str(vis_path_calibrated.name)
            output_files['metadata_calibrated'] = str(calibrated_metadata_path.name)
            calibration_status = 'calibrated'
        else:
            calibration_status = 'no_calibration_needed'
        
        metadata = {
            'source_pdf': str(Path(pdf_path).name),
            'page_number': page_number,
            'processing_time': datetime.now().isoformat(),
            'calibration_status': calibration_status,
            'image_size': {
                'width': image.shape[1],
                'height': image.shape[0]
            },
            'dpi': dpi,
            'total_regions': len(regions),
            'regions': [region.to_dict() for region in regions],
            'output_files': output_files
        }
        
        metadata_path = output_path / f"page{page_number:03d}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"   Saved: {metadata_path}")
        
        # 6. 生成摘要报告
        print("\n" + "="*60)
        print("✅ Processing Complete!")
        print(f"📊 Identified {len(regions)} regions:")
        
        # 统计各类型区域
        type_counts = {}
        for region in regions:
            type_counts[region.type] = type_counts.get(region.type, 0) + 1
        
        for type_name, count in sorted(type_counts.items()):
            print(f"   - {type_name}: {count} region(s)")
        
        print(f"\n📁 Results saved in: {output_path}")
        print(f"   - Original image: {original_path.name}")
        print(f"   - Visualization: {vis_path.name}")
        print(f"   - Extracted regions: {len(extracted_files)} files")
        print(f"   - Metadata: {metadata_path.name}")
        print("="*60)
        
        return {
            'success': True,
            'page_number': page_number,
            'output_dir': str(output_path),
            'total_regions': len(regions),
            'regions': [region.to_dict() for region in regions],
            'files': {
                'original': str(original_path),
                'visualization': str(vis_path),
                'metadata': str(metadata_path),
                'regions': [str(output_path / f) for f in extracted_files]
            }
        }


def main():
    """主函数：命令行接口"""
    if len(sys.argv) < 2:
        print("Usage: python qwen3_vl_segmentation.py <PDF_file> [page_number] [--output-dir DIR]")
        print("\nExamples:")
        print("  python qwen3_vl_segmentation.py document.pdf")
        print("  python qwen3_vl_segmentation.py document.pdf 2")
        print("  python qwen3_vl_segmentation.py document.pdf 1 --output-dir ./results")
        print("\nNote: Requires DASHSCOPE_API_KEY environment variable")
        sys.exit(1)
    
    # 解析参数
    pdf_path = sys.argv[1]
    page_number = 1
    output_dir = None
    
    # 解析页码
    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        page_number = int(sys.argv[2])
    
    # 解析输出目录
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]
    
    # 检查文件存在
    if not Path(pdf_path).exists():
        print(f"❌ Error: File not found - {pdf_path}")
        sys.exit(1)
    
    # 检查API密钥
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("❌ Error: DASHSCOPE_API_KEY not found in environment variables")
        print("\nPlease set it using:")
        print("  export DASHSCOPE_API_KEY='your_api_key_here'")
        sys.exit(1)
    
    try:
        # 创建分割器并处理
        segmenter = Qwen3VLSegmentation()
        result = segmenter.process_page(
            pdf_path=pdf_path,
            page_number=page_number,
            output_dir=output_dir
        )
        
        # 根据结果设置退出码
        sys.exit(0 if result['success'] else 1)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()