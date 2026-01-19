import copy
import hashlib
import json
import os
import threading
import time
from enum import IntEnum
from threading import Lock
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import logging
from django.db import connections

from backend import settings
from customized.customization.services import CustomizationService
from customized.customization.public_opionion_analysis_service import analysis
from customized.customization.serializers import PublicOpinionSerializer
# from customized.delivery_performance.config.send_feishu import send_feishu  # 暂时注释，该模块不存在
from llm.check_utils.utils import check_token_and_get_llm

customization_service = CustomizationService()

logger = logging.getLogger(__name__)

# 输入缓存队列
task_input_cache = {}
task_input_cache_lock = Lock()


class ProcessingStatus(IntEnum):
    PROCESSED = 0    # "处理完毕" ： 0
    NO_CONTENT = 1   # "没有取到内容"  : 1
    PROCESS_FAILED = 2  # "处理失败" ： 2 # 例如从数据库中取数据失败了（数据库出了问题）
    PROCESSING = 3      # "处理中" ： 3
    PROCESSING_LLM_ERROR_NO_REPEAT = 4  # 推理大模型请求发生错误: 400 Client Error: Bad Request for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    PROCESSING_LLM_ERROR_REPEAT = 5  # "推理大模型请求发生错误: 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" ： 5
    PROCESSING_DUPLICATE = 6  # "批量处理中,不要重复相同数据的请求" ： 6

@api_view(['POST'])
def public_sentiment_analysis_service(request):
    logger.info(f"public_sentiment_analysis_service_开始执行 - IP: {request.META.get('REMOTE_ADDR')}")

    # 1. 验证token和获取LLM模型
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    check_result, llm_model_dict, user_id, service_target, service_appid = check_token_and_get_llm(request.META.get('REMOTE_ADDR'), auth_header)
    if "error" in check_result:
        return Response(check_result, status=status.HTTP_401_UNAUTHORIZED)

    # 2. 验证输入格式
    payload = request.data
    task_id = payload.get('task_id')
    serializer = PublicOpinionSerializer(data=payload)
    if not serializer.is_valid():
        logger.error(f"public_sentiment_analysis_service_输入格式错误 - TaskID: {task_id}, Errors: {serializer.errors}")
        return Response({
            'error': {
                'code': 'INVALID_REQUEST',
                'message': '请求参数无效',
                'details': serializer.errors
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # 3. 确保目录存在
    base_dir = os.path.join(settings.BASE_DIR, "yuqing")
    dirs = ['pending', 'error', 'success']
    for dir_name in dirs:
        dir_path = os.path.join(base_dir, dir_name)
        os.makedirs(dir_path, exist_ok=True)
    pending_dir = os.path.join(base_dir, 'pending')
    pending_file_path = os.path.join(pending_dir, f'{task_id}.json')

    # 4. 处理缓存和文件写入
    with task_input_cache_lock:
        if os.path.exists(pending_file_path):
            logger.info(f"public_sentiment_analysis_service_任务已存在 - TaskID: {task_id}")
            return Response({
                'task_id': task_id,
                'status': ProcessingStatus.PROCESSING.value
            }, status=status.HTTP_200_OK)

        # 写入缓存和文件
        task_data = {
            'input': payload,
            'output': {},
            "error_reason": "",
            "process": ["cache_begin"]
        }
        task_input_cache[task_id] = task_data
        logger.info(f"public_sentiment_analysis_service_新增任务缓存 - TaskID: {task_id}, 当前缓存数: {len(task_input_cache)}")

        with open(pending_file_path, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False, indent=4)

    # 5. 启动分析线程
    def run_analysis():
        try:
            analysis(payload, llm_model_dict, service_target, user_id, task_input_cache, task_input_cache_lock)
        except Exception as e:
            logger.error(f"public_sentiment_analysis_service_分析任务失败 - TaskID: {task_id}, Error: {str(e)}")
            # send_feishu(f"public_sentiment_analysis_service_分析任务失败 - TaskID: {task_id}, Error: {str(e)}")  # 暂时注释
            logger.error(f"public_sentiment_analysis_service_分析任务失败 - TaskID: {task_id}, Error: {str(e)}")
        finally:
            # 清理资源
            with task_input_cache_lock:
                task_input_cache.pop(task_id, None)
                try:
                    if os.path.exists(pending_file_path):
                        os.remove(pending_file_path)
                except Exception as e:
                    logger.error(f"public_sentiment_analysis_service_删除pending文件失败 - TaskID: {task_id}, Error: {str(e)}")
                    # send_feishu(f"public_sentiment_analysis_service_删除pending文件失败 - TaskID: {task_id}, Error: {str(e)}")  # 暂时注释
                    logger.error(f"public_sentiment_analysis_service_删除pending文件失败 - TaskID: {task_id}, Error: {str(e)}")

            # 关闭数据库连接
            for conn in connections.all():
                conn.close_if_unusable_or_obsolete()
            connections.close_all()
            logger.info(f"public_sentiment_analysis_service_释放资源完成 - TaskID: {task_id}")

    # 使用daemon线程避免阻塞主进程退出
    t = threading.Thread(target=run_analysis, daemon=True)
    t.start()

    logger.info(f"public_sentiment_analysis_service_结束执行 - TaskID: {task_id}")
    return Response({
        'task_id': task_id,
        'status': ProcessingStatus.PROCESSING.value
    }, status=status.HTTP_200_OK)
    # # C:\python_code\DjangoProject\test_login_new_lastest_舆情处理
    # print(settings.BASE_DIR)
    # # 步骤4: 舆情分析
    # payload = copy.deepcopy(request.data)
    # task_id = payload['task_id']
    # try:
    #     response_data = analysis(payload, input_model_dict, service_target, user_id)
    #     if len(response_data) > 0 and response_data['result'] != "" and response_data['reason'] != "":
    #         logger.info("api/public_opinion/chat_completion/执行完成")
    #         return Response({
    #             'task_id': task_id,
    #             'status': 0
    #         }, status=status.HTTP_200_OK)
    #     else:
    #         logger.error(f"没有得到结果")
    #         return Response({
    #             'task_id': task_id,
    #             'status': 2
    #         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # except Exception as e:
    #     logger.error(f"Unexpected error during analysis: {str(e)}")
    #     return Response({
    #         'task_id': task_id,
    #         'status': 2
    #     }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # # 步骤5: 保存分析结果(先将舆情分析结果保存到一个本地文件夹中)
    # if len(response_data) > 0 and response_data['result'] != "" and response_data['reason'] != "":
    #     # 创建目录并保存数据到文件
    #     data_dir = os.path.join(settings.BASE_DIR, 'validation_data/pending')
    #     os.makedirs(data_dir, exist_ok=True)
    #     data_file_path = os.path.join(data_dir, f'{task_id}.json')
    #     with open(data_file_path, 'w', encoding='utf-8') as f:
    #         json.dump(response_data, f, ensure_ascii=False, indent=2)
    #     # 先保存
    #     print("先将结果保存到本地")
    #     logger.info("api/public_opinion/chat_completion/执行完成")
    #     return Response({
    #         'task_id': task_id,
    #         'status': "处理完毕"
    #     }, status=status.HTTP_200_OK)
    # else:
    #     logger.info("api/public_opinion/chat_completion/执行完成")
    #     return Response({
    #         'task_id': task_id,
    #         'status': "处理失败"
    #     }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 接口2：根据会话ID获取所有的问答记录
@api_view(['POST'])
def public_sentiment_result_service(request):
    logger.info(f"public_sentiment_result_service_开始执行 - IP: {request.META.get('REMOTE_ADDR')}")

    # 1. 验证token和获取LLM模型
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    check_result, llm_model_dict, user_id, service_target, service_appid = check_token_and_get_llm(request.META.get('REMOTE_ADDR'), auth_header)
    if "error" in check_result:
        logger.error(f"public_sentiment_result_service_Token验证失败 - IP: {request.META.get('REMOTE_ADDR')}")
        return Response(check_result, status=status.HTTP_401_UNAUTHORIZED)

    # 2. 验证请求数据
    try:
        task_id = request.data['task_id']
    except (KeyError, TypeError):
        logger.error("public_sentiment_result_service_无效的请求参数")
        return Response({
            'error': '请求参数无效，缺少task_id'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 3. 优先从服务层查询结果
    try:
        result = customization_service.get_qa_result(task_id)
        if result:
            logger.info(f"public_sentiment_result_service_从服务层获取结果成功 - TaskID: {task_id}")
            return JsonResponse({
                **result,
                'error': "",
                'status': ProcessingStatus.PROCESSED.value,
                'task_id': task_id
            }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"public_sentiment_result_service_数据库查询异常 - TaskID: {task_id}, Error: {str(e)}")
        return JsonResponse({
            'task_id': task_id,
            'status': ProcessingStatus.PROCESS_FAILED.value,
            'error': str(e),
            'score': 0,
            'reason': "",
            'result': ""
        }, status=status.HTTP_200_OK)

    # 4. 检查错误文件
    error_file_path = os.path.join(settings.BASE_DIR, "yuqing", 'error', f'{task_id}.json')
    if os.path.exists(error_file_path):
        logger.info(f"public_sentiment_result_service_从错误文件获取结果 - TaskID: {task_id}")
        try:
            with open(error_file_path, 'r', encoding='utf-8') as f:
                error_data = json.load(f)
                error_reason = error_data.get("error_reason", "")
                # status_value = ProcessingStatus.PROCESSING_LLM_ERROR_REPEAT.value if "429 Client Error: Too Many Requests for url:" in error_reason else ProcessingStatus.PROCESSING_LLM_ERROR_NO_REPEAT.value
                status_value = ProcessingStatus.PROCESS_FAILED.value
                return JsonResponse({
                    'task_id': task_id,
                    'status': status_value,
                    'error': error_reason,
                    'score': 0,
                    'reason': "",
                    'result': ""
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"public_sentiment_result_service_读取错误文件失败 - TaskID: {task_id}, Error: {str(e)}")

    # 5. 默认返回处理中状态
    logger.info(f"public_sentiment_result_service_任务正在处理中 - TaskID: {task_id}")
    return JsonResponse({
        'task_id': task_id,
        'status': ProcessingStatus.NO_CONTENT.value,
        'score': 0,
        'reason': "",
        'error': "",
        'result': ""
    }, status=status.HTTP_200_OK)


# 接口3：批量处理接口
@api_view(['POST'])
def batch_public_sentiment_analysis_service(request):
    logger.info("api/public_opinion/batch_analysis/开始执行")
    ip_address = request.META.get('REMOTE_ADDR')
    logger.info("REMOTE_ADDR: " + str(ip_address))

    # 步骤1: 检查token以及获取该用户可以使用的大模型
    # 用户服务器的公网地址
    ip_address = request.META.get('REMOTE_ADDR')
    # token
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    # 检查token以及获取该用户可以使用的大模型
    check_token_result, llm_model_dict, user_id, service_target, service_appid = check_token_and_get_llm(ip_address,
                                                                                                         auth_header)
    if "error" in check_token_result:
        return Response(check_token_result, status=status.HTTP_401_UNAUTHORIZED)

    # 步骤2: 防抖处理：生成请求内容的哈希值
    request_content = json.dumps(request.data, sort_keys=True).encode()
    content_hash = hashlib.sha256(request_content).hexdigest()

    # 步骤3: 检查Redis是否存在相同哈希（假设使用redis库，需要先安装和配置）, 如果存在，则不在重复处理
    if cache.get(f"batch_request_{content_hash}"):
        return Response({'status': ProcessingStatus.PROCESSING_DUPLICATE.value, 'count': len(request.data)}, status=status.HTTP_400_BAD_REQUEST)
    cache.set(f"batch_request_{content_hash}", "processing", 60 * 10)  # 10分钟有效期
    logger.info("---batch_analysis都存储到Redis队列---")

    # 步骤4: 启动处理线程（或考虑使用Celery等任务队列）
    def process_batch_queue():
        # 对request.data中每一个子任务做analysis
        for item in request.data:
            try:
                analysis(item, llm_model_dict, service_target, user_id)
            except Exception as e:
                logger.error(f"批量处理失败: {str(e)}---" + item['task_id'])
        # 处理完后删除redis
        if cache.get(f"batch_request_{content_hash}"):
            cache.delete(f"batch_request_{content_hash}")
    threading.Thread(target=process_batch_queue).start()

    return Response({'status': ProcessingStatus.PROCESSING.value, 'count': len(request.data)}, status=status.HTTP_200_OK)


# 接受用户输入的查询指令，返回批量处理结果
@api_view(['POST'])
def batch_public_sentiment_result_service(request):
    logger.info("api/public_opinion/batch_result/开始执行")

    # 步骤1: 检查token以及获取该用户可以使用的大模型
    # 用户服务器的公网地址
    ip_address = request.META.get('REMOTE_ADDR')
    # token
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    # 检查token以及获取该用户可以使用的大模型
    check_token_result, llm_model_dict, user_id, service_target, service_appid = check_token_and_get_llm(ip_address, auth_header)
    if "error" in check_token_result:
        return Response(check_token_result, status=status.HTTP_401_UNAUTHORIZED)

    # 步骤2: 获取请求中的task_id列表
    try:
        task_ids = [item['task_id'] for item in request.data]
    except (KeyError, TypeError):
        return Response({'error': '请求参数无效'}, status=status.HTTP_400_BAD_REQUEST)

    # 步骤3: 批量查询服务层
    logger.info("开始批量查询服务层...")
    result_map = customization_service.batch_get_qa_results(task_ids)

    # 步骤4: 组装响应数据
    response_data = []
    for task_id in task_ids:
        if task_id in result_map:
            validation_data = result_map[task_id]
            validation_data['task_id'] = task_id
        else:
            logger.error(f"数据库中没有取出结果: " + "--" + str(task_id))
            validation_data = dict()
            validation_data['task_id'] = task_id
            validation_data["score"] = 0
            validation_data["reason"] = ""
            validation_data["result"] = ""
            validation_data["status"] = 1
        response_data.append(validation_data)

    logger.info(f"批量查询完成，返回{len(response_data)}条结果")
    return JsonResponse(response_data, safe=False, status=status.HTTP_200_OK)


# 清理pending文件夹中的内容
@api_view(['POST'])
def public_sentiment_pending_analysis_service(request):
    logger.info("public_sentiment_pending_analysis_service-开始执行清除缓存")
    # 1. 验证token和获取LLM模型
    check_result, llm_model_dict, user_id, service_target, service_appid = check_token_and_get_llm(
        request.META.get('REMOTE_ADDR'),
        request.META.get('HTTP_AUTHORIZATION')
    )
    
    if "error" in check_result:
        return Response(check_result, status=status.HTTP_401_UNAUTHORIZED)

    # 2. 确保所有目录存在
    base_dir = os.path.join(settings.BASE_DIR, "yuqing")
    dirs = ['pending', 'error', 'success']
    for dir_name in dirs:
        dir_path = os.path.join(base_dir, dir_name)
        os.makedirs(dir_path, exist_ok=True)

    # 3. 处理pending目录中的文件
    pending_dir = os.path.join(base_dir, 'pending')
    processed_count = 0
    error_count = 0

    def safe_remove_file(file_path, max_retries=3, delay=1):
        """安全删除文件，带有重试机制"""
        for i in range(max_retries):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return True
            except Exception as e:
                logger.warning(f"pending - 删除文件失败(尝试 {i + 1}/{max_retries}) - {file_path}, Error: {str(e)}")
                time.sleep(delay)
        return False

    for filename in os.listdir(pending_dir):
        if not filename.endswith('.json'):
            continue

        file_path = os.path.join(pending_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
                payload = task_data['input']
                task_id = payload['task_id']

                # 4. 将任务加入缓存
                with task_input_cache_lock:
                    task_input_cache[task_id] = {
                        'input': payload,
                        'output': {},
                        "error_reason": "",
                        "process": ["cache_begin"]
                    }

                # 5. 执行分析任务
                try:
                    analysis(payload, llm_model_dict, service_target, user_id,
                             task_input_cache, task_input_cache_lock)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"pending - 分析任务失败 - TaskID: {task_id}, Error: {str(e)}")
                    # send_feishu(f"pending - 分析任务失败 - TaskID: {task_id}, Error: {str(e)}")  # 暂时注释
                    logger.error(f"pending - 分析任务失败 - TaskID: {task_id}, Error: {str(e)}")
                    error_count += 1
                finally:
                    # 确保先关闭所有资源
                    for conn in connections.all():
                        conn.close_if_unusable_or_obsolete()
                    connections.close_all()

                    # 最后清理缓存
                    with task_input_cache_lock:
                        task_input_cache.pop(task_id, None)

            # 尝试删除文件
            if not safe_remove_file(file_path):
                logger.error(f"pending - 最终删除文件失败 - {file_path}")

        except Exception as e:
            logger.error(f"pending - 处理文件失败 - {filename}, Error: {str(e)}")
            error_count += 1

    logger.info(f"public_sentiment_pending_analysis_service-结束执行, 处理成功: {processed_count}, 失败: {error_count}")
    return Response({
        'status': ProcessingStatus.PROCESSED.value,
        'processed_count': processed_count,
        'error_count': error_count
    }, status=status.HTTP_200_OK)