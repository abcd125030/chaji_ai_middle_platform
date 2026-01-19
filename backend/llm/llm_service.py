import copy
import json
import uuid
from django.db.models.functions.datetime import TruncBase
import requests
import random

from authentication.models import User
from django.conf import settings
# from chat_sessions.models import Session, QA  # chat_sessions已弃用
from llm.service_providers import BaseModelServiceProvider
import datetime
import logging
import tiktoken

from router.models import LLMModel

logger = logging.getLogger(__name__)


class LLMService:
    """
    统一的LLM服务接口
    重构后提供清晰的内部/外部服务分离
    """
    
    def __init__(self):
        self._internal_service = None
        self._external_api = None
    
    @property
    def internal(self):
        """获取内部LLM服务接口"""
        # 直接返回一个包装器，提供兼容的接口
        from .core_service import CoreLLMService
        from .config_manager import ModelConfigManager
        
        class InternalWrapper:
            def __init__(self):
                self.core_service = CoreLLMService()
                self.config_manager = ModelConfigManager()
            
            def get_structured_llm(self, output_schema, model_name: str, user=None, session_id=None):
                model_config = self.config_manager.get_model_config(model_name)
                return self.core_service.get_structured_llm(
                    output_schema,
                    model_config,
                    user=user,
                    session_id=session_id,
                    model_name=model_name,
                    source_app='legacy',
                    source_function='llm_service.internal'
                )
            
            def call_llm(self, model_name: str, messages, user=None, session_id=None, **kwargs):
                model_config = self.config_manager.get_model_config(model_name)
                return self.core_service.call_llm(
                    messages=messages,
                    user=user,
                    session_id=session_id,
                    model_name=model_name,
                    source_app='legacy',
                    source_function='llm_service.internal',
                    **model_config,
                    **kwargs
                )
            
            def call_vision_model(self, model_name: str, text_prompt: str, images: list,
                                user=None, session_id=None, system_prompt=None, **kwargs):
                model_config = self.config_manager.get_model_config(model_name)
                return self.core_service.call_vision_llm(
                    text_prompt=text_prompt,
                    images=images,
                    system_prompt=system_prompt,
                    user=user,
                    session_id=session_id,
                    model_name=model_name,
                    source_app='legacy',
                    source_function='llm_service.internal.vision',
                    **model_config,
                    **kwargs
                )
        
        if self._internal_service is None:
            self._internal_service = InternalWrapper()
        return self._internal_service
    
    @property
    def external_api(self):
        """获取外部API处理器"""
        if self._external_api is None:
            from .external_api import ExternalLLMAPI
            self._external_api = ExternalLLMAPI()
        return self._external_api
    
    def get_structured_llm(self, output_schema, model_name: str, user=None, session_id=None):
        """
        获取结构化LLM调用器
        代理到内部服务，为了保持向后兼容性
        """
        return self.internal.get_structured_llm(output_schema, model_name, user=user, session_id=session_id)
    
    def call_vision_model(self, model_name: str, text_prompt: str, images: list, 
                         user=None, session_id=None, system_prompt=None, **kwargs):
        """
        调用视觉模型处理图片和文本
        
        参数:
            model_name: 模型名称（需要在数据库中配置为vision类型）
            text_prompt: 文本提示词
            images: 图片列表，支持：
                - base64字符串
                - HTTP/HTTPS URL  
                - 本地文件路径
            user: 用户对象（可选）
            session_id: 会话ID（可选）
            system_prompt: 系统提示词（可选）
            **kwargs: 其他参数（temperature, max_tokens等）
        
        返回:
            模型响应结果
        """
        return self.internal.call_vision_model(
            model_name, text_prompt, images, 
            user=user, session_id=session_id,
            system_prompt=system_prompt, **kwargs
        )
    
    # 保持旧接口的兼容性方法
    def send_customization_picture_request(self, *args, **kwargs):
        """处理定制图片请求 - 兼容性方法"""
        return LLMServiceProvider().send_request(*args, **kwargs)

    def send_customization_request(self, *args, **kwargs):
        """处理定制文本请求 - 兼容性方法"""
        return LLMServiceProvider().send_request(*args, **kwargs)

    def write_qa_to_customization(self, *args, **kwargs):
        """将QA写入定制化存储 - 兼容性方法"""
        return LLMServiceProvider().write_qa_to_session(*args, **kwargs)


class LLMServiceProvider(BaseModelServiceProvider):
    """
    旧的LLM服务提供者
    保留用于向后兼容，但建议使用新的架构
    """
    
    def send_customization_picture_request(self, *args, **kwargs):
        """处理定制图片请求"""
        return self.send_request(*args, **kwargs)

    def send_customization_request(self, *args, **kwargs):
        """处理定制文本请求"""
        return self.send_request(*args, **kwargs)

    def write_qa_to_customization(self, *args, **kwargs):
        """将QA写入定制化存储"""
        return self.write_qa_to_session(*args, **kwargs)
    
    # 新增：为外部API提供兼容接口
    def handle_external_request(self, request):
        """处理外部API请求的兼容方法"""
        from .external_api import ExternalLLMAPI
        api_handler = ExternalLLMAPI()
        return api_handler.handle_external_request(request)
    def send_request(self, model_name, model_endpoint, model_key, model_id, service_target, user_id, payload, custom_headers, params):
        # chat_sessions已弃用，不再处理session
        logger.info("LLMServiceProvider send_request 开始")
        try:
            session_id = payload.get('session_id', str(uuid.uuid4()))
            session = None  # chat_sessions已弃用
            # 优先使用调用时传入的 payload 作为基础
            final_payload = payload.copy()
            # 然后使用模型在数据库中配置的 params 进行覆盖，以支持特定模型的专用参数
            if params:
                final_payload.update(params)

            # 确保 payload 中包含 model 字段，除非 params 中已经指定了
            if 'model' not in final_payload:
                final_payload['model'] = model_id

            # 删除内部使用的 session_id，不发送给大模型
            if 'session_id' in final_payload:
                del final_payload['session_id']

            headers = {
                'Content-Type': 'application/json',
            }
            
            # 合并自定义请求头
            if custom_headers:
                headers.update(custom_headers)

            # 如果有api-key, 则需要放在headers中
            if model_key != "":
                headers['Authorization'] = "Bearer " + model_key
                headers['Content-Type'] = "application/json"
                # 阿里百炼qwq-32b只接受流式格式
                if model_id == "qwq-32b":
                    final_payload['stream'] = True

            if model_endpoint == "https://openrouter.ai/api/v1/chat/completions":
                headers['HTTP-Referer'] = "https://chagee.com"
                headers['X-Title'] = service_target

            logger.info("headers: " + str(headers))
            bStream = False
            if final_payload.get('stream') == True:
                bStream = True

            # qwen-32b只能临时使用gpt-3.5-turbo来代替，否则报错
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

            logger.info("大模型调用开始")
            llm_model = LLMModel.objects.get(name=model_name)
            llm_start_time = datetime.datetime.now()
            try:
                # 打印请求头和请求体
                logger.info(f"Request Headers: {headers}\nRequest Payload: {json.dumps(final_payload, ensure_ascii=False)}")
                response = requests.post(model_endpoint, headers=headers, json=final_payload, timeout=300)
                logger.info(f"响应状态码: {response.status_code}\n响应头: {dict(response.headers)}")
                # 记录部分响应内容（避免日志过大）
                logger.info(f"响应内容预览: {response.text}")
                # 检查响应状态码
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # 请求失败，增加调用计数
                # llm_model.call_count += 1
                # llm_model.save()
                llm_end_time = datetime.datetime.now()
                logger.info(f"大模型调用结束\n大模型调用耗时：{llm_end_time - llm_start_time}")
                error_message = f"HTTP错误: {e}"
                logger.error(f"error: {error_message}\nLLMServiceProvider send_request 结束")
                return {"error": error_message}
            except requests.exceptions.Timeout:
                # # 请求失败，增加调用计数
                # llm_model.call_count += 1
                # llm_model.save()
                llm_end_time = datetime.datetime.now()
                logger.info(f"大模型调用结束\n大模型调用耗时：{llm_end_time - llm_start_time}")
                error_message = f"大模型请求超时，已停止访问。"
                logger.error(f"error: {error_message}\nLLMServiceProvider send_request 结束")
                return {"error": error_message}
            except requests.exceptions.RequestException as e:
                # 请求失败，增加调用计数
                # llm_model.call_count += 1
                # llm_model.save()
                llm_end_time = datetime.datetime.now()
                logger.info(f"大模型调用结束\n大模型调用耗时：{llm_end_time - llm_start_time}\n大模型请求发生错误: {e}\nLLMServiceProvider send_request 结束")
                return {"error": f"大模型请求发生错误: {e}"}
            except Exception as e:
                # 处理其他未知异常
                # llm_model.call_count += 1
                # llm_model.save()
                llm_end_time = datetime.datetime.now()
                logger.info(f"大模型调用结束\n大模型调用耗时：{llm_end_time - llm_start_time}\n大模型请求发生错误: {e}\nLLMServiceProvider send_request 结束")
                return {"error": f"大模型请求发生错误: {e}"}

            logger.info("大模型调用结束------------------------------")
            # 请求成功，增加成功计数
            llm_model.success_count += 1
            llm_model.save()
            # 请求成功，增加调用计数
            llm_model.call_count += 1
            llm_model.save()
            llm_end_time = datetime.datetime.now()
            logger.info("大模型调用结束")
            logger.info(f'大模型调用耗时：{llm_end_time - llm_start_time}')
            deal_response = dict()
            if response.status_code == 200:
                is_sse = 'text/event-stream' in response.headers.get('Content-Type', '')

                # 如果用户请求流式传输并且服务器确认是SSE流，则返回一个生成器
                if bStream and is_sse:
                    def stream_generator():
                        full_text = ""
                        usage_from_response = None
                        response_template = None
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
                                            # response_template 始终会被最后一个 chunk 覆盖
                                            response_template = chunk
                                        if chunk.get("usage"):
                                            usage_from_response = chunk.get("usage")
                                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                                        content = delta.get("content")
                                        if content:
                                            full_text += content
                                    except (json.JSONDecodeError, IndexError):
                                        logger.warning(f"无法解析或处理SSE流中的块: {line_str}")
                                        continue
                        finally:
                            logger.info("SSE stream finished. Constructing final response and saving to database.")
                            if usage_from_response:
                                input_tokens = usage_from_response.get('prompt_tokens', 0)
                                output_tokens = usage_from_response.get('completion_tokens', 0)
                            else:
                                prompt_content = "".join([msg.get('content', '') for msg in final_payload.get('messages', []) if msg.get('content')])
                                input_tokens = len(encoding.encode(prompt_content))
                                output_tokens = len(encoding.encode(full_text))
                            total_tokens = input_tokens + output_tokens
                            
                            # 1. 为数据库构建完整的响应对象
                            print('response_template:', response_template)
                            db_response = response_template.copy() if response_template else {}
                            db_response.update({
                                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': full_text}}],
                                'usage': {'prompt_tokens': input_tokens, 'total_tokens': total_tokens, 'completion_tokens': output_tokens},
                                "session_id": str(session.session_id),
                                "model_name": model_name,
                                "origin": final_payload
                            })

                            # 2. 构建最后一个data 块，从 db_response 中移除 choices 字段
                            client_data = db_response.copy()
                            if 'choices' in client_data:
                                del client_data['choices']
                            
                            print('db_response:', db_response)
                            print('client_data:', client_data)


                            # 3. 向客户端发送仅包含元数据的最终数据块
                            final_data_str = json.dumps(client_data, ensure_ascii=False)
                            yield f"data: {final_data_str}\n\n"
                            
                            # 4. 发送标准的 [DONE] 信号
                            yield "data: [DONE]\n\n"

                            # 5. chat_sessions已弃用，不再保存到数据库
                            # 原来的session相关操作已移除
                            logger.info("LLMServiceProvider send_request 结束 (stream)")
                    
                    return stream_generator()
                
                # 其他所有情况（非流式请求，或服务器未返回流）都作为普通JSON处理
                else:
                    if bStream and not is_sse:
                        logger.warning("客户端请求了流式响应，但服务器未返回text/event-stream。将作为非流式响应处理。")
                    
                    try:
                        response_json_data = response.json()
                        deal_response = response_json_data.copy()
                        
                        usage = deal_response.get('usage')
                        if not usage or not usage.get('total_tokens'):
                            prompt_content = "".join([msg.get('content', '') for msg in final_payload.get('messages', []) if msg.get('content')])
                            response_content = "".join([choice.get('message', {}).get('content', '') for choice in deal_response.get('choices', []) if choice.get('message', {}).get('content')])
                            
                            input_tokens = len(encoding.encode(prompt_content))
                            output_tokens = len(encoding.encode(response_content))
                            total_tokens = input_tokens + output_tokens
                            usage = {
                                'prompt_tokens': input_tokens,
                                'completion_tokens': output_tokens,
                                'total_tokens': total_tokens
                            }
                            deal_response['usage'] = usage

                        deal_response["session_id"] = str(session_id)
                        deal_response["model_name"] = model_name
                        deal_response["origin"] = final_payload
                        
                        # chat_sessions已弃用，不再记录session信息
                        # self.write_qa_to_session(model_name, session, payload, params, response_json_data, deal_response)
                        logger.info("LLMServiceProvider send_request 结束")
                        return deal_response
                    except ValueError as e:
                        error_message = f"无效的JSON数据: {e}"
                        logger.error("error: " + error_message)
                        logger.info("LLMServiceProvider send_request 结束")
                        return {"error": error_message}
            else:
                error_message = f"请求失败，状态码 {response.status_code}: {response.text}"
                logger.error(f"error: {error_message}\nLLMServiceProvider send_request 结束")
                return {"error": error_message}
        except requests.exceptions.RequestException as e:
            error_message = f"Request failed: {str(e)}"
            logger.error(f"error: {error_message}\nLLMServiceProvider send_request 结束")
            return {"error": error_message}
        except Exception as e:
            # 处理其他未知异常
            error_message = f"出现未知错误: {e}"
            logger.error(f"error: {error_message}\nLLMServiceProvider send_request 结束")
            return {"error": error_message}

    def write_qa_to_session(self, model_name, session, payload, params, response_json, deal_response):
        # chat_sessions已弃用，不再记录QA
        pass

    def _prepare_request_data(self, payload, model_key, model_id, model_endpoint, service_target):
        """准备请求数据"""
        final_payload = copy.deepcopy(payload)
        headers = {'Content-Type': 'application/json'}

        if model_key:
            headers.update({
                'Authorization': f"Bearer {model_key}",
                'Content-Type': "application/json"
            })
            if model_id == "qwq-32b":
                final_payload['stream'] = True

        if model_endpoint == "https://openrouter.ai/api/v1/chat/completions":
            headers.update({
                'HTTP-Referer': "https://chagee.com",
                'X-Title': service_target
            })

        return final_payload, headers

    def _update_model_stats(self, llm_model, success=True):
        """更新模型统计信息"""
        llm_model.call_count += 1
        if success:
            llm_model.success_count += 1
        llm_model.save()


