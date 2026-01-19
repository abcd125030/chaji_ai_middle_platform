import json
import requests
import logging
from typing import Dict, Any, Optional, List, Union, Generator
import time
import base64
from pathlib import Path

from .retry_utils import LLMRetryHandler, RetryConfig
from .log_service import LLMLogService

logger = logging.getLogger(__name__)

class CoreLLMService:
    """
    纯净的LLM调用服务
    只负责调用LLM API，不涉及鉴权和权限
    """
    
    def __init__(self):
        self._request_cache = {}
    
    def call_llm(self, model_id: str, endpoint: str, api_key: str, 
                 messages: List[Dict], custom_headers: Optional[Dict] = None, 
                 params: Optional[Dict] = None, 
                 user=None, session_id: str = None,
                 source_app: str = None, source_function: str = None,
                 model_name: str = None, vendor_name: str = None, 
                 vendor_id: str = None, enable_logging: bool = True,
                 **kwargs) -> Union[Dict, Generator]:
        """
        纯净的LLM API调用
        参数：模型配置信息 + 调用参数
        返回：LLM响应 (支持流式和非流式)
        
        新增参数:
            user: 用户对象（用于日志记录）
            session_id: 会话ID
            source_app: 来源应用
            source_function: 来源函数
            model_name: 模型名称（用于日志，如果不提供则使用model_id）
            vendor_name: 供应商名称
            vendor_id: 供应商标识
            enable_logging: 是否启用日志记录
        """
        headers = {'Content-Type': 'application/json'}
        
        # 设置API key
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        # 合并自定义headers
        if custom_headers:
            headers.update(custom_headers)
        
        # 构建payload
        payload = {
            'model': model_id,
            'messages': messages,
            **(params or {}),
            **kwargs
        }
        
        # 打印完整的LLM请求信息（单个logger调用，用于调试）
        messages_debug = []
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # 如果内容太长，截断显示
            if len(content) > 3000:
                content_display = f"{content}\n总长度: {len(content)} 字符]"
            else:
                content_display = content
            messages_debug.append(f"【Message {i+1} - Role: {role}】\n{content_display}")
        
        llm_request_debug = f"""
{"=" * 60}
🤖 LLM 调用请求
模型: {model_id}
端点: {endpoint}
流式: {payload.get('stream', False)}
{"=" * 60}

{chr(10).join(messages_debug)}

{"=" * 60}
"""
        # logger.info(llm_request_debug)
        
        # 特殊处理
        if model_id == "qwq-32b":
            payload['stream'] = True
        
        # OpenRouter特殊headers
        if endpoint == "https://openrouter.ai/api/v1/chat/completions":
            headers.update({
                'HTTP-Referer': "https://chagee.com",
                'X-Title': "Internal Service"
            })

        # 创建日志记录
        log_entry = None
        if enable_logging:
            log_entry = LLMLogService.create_call_log(
                model_name=model_id,  # 统一使用 model_id 作为 model_name
                model_id=model_id,
                endpoint=endpoint,
                messages=messages,
                params={**params, **kwargs} if params else kwargs,
                headers=headers,
                user=user,
                session_id=session_id,
                call_type='structured' if 'output_schema' in kwargs else 'chat',
                source_app=source_app or 'llm',
                source_function=source_function or 'core_service.call_llm',
                vendor_name=vendor_name,
                vendor_id=vendor_id,
                is_stream=payload.get('stream', False),
                metadata={}
            )
        
        # 创建重试配置
        retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True
        )
        
        # 定义请求函数
        def make_request():
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=300,
                stream=payload.get('stream', False)
            )
            response.raise_for_status()
            return response
        
        try:
            # 使用重试机制执行请求
            response = LLMRetryHandler.retry_with_backoff(
                make_request,
                retry_config,
                on_retry=lambda attempt, error, delay: self._on_retry(
                    log_entry, attempt, error, delay
                )
            )
            
            # 检查是否是流式响应
            is_stream = payload.get('stream', False)
            is_sse = 'text/event-stream' in response.headers.get('Content-Type', '')
            
            if is_stream and is_sse:
                logger.info("返回流式响应生成器")
                return self._handle_stream_response(response, log_entry)
            else:
                # 打印响应结果
                response_data = response.json()
                content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 准备响应日志
                if len(content) > 3000:
                    content_display = f"{content}\n总长度: {len(content)} 字符]"
                else:
                    content_display = content
                
                usage = response_data.get('usage', {})
                llm_response_debug = f"""
{"=" * 60}
✅ LLM 响应结果
模型: {model_id}
内容长度: {len(content)} 字符
Token使用: 输入 {usage.get('prompt_tokens', 'N/A')} | 输出 {usage.get('completion_tokens', 'N/A')} | 总计 {usage.get('total_tokens', 'N/A')}
{"=" * 60}

【响应内容】
{content_display}

{"=" * 60}
"""
                # logger.debug(llm_response_debug)
                
                # 更新日志记录
                if log_entry:
                    usage = response_data.get('usage', {})
                    LLMLogService.update_success(
                        log_entry,
                        response_content=content,
                        response_raw=response_data,
                        usage_data=usage
                    )
                
                return response_data
                
        except requests.exceptions.Timeout:
            error_desc, _ = LLMRetryHandler.get_error_description(Exception("Timeout"))
            logger.info(f"LLM服务调用失败: {error_desc}")
            if log_entry:
                LLMLogService.update_timeout(log_entry)
            raise Exception(error_desc)
        except requests.exceptions.RequestException as e:
            error_desc, _ = LLMRetryHandler.get_error_description(e)
            logger.info(f"LLM服务调用失败: {error_desc}")
            if log_entry:
                LLMLogService.update_failure(log_entry, error_desc)
            raise Exception(error_desc)
        except Exception as e:
            error_desc, _ = LLMRetryHandler.get_error_description(e)
            logger.info(f"LLM服务调用异常: {error_desc}")
            if log_entry:
                LLMLogService.update_failure(log_entry, str(e))
            # 如果异常信息已经是友好描述，直接使用
            if any(desc in str(e) for desc in LLMRetryHandler.RETRYABLE_ERRORS.values()):
                raise
            else:
                raise Exception(error_desc)
    
    def _handle_stream_response(self, response, log_entry=None) -> Generator:
        """处理流式响应"""
        full_text = ""
        response_template = None
        usage_data = {}
        
        try:
            for line in response.iter_lines():
                if line:
                    line_str = line.lstrip(b'data: ').strip()
                    if not line_str or line_str == b'[DONE]':
                        continue
                    
                    yield f"data: {line_str.decode('utf-8')}\n\n"
                    
                    try:
                        chunk = json.loads(line_str)
                        if response_template is None:
                            response_template = chunk
                        
                        # 检查是否有usage信息
                        if chunk.get("usage"):
                            usage_data = chunk.get("usage")
                        
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            full_text += content
                    except json.JSONDecodeError:
                        continue
        finally:
            # 更新日志记录
            if log_entry and full_text:
                # 如果没有usage信息，尝试估算
                if not usage_data:
                    try:
                        import tiktoken
                        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
                        prompt_tokens = sum(len(encoding.encode(msg.get('content', ''))) 
                                          for msg in log_entry.request_messages if msg.get('content'))
                        completion_tokens = len(encoding.encode(full_text))
                        usage_data = {
                            'prompt_tokens': prompt_tokens,
                            'completion_tokens': completion_tokens,
                            'total_tokens': prompt_tokens + completion_tokens
                        }
                    except:
                        pass
                
                LLMLogService.update_success(
                    log_entry,
                    response_content=full_text,
                    response_raw=response_template or {},
                    usage_data=usage_data
                )
            
            # 发送结束信号
            yield "data: [DONE]\n\n"
    
    def _on_retry(self, log_entry, attempt, error, delay):
        """重试时的回调"""
        logger.info(f"LLM请求第{attempt}次尝试失败，{delay:.2f}秒后重试")
        if log_entry:
            LLMLogService.update_retry(log_entry, attempt)
    
    def call_vision_llm(self, model_id: str, endpoint: str, api_key: str,
                       text_prompt: str, images: List[str],
                       custom_headers: Optional[Dict] = None,
                       params: Optional[Dict] = None,
                       user=None, session_id: str = None,
                       source_app: str = None, source_function: str = None,
                       model_name: str = None, vendor_name: str = None,
                       vendor_id: str = None, enable_logging: bool = True,
                       system_prompt: Optional[str] = None,
                       **kwargs) -> Union[Dict, Generator]:
        """
        视觉模型专用调用方法
        
        参数:
            model_id: 模型ID
            endpoint: API端点
            api_key: API密钥
            text_prompt: 文本提示词
            images: 图片列表，支持以下格式：
                - base64字符串 (data:image/jpeg;base64,...)
                - HTTP/HTTPS URL
                - 本地文件路径
            system_prompt: 可选的系统提示词
            其他参数同 call_llm 方法
        
        返回:
            LLM响应 (支持流式和非流式)
        """
        try:
            # 构建多模态消息
            messages = self._build_vision_messages(text_prompt, images, system_prompt)
            
            # 记录视觉模型调用信息
            logger.info(f"""
视觉模型调用:
- 模型: {model_id}
- 文本提示: {text_prompt[:100]}...
- 图片数量: {len(images)}
- 系统提示: {'有' if system_prompt else '无'}
""")
            
            # 复用现有的 call_llm 方法
            return self.call_llm(
                model_id=model_id,
                endpoint=endpoint,
                api_key=api_key,
                messages=messages,
                custom_headers=custom_headers,
                params=params,
                user=user,
                session_id=session_id,
                source_app=source_app or 'llm',
                source_function=source_function or 'core_service.call_vision_llm',
                model_name=model_name,
                vendor_name=vendor_name,
                vendor_id=vendor_id,
                enable_logging=enable_logging,
                **kwargs
            )
        except Exception as e:
            logger.error(f"视觉模型调用失败: {str(e)}")
            raise
    
    def _build_vision_messages(self, text: str, images: List[str], 
                               system_prompt: Optional[str] = None) -> List[Dict]:
        """
        构建视觉模型的消息格式
        支持OpenAI标准格式和其他主流格式
        
        参数:
            text: 文本提示词
            images: 图片列表
            system_prompt: 可选的系统提示词
        
        返回:
            符合视觉模型要求的消息列表
        """
        messages = []
        
        # 添加系统提示词（如果有）
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 构建用户消息内容
        content = []
        
        # 添加文本内容
        if text:
            content.append({
                "type": "text",
                "text": text
            })
        
        # 处理每个图片
        for i, image in enumerate(images):
            try:
                image_url = self._process_image_input(image)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                })
                logger.debug(f"图片 {i+1} 已处理: {image_url[:100]}...")
            except Exception as e:
                logger.warning(f"处理图片 {i+1} 失败: {str(e)}")
                # 可以选择跳过失败的图片或抛出异常
                continue
        
        # 添加用户消息
        messages.append({
            "role": "user",
            "content": content
        })
        
        return messages
    
    def _process_image_input(self, image: str) -> str:
        """
        处理不同格式的图片输入
        
        参数:
            image: 图片输入，可以是:
                - base64字符串 (data:image/...)
                - HTTP/HTTPS URL
                - 本地文件路径
        
        返回:
            处理后的图片URL (base64或HTTP URL)
        """
        # 如果已经是data URL或HTTP URL，直接返回
        if image.startswith('data:image/') or image.startswith(('http://', 'https://')):
            return image
        
        # 否则假定是本地文件路径，转换为base64
        try:
            return self._file_to_base64(image)
        except Exception as e:
            raise ValueError(f"无法处理图片输入: {str(e)}")
    
    def _file_to_base64(self, file_path: str) -> str:
        """
        将本地文件转换为base64格式的data URL
        
        参数:
            file_path: 文件路径
        
        返回:
            base64格式的data URL
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"路径不是文件: {file_path}")
        
        # 获取文件扩展名和MIME类型
        suffix = path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        
        mime_type = mime_types.get(suffix, 'image/jpeg')
        
        # 读取文件并转换为base64
        with open(path, 'rb') as f:
            image_data = f.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
        
        return f"data:{mime_type};base64,{base64_data}"
    
    def get_structured_llm(self, output_schema, model_config: Dict, **kwargs):
        """
        返回结构化LLM调用器
        
        参数:
            output_schema: 输出模式定义
            model_config: 模型配置信息
            **kwargs: 额外参数（user, session_id, model_name等）
        """
        return StructuredLLMClient(
            core_service=self,
            output_schema=output_schema,
            **model_config,
            **kwargs
        )


class StructuredLLMClient:
    """结构化LLM调用客户端"""
    
    def __init__(self, core_service: CoreLLMService, output_schema, 
                 model_id: str, endpoint: str, api_key: str, 
                 custom_headers: Optional[Dict] = None, 
                 params: Optional[Dict] = None, 
                 user=None, session_id: str = None,
                 model_name: str = None, vendor_name: str = None,
                 vendor_id: str = None, source_app: str = None,
                 source_function: str = None, **kwargs):
        self.core_service = core_service
        self.output_schema = output_schema
        self.config = {
            'model_id': model_id,
            'endpoint': endpoint,
            'api_key': api_key,
            'custom_headers': custom_headers,
            'params': params
        }
        # 保存日志相关参数
        self.log_params = {
            'user': user,
            'session_id': session_id,
            'model_name': model_name,
            'vendor_name': vendor_name,
            'vendor_id': vendor_id,
            'source_app': source_app,
            'source_function': source_function,
            'enable_logging': True
        }
    
    def invoke(self, prompt: str, system_prompt: Optional[str] = None):
        """
        调用LLM并返回结构化输出
        
        参数:
            prompt: 用户提示词内容
            system_prompt: 可选的系统提示词，用于设置LLM的行为规范
        """
        # 构建结构化提示词
        schema_json = self.output_schema.model_json_schema()
        schema_str = json.dumps(schema_json, indent=2, ensure_ascii=False)
        
        # 简化的消息构建逻辑
        if system_prompt:
            # 有系统提示词时，使用 system role + user role
            messages = [
                {
                    'role': 'system', 
                    'content': f"{system_prompt}\n\nOutput JSON Schema:\n{schema_str}\n\nIMPORTANT: Output ONLY valid JSON matching the schema above. No explanations, no markdown."
                },
                {'role': 'user', 'content': prompt}
            ]
        else:
            # 无系统提示词时，合并到 user role
            messages = [
                {
                    'role': 'user',
                    'content': f"{prompt}\n\nOutput as JSON following this schema:\n{schema_str}\n\nIMPORTANT: Output ONLY valid JSON. No explanations, no markdown formatting."
                }
            ]
        
        # 调用核心LLM服务 (强制非流式)，传入日志相关参数
        response = self.core_service.call_llm(
            messages=messages,
            temperature=0.75,  # 结构化输出需要低温度
            stream=False,  # 结构化输出不支持流式
            **self.config,
            **self.log_params  # 传入日志相关参数
        )
        
        # 解析结构化输出
        return self._parse_structured_response(response)
    
    def _parse_structured_response(self, response: Dict) -> Any:
        """
        解析LLM响应并返回结构化数据
        
        参数:
            response: LLM原始响应
        返回:
            解析后的Pydantic模型实例
        """
        raw_response_text = None
        
        try:
            # 获取原始响应文本
            raw_response_text = response['choices'][0]['message']['content']
            
            # 清理响应文本，提取JSON
            json_str = self._extract_json_from_response(raw_response_text)
            
            # 解析JSON并返回模型实例
            data = json.loads(json_str)
            return self.output_schema(**data)
            
        except json.JSONDecodeError as e:
            logger.error(f"结构化输出解析失败: {e}")
            # 尝试更激进的清理
            if raw_response_text:
                json_str = self._aggressive_json_cleanup(raw_response_text)
                try:
                    data = json.loads(json_str)
                    return self.output_schema(**data)
                except Exception as final_e:
                    logger.error(f"激进清理后仍解析失败: {final_e}")
        except Exception as e:
            logger.error(f"结构化输出处理失败: {e}")
        
        # 无论什么异常，都返回默认的模型实例而不是抛出异常
        # 创建一个包含默认值的实例
        try:
            # 尝试创建带有错误信息的默认实例
            # 获取模型的所有字段
            schema_fields = self.output_schema.model_fields
            default_data = {}
            
            for field_name, field_info in schema_fields.items():
                # 为每个字段设置合适的默认值
                if field_info.is_required():
                    # 必填字段设置默认值
                    if field_info.annotation == str:
                        default_data[field_name] = f"[解析失败] 原始响应: {raw_response_text[:200] if raw_response_text else '无响应'}"
                    elif field_info.annotation == int:
                        default_data[field_name] = 0
                    elif field_info.annotation == float:
                        default_data[field_name] = 0.0
                    elif field_info.annotation == bool:
                        default_data[field_name] = False
                    elif field_info.annotation == list:
                        default_data[field_name] = []
                    elif field_info.annotation == dict:
                        default_data[field_name] = {}
                    else:
                        # 对于复杂类型，尝试使用None或空字典
                        default_data[field_name] = None if not field_info.is_required() else {}
            
            return self.output_schema(**default_data)
        except Exception as create_e:
            logger.error(f"创建默认实例失败: {create_e}")
            # 最后的fallback：使用空字典创建实例
            try:
                return self.output_schema()
            except:
                # 如果连空实例都无法创建，构造一个最小化的实例
                return self.output_schema(**{field_name: "" if field_info.annotation == str else None 
                                            for field_name, field_info in self.output_schema.model_fields.items() 
                                            if field_info.is_required()})
    
    def _extract_json_from_response(self, text: str) -> str:
        """
        从响应文本中提取JSON字符串
        """
        import re
        
        # 如果包含markdown代码块，提取其中的JSON
        if "```json" in text or "```" in text:
            # 查找JSON对象的边界
            start_index = text.find('{')
            end_index = text.rfind('}')
            if start_index != -1 and end_index != -1 and end_index > start_index:
                text = text[start_index:end_index + 1]
            else:
                # 移除markdown标记
                text = text.replace('```json', '').replace('```', '').strip()
        else:
            text = text.strip()
        
        # 清理常见的格式问题
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # 修复无效的反斜杠转义
        # 保留合法的JSON转义: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        text = re.sub(r'\\(?!["\\/bfnrtu])', '', text)
        
        # 修复表格格式中的常见问题
        text = text.replace('|\\ ', '| ').replace('|\\', '|')
        
        return text
    
    def _aggressive_json_cleanup(self, text: str) -> str:
        """
        更激进的JSON清理策略
        """
        import re
        
        # 先进行基本提取
        json_str = self._extract_json_from_response(text)
        
        # 尝试修复缺失的逗号
        json_str = re.sub(r'(?<=")\s*(?="[a-zA-Z_])', r',', json_str)
        
        # 修复表格格式问题
        json_str = re.sub(r'\|\s*\\\s*\|', '| |', json_str)
        
        # 如果还是失败，尝试移除所有反斜杠
        if '\\' in json_str:
            json_str = json_str.replace('\\', '')
        
        return json_str