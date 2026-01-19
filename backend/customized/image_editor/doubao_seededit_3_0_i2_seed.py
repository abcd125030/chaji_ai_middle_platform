import json
import requests
import logging
import time
import re

# 新流程不再使用prompts_config中的提示词，直接使用内置的完整提示词

# 导入配置管理器
from .config_manager import config_manager

logger = logging.getLogger(__name__)

class DoubaoImageGenerator:
    def __init__(self, api_key, volc_access_key=None, volc_secret_key=None):
        """
        初始化火山引擎图像生成器
        
        Args:
            api_key (str): 火山引擎API密钥（用于豆包API）
            volc_access_key (str): 火山引擎Access Key（用于CV API，可选）
            volc_secret_key (str): 火山引擎Secret Key（用于CV API，可选）
        """
        self.api_key = api_key
        self.api_url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        self.api_chat_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 初始化火山引擎CV服务（用于抠图）
        self.volc_access_key = volc_access_key
        self.volc_secret_key = volc_secret_key
    
    def generate_image_from_text(self, prompt, model=None, 
                                 response_format=None, size=None, seed=None, 
                                 guidance_scale=None, watermark=None):
        """
        调用火山引擎 Seedream 3.0 T2I API 生成图片（文生图）
        
        Args:
            prompt (str): 提示词
            model (str): 模型名称，默认使用 doubao-seedream-3-0-t2i-250415
            response_format (str): 响应格式
            size (str): 图片尺寸，支持特定的尺寸列表
            seed (int): 随机种子
            guidance_scale (float): 引导比例
            watermark (bool): 是否添加水印
            
        Returns:
            tuple: (API响应结果, 使用的seed值)
        """
        # 设置默认模型为 Seedream 3.0 T2I
        if model is None:
            model = 'doubao-seedream-3-0-t2i-250415'
        
        if response_format is None:
            response_format = config_manager.get_response_format()
        
        # 对于文生图，使用特定的尺寸，默认 1024x1024
        if size is None:
            size = '1024x1024'
        
        if guidance_scale is None:
            guidance_scale = 7.5  # T2I 模型的默认值
        
        if watermark is None:
            watermark = config_manager.should_add_watermark()
        
        # 获取seed值
        if seed is None:
            seed = config_manager.get_seed()
        
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
            "size": size,
            "seed": seed,
            "guidance_scale": guidance_scale,
            "watermark": watermark
        }
        
        try:
            logger.info(f"正在使用文生图生成图片，Prompt长度: {len(prompt)}，使用seed: {seed}")
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=60)
            
            # 记录完整响应信息用于调试
            response_text = response.text if response.text else "No response body"
            
            if response.status_code != 200:
                logger.error(f"T2I API请求失败 - 状态码: {response.status_code}")
                logger.error(f"Error details - Response body: {response_text}")
                logger.error(f"Error details - Request URL: {self.api_url}")
                logger.error(f"Error details - Request payload: {json.dumps(payload, ensure_ascii=False)}")
                
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"火山引擎文生图成功")
            return result, seed  # 返回结果和使用的seed值
            
        except requests.exceptions.RequestException as e:
            logger.error(f"T2I API请求失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Error details - Status code: {e.response.status_code}")
                logger.error(f"Error details - Response body: {e.response.text if e.response.text else 'No response body'}")
            return None, seed
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"Error details - Response text: {response.text if 'response' in locals() else 'Response not available'}")
            return None, seed
    
    def generate_image(self, image_url, prompt=None, model=None, 
                      response_format=None, size=None, seed=None, 
                      guidance_scale=None, watermark=None):
        """
        调用火山引擎API生成图片
        
        Args:
            image_url (str): 输入图片URL
            prompt (str): 提示词
            model (str): 模型名称
            response_format (str): 响应格式
            size (float): 图片尺寸
            seed (int): 随机种子，默认为None，将自动生成随机数
            guidance_scale (float): 引导比例
            watermark (bool): 是否添加水印
            
        Returns:
            tuple: (API响应结果, 使用的seed值)
        """
        # 从配置管理器获取默认值
        if prompt is None:
            prompt = config_manager.get_default_prompt()
        
        if model is None:
            model = config_manager.get_generation_model()
        
        if response_format is None:
            response_format = config_manager.get_response_format()
        
        if size is None:
            size = config_manager.get_image_size()
        
        if guidance_scale is None:
            guidance_scale = config_manager.get_guidance_scale()
        
        if watermark is None:
            watermark = config_manager.should_add_watermark()
        
        # 获取seed值
        if seed is None:
            seed = config_manager.get_seed()
        
        payload = {
            "model": model,
            "prompt": prompt,
            "image": image_url,
            "response_format": response_format,
            "size": size,
            # "seed": seed,
            "guidance_scale": guidance_scale,
            "watermark": watermark
        }
        
        try:
            logger.info(f"正在生成图片，输入URL: {image_url}，使用seed: {seed}")
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=60)
            
            # 记录完整响应信息用于调试
            response_text = response.text if response.text else "No response body"
            
            if response.status_code != 200:
                logger.error(f"API请求失败 - 状态码: {response.status_code}")
                logger.error(f"Error details - Response body: {response_text}")
                logger.error(f"Error details - Request URL: {self.api_url}")
                logger.error(f"Error details - Request payload: {json.dumps(payload, ensure_ascii=False)}")
                
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"火山引擎图片生成成功")
            return result, seed  # 返回结果和使用的seed值
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Error details - Status code: {e.response.status_code}")
                logger.error(f"Error details - Response body: {e.response.text if e.response.text else 'No response body'}")
            return None, seed
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"Error details - Response text: {response.text if 'response' in locals() else 'Response not available'}")
            return None, seed

    def check_object_is_only_animal(self, image_url, prompt=None, model=None):
        """
        调用火山引擎API进行图片内容检测
        
        Args:
            image_url (str): 输入图片URL
            prompt (str): 提示词
            model (str): 模型名称
            
        Returns:
            dict: 检测结果，格式为 {
                "object_is_only_animal": bool,  # 是否仅包含动物（宠物）且合规
                "reason_for_false": str/None,   # 不合规原因代码（A-F）或null
                "pet_description": str/None     # 合规时的宠物描述或null
            }
        """
        # 从配置管理器获取模型
        if model is None:
            model = config_manager.get_detection_model()
        
        if prompt is None:
            # 从配置管理器获取提示词
            prompt = config_manager.get_detection_prompt()
            if not prompt:
                # 如果配置中没有设置，使用默认提示词
                prompt = """你必须分析图片并输出JSON格式的结果。

<purpose>
检测图片内容是否合规。特别注意：动物的交配、生殖、繁殖行为属于不合规内容。需要检测是否存在暴力、色情内容，以及图片内容的主体是否仅为动物（宠物）且不包含人类。
如果图片合规，你必须生成极其详细和精确的宠物描述，用于文生图模型重建。
</purpose>

<options_for_false_reason>
- A: 图片包含暴力内容
- B: 图片包含色情内容（特别包括但不限于：动物交配、动物生殖器官展示、动物繁殖行为、动物求偶行为等）
- C: 图片主体不是动物
- D: 图片包含完整的人类面部或上半身躯干肢体
- E: 图片质量过低（分辨率或清晰度不足）
- F: 图片包含多个主体
</options_for_false_reason>

<pet_description_requirements>
如果图片合规，你必须提供一个极其详细、精确的宠物描述，包含以下所有方面：

1. **品种与体型**：准确的品种名称、体型大小、身材比例
2. **毛发特征**：
   - 毛发长度（短毛/中长毛/长毛）
   - 毛发质地（直毛/卷毛/波浪毛、粗糙/柔软/丝滑）
   - 毛发密度和蓬松程度
3. **颜色与花纹**：
   - 主色调和次要色调的精确描述
   - 特殊花纹或斑点的位置、形状、大小
   - 渐变色或混色区域的描述
4. **面部特征**：
   - 眼睛：颜色、大小、形状、神态
   - 鼻子：颜色、湿润度
   - 嘴巴：是否张开、舌头位置
   - 耳朵：形状、位置、朝向（立耳/垂耳/半立）
5. **姿态与动作**：
   - 身体姿势（站立/坐姿/卧姿/奔跑/跳跃等）
   - 头部朝向和角度
   - 四肢位置和动作
   - 尾巴位置和状态（上翘/下垂/摇摆等）
6. **特殊细节**：
   - 任何独特的标记或特征（如额头的星形斑、脚掌的白袜等）
   - 配饰（项圈、铃铛、衣服等）的颜色、材质、样式
   - 表情和情绪状态（警觉/放松/兴奋/好奇等）
7. **环境关系**：
   - 宠物在画面中的位置
   - 与地面的接触关系
   - 光照方向和阴影

描述要求：
- 使用精确、具体的词汇
- 按照从整体到局部、从主要到次要的顺序
- 包含所有可见的细节特征
- 描述长度：80-100字
</pet_description_requirements>

<output_rules>
你必须输出一个纯JSON对象，不允许添加任何额外的文字说明、markdown标记或代码块标记。
直接输出JSON，不允许用```json和```包裹。

JSON必须包含以下三个字段（缺一不可）：
1. "object_is_only_animal": boolean类型 - 是否仅包含动物（宠物）且合规
2. "reason_for_false": string类型或null - 如果不合规，必须提供原因代码（A-F）；如果合规，必须为null
3. "pet_description": string类型或null - 如果合规，必须提供80-100字的简洁宠物描述；如果不合规，必须为null

重要：
- 当object_is_only_animal为true时，pet_description字段必须包含80-100字的宠物描述，不能为null或空字符串！
- 输出格式必须是标准JSON，可以直接被JSON.parse()解析
- 不要在JSON前后添加任何文字或符号

正确的输出格式（合规情况）：
{"object_is_only_animal":true,"reason_for_false":null,"pet_description":"一只成年金毛寻回犬，金棕色长毛，体型健壮。深棕色大眼睛，黑色鼻子，耳朵自然下垂。正以坐姿面向镜头，前腿笔直，尾巴自然下垂。佩戴深蓝色项圈，表情友善放松。"}

正确的输出格式（不合规情况）：
{"object_is_only_animal":false,"reason_for_false":"D","pet_description":null}
</output_rules>

现在请分析图片，并严格按照上述要求输出JSON。记住：如果图片是合规的宠物图片，你必须在pet_description字段中提供80-100字的简洁描述，不能返回null！"""
        
        # 记录实际使用的提示词
        logger.info(f"实际使用的检测提示词长度: {len(prompt)}")
        logger.info(f"提示词: {prompt}")
        logger.info(f"提示词是否包含'pet_description': {'pet_description' in prompt}")
        
        # 构建新的消息格式，添加response_format参数以强制结构化输出
        # 添加系统消息以增强输出可靠性
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的图像内容分析助手。你必须输出纯JSON格式的结果，不要使用markdown代码块或任何其他格式包装。直接输出可以被JSON.parse()解析的标准JSON对象。当图片包含宠物且合规时，你必须提供简洁的宠物描述（80-100字）。"
                },
                {
                    "content": [
                        {
                            "image_url": {
                                "url": image_url
                            },
                            "type": "image_url"
                        },
                        {
                            "text": prompt,
                            "type": "text"
                        }
                    ],
                    "role": "user"
                }
            ],
            "temperature": 0.3
        }
        
        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"正在检测图片内容，输入URL: {image_url} (尝试 {attempt + 1}/{max_retries})")
                # 使用聊天API端点而不是图像生成端点
                response = requests.post(self.api_chat_url, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"图片检测成功")
                
                # 解析聊天API返回的结果
                if "choices" in result and len(result["choices"]) > 0:
                    message_content = result["choices"][0]["message"]["content"]
                    
                    try:
                        # 处理text类型返回，可能是纯JSON或被```包裹的JSON
                        logger.info(f"API返回的原始内容: {result}")  # 添加日志查看原始返回
                        logger.info(f"消息内容主体: {message_content.strip()}")
                        
                        # 清理内容：去除可能的markdown代码块标记
                        cleaned_content = message_content.strip()
                        
                        # 检查是否被```json或```包裹
                        if cleaned_content.startswith("```"):
                            # 找到第一个换行符后的内容
                            lines = cleaned_content.split('\n')
                            # 移除第一行（```json或```）和最后一行（```）
                            if len(lines) >= 3 and lines[-1].strip() == "```":
                                cleaned_content = '\n'.join(lines[1:-1])
                            else:
                                # 只有开始标记，没有结束标记的情况
                                cleaned_content = '\n'.join(lines[1:])
                        
                        # 再次清理空白字符
                        cleaned_content = cleaned_content.strip()
                        
                        # 尝试解析JSON
                        parsed_content = json.loads(cleaned_content)
                        logger.info(f"解析JSON响应成功: {parsed_content}")
                        
                        # 验证必需字段
                        if "object_is_only_animal" not in parsed_content:
                            logger.warning("缺少必需字段 'object_is_only_animal'，使用默认值 False")
                        
                        # 提取需要的字段
                        simplified_result = {
                            "object_is_only_animal": parsed_content.get("object_is_only_animal", False),
                            "reason_for_false": parsed_content.get("reason_for_false"),
                            "pet_description": parsed_content.get("pet_description")
                        }
                        
                        # 验证reason_for_false的值是否合法（如果提供了）
                        valid_reasons = ['A', 'B', 'C', 'D', 'E', 'F']
                        if simplified_result["reason_for_false"] and simplified_result["reason_for_false"] not in valid_reasons:
                            logger.warning(f"无效的reason_for_false值: {simplified_result['reason_for_false']}")
                        
                        # 验证逻辑一致性：如果图片合规，必须有宠物描述
                        if simplified_result["object_is_only_animal"] == True:
                            if not simplified_result["pet_description"] or len(simplified_result["pet_description"].strip()) < 30:
                                logger.warning(f"检测通过但宠物描述缺失或过短，重试检测 - 尝试 {attempt + 1}/{max_retries}")
                                if attempt < max_retries - 1:
                                    continue  # 重试
                                else:
                                    # 最后一次尝试，返回错误而不是失败的检测结果
                                    logger.error("多次尝试后仍无法获取有效的宠物描述")
                                    return {
                                        "object_is_only_animal": None,  # 返回None表示服务异常
                                        "reason_for_false": None,
                                        "pet_description": None,
                                        "error": True,
                                        "error_details": {
                                            "error_type": "PetDescriptionGenerationFailed",
                                            "error_message": "AI模型识别到宠物但未能生成有效的描述文本",
                                            "detection_result": simplified_result
                                        }
                                    }
                        
                        logger.info(f"解析结果: {simplified_result}")
                        return simplified_result
                        
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.error(f"解析消息内容失败: {e}, 原始内容: {message_content}")
                        if attempt == max_retries - 1:  # 最后一次尝试
                            # 返回包含错误详情的字典
                            return {
                                "object_is_only_animal": None,
                                "reason_for_false": None,
                                "error": True,
                                "error_details": {
                                    "error_type": "ParseError",
                                    "error_message": f"解析消息内容失败: {str(e)}",
                                    "raw_content": message_content,
                                    "attempt": f"{attempt + 1}/{max_retries}"
                                }
                            }
                        continue
                else:
                    logger.error("API响应格式异常，缺少choices字段")
                    if attempt == max_retries - 1:  # 最后一次尝试
                        return {
                            "object_is_only_animal": None,
                            "reason_for_false": None,
                            "error": True,
                            "error_details": {
                                "error_type": "ResponseFormatError",
                                "error_message": "API响应格式异常，缺少choices字段",
                                "response": result,
                                "attempt": f"{attempt + 1}/{max_retries}"
                            }
                        }
                    continue
                
            except requests.exceptions.RequestException as e:
                logger.error(f"API请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                error_details = {
                    "error_type": "RequestException",
                    "error_message": str(e),
                    "request_url": self.api_chat_url,
                    "attempt": f"{attempt + 1}/{max_retries}"
                }
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Error details - Status code: {e.response.status_code}")
                    logger.error(f"Error details - Response body: {e.response.text if e.response.text else 'No response body'}")
                    logger.error(f"Error details - Request URL: {self.api_chat_url}")
                    error_details["status_code"] = e.response.status_code
                    error_details["response_body"] = e.response.text if e.response.text else 'No response body'
                if attempt < max_retries - 1:
                    time.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    # 返回包含错误详情的字典，让tasks.py可以获取完整错误信息
                    return {
                        "object_is_only_animal": None,
                        "reason_for_false": None,
                        "error": True,
                        "error_details": error_details
                    }
    
    def check_consistency(self, original_url, generated_url, prompt=None, model="doubao-1.5-vision-pro-250328"):
        """
        检测生成图片与原图的一致性
        
        Args:
            original_url (str): 原始图片URL
            generated_url (str): 生成的图片URL
            prompt (str): 检测提示词
            model (str): 模型名称
            
        Returns:
            dict: 检测结果，格式为 {"is_consistent": bool, "inconsistent_reason": str/None, "score": float}
        """
        if prompt is None:
            # 使用默认的一致性检测提示词
            prompt = """<purpose>
对比两张图片，检测生成图片与原图的一致性。主要检查：
1. 主体是否为同一只宠物（品种、毛色、体型特征）
2. 生成质量是否达标（清晰度、完整性）
3. 是否存在明显的生成缺陷（畸形、错位、比例失调等）
</purpose>

<evaluation_criteria>
- 主体一致性（60分）：是否为同一只宠物，品种、毛色、体型特征是否保持一致
- 生成质量（30分）：图片清晰度、完整性、无明显噪点或模糊
- 无缺陷（10分）：无畸形、错位、比例失调等明显缺陷
</evaluation_criteria>

<inconsistent_reasons>
- A: 主体不是同一只宠物（品种或特征完全不同）
- B: 生成质量过低（模糊、噪点过多、无法识别）
- C: 存在严重畸形或错位
- D: 生成不完整或有明显缺失部分
- E: 其他严重问题
</inconsistent_reasons>

<output_rules>
Output must be valid JSON without ``` marks:
{
    "is_consistent": boolean,
    "inconsistent_reason": option-value or null,
    "score": float (0-100)
}

判定标准：
- score >= 70: is_consistent = true
- score < 70: is_consistent = false，需要提供inconsistent_reason
</output_rules>"""
        
        # 构建消息格式，包含两张图片
        payload = {
            "model": model,
            "messages": [
                {
                    "content": [
                        {
                            "type": "text",
                            "text": "原始图片："
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": original_url
                            }
                        },
                        {
                            "type": "text",
                            "text": "生成的图片："
                        },
                        {
                            "type": "image_url", 
                            "image_url": {
                                "url": generated_url
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                    "role": "user"
                }
            ]
        }
        
        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"正在进行一致性检测 (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(self.api_chat_url, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"一致性检测API调用成功")
                
                # 解析返回结果
                if "choices" in result and len(result["choices"]) > 0:
                    message_content = result["choices"][0]["message"]["content"]
                    
                    try:
                        # 智能JSON提取
                        try:
                            parsed_content = json.loads(message_content.strip())
                        except json.JSONDecodeError:
                            # 提取JSON内容
                            code_block_pattern = r'```(?:json)?\s*(.*?)\s*```'
                            code_match = re.search(code_block_pattern, message_content, re.DOTALL)
                            
                            if code_match:
                                json_str = code_match.group(1).strip()
                            else:
                                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                                json_match = re.search(json_pattern, message_content)
                                
                                if json_match:
                                    json_str = json_match.group(0)
                                else:
                                    json_str = message_content.strip()
                            
                            # 修复常见格式问题
                            json_str = re.sub(r'\bTrue\b', 'true', json_str)
                            json_str = re.sub(r'\bFalse\b', 'false', json_str)
                            json_str = re.sub(r'\bNone\b', 'null', json_str)
                            json_str = re.sub(r"'([^']+)'(\s*:)", r'"\1"\2', json_str)
                            json_str = re.sub(r":\s*'([^']*)'(?=[,}])", r': "\1"', json_str)
                            
                            parsed_content = json.loads(json_str)
                        
                        # 验证并提取结果
                        consistency_result = {
                            "is_consistent": parsed_content.get("is_consistent", False),
                            "inconsistent_reason": parsed_content.get("inconsistent_reason"),
                            "score": parsed_content.get("score", 0.0)
                        }
                        
                        logger.info(f"一致性检测结果: {consistency_result}")
                        return consistency_result
                        
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.error(f"解析一致性检测结果失败: {e}, 原始内容: {message_content}")
                        if attempt == max_retries - 1:
                            return {
                                "is_consistent": None,
                                "inconsistent_reason": None,
                                "score": None,
                                "error": True,
                                "error_details": {
                                    "error_type": "ParseError",
                                    "error_message": f"解析一致性检测结果失败: {str(e)}",
                                    "raw_content": message_content,
                                    "attempt": f"{attempt + 1}/{max_retries}"
                                }
                            }
                        continue
                else:
                    logger.error("一致性检测API响应格式异常")
                    if attempt == max_retries - 1:
                        return {
                            "is_consistent": None,
                            "inconsistent_reason": None,
                            "score": None,
                            "error": True,
                            "error_details": {
                                "error_type": "ResponseFormatError",
                                "error_message": "一致性检测API响应格式异常",
                                "response": result,
                                "attempt": f"{attempt + 1}/{max_retries}"
                            }
                        }
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"一致性检测API请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                error_details = {
                    "error_type": "RequestException",
                    "error_message": str(e),
                    "request_url": self.api_chat_url,
                    "attempt": f"{attempt + 1}/{max_retries}"
                }
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Error details - Status code: {e.response.status_code}")
                    logger.error(f"Error details - Response body: {e.response.text if e.response.text else 'No response body'}")
                    logger.error(f"Error details - Request URL: {self.api_chat_url}")
                    error_details["status_code"] = e.response.status_code
                    error_details["response_body"] = e.response.text if e.response.text else 'No response body'
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return {
                        "is_consistent": None,
                        "inconsistent_reason": None,
                        "score": None,
                        "error": True,
                        "error_details": error_details
                    }
            except Exception as e:
                logger.error(f"一致性检测意外错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return {
                        "is_consistent": None,
                        "inconsistent_reason": None,
                        "score": None,
                        "error": True,
                        "error_details": {
                            "error_type": "UnexpectedError",
                            "error_message": f"一致性检测意外错误: {str(e)}",
                            "exception_type": type(e).__name__,
                            "attempt": f"{attempt + 1}/{max_retries}"
                        }
                    }
    
    def remove_background(self, image_url):
        """
        调用火山引擎主体分割API去除背景
        
        Args:
            image_url (str): 输入图片URL
            
        Returns:
            dict: 包含处理结果的字典，格式为 {"success": bool, "image_base64": str, "error": str}
        """
        if not self.volc_access_key or not self.volc_secret_key:
            logger.warning("背景移除功能需要配置火山引擎CV服务的Access Key和Secret Key")
            return {"success": False, "error": "背景移除服务未配置"}
        
        try:
            # 使用新的CV服务类
            from .volcengine_cv_service import VolcengineCVService
            cv_service = VolcengineCVService(self.volc_access_key, self.volc_secret_key)
            return cv_service.remove_background(image_url)
        except Exception as e:
            logger.error(f"调用背景移除服务失败: {e}")
            return {"success": False, "error": f"背景移除服务异常: {str(e)}"}
