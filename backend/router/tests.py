"""
Router模块测试
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import VendorEndpoint, VendorAPIKey, LLMModel

User = get_user_model()


class RouterModelTests(TestCase):
    """模型测试"""
    
    def setUp(self):
        """设置测试数据"""
        self.vendor_endpoint = VendorEndpoint.objects.create(
            vendor_name='TestVendor',
            vendor_id='test_vendor',
            endpoint='https://api.test.com/v1',
            service_type='Text Generation'
        )
        
        self.vendor_apikey = VendorAPIKey.objects.create(
            vendor_name='TestVendor',
            vendor_id='test_vendor',
            api_key='test_api_key_123',
            description='Test API Key'
        )
    
    def test_create_vendor_endpoint(self):
        """测试创建供应商端点"""
        self.assertEqual(self.vendor_endpoint.vendor_name, 'TestVendor')
        self.assertEqual(self.vendor_endpoint.endpoint, 'https://api.test.com/v1')
    
    def test_create_llm_model(self):
        """测试创建LLM模型"""
        model = LLMModel.objects.create(
            name='Test Model',
            model_id='test-model-1',
            model_type='text',
            endpoint=self.vendor_endpoint,
            api_standard='openai'
        )
        self.assertEqual(model.name, 'Test Model')
        self.assertEqual(model.model_type, 'text')
    
    def test_embedding_model_type(self):
        """测试Embedding模型类型"""
        model = LLMModel.objects.create(
            name='Embedding Model',
            model_id='embed-1',
            model_type='embedding',
            endpoint=self.vendor_endpoint,
            api_standard='openai'
        )
        self.assertEqual(model.model_type, 'embedding')
    
    def test_rerank_model_type(self):
        """测试Rerank模型类型"""
        model = LLMModel.objects.create(
            name='Rerank Model',
            model_id='rerank-1',
            model_type='rerank',
            endpoint=self.vendor_endpoint,
            api_standard='custom'
        )
        self.assertEqual(model.model_type, 'rerank')


class RouterAPITests(TestCase):
    """API测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.client = APIClient()
        
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # 生成JWT token
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        
        # 设置认证
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # 创建测试数据
        self.vendor_endpoint = VendorEndpoint.objects.create(
            vendor_name='OpenRouter',
            vendor_id='openrouter',
            endpoint='https://openrouter.ai/api/v1',
            service_type='Text Generation'
        )
        
        self.llm_model = LLMModel.objects.create(
            name='GPT-4',
            model_id='gpt-4',
            model_type='text',
            endpoint=self.vendor_endpoint,
            api_standard='openai'
        )
    
    def test_list_models(self):
        """测试列出模型"""
        response = self.client.get('/api/router/models/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_model(self):
        """测试创建模型"""
        data = {
            'name': 'New Model',
            'model_id': 'new-model-1',
            'model_type': 'embedding',
            'endpoint': self.vendor_endpoint.id,
            'api_standard': 'openai'
        }
        response = self.client.post('/api/router/models/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['model_type'], 'embedding')
    
    def test_filter_by_model_type(self):
        """测试按模型类型过滤"""
        # 创建不同类型的模型
        LLMModel.objects.create(
            name='Embed Model',
            model_id='embed-test',
            model_type='embedding',
            endpoint=self.vendor_endpoint,
            api_standard='openai'
        )
        
        response = self.client.get('/api/router/models/?model_type=embedding')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for model in response.data.get('results', []):
            self.assertEqual(model['model_type'], 'embedding')
    
    def test_embedding_models_endpoint(self):
        """测试获取Embedding模型专用端点"""
        LLMModel.objects.create(
            name='Text Embedding',
            model_id='text-embedding-ada',
            model_type='embedding',
            endpoint=self.vendor_endpoint,
            api_standard='openai'
        )
        
        response = self.client.get('/api/router/models/embedding_models/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_rerank_models_endpoint(self):
        """测试获取Rerank模型专用端点"""
        LLMModel.objects.create(
            name='Reranker',
            model_id='reranker-v1',
            model_type='rerank',
            endpoint=self.vendor_endpoint,
            api_standard='custom'
        )
        
        response = self.client.get('/api/router/models/rerank_models/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_statistics_endpoint(self):
        """测试统计端点"""
        response = self.client.get('/api/router/models/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_models', response.data)
        self.assertIn('by_type', response.data)
        self.assertIn('by_vendor', response.data)
    
    def test_unauthorized_access(self):
        """测试未认证访问"""
        self.client.credentials()  # 清除认证
        response = self.client.get('/api/router/models/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)