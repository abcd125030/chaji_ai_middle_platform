"""
知识库使用示例
展示其他Django应用如何调用知识库功能
"""

# ========================================
# 示例1: 在chat应用中使用知识库
# ========================================

def chat_with_knowledge_example():
    """
    在聊天应用中集成知识库搜索
    """
    from knowledge.api import knowledge_api
    
    def process_chat_message(user_message, user_id="user_001"):
        # 1. 先从知识库搜索相关内容
        knowledge_results = knowledge_api.search_knowledge(
            query=user_message,
            collection_name="chat_knowledge",
            user_id=user_id,
            limit=5,
            threshold=0.7
        )
        
        # 2. 构建上下文
        context = ""
        if knowledge_results:
            context = "\n".join([
                f"- {result['content']}" 
                for result in knowledge_results[:3]
            ])
        
        # 3. 生成回复（这里是示例）
        if context:
            response = f"基于知识库信息：\n{context}\n\n我的回答是..."
        else:
            response = "抱歉，我没有找到相关信息。"
        
        return response


# ========================================
# 示例2: 在agentic工作流中使用知识库
# ========================================

def agentic_knowledge_node_example():
    """
    创建一个知识库节点用于agentic工作流
    """
    from knowledge.api import knowledge_api
    
    class KnowledgeNode:
        """知识库节点"""
        
        def __init__(self, collection_name="agentic_knowledge"):
            self.collection_name = collection_name
        
        def execute(self, input_data):
            """执行节点逻辑"""
            action = input_data.get("action")
            
            if action == "search":
                # 搜索知识
                query = input_data.get("query")
                results = knowledge_api.search_knowledge(
                    query=query,
                    collection_name=self.collection_name,
                    limit=10
                )
                return {"results": results}
            
            elif action == "add":
                # 添加知识
                content = input_data.get("content")
                metadata = input_data.get("metadata", {})
                result = knowledge_api.add_knowledge(
                    content=content,
                    collection_name=self.collection_name,
                    metadata=metadata
                )
                return result
            
            elif action == "update":
                # 更新知识
                item_id = input_data.get("item_id")
                content = input_data.get("content")
                result = knowledge_api.update_knowledge(
                    item_id=item_id,
                    content=content
                )
                return result
            
            else:
                return {"error": "Unknown action"}


# ========================================
# 示例3: 批量导入数据到知识库
# ========================================

def batch_import_example():
    """
    批量导入FAQ数据到知识库
    """
    from knowledge.api import knowledge_api
    
    # 准备FAQ数据
    faq_data = [
        {
            "question": "如何重置密码？",
            "answer": "点击登录页面的'忘记密码'链接，输入注册邮箱，按照邮件指引重置密码。",
            "category": "账户"
        },
        {
            "question": "支持哪些支付方式？",
            "answer": "我们支持微信支付、支付宝、银行卡等多种支付方式。",
            "category": "支付"
        },
        # ... 更多FAQ
    ]
    
    # 批量导入
    success_count = 0
    failed_count = 0
    
    for faq in faq_data:
        content = f"问题：{faq['question']}\n答案：{faq['answer']}"
        metadata = {
            "type": "faq",
            "category": faq["category"],
            "question": faq["question"]
        }
        
        result = knowledge_api.add_knowledge(
            content=content,
            collection_name="faq_knowledge",
            metadata=metadata,
            item_type="faq"
        )
        
        if result.get("success"):
            success_count += 1
        else:
            failed_count += 1
            print(f"Failed to import: {faq['question']}")
    
    print(f"Import completed: {success_count} succeeded, {failed_count} failed")


# ========================================
# 示例4: 在Celery任务中使用知识库
# ========================================

def celery_task_example():
    """
    在Celery异步任务中处理知识库
    """
    from celery import shared_task
    from knowledge.api import knowledge_api
    
    @shared_task
    def process_document_task(document_path, collection_name="documents"):
        """
        异步处理文档并存入知识库
        """
        try:
            # 1. 读取文档内容（示例）
            with open(document_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 2. 分块处理（如果文档很大）
            chunk_size = 1000
            chunks = [content[i:i+chunk_size] 
                     for i in range(0, len(content), chunk_size)]
            
            # 3. 存入知识库
            results = []
            for i, chunk in enumerate(chunks):
                result = knowledge_api.add_knowledge(
                    content=chunk,
                    collection_name=collection_name,
                    metadata={
                        "source": document_path,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    },
                    item_type="document"
                )
                results.append(result)
            
            return {
                "success": True,
                "chunks_processed": len(chunks),
                "results": results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# ========================================
# 示例5: 创建知识库管理命令
# ========================================

def management_command_example():
    """
    Django管理命令示例
    文件位置: management/commands/manage_knowledge.py
    """
    from django.core.management.base import BaseCommand
    from knowledge.api import knowledge_api
    
    class Command(BaseCommand):
        help = '管理知识库数据'
        
        def add_arguments(self, parser):
            parser.add_argument('action', type=str, help='Action to perform')
            parser.add_argument('--collection', type=str, default='default')
            parser.add_argument('--query', type=str, help='Search query')
            parser.add_argument('--content', type=str, help='Content to add')
        
        def handle(self, *args, **options):
            action = options['action']
            collection = options['collection']
            
            if action == 'search':
                query = options.get('query')
                if not query:
                    self.stdout.write(self.style.ERROR('Query is required'))
                    return
                
                results = knowledge_api.search_knowledge(
                    query=query,
                    collection_name=collection
                )
                
                for result in results:
                    self.stdout.write(f"Score: {result['score']:.2f}")
                    self.stdout.write(f"Content: {result['content'][:100]}...")
                    self.stdout.write("-" * 50)
            
            elif action == 'add':
                content = options.get('content')
                if not content:
                    self.stdout.write(self.style.ERROR('Content is required'))
                    return
                
                result = knowledge_api.add_knowledge(
                    content=content,
                    collection_name=collection
                )
                
                if result.get('success'):
                    self.stdout.write(
                        self.style.SUCCESS(f"Added item {result['item_id']}")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"Failed: {result.get('error')}")
                    )
            
            elif action == 'stats':
                stats = knowledge_api.get_collection_stats(collection)
                self.stdout.write(f"Collection: {collection}")
                self.stdout.write(f"Total items: {stats.get('total_items', 0)}")
                self.stdout.write(f"Type distribution: {stats.get('type_distribution', {})}")


# ========================================
# 使用说明
# ========================================
"""
使用方法：

1. 在你的Django应用中导入API：
   from knowledge.api import knowledge_api

2. 调用相应的方法：
   - 添加知识: knowledge_api.add_knowledge(content="...", collection_name="...")
   - 搜索知识: knowledge_api.search_knowledge(query="...", collection_name="...")
   - 更新知识: knowledge_api.update_knowledge(item_id=1, content="...")
   - 删除知识: knowledge_api.delete_knowledge(item_id=1)
   - 列出知识: knowledge_api.list_knowledge(collection_name="...")
   - 获取统计: knowledge_api.get_collection_stats(collection_name="...")

3. 所有方法都返回字典格式的结果，包含success字段表示操作是否成功。

4. 错误处理：
   result = knowledge_api.add_knowledge(...)
   if result.get('success'):
       # 成功处理
       item_id = result['item_id']
   else:
       # 错误处理
       error_msg = result.get('error')
"""