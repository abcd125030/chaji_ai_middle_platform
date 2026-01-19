import copy
import json
import logging
import datetime
import tiktoken
from typing import Dict, Tuple, Any, Union, Generator
from django.http import JsonResponse, StreamingHttpResponse
from .core_service import CoreLLMService
from .config_manager import ModelConfigManager
# chat_sessions 已弃用，改用 LLMLogService 记录数据
from router.models import LLMModel

logger = logging.getLogger(__name__)

class ExternalLLMAPI:
    """
    处理外部API调用的鉴权层
    验证权限后调用核心LLM服务
    """
    
    def __init__(self):
        self.core_service = CoreLLMService()
        self.config_manager = ModelConfigManager()
    
    def handle_external_request(self, request) -> Tuple[Union[Dict, StreamingHttpResponse], int]:
        """
        处理外部API请求
        1. 鉴权
        2. 获取用户可用的模型配置  
        3. 调用核心LLM服务
        4. 保持原有的响应格式和数据库记录
        """
        logger.info("外部LLM API请求开始处理")
        
        # 1. 鉴权 (复用现有逻辑)
        auth_result = self._authenticate_request(request)
        if auth_result[1] != 200:
            return auth_result
        
        llm_model_dict, user_id, service_target, service_appid = auth_result[0]
        
        # 2. 验证模型权限并获取配置
        model_result = self._get_model_config(request.data, llm_model_dict)
        if model_result[1] != 200:
            return model_result
        
        model_config, model_name = model_result[0]
        
        # 3. 准备会话ID（不再使用 chat_sessions，改用 LLMLogService）
        session_id = self._prepare_session(request.data, user_id)
        
        # 4. 调用核心LLM服务
        try:
            # 准备payload
            payload = copy.deepcopy(request.data)
            if 'session_id' in payload:
                del payload['session_id']
            
            # 确保model字段正确
            if 'model' not in payload:
                payload['model'] = model_config['model_id']
            
            # 记录调用开始时间
            llm_model = LLMModel.objects.get(name=model_name)
            llm_start_time = datetime.datetime.now()
            
            logger.info(f"调用核心LLM服务: {model_name}")
            
            # 获取用户对象
            from authentication.models import User
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                user = None
            
            # 从端点提取供应商信息
            vendor_info = self._extract_vendor_info(model_config['endpoint'])
            
            # 调用核心服务，启用日志记录
            response_data = self.core_service.call_llm(
                model_id=model_config['model_id'],
                endpoint=model_config['endpoint'],
                api_key=model_config['api_key'],
                custom_headers=model_config['custom_headers'],
                params=model_config['params'],
                messages=payload.get('messages', []),
                user=user,
                session_id=str(session_id),
                model_name=model_name,
                vendor_name=vendor_info.get('vendor_name'),
                vendor_id=vendor_info.get('vendor_id'),
                source_app='external_api',
                source_function=f'external_api.{service_target}',
                enable_logging=True,
                **{k: v for k, v in payload.items() if k not in ['model', 'messages']}
            )
            
            # 更新模型统计
            llm_model.call_count += 1
            llm_model.success_count += 1
            llm_model.save()
            
            llm_end_time = datetime.datetime.now()
            logger.info(f'LLM调用耗时：{llm_end_time - llm_start_time}')
            
            # 5. 处理响应格式（不再需要 session 对象）
            return self._format_response(
                response_data, session_id, model_name,
                payload, model_config
            )
            
        except Exception as e:
            # 更新失败统计
            llm_model.call_count += 1
            llm_model.save()
            
            logger.error(f"LLM调用失败: {e}")
            return {"error": f"调用大模型服务时发生内部错误: {str(e)}"}, 500
    
    def _authenticate_request(self, request) -> Tuple[Any, int]:
        """处理请求鉴权 - 支持双路径认证（JWT token 和 appid/secret）"""
        from llm.check_utils.utils import check_dual_auth_and_get_llm
        
        ip_address = request.META.get('REMOTE_ADDR')
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        logger.info(f"鉴权检查: IP={ip_address}")
        
        # 使用双路径认证函数
        check_result, llm_model_dict, user_id, service_target, service_appid = \
            check_dual_auth_and_get_llm(ip_address, auth_header, request.data)
        
        if "error" in check_result:
            logger.error(f"鉴权失败: {check_result}")
            return check_result, 401
        
        if user_id == -1:
            error = {'error': '没有为该用户建立外部服务机制'}
            return error, 401
        
        if len(llm_model_dict) <= 0:
            error = {'error': '没有为该用户绑定可以使用的大模型服务'}
            return error, 401
        
        return (llm_model_dict, user_id, service_target, service_appid), 200
    
    def _get_model_config(self, request_data: Dict, llm_model_dict: Dict) -> Tuple[Any, int]:
        """获取并验证模型配置"""
        input_model_id = request_data.get('model')
        if not input_model_id:
            return {"error": "Missing 'model' field in request"}, 400
        
        # 查找用户有权限的模型
        model_name = None
        user_model_config = None
        
        for name, config in llm_model_dict.items():
            if config['model_id'] == input_model_id:
                model_name = name
                user_model_config = config
                break
        
        if not model_name:
            logger.error(f"用户无权使用模型: {input_model_id}")
            return {"error": "该用户无权使用这个模型"}, 401
        
        # 构建最终的模型配置
        try:
            model_config = {
                'model_id': user_model_config['model_id'],
                'endpoint': user_model_config['model_endpoint'],
                'api_key': user_model_config['model_key'],
                'custom_headers': user_model_config.get('custom_headers', {}),
                'params': user_model_config.get('params', {})
            }
            
            return (model_config, model_name), 200
            
        except Exception as e:
            logger.error(f"模型配置构建失败: {e}")
            return {"error": "模型配置错误"}, 500
    
    def _prepare_session(self, request_data: Dict, user_id: int) -> str:
        """
        准备会话ID（不再创建 Session 对象，因为 chat_sessions 已弃用）
        会话数据由 CoreLLMService 通过 LLMLogService 记录
        """
        import uuid

        if 'session_id' in request_data:
            session_id = request_data['session_id']
        else:
            # 生成新的会话ID
            session_id = str(uuid.uuid4())

        return str(session_id)
    
    def _format_response(self, response_data, session_id: str,
                        model_name: str, payload: Dict, model_config: Dict) -> Tuple[Any, int]:
        """格式化响应，保持与原有接口一致（不再依赖 Session 对象）"""

        # 检查是否是流式响应
        if hasattr(response_data, '__iter__') and not isinstance(response_data, dict):
            logger.info("处理流式响应")
            return self._handle_stream_response(
                response_data, session_id, model_name, payload, model_config
            ), 200

        # 处理非流式响应
        logger.info("处理非流式响应")
        return self._handle_regular_response(
            response_data, session_id, model_name, payload, model_config
        ), 200
    
    def _handle_regular_response(self, response_data: Dict, session_id: str,
                                model_name: str, payload: Dict, model_config: Dict) -> Dict:
        """处理非流式响应（不再依赖 Session 对象，数据由 LLMLogService 记录）"""
        deal_response = response_data.copy()

        # 计算token使用量 (如果响应中没有)
        usage = deal_response.get('usage')
        if not usage or not usage.get('total_tokens'):
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

            prompt_content = "".join([
                msg.get('content', '') for msg in payload.get('messages', [])
                if msg.get('content')
            ])
            response_content = "".join([
                choice.get('message', {}).get('content', '')
                for choice in deal_response.get('choices', [])
                if choice.get('message', {}).get('content')
            ])

            input_tokens = len(encoding.encode(prompt_content))
            output_tokens = len(encoding.encode(response_content))
            total_tokens = input_tokens + output_tokens

            usage = {
                'prompt_tokens': input_tokens,
                'completion_tokens': output_tokens,
                'total_tokens': total_tokens
            }
            deal_response['usage'] = usage

        # 添加额外字段以保持兼容性
        deal_response.update({
            "session_id": session_id,
            "model_name": model_name,
            "origin": payload
        })

        # 注意：会话长度和QA记录不再保存到 chat_sessions
        # 所有数据已通过 CoreLLMService -> LLMLogService 记录

        # 打印要返回的结果
        logger.info(f"要返回的结果: {deal_response}")

        return deal_response
    
    def _handle_stream_response(self, response_generator, session_id: str,
                               model_name: str, payload: Dict, model_config: Dict):
        """处理流式响应（不再依赖 Session 对象）"""
        def stream_wrapper():
            full_text = ""
            usage_from_response = None
            response_template = None

            try:
                for chunk_data in response_generator:
                    yield chunk_data

                    # 尝试解析chunk以收集完整文本
                    if chunk_data.startswith("data: ") and not chunk_data.strip().endswith("[DONE]"):
                        try:
                            chunk_str = chunk_data[6:].strip()  # 移除 "data: "
                            chunk = json.loads(chunk_str)

                            if response_template is None:
                                response_template = chunk

                            if chunk.get("usage"):
                                usage_from_response = chunk.get("usage")

                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                full_text += content
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue
            finally:
                # 流式响应结束，数据已通过 CoreLLMService -> LLMLogService 记录
                logger.info("流式响应结束（数据已由 LLMLogService 记录）")

        return StreamingHttpResponse(stream_wrapper(), content_type='text/event-stream')
    
    # _save_qa_record 方法已移除，因为 chat_sessions 已弃用
    # 所有数据记录由 CoreLLMService -> LLMLogService 完成

    def _extract_vendor_info(self, endpoint: str) -> Dict[str, str]:
        """从端点URL提取供应商信息"""
        endpoint_lower = endpoint.lower()
        
        vendor_map = {
            'openrouter.ai': {'vendor_name': 'OpenRouter', 'vendor_id': 'openrouter'},
            'dashscope.aliyuncs.com': {'vendor_name': '阿里云百炼大模型', 'vendor_id': 'aliyun'},
            'openai.com': {'vendor_name': 'OpenAI', 'vendor_id': 'openai'},
            'anthropic.com': {'vendor_name': 'Anthropic', 'vendor_id': 'anthropic'},
            'baidu.com': {'vendor_name': 'Baidu', 'vendor_id': 'baidu'},
            'moonshot.cn': {'vendor_name': 'Moonshot', 'vendor_id': 'moonshot'},
            'zhipuai.cn': {'vendor_name': 'Zhipu', 'vendor_id': 'zhipu'},
            'deepseek.com': {'vendor_name': 'DeepSeek', 'vendor_id': 'deepseek'},
        }
        
        for domain, info in vendor_map.items():
            if domain in endpoint_lower:
                return info
        
        return {'vendor_name': '', 'vendor_id': ''}