import copy
import json
import uuid
import random
import requests
import datetime
import logging
import tiktoken

from django.conf import settings
from authentication.models import User
from customized.customization.models import CustomizedQA
from router.models import LLMModel
from llm.llm_service import LLMServiceProvider

logger = logging.getLogger(__name__)

class CustomizationService:
    def __init__(self):
        from llm.llm_service import LLMServiceProvider
        self.llm_service = LLMServiceProvider()

    def get_qa_result(self, task_id):
        """获取单个QA结果"""
        try:
            qa = CustomizedQA.objects.filter(
                task_id=task_id,
                is_final="是"
            ).order_by('-id').first()
            return qa.output if qa else None
        except Exception as e:
            logger.error(f"get_qa_result failed for task_id {task_id}: {str(e)}")
            return None

    def batch_get_qa_results(self, task_ids):
        """批量获取QA结果"""
        try:
            query_results = CustomizedQA.objects.filter(
                task_id__in=task_ids,
                is_final="是"
            ).values('task_id', 'output')
            return {str(q['task_id']): q['output'] for q in query_results}
        except Exception as e:
            logger.error(f"batch_get_qa_results failed: {str(e)}")
            return {}
    def send_customization_picture_request(self, model_name, model_endpoint, model_key, model_id, service_target,
                                         user_id, srcpayload, payload, params):
        logger.info("CustomizationService send_customization_picture_request 开始")
        try:
            # 1. 准备请求数据
            final_payload, headers = self._prepare_request_data(payload, model_key, model_id, model_endpoint,
                                                               service_target)

            logger.info("headers: " + str(headers))
            logger.info("图片大模型调用开始")
            llm_model = LLMModel.objects.get(name=model_name)
            llm_start_time = datetime.datetime.now()

            try:
                # 2. 测试环境处理
                if settings.IS_TEST_ENV:
                    response = self._handle_test_environment()
                else:
                    response = requests.post(model_endpoint, headers=headers, json=final_payload, timeout=300)
                    response.raise_for_status()

                # 3. 处理成功响应
                deal_response = self._process_successful_response(
                    response, model_name, final_payload, user_id,
                    service_target, srcpayload, payload, params
                )

                # 4. 更新模型统计
                self._update_model_stats(llm_model, success=True)

                logger.info("CustomizationService send_customization_picture_request 结束")
                return deal_response

            except (requests.exceptions.Timeout, requests.exceptions.RequestException, Exception) as e:
                return self._handle_request_exception(e, llm_model, llm_start_time)

        except Exception as e:
            error_message = str(e)
            if "port 5432" in error_message or "PostgreSQL" in error_message:
                error_message = "PostgreSQL当前无法使用"
            else:
                error_message = f"出现未知错误: {e}"
            logger.error("error: " + error_message)
            logger.info("CustomizationService send_customization_picture_request 结束")
            return {"error": error_message}

    def send_customization_request(self, model_name, model_endpoint, model_key, model_id, service_target, user_id,
                                 srcpayload, payload, params):
        logger.info("CustomizationService send_customization_request 开始")
        try:
            # 1. 准备请求数据
            final_payload, headers = self._prepare_request_data(payload, model_key, model_id, model_endpoint,
                                                               service_target)

            # 2. 处理流式标志
            bStream = final_payload.get('stream', False)

            # 3. 初始化模型
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            llm_model = LLMModel.objects.get(name=model_name)
            llm_start_time = datetime.datetime.now()

            try:
                # 4. 测试环境处理
                if settings.IS_TEST_ENV:
                    response = self._handle_test_customization_environment()
                    bStream = False
                else:
                    response = requests.post(model_endpoint, headers=headers, json=final_payload, timeout=300)
                    response.raise_for_status()

                # 5. 处理响应
                deal_response = self._process_customization_response(
                    response, model_name, final_payload, user_id,
                    service_target, srcpayload, payload, params,
                    bStream, encoding
                )

                # 6. 更新模型统计
                self._update_model_stats(llm_model, success=True)

                logger.info(f'推理大模型调用耗时：{datetime.datetime.now() - llm_start_time}')
                logger.info("CustomizationService send_customization_request 结束")
                return deal_response

            except (requests.exceptions.Timeout, requests.exceptions.RequestException, Exception) as e:
                return self._handle_customization_exception(e, llm_model, llm_start_time)

        except Exception as e:
            error_message = str(e)
            if "port 5432" in error_message or "PostgreSQL" in error_message:
                error_message = "PostgreSQL当前无法使用"
            else:
                error_message = f"出现未知错误: {e}"
            logger.error("error: " + error_message)
            logger.info("CustomizationService send_customization_request 结束")
            return {"error": error_message}

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

    def _handle_test_environment(self):
        """处理测试环境的模拟响应"""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "图片展示了一家名为'CHAGEE 霸王茶姬'的店铺，夜晚灯光亮起，招牌显眼。店内顾客较多，门外摆放着桌椅和植物装饰。霸王茶姬的标志在招牌左侧清晰可见，整体环境热闹且现代。",
                    "role": "assistant"
                },
                "finish_reason": "stop",
                "index": 0,
                "logprobs": None
            }],
            "object": "chat.completion",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            },
            "created": 1745724319,
            "system_fingerprint": None,
            "model": "qwen-vl-max-latest",
            "id": "chatcmpl-e6bb94ae-af0a-945d-9986-9aa3e9e846d2"
        }

        class MockResponse:
            def __init__(self, json_data, status_code):
                self._json_data = json_data
                self.status_code = status_code

            def json(self):
                return self._json_data

        rand_num = random.random()
        if rand_num < 0.2:
            raise requests.exceptions.RequestException("模拟请求异常")
        elif rand_num < 0.3:
            raise requests.exceptions.Timeout("模拟请求超时")

        return MockResponse(mock_response, 200)

    def _process_successful_response(self, response, model_name, final_payload, user_id, service_target, srcpayload,
                                   payload, params):
        """处理成功的响应"""
        if response.status_code != 200:
            error_message = f"Request failed with status code {response.status_code}"
            logger.error("error: " + error_message)
            return {"error": error_message}

        try:
            response_json_data = response.json()
            deal_response = {
                'choices': [],
                'usage': {},
                'model_name': model_name,
                'origin': final_payload
            }

            for choice in response_json_data['choices']:
                deal_response['choices'].append({
                    'index': choice['index'],
                    'message': {
                        'role': choice['message']['role'],
                        'content': choice['message']['content']
                    }
                })

            deal_response['usage'].update({
                'prompt_tokens': response_json_data['usage']['prompt_tokens'],
                'total_tokens': response_json_data['usage']['total_tokens'],
                'completion_tokens': response_json_data['usage']['completion_tokens']
            })

            self.write_qa_to_customization(
                model_name, user_id, service_target, srcpayload, payload, params,
                response_json_data, deal_response, deal_response['choices'][0]['message'],
                "否", response_json_data['usage']['prompt_tokens'],
                response_json_data['usage']['completion_tokens']
            )

            return deal_response

        except ValueError as e:
            error_message = f"Invalid JSON data: {e}"
            logger.error("error: " + error_message)
            return {"error": error_message}

    def _handle_request_exception(self, exception, llm_model, start_time):
        """处理请求异常"""
        self._update_model_stats(llm_model, success=False)
        end_time = datetime.datetime.now()
        logger.info("图片大模型调用结束")
        logger.info(f'图片大模型调用耗时：{end_time - start_time}')

        if isinstance(exception, requests.exceptions.Timeout):
            error_message = "图片大模型请求超过90秒, 已停止访问。"
        elif isinstance(exception, requests.exceptions.RequestException):
            error_message = f"图片大模型请求发生RequestException错误: {str(exception)}"
        else:
            error_message = f"图片大模型请求发生错误: {str(exception)}"

        logger.error("error: " + error_message)
        logger.info("CustomizationService send_customization_picture_request 结束")
        return {"error": error_message}

    def _handle_test_customization_environment(self):
        """处理测试环境的模拟响应"""
        mock_responses = [
            {
                "结论": "类别1",
                "原因": "文字中明确提到霸王茶姬是有负面舆情，符合类别1的定义。"
            },
            {
                "结论": "类别2",
                "原因": "文字中提到霸王茶姬产品质量问题，符合类别2的定义。"
            },
            {
                "结论": "类别3",
                "原因": "文字中提到霸王茶姬服务态度问题，符合类别3的定义。"
            },
            {
                "结论": "类别4",
                "原因": "文字中提到霸王茶姬代下单行为，符合类别4的定义。"
            },
            {
                "结论": "其他",
                "原因": "文字中没有提到任何与霸王茶姬相关的问题。"
            }
        ]

        selected_response = random.choice(mock_responses)
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps(selected_response, ensure_ascii=False),
                    "role": "assistant"
                },
                "finish_reason": "stop",
                "index": 0
            }],
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 50,
                "total_tokens": 250
            }
        }

        class MockResponse:
            def __init__(self, json_data, status_code):
                self._json_data = json_data
                self.status_code = status_code

            def json(self):
                return self._json_data

        rand_num = random.random()
        if rand_num < 0.1:
            raise requests.exceptions.RequestException("模拟请求异常")
        elif rand_num < 0.4:
            raise requests.exceptions.Timeout("模拟请求超时")

        return MockResponse(mock_response, 200)

    def _process_customization_response(self, response, model_name, final_payload, user_id, service_target, srcpayload,
                                      payload, params, bStream, encoding):
        """处理自定义请求的响应"""
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"Request failed with status code {response.status_code}")

        deal_response = {
            'choices': [],
            'usage': {},
            'model_name': model_name,
            'origin': final_payload
        }

        if bStream:
            return self._handle_stream_response(response, encoding, final_payload, deal_response, model_name, user_id,
                                              service_target, srcpayload, payload, params)
        else:
            return self._handle_normal_response(response, model_name, user_id, service_target, srcpayload, payload,
                                              params, deal_response)

    def _handle_stream_response(self, response, encoding, final_payload, deal_response, model_name, user_id,
                              service_target, srcpayload, payload, params):
        """处理流式响应"""
        full_text = ""
        for line in response.iter_lines():
            if line:
                line = line.lstrip(b'data: ')
                try:
                    chunk = json.loads(line)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        full_text += content
                except json.JSONDecodeError:
                    continue

        input_tokens = len(encoding.encode(final_payload['messages'][0]['content']))
        output_tokens = len(encoding.encode(full_text))

        deal_response['choices'].append({
            'index': 0,
            'message': {
                'role': "assistant",
                'content': full_text
            }
        })
        deal_response['usage'].update({
            'prompt_tokens': input_tokens,
            'total_tokens': input_tokens + output_tokens,
            'completion_tokens': output_tokens
        })

        return_response_data = self._process_response_category(deal_response)

        self.write_qa_to_customization(
            model_name, user_id, service_target, srcpayload, payload, params,
            deal_response, deal_response, return_response_data,
            "是", str(input_tokens),
            str(output_tokens))

        return return_response_data

    def _handle_normal_response(self, response, model_name, user_id, service_target, srcpayload, payload, params,
                              deal_response):
        """处理普通响应"""
        response_json = response.json()

        for choice in response_json['choices']:
            deal_response['choices'].append({
                'index': choice['index'],
                'message': {
                    'role': choice['message']['role'],
                    'content': choice['message']['content']
                }
            })

        deal_response['usage'].update(response_json['usage'])

        return_response_data = self._process_response_category(deal_response)

        self.write_qa_to_customization(
            model_name, user_id, service_target, srcpayload, payload, params,
            response_json, deal_response, return_response_data,
            "是", response_json['usage']['prompt_tokens'],
            response_json['usage']['completion_tokens']
        )

        return return_response_data

    def _handle_customization_exception(self, exception, llm_model, start_time):
        """处理异常情况"""
        llm_model.call_count += 1
        llm_model.save()
        end_time = datetime.datetime.now()
        logger.info("推理大模型调用结束")
        logger.info(f'推理大模型调用耗时：{end_time - start_time}')

        if isinstance(exception, requests.exceptions.Timeout):
            error_message = "推理大模型请求超过90秒, 已停止访问。"
        elif isinstance(exception, requests.exceptions.RequestException):
            error_message = f"推理大模型请求发生RequestException错误: {str(exception)}"
        else:
            error_message = f"推理大模型请求发生错误: {str(exception)}"

        logger.error("error: " + error_message)
        logger.info("CustomizationService send_customization_request 结束")
        return {"error": error_message}

    def _update_model_stats(self, llm_model, success=True):
        """更新模型统计信息"""
        llm_model.call_count += 1
        if success:
            llm_model.success_count += 1
        llm_model.save()

    def _process_response_category(self, deal_response):
        """
        处理响应类别和评分

        Args:
            deal_response (dict): 处理后的响应数据

        Returns:
            dict: 包含结果、原因和评分的字典
        """
        return_response_data = {
            'result': "中立",
            'reason': "",
            'score': 50
        }

        try:
            response_data_content = deal_response['choices'][0]['message']['content']

            if '"结论"' in response_data_content and '"原因"' in response_data_content:
                response_data_content = response_data_content.strip('`').strip('json')
                print(response_data_content)

                response_data_content_dict = json.loads(response_data_content)
                category = response_data_content_dict['结论']
                reason = response_data_content_dict['原因']

                return_response_data['reason'] = reason

                category_mapping = {
                    "类别1": ("负向", 60),
                    "类别 1": ("负向", 60),
                    "类别2": ("负向", 80),
                    "类别 2": ("负向", 80),
                    "类别3": ("负向", 80),
                    "类别 3": ("负向", 80),
                    "类别4": ("负向", 70),
                    "类别 4": ("负向", 70),
                    "其他": ("中立", 50)
                }

                if category in category_mapping:
                    result, score = category_mapping[category]
                    return_response_data['result'] = result
                    return_response_data['score'] = score
                else:
                    return_response_data['result'] = category

        except (KeyError, json.JSONDecodeError, IndexError) as e:
            logger.error(f"处理响应类别时出错: {str(e)}")

        return return_response_data

    def write_qa_to_customization(self, model_name, user_id, service_target, srcpayload, payload, params, response_json,
                                deal_response, output, is_final, input_session_length, output_session_length):
        """
        将自定义请求的QA记录写入数据库

        Args:
            model_name (str): 模型名称
            user_id (str): 用户ID
            service_target (str): 服务目标
            srcpayload (dict): 原始请求负载
            payload (dict): 处理后的请求负载
            params (dict): 请求参数
            response_json (dict): 原始响应JSON
            deal_response (dict): 处理后的响应
            output (dict): 输出内容
            is_final (str): 是否为最终结果
            input_session_length (int): 输入会话长度
            output_session_length (int): 输出会话长度
        """
        try:
            if not all([model_name, user_id, service_target]):
                logger.error("必要参数缺失")
                return

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"用户不存在: {user_id}")
                return

            qa_data = {
                'source_app': 'App',
                'source_type': 'customization',
                'user': user,
                'task_id': srcpayload['task_id'],
                'input': srcpayload,
                'prompt_text': payload.get('messages', ''),
                'prompt_images': payload.get('images', []),
                'prompt_files': payload.get('files', []),
                'model': model_name,
                'prompt_params': params,
                'origin_response': response_json,
                'response': deal_response,
                'output': output,
                'is_final': is_final,
                'input_session_length': input_session_length,
                'output_session_length': output_session_length
            }

            CustomizedQA.objects.create(**qa_data)

            logger.info(f"成功创建自定义QA记录: user_id={user_id}, model={model_name}")

        except Exception as e:
            logger.error(f"创建自定义QA记录失败: {str(e)}")