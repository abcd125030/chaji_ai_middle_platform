"""
知识库服务层模块
提供知识库相关的业务逻辑服务
使用 LangChain VectorStore 替代 mem0
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.db import transaction
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from typing import List
import uuid
import requests

from .models import KnowledgeCollection, KnowledgeItem, KnowledgeInteraction, KnowledgeConfig
from .config_bridge import knowledge_config_bridge

logger = logging.getLogger("django")


class AliyunEmbeddings(Embeddings):
    """阿里云兼容的嵌入模型"""
    
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 阿里云 API 使用 input 参数（OpenAI 兼容）
        data = {
            "model": self.model,
            "input": texts
        }
        
        # text-embedding-v4 支持通过 dimensions 参数指定维度
        if self.model == 'text-embedding-v4':
            data["dimensions"] = 2048  # 硬编码使用 2048 维度
        
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            raise Exception(f"Embedding API error: {response.text}")
        
        result = response.json()
        embeddings = [item["embedding"] for item in result["data"]]
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        return self.embed_documents([text])[0]


class KnowledgeService:
    """知识库服务类 - 封装所有知识库相关业务逻辑"""
    
    def __init__(self):
        self._qdrant_client = None
        self._vectorstore = None
        self._embeddings = None
        self._active_config = None
        
    def get_active_config(self) -> KnowledgeConfig:
        """获取当前激活的知识库配置"""
        if self._active_config is None:
            try:
                self._active_config = KnowledgeConfig.objects.get(is_active=True)
            except KnowledgeConfig.DoesNotExist:
                raise ValueError("未找到激活的知识库配置。请在管理后台配置并激活一个。")
            except KnowledgeConfig.MultipleObjectsReturned:
                logger.error("发现多个激活的知识库配置")
                raise ValueError("找到多个激活的知识库配置。请确保只有一个配置处于激活状态。")
        return self._active_config
    
    def get_qdrant_client(self) -> QdrantClient:
        """获取或创建 Qdrant 客户端"""
        if self._qdrant_client is None:
            kb_config = self.get_active_config()
            vector_config = knowledge_config_bridge.get_vector_store_config()
            
            if vector_config['provider'] != 'qdrant':
                raise ValueError(f"当前配置的向量存储不是 Qdrant: {vector_config['provider']}")
            
            qdrant_config = vector_config['config']
            
            # 临时清除代理环境变量
            old_proxies = {}
            proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'no_proxy', 'NO_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    old_proxies[var] = os.environ[var]
                    del os.environ[var]
            
            os.environ['NO_PROXY'] = 'localhost,127.0.0.1,*.local'
            os.environ['no_proxy'] = 'localhost,127.0.0.1,*.local'
            
            try:
                self._qdrant_client = QdrantClient(
                    host=qdrant_config['host'],
                    port=qdrant_config['port'],
                    api_key=qdrant_config.get('api_key'),
                    prefer_grpc=False,
                    timeout=10,
                    https=False
                )
                logger.info(f"成功连接到 Qdrant: {qdrant_config['host']}:{qdrant_config['port']}")
            finally:
                # 恢复代理设置
                for var, value in old_proxies.items():
                    os.environ[var] = value
                if 'NO_PROXY' not in old_proxies:
                    del os.environ['NO_PROXY']
                if 'no_proxy' not in old_proxies:
                    del os.environ['no_proxy']
        
        return self._qdrant_client
    
    def get_embeddings(self):
        """获取嵌入模型实例"""
        if self._embeddings is None:
            embedder_config = knowledge_config_bridge.get_embedder_config()
            
            # 从配置中提取必要信息
            # 硬编码使用 text-embedding-v4，支持 2048 维度
            model = 'text-embedding-v4'  # 强制使用 v4 模型
            api_key = embedder_config['config'].get('api_key', '')
            base_url = embedder_config['config'].get('openai_base_url') or embedder_config['config'].get('base_url')
            provider = embedder_config.get('provider', 'openai')
            
            # 根据 provider 选择合适的嵌入类
            if provider in ['openai', 'aliyun'] and 'dashscope.aliyuncs.com' in (base_url or ''):
                # 使用自定义的阿里云嵌入类
                self._embeddings = AliyunEmbeddings(
                    model=model,
                    api_key=api_key,
                    base_url=base_url
                )
                logger.info(f"初始化阿里云嵌入模型: {model} (硬编码2048维), base_url: {base_url}")
            else:
                # 使用标准的 OpenAI 嵌入类
                from langchain_openai import OpenAIEmbeddings
                self._embeddings = OpenAIEmbeddings(
                    model=model,
                    openai_api_key=api_key,
                    openai_api_base=base_url
                )
                logger.info(f"初始化 OpenAI 嵌入模型: {model} (硬编码2048维), base_url: {base_url}")
        
        return self._embeddings
    
    def get_or_create_collection(self, collection_name: str) -> None:
        """获取或创建 Qdrant 集合"""
        client = self.get_qdrant_client()
        kb_config = self.get_active_config()
        
        # 检查集合是否存在
        collections = client.get_collections().collections
        collection_exists = any(c.name == collection_name for c in collections)
        
        if not collection_exists:
            # 创建新集合 - 硬编码使用 2048 维度（text-embedding-v4 支持）
            embedding_dims = 2048  # 硬编码 2048 维度
            
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=embedding_dims,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"创建新的 Qdrant 集合: {collection_name}, 维度: {embedding_dims}")
        else:
            logger.info(f"使用现有 Qdrant 集合: {collection_name}")
    
    def get_vectorstore(self, collection_name: str) -> QdrantVectorStore:
        """获取或创建向量存储实例"""
        # 确保集合存在
        self.get_or_create_collection(collection_name)
        
        # 创建向量存储
        client = self.get_qdrant_client()
        embeddings = self.get_embeddings()
        
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings
        )
        
        return vectorstore
    
    @transaction.atomic
    def store_knowledge(
        self, 
        content: str,
        collection_name: str = "default",
        user_id: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "tool"
    ) -> Dict[str, Any]:
        """存储知识到知识库"""
        
        if not content:
            raise ValueError("内容不能为空")
        
        metadata = metadata or {}
        
        # 获取或创建集合
        # 注意：这里的collection_name已经包含了user_id（格式: original_name_user_id）
        # 我们需要提取原始名称用于数据库存储
        original_name = collection_name.rsplit('_', 1)[0] if '_' in collection_name else collection_name
        
        collection, created = KnowledgeCollection.objects.get_or_create(
            name=original_name,
            defaults={
                'description': f'自动创建的{original_name}集合',
                'qdrant_collection_name': collection_name  # 保存实际的Qdrant集合名
            }
        )
        
        # 如果集合已存在但qdrant_collection_name为空，更新它
        if not created and not collection.qdrant_collection_name:
            collection.qdrant_collection_name = collection_name
            collection.save()
        
        if created:
            logger.info(f"创建新的知识库集合: {original_name}, Qdrant集合: {collection_name}")
        
        # 创建知识项
        knowledge_item = KnowledgeItem.objects.create(
            collection=collection,
            content=content,
            metadata=metadata,
            source_identifier=source,
            item_type='text',
            status='active'
        )
        
        # 记录交互
        KnowledgeInteraction.objects.create(
            collection=collection,
            interaction_type='add_data',
            request_payload={
                'action': 'store',
                'metadata': metadata,
                'source': source,
                'user_id': user_id
            }
        )
        
        # 尝试存储到向量数据库
        vector_id = None
        vector_stored = False
        
        try:
            vectorstore = self.get_vectorstore(collection_name)
            
            # 准备文档
            doc_metadata = {
                **metadata,
                'item_id': str(knowledge_item.id),
                'user_id': user_id,
                'source': source
            }
            
            document = Document(
                page_content=content,
                metadata=doc_metadata
            )
            
            # 添加到向量存储
            vector_ids = vectorstore.add_documents([document])
            
            if vector_ids and len(vector_ids) > 0:
                vector_id = vector_ids[0]
                vector_stored = True
                logger.info(f"成功存储到向量数据库: {vector_id}")
            else:
                logger.warning("向量存储返回空ID列表")
                
        except Exception as e:
            logger.error(f"向量数据库存储失败 - collection: {collection_name}, 错误: {str(e)}", exc_info=True)
            vector_stored = False
        
        return {
            'item_id': knowledge_item.id,
            'vector_id': vector_id,
            'collection': collection_name,
            'vector_stored': vector_stored,
            'content_preview': content[:200] + "..." if len(content) > 200 else content,
            'created_at': knowledge_item.added_at.isoformat()
        }
    
    def retrieve_knowledge(
        self,
        query: str,
        collection_name: str = "default",
        user_id: str = "system",
        limit: int = 10,
        distance_threshold: float = 1.0
    ) -> Dict[str, Any]:
        """从知识库检索知识
        
        Args:
            query: 查询文本
            collection_name: 集合名称
            user_id: 用户ID
            limit: 返回结果数量限制
            distance_threshold: 余弦距离阈值，范围[0,2]，越小越相似
        """
        
        if not query:
            raise ValueError("查询内容不能为空")
        
        limit = min(limit, 50)  # 限制最大返回数量
        
        # 尝试向量搜索
        vector_results = []
        
        try:
            vectorstore = self.get_vectorstore(collection_name)
            
            # 执行相似度搜索（返回的是余弦距离）
            docs_with_scores = vectorstore.similarity_search_with_score(
                query=query,
                k=limit
            )
            
            for doc, score in docs_with_scores:
                # score 是余弦距离，范围 [0, 2]，越小越相似
                if score <= distance_threshold:
                    vector_results.append({
                        'content': doc.page_content,
                        'distance': score,  # 直接使用距离
                        'metadata': doc.metadata,
                        'source': 'vector_db'
                    })
                    
            logger.info(f"向量搜索返回 {len(vector_results)} 条结果")
            
        except Exception as e:
            logger.warning(f"向量搜索失败: {str(e)}")
        
        # 数据库搜索作为备份
        db_results = []
        try:
            collection = KnowledgeCollection.objects.filter(
                name=collection_name
            ).first()
            
            if collection:
                items = KnowledgeItem.objects.filter(
                    collection=collection,
                    content__icontains=query
                )[:limit]
                
                for item in items:
                    db_results.append({
                        'content': item.content,
                        'distance': 0.8,  # 文本匹配给予固定距离值
                        'metadata': item.metadata or {},
                        'source': 'database',
                        'created_at': item.added_at.isoformat()
                    })
                    
                logger.info(f"数据库搜索返回 {len(db_results)} 条结果")
        except Exception as e:
            logger.warning(f"数据库搜索失败: {str(e)}")
        
        # 合并并去重结果
        all_results = []
        seen_contents = set()
        
        for result in vector_results + db_results:
            content_hash = hash(result['content'][:100])  # 使用前100字符作为去重依据
            if content_hash not in seen_contents:
                all_results.append(result)
                seen_contents.add(content_hash)
        
        # 按距离排序（越小越相似）
        all_results.sort(key=lambda x: x['distance'])
        
        # 记录交互
        try:
            if collection:
                KnowledgeInteraction.objects.create(
                    collection=collection,
                    interaction_type='search_data',
                    request_payload={
                        'query': query,
                        'user_id': user_id,
                        'limit': limit,
                        'threshold': distance_threshold
                    },
                    response_payload={
                        'results_count': len(all_results)
                    }
                )
        except Exception as e:
            logger.warning(f"记录交互失败: {str(e)}")
        
        return {
            'results': all_results[:limit],
            'total_count': len(all_results),
            'vector_results_count': len([r for r in all_results if r['source'] == 'vector_db']),
            'database_results_count': len([r for r in all_results if r['source'] == 'database'])
        }
    
    def list_collections(self, user_id: str = "system") -> List[Dict[str, Any]]:
        """列出所有可用的知识库集合"""
        collections = KnowledgeCollection.objects.all()
        collection_list = []
        
        for collection in collections:
            item_count = KnowledgeItem.objects.filter(collection=collection).count()
            interaction_count = KnowledgeInteraction.objects.filter(collection=collection).count()
            
            collection_list.append({
                'id': collection.id,
                'name': collection.name,
                'description': collection.description,
                'item_count': item_count,
                'interaction_count': interaction_count,
                'created_at': collection.created_at.isoformat(),
                'updated_at': collection.updated_at.isoformat(),
                'status': 'active'
            })
        
        return collection_list
    
    def delete_knowledge(
        self,
        item_id: int,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """删除知识项"""
        try:
            knowledge_item = KnowledgeItem.objects.get(id=item_id)
            collection = knowledge_item.collection
            
            # 记录删除交互
            KnowledgeInteraction.objects.create(
                collection=collection,
                interaction_type='delete_data',
                request_payload={
                    'action': 'delete',
                    'item_id': item_id,
                    'user_id': user_id
                }
            )
            
            # TODO: 从向量数据库删除对应文档
            # 需要在存储时记录向量ID，或使用元数据过滤删除
            
            # 删除知识项
            knowledge_item.delete()
            
            return {
                'success': True,
                'message': f'知识项 {item_id} 已删除',
                'collection': collection.name
            }
            
        except KnowledgeItem.DoesNotExist:
            raise ValueError(f"知识项 {item_id} 不存在")
    
    def update_knowledge(
        self,
        item_id: int,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """更新知识项"""
        try:
            knowledge_item = KnowledgeItem.objects.get(id=item_id)
            
            old_content = knowledge_item.content
            old_metadata = knowledge_item.metadata
            
            if content is not None:
                knowledge_item.content = content
            
            if metadata is not None:
                knowledge_item.metadata = metadata
            
            knowledge_item.save()
            
            # 记录更新交互
            KnowledgeInteraction.objects.create(
                collection=knowledge_item.collection,
                interaction_type='add_data',  # 使用add_data表示更新
                request_payload={
                    'action': 'update',
                    'item_id': item_id,
                    'user_id': user_id,
                    'old_content_preview': old_content[:100] if old_content else None,
                    'new_content_preview': content[:100] if content else None,
                    'metadata_changed': metadata != old_metadata
                }
            )
            
            # TODO: 更新向量数据库中的对应文档
            # 需要先删除旧文档，再添加新文档
            
            return {
                'success': True,
                'item_id': item_id,
                'updated_fields': {
                    'content': content is not None,
                    'metadata': metadata is not None
                }
            }
            
        except KnowledgeItem.DoesNotExist:
            raise ValueError(f"知识项 {item_id} 不存在")
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """获取集合统计信息"""
        try:
            collection = KnowledgeCollection.objects.get(
                name=collection_name
            )
            
            item_count = KnowledgeItem.objects.filter(collection=collection).count()
            
            # 按类型统计
            type_stats = {}
            for item_type in ['text', 'document', 'faq', 'memory', 'reference']:
                type_stats[item_type] = KnowledgeItem.objects.filter(
                    collection=collection,
                    item_type=item_type
                ).count()
            
            # 交互统计
            interaction_stats = {}
            for interaction_type in ['add_data', 'search_query', 'search_data', 'get_data', 'delete_data']:
                interaction_stats[interaction_type] = KnowledgeInteraction.objects.filter(
                    collection=collection,
                    interaction_type=interaction_type
                ).count()
            
            # 获取最近的项目
            recent_items = KnowledgeItem.objects.filter(
                collection=collection
            ).order_by('-added_at')[:5]
            
            recent_items_list = [
                {
                    'id': item.id,
                    'content_preview': item.content[:100] + "..." if len(item.content) > 100 else item.content,
                    'created_at': item.added_at.isoformat()
                }
                for item in recent_items
            ]
            
            return {
                'collection_name': collection_name,
                'total_items': item_count,
                'type_distribution': type_stats,
                'interaction_stats': interaction_stats,
                'recent_items': recent_items_list,
                'created_at': collection.created_at.isoformat(),
                'updated_at': collection.updated_at.isoformat()
            }
            
        except KnowledgeCollection.DoesNotExist:
            raise ValueError(f"集合 {collection_name} 不存在")