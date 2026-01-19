from django.test import TestCase


## 第五步：为新接口添加单元测试
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock


class KnowledgeSearchAPITestCase(APITestCase):
    @patch('knowledge.views.get_or_create_mem0_instance')
    def test_search_success(self, mock_get_mem0):
        """
        测试 /api/knowledge/data/search/ 接口成功调用的情况
        """
        # 准备 mock 数据
        mock_memory_instance = MagicMock()
        mock_search_result = {
            "results": [
                {"id": "1", "memory": "Test memory 1", "score": 0.9},
                {"id": "2", "memory": "Test memory 2", "score": 0.8}
            ]
        }
        mock_memory_instance.search.return_value = mock_search_result
        
        mock_kc_instance = MagicMock()
        mock_get_mem0.return_value = (mock_memory_instance, mock_kc_instance)

        # 准备请求数据
        url = reverse('knowledge:knowledge_search_data')
        data = {
            "user_id": "test_user",
            "collection_name": "test_collection",
            "query": "test query",
            "limit": 2
        }

        # 发起请求
        response = self.client.post(url, data, format='json')

        # 断言
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, mock_search_result)
        
        # 验证 mock 是否被调用
        mock_get_mem0.assert_called_once()
        mock_memory_instance.search.assert_called_once_with(
            query="test query",
            user_id="test_user",
            limit=2
        )

    def test_search_missing_params(self):
        """
        测试缺少必要参数时接口返回 400
        """
        url = reverse('knowledge:knowledge_search_data')
        data = {
            "user_id": "test_user",
            "collection_name": "test_collection",
            # "query" is missing
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)# Create your tests here.
