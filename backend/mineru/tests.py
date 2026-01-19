import os
import base64
from io import BytesIO
from pathlib import Path
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from .models import PDFParseTask, ParseResult
from .services import MinerUService
from .serializers import PDFParseTaskSerializer

User = get_user_model()


class PDFParseTaskModelTest(TestCase):
    """PDF解析任务模型测试"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_create_task(self):
        """测试创建任务"""
        task = PDFParseTask.objects.create(
            user=self.user,
            original_filename='test.pdf',
            file_type='pdf',
            file_size=1024
        )
        
        self.assertIsNotNone(task.task_id)
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.parse_method, 'auto')
        self.assertFalse(task.debug_enabled)
    
    def test_status_update(self):
        """测试状态更新"""
        task = PDFParseTask.objects.create(
            user=self.user,
            original_filename='test.pdf',
            file_type='pdf',
            file_size=1024
        )
        
        # 更新状态为完成
        task.status = 'completed'
        task.save()
        
        # 检查完成时间是否自动设置
        self.assertIsNotNone(task.completed_at)


class MinerUServiceTest(TestCase):
    """MinerU 服务测试"""
    
    def setUp(self):
        self.service = MinerUService()
    
    def test_validate_file_size(self):
        """测试文件大小验证"""
        # 创建超大文件
        large_file = b'x' * (101 * 1024 * 1024)  # 101MB
        is_valid, message, _ = self.service.validate_file(large_file)
        
        self.assertFalse(is_valid)
        self.assertIn('超过限制', message)
    
    def test_validate_file_type(self):
        """测试文件类型验证"""
        # 创建假的 PDF 文件头
        pdf_header = b'%PDF-1.4'
        
        with patch('filetype.guess') as mock_guess:
            # 模拟 PDF 文件
            mock_type = MagicMock()
            mock_type.extension = 'pdf'
            mock_guess.return_value = mock_type
            
            is_valid, message, file_ext = self.service.validate_file(pdf_header)
            
            self.assertTrue(is_valid)
            self.assertEqual(file_ext, 'pdf')
            
            # 模拟不支持的文件类型
            mock_type.extension = 'exe'
            mock_guess.return_value = mock_type
            
            is_valid, message, file_ext = self.service.validate_file(b'MZ')
            
            self.assertFalse(is_valid)
            self.assertIn('不支持', message)


class PDFParseTaskAPITest(TransactionTestCase):
    """PDF解析任务 API 测试"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_tasks(self):
        """测试获取任务列表"""
        # 创建测试任务
        PDFParseTask.objects.create(
            user=self.user,
            original_filename='test1.pdf',
            file_type='pdf',
            file_size=1024
        )
        PDFParseTask.objects.create(
            user=self.user,
            original_filename='test2.pdf',
            file_type='pdf',
            file_size=2048
        )
        
        url = reverse('mineru:task-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    @patch('mineru.views.process_document_task.delay')
    def test_upload_file(self, mock_process_task):
        """测试文件上传"""
        # 创建测试文件
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        url = reverse('mineru:task-upload')
        data = {
            'file': ('test.png', img_bytes, 'image/png'),
            'parse_method': 'auto'
        }
        
        with patch('mineru.services.MinerUService.validate_file') as mock_validate:
            mock_validate.return_value = (True, 'OK', 'png')
            
            with patch('mineru.services.MinerUService.save_uploaded_file') as mock_save:
                mock_save.return_value = '/fake/path/test.png'
                
                response = self.client.post(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('task_id', response.data)
        
        # 检查任务是否创建
        task = PDFParseTask.objects.get(task_id=response.data['task_id'])
        self.assertEqual(task.original_filename, 'test.png')
        self.assertEqual(task.file_type, 'png')
        
        # 检查异步任务是否被调用
        mock_process_task.assert_called_once_with(str(task.task_id))
    
    def test_task_status(self):
        """测试任务状态查询"""
        task = PDFParseTask.objects.create(
            user=self.user,
            original_filename='test.pdf',
            file_type='pdf',
            file_size=1024,
            status='processing'
        )
        
        url = reverse('mineru:task-status', kwargs={'pk': task.task_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'processing')
        self.assertEqual(response.data['progress'], 50)
    
    def test_unauthorized_access(self):
        """测试未授权访问"""
        self.client.force_authenticate(user=None)
        
        url = reverse('mineru:task-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SerializerTest(TestCase):
    """序列化器测试"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_task_serializer(self):
        """测试任务序列化器"""
        task = PDFParseTask.objects.create(
            user=self.user,
            original_filename='test.pdf',
            file_type='pdf',
            file_size=1024,
            status='completed'
        )
        
        serializer = PDFParseTaskSerializer(task)
        data = serializer.data
        
        self.assertEqual(data['original_filename'], 'test.pdf')
        self.assertEqual(data['status'], 'completed')
        self.assertEqual(data['status_display'], '已完成')
        self.assertIn('task_id', data)
