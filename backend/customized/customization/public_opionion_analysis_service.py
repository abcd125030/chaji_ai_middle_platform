import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor

from backend import settings
from customized.customization.conf import text_max_retries, text_maybe_reused_errors
# from customized.delivery_performance.config.send_feishu import send_feishu  # 暂时注释，该模块不存在
from customized.customization.services import CustomizationService
import logging
logger = logging.getLogger(__name__)
logger_pic_num = logging.getLogger('django_pic_num')


# def process_picture(pic, input_model_dict, service_target, user_id, payload, llm_service):
#     # if '阿里百炼qwen-vl-max-latest' in input_model_dict:
#     bFindUsedModel = False
#     for pic_input_model_name in input_model_dict.keys():
#         # pic_input_model_name = '阿里百炼qwen-vl-max-latest'
#         if input_model_dict[pic_input_model_name]['model_type'] == "vision":
#             bFindUsedModel = True
#             input_model_endpoint = input_model_dict[pic_input_model_name]['model_endpoint']
#             input_model_key = input_model_dict[pic_input_model_name]['model_key']
#             input_model_id = input_model_dict[pic_input_model_name]['model_id']
#             payload_content = call_picture_api(input_model_id, pic, False)
#             params = dict()
#             response_picture_data = llm_service.send_customization_picture_request(
#                 pic_input_model_name, input_model_endpoint, input_model_key, input_model_id,
#                 service_target, user_id, payload, payload_content, params
#             )
#             if len(response_picture_data) > 0 and 'error' not in response_picture_data:
#                 logger.info(f"get result {pic_input_model_name} request: " + "---" + str(payload['task_id']))
#                 return response_picture_data['choices'][0]['message']['content']
#             logger.error(f"no get result {pic_input_model_name} request: " + "---" + str(payload['task_id']))
#     if bFindUsedModel:
#         logger.error(f"所有的图片大模型都没有取到结果" + "---" + str(payload['task_id']))
#     else:
#         logger.error(f"没有找到对应的图片大模型" + "---" + str(payload['task_id']))
#     return ""

# 舆情分析
def analysis(payload, input_model_dict, service_target, user_id, task_input_cache, task_input_cache_lock):
    task_id = payload['task_id']
    custom_service = CustomizationService()

    # 1. 图片数量过多可能会影响postsql据库的稳定性，所以需要减少图片的数量
    def filter_images(images):
        n = len(images)
        if n > 3:
            middle_index = n // 2
            return [images[0], images[middle_index], images[-1]]
        return images

    # 2. 处理图片内容
    def process_images(pics):
        input_str = payload['content']
        llm_start_time = datetime.datetime.now()
        logger_pic_num.info(f"图片上传数量: {len(pics)}")
        pics = filter_images(pics)

        for pic in pics:
            for model_name, model_info in input_model_dict.items():
                if model_info['model_type'] == "vision":
                    try:
                        payload_content = call_picture_api(model_info['model_id'], pic, False)
                        response = custom_service.send_customization_picture_request(
                            model_name,
                            model_info['model_endpoint'],
                            model_info['model_key'],
                            model_info['model_id'],
                            service_target, user_id, payload, payload_content, {}
                        )

                        if response and 'error' not in response:
                            content = response['choices'][0]['message']['content']
                            input_str += f"\n{content}"
                            update_task_status(task_id, "pic_success")
                        else:
                            # 当出现PostgreSQL当前无法使用这个错误时，才发飞书告警; 如果是大模型接口400，429等错误，则并不需要飞书通知。
                            if str(response['error']).find("PostgreSQL当前无法使用") >= 0:
                                # send_feishu("task_id: " + str(task_id) + "----" + "pic_error: " + str(response['error']))  # 暂时注释
                                logger.error(f"task_id: {task_id}----pic_error: {response['error']}")
                            update_task_status(task_id, "pic_error")
                    except Exception as e:
                        # send_feishu("task_id: " + str(task_id) + "----" + "pic_error: " + f"图片处理失败 - Model: {model_name}, Error: {str(e)}")  # 暂时注释
                        logger.error(f"图片处理失败 - Model: {model_name}, Error: {str(e)}")
                        update_task_status(task_id, "pic_error")

        llm_end_time = datetime.datetime.now()
        logger.info(f'图片处理耗时: {llm_end_time - llm_start_time}')
        return input_str

    # if len(pics) > 0:
    #     logger_pic_num.info("The number of images uploaded for this public opinion analysis is : " + str(len(pics)))
    #     # 图片数量过多可能会影响POSTSQL数据库的稳定性，所以需要减少图片的数量
    #     pics = filter_images(pics)
    #     # 此处我用线程池替换(处理用户一次性传入多张图片)
    #     llm_start_time = datetime.datetime.now()
    #     max_workers = min(3, len(pics))
    #     with ThreadPoolExecutor(max_workers=max_workers) as executor:
    #         futures = []
    #         for pic in pics:
    #             future = executor.submit(process_picture, pic, input_model_dict, service_target, user_id, payload,
    #                                      llm_service)
    #             futures.append(future)

    #         for future in futures:
    #             result = future.result()
    #             if result != "":
    #                 input_str += '\n'
    #                 input_str += result
    #     llm_end_time = datetime.datetime.now()
    #     logger.info("多线程调用结束")
    #     logger.info(f'多线程调用耗时：{llm_end_time - llm_start_time}')

    # 3. 更新任务状态
    def update_task_status(task_id, status, error_msg=None):
        if task_id and task_id in task_input_cache:
            with task_input_cache_lock:
                task_input_cache[task_id]['process'].append(status)
                if error_msg:
                    task_input_cache[task_id]['error_reason'] = error_msg

    # 4. 保存结果文件
    def save_result_file(task_id, data, is_success=True):
        dir_type = 'success' if is_success else 'error'
        dir_path = os.path.join(settings.BASE_DIR, "yuqing", dir_type)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{task_id}.json")

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"保存{dir_type}文件失败 - {file_path}, Error: {str(e)}")

    # 主流程
    try:
        # 处理文字
        input_str = process_images(payload['im_body'])
        logger.debug(f"处理后的输入内容: {input_str}")

        # 生成提示词
        script_dir = os.path.dirname(os.path.abspath(__file__))
        example_path = os.path.join(script_dir, 'dict_example.json')
        prompt = make_content_prompt(input_str, example_path)

        # 调用文本模型
        for model_name, model_info in input_model_dict.items():
            if model_info['model_type'] == "reasoning":
                try:
                    payload_content = call_content_api(model_info['model_id'], prompt, False)
                    max_retries = text_max_retries
                    retry_count = 0
                    response = None

                    while retry_count < max_retries:
                        response = custom_service.send_customization_request(
                            model_name,
                            model_info['model_endpoint'],
                            model_info['model_key'],
                            model_info['model_id'],
                            service_target, user_id, payload, payload_content, {}
                        )

                        if 'error' in response and any(err in response['error'] for err in text_maybe_reused_errors):
                            retry_count += 1
                            logger.warning(f"遇到可重试错误，正在进行第{retry_count}次重试 - 任务ID: {task_id}")
                            continue
                        break

                    if 'error' in response:
                        # 当出现PostgreSQL当前无法使用这个错误时，才发飞书告警; 如果是大模型接口400，429等错误，则并不需要飞书通知。
                        if str(response['error']).find("PostgreSQL当前无法使用") >= 0:
                            # send_feishu("task_id: " + str(task_id) + "----" + "text_error: " + str(response['error']))  # 暂时注释
                            logger.error(f"task_id: {task_id}----text_error: {response['error']}")
                        update_task_status(task_id, "text_error", response['error'])
                        save_result_file(task_id, task_input_cache[task_id], False)
                    else:
                        update_task_status(task_id, "text_success")
                        with task_input_cache_lock:
                            task_input_cache[task_id]['output'] = response
                        save_result_file(task_id, task_input_cache[task_id])
                    return response

                except Exception as e:
                    error_msg = f"模型请求失败 - {model_name}: {str(e)}"
                    update_task_status(task_id, "text_error", error_msg)
                    # send_feishu("task_id: " + str(task_id) + "----" + "text_error: " + str(error_msg))  # 暂时注释
                    logger.error(f"task_id: {task_id}----text_error: {error_msg}")
                    save_result_file(task_id, task_input_cache[task_id], False)
                    return {"error": error_msg}

        logger.error("没有找到可用的文本分析模型")
        return {"error": "没有找到可用的文本分析模型"}

    except Exception as e:
        logger.error(f"舆情分析流程异常: {str(e)}")
        return {"error": f"舆情分析流程异常: {str(e)}"}


# 获取分析结果
def get_result(data_dir, task_id):
    """检查并处理验证数据文件"""
    validation_data = dict()
    pending_dir = os.path.join(data_dir, 'validation_data/pending')
    if not os.path.exists(pending_dir):
        os.makedirs(pending_dir)

    filename = os.path.join(pending_dir, task_id)
    file_path = filename + ".json"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            validation_data = json.load(f)
        # 处理响应
        processed_dir = os.path.join(data_dir, 'validation_data/processed')
        os.makedirs(processed_dir, exist_ok=True)
        os.rename(file_path, os.path.join(processed_dir, task_id) + ".json")
        logger.info(f"文件已处理: {filename}")

    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
    except Exception as e:
        logger.error(f"Unexpected error reading file: {str(e)}")
    return validation_data


#
def make_content_prompt(input_str, input_dict_example_json):
    # dict_example = {"输入": "霸王茶姬代替下单三元卖自己的优惠券", "结论": "类别3",
    #                 "原因": "此内容提到利用特定方式（优惠券代下单）获取利益，符合黑灰产信息特征。"}

    dict_examples = list()
    try:
        if not os.path.exists(input_dict_example_json):
            logger.error(f"文件 {input_dict_example_json} 不存在，请检查路径。")
        # 读取 Excel 文件
        with open(input_dict_example_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 构建DataFrame所需的数据结构
            for item in data:
                dict_example = {
                    "输入": item.get('示例输入'),
                    "结论": item.get('结论'),
                    "原因": item.get('原因'),
                }
                dict_examples.append(dict_example)
    except FileNotFoundError:
        logger.error("未找到示例文件，请检查文件路径。")
    except Exception as e:
        logger.error(f"读取文件时出现错误: {e}")

    # 构建特例部分
    reference_case_str = ""
    for i, case in enumerate(dict_examples):
        reference_case_str += f"""
        <reference_case_{i + 1}>
            需要甄别的内容：
            ```
            {case["输入"]}
            ```
            实际甄别的输出结果：
            ```
            {{
                "结论": "{case['结论']}",
                "原因": "{case['原因']}",
            }}
            ```
        </reference_case_{i + 1}>
        """

    prompt = f'''
        你现在是一个专业的舆情分析专家，专注于识别和分类文字内容中的舆情信息。请根据以下类别规则，对输入的文字内容进行判断，并给出明确结论。

        <judge_rules>
        类别 1：负面的舆情客诉信息，负面评价
            定义：用户针对产品、服务等表达不满、投诉或批评的内容。
            示例：抱怨服务质量差、产品有问题、体验不佳等。

        类别 2：数据泄露风险
            定义：文字中提及数据被非法获取、不当传播、隐私泄露等相关内容。
            示例：提到系统漏洞导致信息泄露、个人隐私被公开、未经授权的数据访问等。

        类别 3：黑灰产信息（工具开发，薅羊毛）
            定义：涉及利用工具、技术或手段非法获利、不正当获取利益的行为。
            示例：讨论如何利用漏洞获利、制作或销售作弊工具、薅取平台福利等。

        类别 4：代下单
            定义：免费或者收费给予他人优惠券或者可指定地方下单自取，代替他人进行商品或服务下单的行为。
            示例：为他人代下单，并在宣传中诱导消费者参与，借助此行为薅取商家及平台推出的优惠福利。
            
        其他：不属于上述任何类别
        </judge_rules>

        如果文字内容与上述四类无关，请明确指出原因。

        <task_requirements>
            - 根据分析规则，明确指出这段文字属于哪个类别。
            - 若属于某类别，请简要说明原因（每条原因不超过 100 字）。
            - 若都不属于，请说明具体原因。
        </task_requirements>

        <reference_case_for_align_to>
            {reference_case_str}
        </reference_case_for_align_to>
        
        以下是你要甄别的文本内容：
        {input_str}

        <judge_result_format_requirements>
        "结论"options = ["类别1", "类别2", "类别3", "类别4",  "其他"]

        "原因"rules = "简洁清晰的解释"
        </judge_result_format_requirements>

        仅允许且必须按照如下格式输出(具体内容仅作示例)：
        ```
        {{
            "结论": "类别1",
            "原因": "用户投诉奶茶饮用后出现身体不适症状（恶心、发烧、腹泻），属于负面客诉信息。"
        }}
        ```

        '''
    # logger.info(prompt)
    return prompt


# 根据content的内容生成请求的JSON数据
def call_content_api(model, content, bstream):
    # 定义请求的 JSON 数据
    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "stream": bstream,
        "max_tokens": 8096,
        "temperature": 0.7,
        "top_p": 0.7,
        "frequency_penalty": 0.5,
        "n": 1,
    }
    return data


def call_picture_api(model, picture, bstream):
    # 定义请求的 JSON 数据
    data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant."}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"{picture}"}
                    },
                    {"type": "text", "text": "简要描述图片内容，如果发现有霸王茶姬相关的内容，则需要描述出来，字数尽量不超过100字"},
                ],
            },
        ],
        "stream": bstream,
        "max_tokens": 8096,
        "temperature": 0.7,
        "top_p": 0.7,
        "frequency_penalty": 0.5,
        "n": 1,
    }
    return data

