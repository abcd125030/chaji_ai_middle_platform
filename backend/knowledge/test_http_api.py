"""
测试知识库HTTP API
"""
import requests
import json
import os

# 禁用代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

BASE_URL = "http://localhost:6066/api/knowledge"

def test_http_apis():
    """测试HTTP API端点"""
    
    print("=" * 50)
    print("HTTP API测试")
    print("=" * 50)
    
    # 1. 健康检查
    print("\n1. 健康检查...")
    response = requests.get(f"{BASE_URL}/health/")
    if response.status_code == 200:
        print(f"✅ 健康检查通过: {response.json()}")
    else:
        print(f"❌ 健康检查失败: {response.status_code}")
    
    # 2. 添加知识
    print("\n2. 添加知识...")
    add_data = {
        "user_id": "test_user",
        "collection_name": "http_test",
        "content": "这是通过HTTP API添加的知识",
        "metadata": {"source": "http_test"}
    }
    response = requests.post(f"{BASE_URL}/data/add/", json=add_data)
    if response.status_code == 200:
        print(f"✅ 成功添加知识")
        result = response.json()
        print(f"   响应: {result.get('message')}")
    else:
        print(f"❌ 添加失败: {response.status_code}")
        print(f"   错误: {response.text}")
    
    # 3. 列出知识
    print("\n3. 列出知识...")
    response = requests.get(f"{BASE_URL}/data/list/?collection_name=http_test")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 成功获取列表")
        print(f"   找到 {result['pagination']['total_count']} 条知识")
        if result['items']:
            item_id = result['items'][0]['id']
            print(f"   第一条ID: {item_id}")
    else:
        print(f"❌ 列出失败: {response.status_code}")
    
    # 4. 搜索知识
    print("\n4. 搜索知识...")
    search_data = {
        "user_id": "test_user",
        "collection_name": "http_test",
        "query": "HTTP API"
    }
    response = requests.post(f"{BASE_URL}/data/search/", json=search_data)
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 搜索成功")
        print(f"   找到 {len(result.get('search_results', []))} 条结果")
    else:
        print(f"❌ 搜索失败: {response.status_code}")
    
    # 5. 批量添加
    print("\n5. 批量添加...")
    batch_data = {
        "collection_name": "http_test",
        "user_id": "test_user",
        "items": [
            {"content": "批量知识1", "metadata": {"index": 1}},
            {"content": "批量知识2", "metadata": {"index": 2}},
            {"content": "批量知识3", "metadata": {"index": 3}}
        ]
    }
    response = requests.post(f"{BASE_URL}/data/batch/add/", json=batch_data)
    if response.status_code in [200, 207]:
        result = response.json()
        print(f"✅ 批量添加完成")
        print(f"   成功: {len(result.get('success_items', []))}")
        print(f"   失败: {len(result.get('failed_items', []))}")
    else:
        print(f"❌ 批量添加失败: {response.status_code}")
    
    print("\n" + "=" * 50)
    print("HTTP API测试完成")
    print("=" * 50)


if __name__ == "__main__":
    print("请确保Django服务器正在运行 (python manage.py runserver)")
    print("测试URL:", BASE_URL)
    print()
    
    try:
        test_http_apis()
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保Django服务器正在运行")
    except Exception as e:
        print(f"❌ 测试失败: {e}")