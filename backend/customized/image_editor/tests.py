from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import ImageEditTask, BatchTask


class ImageEditorAPITests(APITestCase):
    """图片编辑器API测试"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
    
    def test_submit_task(self):
        """测试提交单个任务"""
        data = {
            'prompt': '梵高风格',
            'image': 'https://example.com/test.jpg',
            'callback_url': 'https://example.com/callback'
        }
        response = self.client.post('/api/customized/image_editor/submit/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 0)
        self.assertIn('task_id', response.data['data'])
    
    def test_query_task(self):
        """测试查询任务结果"""
        # TODO: 先创建一个任务，然后查询
        pass
    
    def test_batch_submit(self):
        """测试批量提交任务"""
        data = {
            'tasks': [
                {'prompt': '梵高风格', 'image': 'https://example.com/test1.jpg'},
                {'prompt': '水墨画风格', 'image': 'https://example.com/test2.jpg'}
            ],
            'callback_url': 'https://example.com/batch_callback'
        }
        response = self.client.post('/api/customized/image_editor/batch_submit/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 0)
        self.assertEqual(len(response.data['data']['tasks']), 2)