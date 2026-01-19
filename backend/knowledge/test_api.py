"""
知识库API测试脚本
用于测试知识库的各种功能
"""
import os
import sys
import django

# 设置Django环境
sys.path.insert(0, '/Users/chagee/Repos/X/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from knowledge.api import knowledge_api
from knowledge.models import KnowledgeConfig, KnowledgeCollection, KnowledgeItem
import json


def test_knowledge_api():
    """测试知识库API的各种功能"""
    
    print("=" * 50)
    print("知识库API测试")
    print("=" * 50)
    
    # 1. 检查是否有激活的配置
    print("\n1. 检查知识库配置...")
    try:
        config = KnowledgeConfig.objects.get(is_active=True)
        print(f"✅ 找到激活的配置: {config.name}")
        print(f"   - Qdrant: {config.qdrant_host}:{config.qdrant_port}")
        print(f"   - Embedder: {config.embedder_provider}")
    except KnowledgeConfig.DoesNotExist:
        print("❌ 未找到激活的配置，需要先在Admin中配置")
        return
    
    # 2. 测试添加知识
    print("\n2. 测试添加知识...")
    test_content = "Python是一种高级编程语言，以其简洁和易读性著称。"
    result = knowledge_api.add_knowledge(
        content=test_content,
        collection_name="test_collection",
        metadata={"category": "programming", "language": "zh"},
        item_type="text"
    )
    
    if result.get('success'):
        print(f"✅ 成功添加知识，ID: {result.get('item_id')}")
        test_item_id = result.get('item_id')
    else:
        print(f"❌ 添加失败: {result.get('error')}")
        return
    
    # 3. 测试搜索知识
    print("\n3. 测试搜索知识...")
    search_results = knowledge_api.search_knowledge(
        query="Python编程",
        collection_name="test_collection",
        limit=5
    )
    
    if search_results:
        print(f"✅ 找到 {len(search_results)} 条结果")
        for i, result in enumerate(search_results[:3]):
            print(f"   [{i+1}] Score: {result.get('score', 0):.2f}")
            print(f"       Content: {result['content'][:50]}...")
    else:
        print("⚠️  未找到搜索结果")
    
    # 4. 测试更新知识
    print("\n4. 测试更新知识...")
    update_result = knowledge_api.update_knowledge(
        item_id=test_item_id,
        content="Python是一种解释型、面向对象的高级编程语言。",
        metadata={"category": "programming", "updated": True}
    )
    
    if update_result.get('success'):
        print(f"✅ 成功更新知识项 {test_item_id}")
    else:
        print(f"❌ 更新失败: {update_result.get('error')}")
    
    # 5. 测试列出知识
    print("\n5. 测试列出知识...")
    list_result = knowledge_api.list_knowledge(
        collection_name="test_collection",
        page=1,
        page_size=10
    )
    
    if list_result.get('success'):
        items = list_result.get('items', [])
        print(f"✅ 找到 {len(items)} 条知识")
        for item in items[:3]:
            print(f"   - ID: {item['id']}, Type: {item['item_type']}")
            print(f"     Content: {item['content'][:50]}...")
    else:
        print(f"❌ 列出失败: {list_result.get('error')}")
    
    # 6. 测试获取统计信息
    print("\n6. 测试获取统计信息...")
    stats = knowledge_api.get_collection_stats("test_collection")
    
    if not stats.get('error'):
        print(f"✅ 集合统计:")
        print(f"   - 总条目: {stats.get('total_items', 0)}")
        print(f"   - 类型分布: {stats.get('type_distribution', {})}")
    else:
        print(f"❌ 获取统计失败: {stats.get('error')}")
    
    # 7. 测试删除知识
    print("\n7. 测试删除知识...")
    delete_result = knowledge_api.delete_knowledge(
        item_id=test_item_id
    )
    
    if delete_result.get('success'):
        print(f"✅ 成功删除知识项 {test_item_id}")
    else:
        print(f"❌ 删除失败: {delete_result.get('error')}")
    
    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)


def test_batch_operations():
    """测试批量操作"""
    print("\n" + "=" * 50)
    print("批量操作测试")
    print("=" * 50)
    
    # 准备测试数据
    test_items = [
        {"content": "Django是Python的Web框架", "metadata": {"type": "framework"}},
        {"content": "Flask是轻量级Web框架", "metadata": {"type": "framework"}},
        {"content": "FastAPI是现代化的API框架", "metadata": {"type": "framework"}},
    ]
    
    print("\n1. 批量添加测试...")
    success_count = 0
    item_ids = []
    
    for item in test_items:
        result = knowledge_api.add_knowledge(
            content=item["content"],
            collection_name="batch_test",
            metadata=item["metadata"]
        )
        if result.get('success'):
            success_count += 1
            item_ids.append(result['item_id'])
    
    print(f"✅ 成功添加 {success_count}/{len(test_items)} 条知识")
    
    # 测试搜索
    print("\n2. 搜索批量添加的内容...")
    results = knowledge_api.search_knowledge(
        query="Web框架",
        collection_name="batch_test"
    )
    print(f"✅ 找到 {len(results)} 条相关结果")
    
    # 清理测试数据
    print("\n3. 清理测试数据...")
    for item_id in item_ids:
        knowledge_api.delete_knowledge(item_id)
    print(f"✅ 清理了 {len(item_ids)} 条测试数据")


if __name__ == "__main__":
    try:
        # 运行主要测试
        test_knowledge_api()
        
        # 运行批量操作测试
        test_batch_operations()
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()