"""
知识库存储与检索工具模块

本模块实现了一个知识库管理工具，用于在AI代理系统中存储、检索和管理结构化知识信息。
该工具支持多种操作类型，包括存储、检索、搜索、列表、删除、更新和统计等功能。

## 模块功能概述
- 知识存储：将文本内容存储到向量数据库和关系数据库中
- 智能检索：基于语义相似度的知识检索
- 用户隔离：每个用户自动拥有独立的专属知识库集合
- 元数据支持：支持标签、来源、重要性等元数据
- 自动集合管理：基于 user_id 自动创建和管理用户专属集合

## 输入输出规范

### 输入参数结构 (KnowledgeBaseInput)
- action: 操作类型 (store/retrieve/search/list/delete/update/stats)
- content: 要存储的知识内容 (store操作必需)
- metadata: 附加元数据信息 (可选)
  - tags: 标签列表
  - source: 知识来源
  - importance: 重要性级别 (low/medium/high)
- query: 搜索查询内容 (retrieve/search操作必需)
- limit: 返回结果最大数量 (默认: 10, 最大: 50)
- distance_threshold: 余弦距离阈值 (默认: 1.0)
- item_id: 知识项ID (delete/update操作必需)

### execute方法参数
- tool_input (Dict[str, Any]): 包含上述输入参数
- runtime_state (Any): 运行时状态信息
- user_id (Optional[Union[str, int]]): 用户标识符，用于个性化服务和日志追踪

### 输出结构
统一返回格式包含以下字段：
- status: 执行状态 ("success"/"error")
- output: 人类可读的结果描述
- type: 输出类型 ("text")
- raw_data: 原始数据对象
- metrics: 性能指标列表
- metadata: 执行元信息
- message: 简短状态消息

## 内部处理流程

### 1. 存储流程 (store)
1. 参数验证：检查content参数和user_id
2. 自动生成用户专属集合名：user_{user_id}_knowledge
3. 调用KnowledgeService.store_knowledge()
4. 生成向量嵌入并存储到向量数据库
5. 返回存储结果和知识项ID

### 2. 检索流程 (retrieve/search)
1. 参数验证：检查query参数和user_id
2. 自动使用用户专属集合：user_{user_id}_knowledge
3. 调用KnowledgeService.retrieve_knowledge()
4. 执行语义搜索和关键词搜索
5. 按相似度阈值过滤结果
6. 格式化输出结果

### 3. 管理流程 (list/delete/update/stats)
- list: 列出用户所有知识库集合
- delete: 删除指定知识项
- update: 更新知识项内容或元数据
- stats: 获取集合统计信息

## 执行逻辑架构

### 主要执行路径
1. execute() -> 分发到对应的私有方法
2. 各私有方法调用KnowledgeService服务层
3. 服务层处理数据库操作和向量运算
4. 格式化结果返回给调用者

### 错误处理机制
- 参数验证失败返回错误状态
- 异常捕获并记录日志
- 统一错误响应格式
- 保护性编程防止系统崩溃

## 函数调用关系

### 内部函数调用链
execute() -> _store_knowledge()/_retrieve_knowledge()/_search_knowledge()/_list_collections()/_delete_knowledge()/_update_knowledge()/_get_collection_stats()

### 方法间调用关系
- execute(): 主入口，负责操作分发
- _store_knowledge(): 处理存储逻辑
- _retrieve_knowledge(): 处理检索逻辑
- _search_knowledge(): 委托给_retrieve_knowledge()
- _list_collections(): 列出集合
- _delete_knowledge(): 删除知识项
- _update_knowledge(): 更新知识项
- _get_collection_stats(): 获取统计信息

## 外部依赖关系

### 核心框架依赖
- tools.core.base.BaseTool: 工具基类，提供基础功能
- tools.core.registry.register_tool: 工具注册装饰器
- tools.core.types.ToolType: 工具类型枚举

### 业务服务依赖
- knowledge.services.KnowledgeService: 知识管理服务层
  - store_knowledge(): 存储知识到数据库和向量库
  - retrieve_knowledge(): 检索知识内容
  - list_collections(): 列出用户集合
  - delete_knowledge(): 删除知识项
  - update_knowledge(): 更新知识项
  - get_collection_stats(): 获取统计信息

### 系统依赖
- logging: Django日志系统
- typing: 类型注解支持

## 集合命名规范
用户集合名称格式: user_{user_id}_knowledge
- 每个用户拥有唯一的专属知识库集合
- 自动处理用户ID中的特殊字符（替换为下划线）
- 确保不同用户的知识完全隔离
- 无需手动指定集合名称，系统自动管理

## 性能考虑
- 限制单次检索结果数量(最大50条)
- 使用向量相似度阈值过滤结果
- 批量操作优化
- 异常处理不影响系统稳定性
"""

from tools.core.base import BaseTool
from tools.core.registry import register_tool
from tools.core.types import ToolType
from typing import Dict, Any, Optional, Union, List, Literal
from pydantic import BaseModel, Field
import logging
from knowledge.services import KnowledgeService

logger = logging.getLogger("django")


class KnowledgeMetadata(BaseModel):
    """知识元数据模型"""
    tags: Optional[List[str]] = Field(
        default=None,
        description="标签列表"
    )
    source: Optional[str] = Field(
        default=None,
        description="知识来源"
    )
    importance: Optional[Literal["low", "medium", "high"]] = Field(
        default=None,
        description="重要性级别"
    )


class KnowledgeBaseInput(BaseModel):
    """知识库工具输入参数模型"""
    action: Literal["store", "retrieve", "search", "list", "delete", "update", "stats"] = Field(
        description="要执行的操作类型"
    )
    # 移除 collection_name 参数，改为使用 user_id 自动生成
    content: Optional[str] = Field(
        default=None,
        description="要存储的知识内容（store操作必需）"
    )
    metadata: Optional[KnowledgeMetadata] = Field(
        default=None,
        description="附加的元数据信息"
    )
    query: Optional[str] = Field(
        default=None,
        description="搜索查询（retrieve/search操作必需）"
    )
    limit: Optional[int] = Field(
        default=10,
        description="返回结果的最大数量",
        le=50
    )
    distance_threshold: Optional[float] = Field(
        default=1.0,
        description="余弦距离阈值（0-2之间，越小越相似）"
    )
    item_id: Optional[int] = Field(
        default=None,
        description="知识项ID（delete/update操作必需）"
    )

@register_tool(
    name="KnowledgeBase",
    description="知识库存储和检索工具。输入：操作类型(store/retrieve/search)和相关参数。输出：存储确认或检索结果。用途：在对话中存储重要信息、检索历史记录、搜索相关知识。支持：向量数据库存储、语义搜索、上下文记忆管理。",
    tool_type=ToolType.RETRIEVAL,
    category="retrieval"
)
class KnowledgeBaseTool(BaseTool):
    """知识库管理工具 - 用于存储和检索结构化知识"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.service = KnowledgeService()
    
    def get_input_schema(self) -> Dict[str, Any]:
        return KnowledgeBaseInput.model_json_schema()
    
    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        # 使用Pydantic模型验证输入
        try:
            parsed_input = KnowledgeBaseInput(**tool_input)
        except Exception as e:
            return {
                "status": "error",
                "output": f"输入参数验证失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "error_type": "ValidationError",
                    "user_id": user_id
                },
                "message": f"输入参数验证失败: {str(e)}"
            }
        
        action = parsed_input.action
        
        # 检查 user_id 是否存在
        if not user_id:
            return {
                "status": "error",
                "output": "知识库操作需要提供 user_id",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": "Missing user_id",
                    "error_type": "ValidationError"
                },
                "message": "知识库操作失败：缺少用户标识"
            }
        
        # 基于 user_id 生成唯一的 collection name
        # 将user_id转换为字符串并清理特殊字符
        user_id_str = str(user_id).replace('-', '_').replace(' ', '_').replace('.', '_')
        
        # 每个用户有一个专属的知识库集合
        user_collection_name = f"user_{user_id_str}_knowledge"
        logger.debug(f"使用用户专属collection: {user_collection_name} for user_id: {user_id}")
        
        try:
            if action == 'store':
                return self._store_knowledge(parsed_input, user_collection_name, user_id)
            elif action == 'retrieve':
                return self._retrieve_knowledge(parsed_input, user_collection_name, user_id)
            elif action == 'search':
                return self._search_knowledge(parsed_input, user_collection_name, user_id)
            elif action == 'list':
                return self._list_collections(user_id)
            elif action == 'delete':
                return self._delete_knowledge(parsed_input, user_id)
            elif action == 'update':
                return self._update_knowledge(parsed_input, user_id)
            elif action == 'stats':
                return self._get_collection_stats(user_collection_name)
            else:
                return {
                    "status": "error",
                    "output": f"不支持的操作类型: {action}",
                    "type": "text",
                    "metrics": [],
                    "metadata": {"user_id": user_id},
                    "message": f"执行失败：不支持的操作类型 {action}"
                }
        except Exception as e:
            logger.error(f"知识库操作失败: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "output": f"知识库操作失败: {str(e)}",
                "type": "text",
                "metrics": [],
                "metadata": {"tool_input": tool_input, "error": str(e), "user_id": user_id},
                "message": f"知识库操作失败"
            }
    
    def _store_knowledge(self, parsed_input: KnowledgeBaseInput, collection_name: str, user_id: Optional[Union[str, int]]) -> Dict[str, Any]:
        """存储知识到知识库"""
        content = parsed_input.content
        if not content:
            return {
                "status": "error",
                "output": "存储操作需要提供content参数",
                "type": "text",
                "metrics": [],
                "metadata": {"user_id": user_id},
                "message": "存储失败：缺少content参数"
            }
        
        metadata = parsed_input.metadata.model_dump() if parsed_input.metadata else {}
        
        try:
            # 使用服务层存储知识
            result = self.service.store_knowledge(
                content=content,
                collection_name=collection_name,
                user_id=user_id,
                metadata=metadata,
                source=metadata.get('source', 'agent_tool')
            )
            
            # 生成语义化输出
            output_text = f"""知识已成功存储到集合 '{collection_name}'

存储详情：
- 知识项ID: {result['item_id']}
- 向量ID: {result.get('vector_id', '无')}
- 内容预览: {result['content_preview']}
- 内容长度: {len(content)} 字符
- 已创建向量嵌入: {'是' if result.get('vector_stored', False) else '否'}"""
            
            return {
                "status": "success",
                "output": output_text,
                "type": "text",
                "raw_data": {
                    "item_id": result['item_id'],
                    "vector_id": result.get('vector_id'),
                    "collection": collection_name,
                    "content_preview": result['content_preview'],
                    "vector_stored": result.get('vector_stored', False)
                },
                "metrics": [
                    f"存储项ID: {result['item_id']}",
                    f"内容长度: {len(content)} 字符",
                    f"向量嵌入: {'已创建' if result.get('vector_stored', False) else '未创建'}"
                ],
                "metadata": {
                    "tool_input": parsed_input.model_dump(),
                    "collection_name": collection_name,
                    "user_id": user_id
                },
                "message": f"成功存储知识到集合 '{collection_name}'"
            }
            
        except Exception as e:
            logger.error(f"存储知识失败: {str(e)}", exc_info=True)
            raise
    
    def _retrieve_knowledge(self, parsed_input: KnowledgeBaseInput, collection_name: str, user_id: Optional[Union[str, int]]) -> Dict[str, Any]:
        """从知识库检索知识"""
        query = parsed_input.query
        if not query:
            return {
                "status": "error",
                "output": "检索操作需要提供query参数",
                "type": "text",
                "metrics": [],
                "metadata": {"user_id": user_id},
                "message": "检索失败：缺少query参数"
            }
        
        limit = min(parsed_input.limit, 50)  # 限制最大返回数量
        distance_threshold = parsed_input.distance_threshold
        
        try:
            # 使用服务层检索知识
            result = self.service.retrieve_knowledge(
                query=query,
                collection_name=collection_name,
                user_id=user_id,
                limit=limit,
                distance_threshold=distance_threshold
            )
            
            filtered_results = result['results']
            
            if filtered_results:
                # 格式化输出为可读的文本
                output_lines = [f"针对查询 '{query}' 找到 {len(filtered_results)} 条相关知识：\n"]
                
                for i, item in enumerate(filtered_results, 1):
                    output_lines.append(f"{i}. 知识项 (ID: {item.get('id', 'N/A')}, 相似度: {1-item.get('distance', 1):.2f})")
                    output_lines.append(f"   内容: {item.get('content', '无内容')[:200]}...")
                    if item.get('metadata'):
                        output_lines.append(f"   元数据: {item.get('metadata')}")
                    output_lines.append("")
                
                output_text = "\n".join(output_lines)
                
                avg_distance = sum(r.get('distance', 0) for r in filtered_results) / len(filtered_results) if filtered_results else 0
                
                return {
                    "status": "success",
                    "output": output_text,
                    "type": "text",
                    "raw_data": {
                        "results": filtered_results,
                        "total_count": result['total_count'],
                        "vector_results_count": result['vector_results_count'],
                        "database_results_count": result['database_results_count']
                    },
                    "metrics": [
                        f"找到 {len(filtered_results)} 条结果",
                        f"向量搜索: {result['vector_results_count']} 条",
                        f"数据库搜索: {result['database_results_count']} 条",
                        f"平均相似度: {1-avg_distance:.2f}"
                    ],
                    "metadata": {
                        "tool_input": parsed_input.model_dump(),
                        "collection_name": collection_name,
                        "user_id": user_id
                    },
                    "message": f"成功检索到 {len(filtered_results)} 条相关知识"
                }
            else:
                return {
                    "status": "success",
                    "output": f"未找到与 '{query}' 相关的知识",
                    "type": "text",
                    "raw_data": {"results": [], "total_count": 0},
                    "metrics": ["找到 0 条结果"],
                    "metadata": {
                        "tool_input": parsed_input.model_dump(),
                        "collection_name": collection_name,
                        "user_id": user_id
                    },
                    "message": "未找到相关知识"
                }
            
        except Exception as e:
            logger.error(f"检索知识失败: {str(e)}", exc_info=True)
            raise
    
    def _search_knowledge(self, parsed_input: KnowledgeBaseInput, collection_name: str, user_id: Optional[Union[str, int]]) -> Dict[str, Any]:
        """语义搜索知识库"""
        # search 和 retrieve 类似，但更注重语义匹配
        return self._retrieve_knowledge(parsed_input, collection_name, user_id)
    
    def _list_collections(self, user_id: Optional[Union[str, int]]) -> Dict[str, Any]:
        """列出所有可用的知识库集合"""
        try:
            # 使用服务层列出集合
            collection_list = self.service.list_collections(user_id=user_id)
            
            if collection_list:
                # 格式化输出
                output_lines = [f"用户 {user_id} 的知识库集合列表：\n"]
                total_items = 0
                
                for i, coll in enumerate(collection_list, 1):
                    item_count = coll.get('item_count', 0)
                    total_items += item_count
                    output_lines.append(f"{i}. {coll.get('name', '未命名')}")
                    output_lines.append(f"   - 知识项数量: {item_count}")
                    output_lines.append(f"   - 创建时间: {coll.get('created_at', '未知')}")
                    output_lines.append("")
                
                output_lines.append(f"总计: {len(collection_list)} 个集合, {total_items} 个知识项")
                output_text = "\n".join(output_lines)
            else:
                output_text = "未找到任何知识库集合"
            
            return {
                "status": "success",
                "output": output_text,
                "type": "text",
                "raw_data": collection_list,
                "metrics": [
                    f"集合数量: {len(collection_list)}",
                    f"总知识项: {sum(c.get('item_count', 0) for c in collection_list)}"
                ],
                "metadata": {"user_id": user_id},
                "message": f"找到 {len(collection_list)} 个知识库集合"
            }
            
        except Exception as e:
            logger.error(f"列出集合失败: {str(e)}", exc_info=True)
            raise
    
    def _delete_knowledge(self, parsed_input: KnowledgeBaseInput, user_id: Optional[Union[str, int]]) -> Dict[str, Any]:
        """删除知识项"""
        item_id = parsed_input.item_id
        if not item_id:
            return {
                "status": "error",
                "output": "删除操作需要提供item_id参数",
                "type": "text",
                "metrics": [],
                "metadata": {"user_id": user_id},
                "message": "删除失败：缺少item_id参数"
            }
        
        try:
            result = self.service.delete_knowledge(
                item_id=item_id,
                user_id=user_id
            )
            
            output_text = f"知识项 {item_id} 已成功删除\n集合: {result.get('collection', '未知')}"
            
            return {
                "status": "success",
                "output": output_text,
                "type": "text",
                "raw_data": result,
                "metrics": [
                    f"删除项ID: {item_id}",
                    f"删除状态: {'成功' if result.get('success') else '失败'}"
                ],
                "metadata": {
                    "tool_input": parsed_input.model_dump(),
                    "user_id": user_id
                },
                "message": result.get('message', f"知识项 {item_id} 已删除")
            }
        except Exception as e:
            logger.error(f"删除知识失败: {str(e)}", exc_info=True)
            raise
    
    def _update_knowledge(self, parsed_input: KnowledgeBaseInput, user_id: Optional[Union[str, int]]) -> Dict[str, Any]:
        """更新知识项"""
        item_id = parsed_input.item_id
        if not item_id:
            return {
                "status": "error",
                "output": "更新操作需要提供item_id参数",
                "type": "text",
                "metrics": [],
                "metadata": {"user_id": user_id},
                "message": "更新失败：缺少item_id参数"
            }
        
        content = parsed_input.content
        metadata = parsed_input.metadata.model_dump() if parsed_input.metadata else None
        
        if not content and not metadata:
            return {
                "status": "error",
                "output": "更新操作需要提供content或metadata参数",
                "type": "text",
                "metrics": [],
                "metadata": {"user_id": user_id},
                "message": "更新失败：缺少更新内容"
            }
        
        try:
            result = self.service.update_knowledge(
                item_id=item_id,
                content=content,
                metadata=metadata,
                user_id=user_id
            )
            
            updated_fields = result.get('updated_fields', {})
            output_lines = [f"知识项 {item_id} 已成功更新\n"]
            
            if updated_fields.get('content'):
                output_lines.append("- 内容: 已更新")
            if updated_fields.get('metadata'):
                output_lines.append("- 元数据: 已更新")
            
            output_text = "\n".join(output_lines)
            
            return {
                "status": "success",
                "output": output_text,
                "type": "text",
                "raw_data": result,
                "metrics": [
                    f"更新项ID: {item_id}",
                    f"内容更新: {'是' if updated_fields.get('content') else '否'}",
                    f"元数据更新: {'是' if updated_fields.get('metadata') else '否'}"
                ],
                "metadata": {
                    "tool_input": parsed_input.model_dump(),
                    "user_id": user_id
                },
                "message": f"知识项 {item_id} 已更新"
            }
        except Exception as e:
            logger.error(f"更新知识失败: {str(e)}", exc_info=True)
            raise
    
    def _get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """获取集合统计信息"""
        try:
            stats = self.service.get_collection_stats(collection_name)
            
            # 格式化输出
            output_lines = [f"集合 '{collection_name}' 的统计信息：\n"]
            output_lines.append(f"- 总知识项: {stats.get('total_items', 0)}")
            output_lines.append(f"- 创建时间: {stats.get('created_at', '未知')}")
            output_lines.append(f"- 最后更新: {stats.get('last_updated', '未知')}")
            
            if stats.get('interaction_stats'):
                output_lines.append("\n交互统计:")
                for action, count in stats['interaction_stats'].items():
                    output_lines.append(f"  - {action}: {count} 次")
            
            output_text = "\n".join(output_lines)
            
            total_interactions = sum(stats.get('interaction_stats', {}).values())
            
            return {
                "status": "success",
                "output": output_text,
                "type": "text",
                "raw_data": stats,
                "metrics": [
                    f"知识项数量: {stats.get('total_items', 0)}",
                    f"总交互次数: {total_interactions}"
                ],
                "metadata": {"collection_name": collection_name},
                "message": f"获取集合 '{collection_name}' 统计信息成功"
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}", exc_info=True)
            raise