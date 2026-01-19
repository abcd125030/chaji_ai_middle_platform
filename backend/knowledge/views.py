"""
知识库视图模块
包含知识库系统的API视图和核心业务逻辑
"""
import json
import os
import time
import logging # 新增日志功能
import requests
from typing import Optional
from requests.exceptions import RequestException
from django.conf import settings as django_settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated # 假设需要认证

from qdrant_client import QdrantClient
# from qdrant_client.http.exceptions import UnexpectedResponseError # 可用于更精确的"未找到集合"判断

from .models import KnowledgeCollection, KnowledgeItem, KnowledgeInteraction, KnowledgeConfig
from .services import KnowledgeService

logger = logging.getLogger(__name__) # 新增

# 创建全局知识服务实例
knowledge_service = KnowledgeService()


# 辅助函数：获取内部认证服务的 JWT token
def fetch_internal_jwt_token(app_id, secret):
    """
    通过内部认证服务获取 JWT token
    """
    auth_service_url = getattr(django_settings, 'INTERNAL_AUTH_SERVICE_URL',
                              os.environ.get('INTERNAL_AUTH_SERVICE_URL'))
    if not auth_service_url:
        # 最好在服务器端记录此错误，并向客户端抛出更通用的错误，
        # 或者让调用者处理配置问题。
        # 目前，这与计划中抛出 ValueError 的含义相符。
        raise ValueError("INTERNAL_AUTH_SERVICE_URL 未配置")
    
    try:
        # 假设认证服务端点是相对于基础 URL 的 /api/auth/token
        # 计划 X/docs/plans/2025-05-30_update_knowledge_auth_plan.md 使用 /api/service/auth/
        # 并期望 'access_token'。此函数期望 'token'。
        # 此函数是预先存在的，因此我将暂时保留其当前逻辑。
        # 如果此 JWT 用于 LLM，并且 LLM 期望 'Bearer <token>'，则此函数可能需要调整
        # 或者调用者需要对其进行格式化。目前，假设它返回原始 token 字符串。
        response = requests.post(
            f"{auth_service_url.rstrip('/')}/api/auth/token", # 确保没有双斜杠
            json={"app_id": app_id, "secret": secret},
            timeout=60 # 增加超时时间以适应复杂查询
        )
        response.raise_for_status() # 对不良响应(4XX 或 5XX)抛出 HTTPError
        token_data = response.json()
        access_token = token_data.get('token') # 或 'access_token'，取决于认证服务
        if not access_token:
            raise ValueError("在认证服务响应中未找到 Token。")
        return access_token
    except RequestException as e:
        # 记录详细错误 e 以进行服务器端调试
        # print(f"获取 JWT token 错误: {e}, 响应: {e.response.text if e.response else '无响应'}")
        raise ValueError(f"从认证服务获取 JWT token 失败: {str(e)}")
    except (ValueError, KeyError) as e: # 处理 JSON 解析错误或缺失键
        # print(f"认证服务响应无效: {e}")
        raise ValueError(f"认证服务响应无效: {str(e)}")


# 辅助函数：获取或创建 KnowledgeCollection
def get_or_create_knowledge_collection(collection_name_from_api, user_id_from_api, request_data=None,
                               app_id_from_request=None, secret_from_request=None):
    """
    获取或创建 KnowledgeCollection 实例
    """
    knowledge_collection, created = KnowledgeCollection.objects.get_or_create(
        name=collection_name_from_api,
        defaults={
            'description': f'Collection for {collection_name_from_api}'
        }
    )
    
    if created:
        logger.info(f"Created new knowledge collection: {collection_name_from_api}")
    
    # 确保向量存储集合存在（使用用户ID实现数据隔离）
    collection_name_with_user = f"{collection_name_from_api}_{user_id_from_api}"
    try:
        knowledge_service.get_or_create_collection(collection_name_with_user)
    except Exception as e:
        logger.error(f"Failed to create vector store collection: {e}")
        raise ValueError(f"创建向量存储集合失败: {str(e)}")
    
    return knowledge_collection


@csrf_exempt
def health_check(request):
    """
    健康检查端点
    返回:
        JsonResponse: 包含服务状态信息
    """
    return JsonResponse({"status": "ok", "message": "knowledge app is running!"})


class KnowledgeAddDataView(APIView):
    """
    知识库数据添加API视图
    
    功能:
        - 向指定知识库集合添加新数据
        - 记录数据添加交互日志
        
    请求参数:
        - user_id: 用户ID
        - collection_name: 集合名称
        - content: 要添加的内容
        - metadata: 元数据(可选)
        - app_id: 应用ID(可选)
        - secret: 应用密钥(可选)
    """
    permission_classes = [IsAuthenticated]  # 启用认证

    def post(self, request, *args, **kwargs):
        start_time = time.time()
        interaction_log = KnowledgeInteraction(interaction_type='add_data')
        # if request.user.is_authenticated: # 如果用户已认证，则记录用户
        #     interaction_log.user = request.user

        try:
            data = request.data
            user_id = data.get('user_id')
            collection_name = data.get('collection_name')
            content_to_add = data.get('content')
            metadata = data.get('metadata', {})

            # 从请求体中获取 app_id 和 secret（如果客户端提供）
            app_id_req = data.get('app_id')
            secret_req = data.get('secret')

            if not all([user_id, collection_name, content_to_add]):
                interaction_log.status_code = status.HTTP_400_BAD_REQUEST
                interaction_log.error_message = "缺少 user_id, collection_name 或 content。"
                # interaction_log.save() # 保存将在 finally 块中进行
                return Response(
                    {"error": "缺少 user_id, collection_name 或 content。"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 如果提供了 app_id，则记录 app_id，但绝不记录 secret
            log_request_payload = {"user_id": user_id, "collection_name": collection_name, "content_length": len(content_to_add), "metadata": metadata}
            if app_id_req:
                log_request_payload["app_id_provided"] = True # 指示请求中提供了 app_id
            interaction_log.request_payload = log_request_payload


            kc_instance = get_or_create_knowledge_collection(
                collection_name_from_api=collection_name,
                user_id_from_api=user_id,
                request_data=data,
                app_id_from_request=app_id_req,
                secret_from_request=secret_req
            )
            interaction_log.collection = kc_instance

            # 使用KnowledgeService存储知识
            collection_name_with_user = f"{collection_name}_{user_id}"
            add_response = knowledge_service.store_knowledge(
                content=content_to_add,
                collection_name=collection_name_with_user,
                user_id=user_id,
                metadata=metadata,
                source=metadata.get("source_identifier", f"api_add_{int(time.time())}")
            )

            response_data = {"message": "Data added successfully.", "details": add_response}
            interaction_log.response_payload = response_data
            interaction_log.status_code = status.HTTP_200_OK

        except ValueError as ve: 
            response_data = {"error": str(ve)}
            interaction_log.error_message = str(ve)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR # 如果是客户端配置问题，则为 400
            # return Response(response_data, status=interaction_log.status_code) # 响应在 finally 之后处理
        except Exception as e:
            response_data = {"error": f"添加数据失败: {str(e)}"}
            interaction_log.error_message = str(e)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            # logger.error(f"AddDataView 中发生错误: {e}", exc_info=True)
        finally:
            interaction_log.duration_ms = int((time.time() - start_time) * 1000)
            interaction_log.save()

        if interaction_log.status_code == status.HTTP_200_OK:
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(response_data, status=interaction_log.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR)


class KnowledgeSearchView(APIView):
    """
    知识库仅搜索API视图
    
    功能:
        - 从知识库检索相关信息 (不通过LLM生成答案)
        - 记录搜索交互日志
        
    请求参数:
        - user_id: 用户ID
        - collection_name: 集合名称
        - query: 查询文本
        - limit: 返回结果数量限制(默认5)
        - app_id: 应用ID(可选)
        - secret: 应用密钥(可选)
    """
    permission_classes = [IsAuthenticated]  # 启用认证

    def post(self, request, *args, **kwargs):
        start_time = time.time()
        interaction_log = KnowledgeInteraction(interaction_type='search_data') # 使用新的交互类型

        try:
            data = request.data
            user_id = data.get('user_id')
            collection_name = data.get('collection_name')
            query_text = data.get('query')
            limit = data.get('limit', 5)

            app_id_req = data.get('app_id')
            secret_req = data.get('secret')

            if not all([user_id, collection_name, query_text]):
                interaction_log.status_code = status.HTTP_400_BAD_REQUEST
                interaction_log.error_message = "缺少 user_id, collection_name 或 query。"
                return Response(
                    {"error": "缺少 user_id, collection_name 或 query。"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            log_request_payload = {"user_id": user_id, "collection_name": collection_name, "query": query_text, "limit": limit}
            if app_id_req:
                log_request_payload["app_id_provided"] = True
            interaction_log.request_payload = log_request_payload

            kc_instance = get_or_create_knowledge_collection(
                collection_name_from_api=collection_name, 
                user_id_from_api=user_id, 
                request_data=data,
                app_id_from_request=app_id_req, 
                secret_from_request=secret_req
            )
            interaction_log.collection = kc_instance

            # 使用KnowledgeService检索知识
            collection_name_with_user = f"{collection_name}_{user_id}"
            search_response = knowledge_service.retrieve_knowledge(
                query=query_text,
                collection_name=collection_name_with_user,
                user_id=user_id,
                limit=limit
            )
            
            # 直接返回原始搜索结果
            response_data = search_response.get('results', [])
            interaction_log.response_payload = response_data
            interaction_log.status_code = status.HTTP_200_OK

        except ValueError as ve: 
            response_data = {"error": str(ve)}
            interaction_log.error_message = str(ve)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        except Exception as e:
            response_data = {"error": f"搜索数据失败: {str(e)}"}
            interaction_log.error_message = str(e)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        finally:
            interaction_log.duration_ms = int((time.time() - start_time) * 1000)
            interaction_log.save()

        if interaction_log.status_code == status.HTTP_200_OK:
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(response_data, status=interaction_log.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR)


class KnowledgeQueryView(APIView):
    """
    知识库查询API视图
    
    功能:
        - 从知识库查询相关信息
        - 使用LLM生成答案
        - 记录查询交互日志
        
    请求参数:
        - user_id: 用户ID
        - collection_name: 集合名称
        - query: 查询文本
        - limit: 返回结果数量限制(默认5)
        - app_id: 应用ID(可选)
        - secret: 应用密钥(可选)
    """
    permission_classes = [IsAuthenticated]  # 启用认证

    def post(self, request, *args, **kwargs):
        start_time = time.time()
        interaction_log = KnowledgeInteraction(interaction_type='search_query')
        # if request.user.is_authenticated: # 如果用户已认证，则记录用户
        #     interaction_log.user = request.user
        
        try:
            data = request.data
            user_id = data.get('user_id')
            collection_name = data.get('collection_name')
            query_text = data.get('query')
            limit = data.get('limit', 5)

            # 从请求体中获取 app_id 和 secret（如果客户端提供）
            app_id_req = data.get('app_id')
            secret_req = data.get('secret')

            if not all([user_id, collection_name, query_text]):
                interaction_log.status_code = status.HTTP_400_BAD_REQUEST
                interaction_log.error_message = "缺少 user_id, collection_name 或 query。"
                # interaction_log.save() # 保存将在 finally 块中进行
                return Response(
                    {"error": "缺少 user_id, collection_name 或 query。"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            log_request_payload = {"user_id": user_id, "collection_name": collection_name, "query": query_text, "limit": limit}
            if app_id_req:
                log_request_payload["app_id_provided"] = True
            interaction_log.request_payload = log_request_payload

            kc_instance = get_or_create_knowledge_collection(
                collection_name_from_api=collection_name, 
                user_id_from_api=user_id, 
                request_data=data,
                app_id_from_request=app_id_req, 
                secret_from_request=secret_req
            )
            interaction_log.collection = kc_instance

            # 使用KnowledgeService检索知识
            collection_name_with_user = f"{collection_name}_{user_id}"
            search_response = knowledge_service.retrieve_knowledge(
                query=query_text,
                collection_name=collection_name_with_user,
                user_id=user_id,
                limit=limit
            )
            
            search_results = search_response.get('results', [])
            recalled_memories_text = []
            
            # 从搜索结果中提取内容
            for item in search_results:
                if item.get('content'):
                    recalled_memories_text.append(item.get('content'))
            
            final_answer = "未找到相关信息来回答问题。"
            llm_prompt_for_log = None

            if recalled_memories_text:
                context_for_llm = "基于以下信息:\n"
                for i, mem_text in enumerate(recalled_memories_text):
                    context_for_llm += f"{i+1}. {mem_text}\n"
                context_for_llm += f"\n请回答问题: {query_text}"
                
                llm_prompt_for_log = {"context_length": len(recalled_memories_text), "question": query_text}
                interaction_log.llm_prompt_data = llm_prompt_for_log
                
                # 使用配置的LLM生成答案
                from openai import OpenAI
                
                # 获取激活的配置
                try:
                    active_config = KnowledgeConfig.objects.get(is_active=True)
                    
                    client = OpenAI(
                        api_key=active_config.llm_api_key,
                        base_url=active_config.openai_base_url
                    )
                    
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "你是一个根据所提供上下文回答问题的助手。请简洁地回答。如果上下文不足，请说明。"},
                            {"role": "user", "content": context_for_llm}
                        ],
                        model=active_config.llm_model_name,
                        temperature=active_config.llm_temperature
                    )
                    final_answer = chat_completion.choices[0].message.content
                except KnowledgeConfig.DoesNotExist:
                    final_answer = "未找到激活的知识库配置。"
                    interaction_log.error_message = "未找到激活的知识库配置"
                except Exception as e_llm:
                    final_answer = f"从 LLM 生成答案时出错: {str(e_llm)}"
                    if interaction_log.error_message:
                        interaction_log.error_message += f"; LLM 错误: {str(e_llm)}"
                    else:
                        interaction_log.error_message = f"LLM 错误: {str(e_llm)}"

            response_data = {
                "answer": final_answer,
                "recalled_context_count": len(recalled_memories_text),
                "raw_search_results": search_results
            }
            interaction_log.response_payload = {"answer_length": len(final_answer), "recalled_count": len(recalled_memories_text)}
            interaction_log.status_code = status.HTTP_200_OK

        except ValueError as ve: 
            response_data = {"error": str(ve)}
            interaction_log.error_message = str(ve)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR # 或 400
            # return Response(response_data, status=interaction_log.status_code)
        except Exception as e:
            response_data = {"error": f"查询数据失败: {str(e)}"}
            interaction_log.error_message = str(e)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            # logger.error(f"QueryView 中发生错误: {e}", exc_info=True)
        finally:
            interaction_log.duration_ms = int((time.time() - start_time) * 1000)
            interaction_log.save()

        if interaction_log.status_code == status.HTTP_200_OK:
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(response_data, status=interaction_log.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR)


class KnowledgeUpdateView(APIView):
    """
    更新知识库中的知识条目
    """
    permission_classes = [IsAuthenticated]  # 启用认证
    
    def post(self, request, *args, **kwargs):
        """
        更新知识条目
        
        请求参数:
        - item_id: 知识条目ID (必需)
        - content: 新的内容 (可选)
        - metadata: 新的元数据 (可选)
        - user_id: 用户ID (可选，默认system)
        """
        start_time = time.time()
        
        # 获取请求参数
        item_id = request.data.get('item_id')
        content = request.data.get('content')
        metadata = request.data.get('metadata')
        user_id = request.data.get('user_id', 'system')
        
        # 参数验证
        if not item_id:
            return Response(
                {"error": "item_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if content is None and metadata is None:
            return Response(
                {"error": "At least one of content or metadata must be provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建交互记录
        interaction_log = KnowledgeInteraction(
            interaction_type='add_data',  # 使用add_data表示更新
            request_payload={
                'item_id': item_id,
                'content': content[:100] if content else None,
                'metadata': metadata,
                'user_id': user_id
            }
        )
        
        try:
            # 获取知识条目
            knowledge_item = KnowledgeItem.objects.get(id=item_id)
            interaction_log.collection = knowledge_item.collection
            
            # 更新内容
            if content is not None:
                knowledge_item.content = content
            
            if metadata is not None:
                knowledge_item.metadata = metadata
            
            knowledge_item.save()
            
            # 如果有向量数据库连接，也更新向量数据库
            if knowledge_item.mem0_item_id:
                memory_instance = get_or_create_mem0_instance(
                    knowledge_item.collection.name,
                    user_id
                )
                if memory_instance:
                    try:
                        # mem0暂不支持直接更新，需要删除后重新添加
                        memory_instance.delete(knowledge_item.mem0_item_id)
                        result = memory_instance.add(
                            messages=knowledge_item.content,
                            user_id=user_id,
                            metadata=knowledge_item.metadata
                        )
                        if isinstance(result, dict):
                            knowledge_item.mem0_item_id = result.get('id')
                            knowledge_item.save()
                    except Exception as e:
                        logger.warning(f"Failed to update vector database: {str(e)}")
            
            response_data = {
                "message": "Knowledge item updated successfully",
                "item_id": item_id,
                "updated_fields": {
                    "content": content is not None,
                    "metadata": metadata is not None
                }
            }
            
            interaction_log.response_payload = response_data
            interaction_log.status_code = status.HTTP_200_OK
            
        except KnowledgeItem.DoesNotExist:
            response_data = {"error": f"Knowledge item with id {item_id} does not exist"}
            interaction_log.error_message = response_data["error"]
            interaction_log.status_code = status.HTTP_404_NOT_FOUND
            
        except Exception as e:
            response_data = {"error": f"Failed to update knowledge item: {str(e)}"}
            interaction_log.error_message = str(e)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            logger.error(f"Error in KnowledgeUpdateView: {e}", exc_info=True)
            
        finally:
            interaction_log.duration_ms = int((time.time() - start_time) * 1000)
            interaction_log.save()
        
        return Response(response_data, status=interaction_log.status_code)


class KnowledgeDeleteView(APIView):
    """
    删除知识库中的知识条目
    """
    permission_classes = [IsAuthenticated]  # 启用认证
    
    def post(self, request, *args, **kwargs):
        """
        删除知识条目
        
        请求参数:
        - item_id: 知识条目ID (必需)
        - user_id: 用户ID (可选，默认system)
        """
        start_time = time.time()
        
        # 获取请求参数
        item_id = request.data.get('item_id')
        user_id = request.data.get('user_id', 'system')
        
        # 参数验证
        if not item_id:
            return Response(
                {"error": "item_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建交互记录
        interaction_log = KnowledgeInteraction(
            interaction_type='delete_data',
            request_payload={
                'item_id': item_id,
                'user_id': user_id
            }
        )
        
        try:
            # 获取知识条目
            knowledge_item = KnowledgeItem.objects.get(id=item_id)
            interaction_log.collection = knowledge_item.collection
            
            # 如果有向量数据库ID，先从向量数据库删除
            if knowledge_item.mem0_item_id:
                memory_instance = get_or_create_mem0_instance(
                    knowledge_item.collection.name,
                    user_id
                )
                if memory_instance:
                    try:
                        memory_instance.delete(knowledge_item.mem0_item_id)
                        logger.info(f"Deleted from vector database: {knowledge_item.mem0_item_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete from vector database: {str(e)}")
            
            # 删除数据库记录
            collection_name = knowledge_item.collection.name
            knowledge_item.delete()
            
            response_data = {
                "message": "Knowledge item deleted successfully",
                "item_id": item_id,
                "collection": collection_name
            }
            
            interaction_log.response_payload = response_data
            interaction_log.status_code = status.HTTP_200_OK
            
        except KnowledgeItem.DoesNotExist:
            response_data = {"error": f"Knowledge item with id {item_id} does not exist"}
            interaction_log.error_message = response_data["error"]
            interaction_log.status_code = status.HTTP_404_NOT_FOUND
            
        except Exception as e:
            response_data = {"error": f"Failed to delete knowledge item: {str(e)}"}
            interaction_log.error_message = str(e)
            interaction_log.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            logger.error(f"Error in KnowledgeDeleteView: {e}", exc_info=True)
            
        finally:
            interaction_log.duration_ms = int((time.time() - start_time) * 1000)
            interaction_log.save()
        
        return Response(response_data, status=interaction_log.status_code)


class KnowledgeListView(APIView):
    """
    列出知识库中的知识条目
    """
    permission_classes = [IsAuthenticated]  # 启用认证
    
    def get(self, request, *args, **kwargs):
        """
        列出知识条目
        
        查询参数:
        - collection_name: 集合名称 (可选)
        - page: 页码 (默认1)
        - page_size: 每页数量 (默认20，最大100)
        - status: 条目状态 (可选)
        """
        # 获取查询参数
        collection_name = request.query_params.get('collection_name')
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        item_status = request.query_params.get('status', 'active')
        
        # 构建查询
        queryset = KnowledgeItem.objects.all()
        
        if collection_name:
            try:
                collection = KnowledgeCollection.objects.get(name=collection_name)
                queryset = queryset.filter(collection=collection)
            except KnowledgeCollection.DoesNotExist:
                return Response(
                    {"error": f"Collection '{collection_name}' does not exist"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if item_status:
            queryset = queryset.filter(status=item_status)
        
        # 分页
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        items = queryset[start_index:end_index]
        
        # 构建响应
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'collection': item.collection.name,
                'content_preview': item.content[:200] + "..." if len(item.content) > 200 else item.content,
                'item_type': item.item_type,
                'status': item.status,
                'metadata': item.metadata,
                'source_identifier': item.source_identifier,
                'mem0_item_id': item.mem0_item_id,
                'added_at': item.added_at.isoformat(),
                'last_accessed_at': item.last_accessed_at.isoformat() if item.last_accessed_at else None
            })
        
        response_data = {
            'items': items_data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


class KnowledgeBatchAddView(APIView):
    """
    批量添加知识到知识库
    """
    permission_classes = [IsAuthenticated]  # 启用认证
    
    def post(self, request, *args, **kwargs):
        """
        批量添加知识条目
        
        请求参数:
        - items: 知识条目列表 (必需)
          - content: 内容 (必需)
          - metadata: 元数据 (可选)
          - item_type: 类型 (可选，默认text)
        - collection_name: 集合名称 (可选，默认default)
        - user_id: 用户ID (可选，默认system)
        """
        start_time = time.time()
        
        # 获取请求参数
        items = request.data.get('items', [])
        collection_name = request.data.get('collection_name', 'default')
        user_id = request.data.get('user_id', 'system')
        
        # 参数验证
        if not items or not isinstance(items, list):
            return Response(
                {"error": "items must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(items) > 100:
            return Response(
                {"error": "Maximum 100 items allowed in batch operation"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取或创建集合
        collection, created = KnowledgeCollection.objects.get_or_create(
            name=collection_name,
            defaults={'description': f'Collection {collection_name}'}
        )
        
        # 获取mem0实例
        memory_instance = get_or_create_mem0_instance(collection_name, user_id)
        
        # 批量处理
        success_items = []
        failed_items = []
        
        for idx, item_data in enumerate(items):
            try:
                # 验证单个条目
                content = item_data.get('content')
                if not content:
                    failed_items.append({
                        'index': idx,
                        'error': 'content is required'
                    })
                    continue
                
                metadata = item_data.get('metadata', {})
                item_type = item_data.get('item_type', 'text')
                
                # 创建知识条目
                knowledge_item = KnowledgeItem.objects.create(
                    collection=collection,
                    content=content,
                    metadata=metadata,
                    item_type=item_type,
                    status='active'
                )
                
                # 尝试存储到向量数据库
                vector_id = None
                if memory_instance:
                    try:
                        result = memory_instance.add(
                            messages=content,
                            user_id=user_id,
                            metadata=metadata
                        )
                        if isinstance(result, dict):
                            vector_id = result.get('id')
                            knowledge_item.mem0_item_id = vector_id
                            knowledge_item.save()
                    except Exception as e:
                        logger.warning(f"Failed to store item {idx} in vector database: {str(e)}")
                
                success_items.append({
                    'index': idx,
                    'item_id': knowledge_item.id,
                    'vector_id': vector_id
                })
                
            except Exception as e:
                failed_items.append({
                    'index': idx,
                    'error': str(e)
                })
                logger.error(f"Failed to process item {idx}: {e}")
        
        # 记录交互
        interaction_log = KnowledgeInteraction.objects.create(
            collection=collection,
            interaction_type='add_data',
            request_payload={
                'batch_size': len(items),
                'collection_name': collection_name,
                'user_id': user_id
            },
            response_payload={
                'success_count': len(success_items),
                'failed_count': len(failed_items)
            },
            duration_ms=int((time.time() - start_time) * 1000),
            status_code=status.HTTP_200_OK if not failed_items else status.HTTP_207_MULTI_STATUS
        )
        
        response_data = {
            'message': f'Batch operation completed: {len(success_items)} succeeded, {len(failed_items)} failed',
            'success_items': success_items,
            'failed_items': failed_items,
            'collection': collection_name
        }
        
        return Response(
            response_data,
            status=status.HTTP_200_OK if not failed_items else status.HTTP_207_MULTI_STATUS
        )


class KnowledgeBatchDeleteView(APIView):
    """
    批量删除知识库中的知识条目
    """
    permission_classes = [IsAuthenticated]  # 启用认证
    
    def post(self, request, *args, **kwargs):
        """
        批量删除知识条目
        
        请求参数:
        - item_ids: 知识条目ID列表 (必需)
        - user_id: 用户ID (可选，默认system)
        """
        start_time = time.time()
        
        # 获取请求参数
        item_ids = request.data.get('item_ids', [])
        user_id = request.data.get('user_id', 'system')
        
        # 参数验证
        if not item_ids or not isinstance(item_ids, list):
            return Response(
                {"error": "item_ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(item_ids) > 100:
            return Response(
                {"error": "Maximum 100 items allowed in batch operation"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 批量处理
        success_items = []
        failed_items = []
        collections_affected = set()
        
        for item_id in item_ids:
            try:
                # 获取知识条目
                knowledge_item = KnowledgeItem.objects.get(id=item_id)
                collection_name = knowledge_item.collection.name
                collections_affected.add(collection_name)
                
                # 如果有向量数据库ID，先从向量数据库删除
                if knowledge_item.mem0_item_id:
                    memory_instance = get_or_create_mem0_instance(collection_name, user_id)
                    if memory_instance:
                        try:
                            memory_instance.delete(knowledge_item.mem0_item_id)
                        except Exception as e:
                            logger.warning(f"Failed to delete item {item_id} from vector database: {str(e)}")
                
                # 删除数据库记录
                knowledge_item.delete()
                
                success_items.append({
                    'item_id': item_id,
                    'collection': collection_name
                })
                
            except KnowledgeItem.DoesNotExist:
                failed_items.append({
                    'item_id': item_id,
                    'error': 'Item does not exist'
                })
            except Exception as e:
                failed_items.append({
                    'item_id': item_id,
                    'error': str(e)
                })
                logger.error(f"Failed to delete item {item_id}: {e}")
        
        # 记录交互（为每个受影响的集合记录）
        for collection_name in collections_affected:
            try:
                collection = KnowledgeCollection.objects.get(name=collection_name)
                KnowledgeInteraction.objects.create(
                    collection=collection,
                    interaction_type='delete_data',
                    request_payload={
                        'batch_size': len(item_ids),
                        'user_id': user_id
                    },
                    response_payload={
                        'success_count': len(success_items),
                        'failed_count': len(failed_items)
                    },
                    duration_ms=int((time.time() - start_time) * 1000),
                    status_code=status.HTTP_200_OK if not failed_items else status.HTTP_207_MULTI_STATUS
                )
            except:
                pass
        
        response_data = {
            'message': f'Batch delete completed: {len(success_items)} succeeded, {len(failed_items)} failed',
            'success_items': success_items,
            'failed_items': failed_items
        }
        
        return Response(
            response_data,
            status=status.HTTP_200_OK if not failed_items else status.HTTP_207_MULTI_STATUS
        )
