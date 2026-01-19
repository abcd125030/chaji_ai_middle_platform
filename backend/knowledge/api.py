"""
知识库内部API
供其他Django应用调用的接口，不需要通过HTTP请求
"""
import logging
from typing import Dict, List, Any, Optional
from django.db import transaction

from .models import KnowledgeCollection, KnowledgeItem, KnowledgeInteraction
from .services import KnowledgeService

logger = logging.getLogger("django")


class KnowledgeAPI:
    """
    知识库内部API类
    提供给其他Django应用调用的统一接口
    """
    
    def __init__(self):
        self.service = KnowledgeService()
    
    @transaction.atomic
    def add_knowledge(
        self,
        content: str,
        collection_name: str = "default",
        user_id: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        item_type: str = "text"
    ) -> Dict[str, Any]:
        """
        添加知识到知识库
        
        Args:
            content: 知识内容
            collection_name: 集合名称
            user_id: 用户ID
            metadata: 元数据
            item_type: 知识类型
            
        Returns:
            包含item_id等信息的字典
            
        Example:
            from knowledge.api import knowledge_api
            result = knowledge_api.add_knowledge(
                content="这是一条知识",
                collection_name="faq",
                metadata={"category": "general"}
            )
        """
        try:
            # 获取或创建集合
            collection, created = KnowledgeCollection.objects.get_or_create(
                name=collection_name,
                defaults={'description': f'Collection {collection_name}'}
            )
            
            # 创建知识条目
            knowledge_item = KnowledgeItem.objects.create(
                collection=collection,
                content=content,
                metadata=metadata or {},
                item_type=item_type,
                status='active'
            )
            
            # 使用KnowledgeService存储到向量数据库
            vector_id = None
            try:
                # 使用用户ID实现数据隔离
                collection_name_with_user = f"{collection_name}_{user_id}"
                result = self.service.store_knowledge(
                    content=content,
                    collection_name=collection_name_with_user,
                    user_id=user_id,
                    metadata=metadata,
                    source='internal_api'
                )
                vector_id = result.get('vector_id')
            except Exception as e:
                logger.warning(f"Failed to store in vector database: {str(e)}")
            
            # 记录交互
            KnowledgeInteraction.objects.create(
                collection=collection,
                interaction_type='add_data',
                request_payload={
                    'source': 'internal_api',
                    'user_id': user_id,
                    'content_length': len(content)
                }
            )
            
            return {
                'success': True,
                'item_id': knowledge_item.id,
                'vector_id': vector_id,
                'collection': collection_name
            }
            
        except Exception as e:
            logger.error(f"Failed to add knowledge: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_knowledge(
        self,
        query: str,
        collection_name: str = "default",
        user_id: str = "system",
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        搜索知识库
        
        Args:
            query: 查询字符串
            collection_name: 集合名称
            user_id: 用户ID
            limit: 返回结果数量限制
            threshold: 相似度阈值
            
        Returns:
            搜索结果列表
            
        Example:
            from knowledge.api import knowledge_api
            results = knowledge_api.search_knowledge(
                query="如何使用",
                collection_name="faq",
                limit=5
            )
        """
        try:
            results = []
            
            # 使用KnowledgeService进行向量搜索
            try:
                # 使用用户ID实现数据隔离
                collection_name_with_user = f"{collection_name}_{user_id}"
                search_response = self.service.retrieve_knowledge(
                    query=query,
                    collection_name=collection_name_with_user,
                    user_id=user_id,
                    limit=limit,
                    distance_threshold=2.0 - threshold * 2  # 转换相似度到距离
                )
                
                for result in search_response.get('results', []):
                    # 转换距离到相似度分数 (0-1)
                    score = max(0, 1 - result.get('distance', 1) / 2)
                    if score >= threshold:
                        results.append({
                            'content': result.get('content', ''),
                            'score': score,
                            'metadata': result.get('metadata', {}),
                            'source': result.get('source', 'vector_db')
                        })
            except Exception as e:
                logger.warning(f"Vector search failed: {str(e)}")
            
            # 如果向量搜索结果不足，补充数据库搜索
            if len(results) < limit:
                try:
                    collection = KnowledgeCollection.objects.get(name=collection_name)
                    db_items = KnowledgeItem.objects.filter(
                        collection=collection,
                        content__icontains=query,
                        status='active'
                    )[:limit - len(results)]
                    
                    for item in db_items:
                        results.append({
                            'content': item.content,
                            'score': 0.5,  # 文本匹配给予固定分数
                            'metadata': item.metadata or {},
                            'source': 'database',
                            'item_id': item.id
                        })
                except:
                    pass
            
            # 记录交互
            try:
                collection = KnowledgeCollection.objects.get(name=collection_name)
                KnowledgeInteraction.objects.create(
                    collection=collection,
                    interaction_type='search_data',
                    request_payload={
                        'source': 'internal_api',
                        'query': query,
                        'user_id': user_id
                    },
                    response_payload={
                        'results_count': len(results)
                    }
                )
            except:
                pass
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search knowledge: {str(e)}", exc_info=True)
            return []
    
    def update_knowledge(
        self,
        item_id: int,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        更新知识条目
        
        Args:
            item_id: 知识条目ID
            content: 新内容（可选）
            metadata: 新元数据（可选）
            user_id: 用户ID
            
        Returns:
            操作结果字典
        """
        try:
            return self.service.update_knowledge(
                item_id=item_id,
                content=content,
                metadata=metadata,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Failed to update knowledge: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_knowledge(
        self,
        item_id: int,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        删除知识条目
        
        Args:
            item_id: 知识条目ID
            user_id: 用户ID
            
        Returns:
            操作结果字典
        """
        try:
            return self.service.delete_knowledge(
                item_id=item_id,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Failed to delete knowledge: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_knowledge(
        self,
        collection_name: Optional[str] = None,
        status: str = "active",
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        列出知识条目
        
        Args:
            collection_name: 集合名称（可选）
            status: 条目状态
            page: 页码
            page_size: 每页数量
            
        Returns:
            包含items和分页信息的字典
        """
        try:
            queryset = KnowledgeItem.objects.all()
            
            if collection_name:
                collection = KnowledgeCollection.objects.get(name=collection_name)
                queryset = queryset.filter(collection=collection)
            
            if status:
                queryset = queryset.filter(status=status)
            
            total_count = queryset.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            items = queryset[start_index:end_index]
            
            items_data = []
            for item in items:
                items_data.append({
                    'id': item.id,
                    'collection': item.collection.name,
                    'content': item.content,
                    'item_type': item.item_type,
                    'status': item.status,
                    'metadata': item.metadata,
                    'added_at': item.added_at.isoformat()
                })
            
            return {
                'success': True,
                'items': items_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to list knowledge: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'items': [],
                'pagination': {}
            }
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Args:
            collection_name: 集合名称
            
        Returns:
            统计信息字典
        """
        try:
            return self.service.get_collection_stats(collection_name)
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}", exc_info=True)
            return {
                'error': str(e)
            }


# 创建全局API实例
knowledge_api = KnowledgeAPI()