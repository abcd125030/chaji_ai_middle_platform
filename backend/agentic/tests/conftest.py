"""
Agentic 测试配置文件

提供测试所需的 fixtures 和通用测试配置
"""
import os
import sys
import django
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

# 配置 Django 设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import Mock, patch

User = get_user_model()


@pytest.fixture
def mock_user():
    """创建测试用户"""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    return user


@pytest.fixture
def mock_llm_response():
    """模拟 LLM 响应"""
    return {
        "choices": [{
            "message": {
                "content": "这是一个模拟的 LLM 响应"
            }
        }]
    }


@pytest.fixture
def mock_graph_definition():
    """模拟图定义数据"""
    return {
        "name": "测试工作流",
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {}
            },
            {
                "id": "llm_node",
                "type": "llm",
                "data": {
                    "prompt": "测试提示词"
                }
            },
            {
                "id": "end",
                "type": "end",
                "data": {}
            }
        ],
        "edges": [
            {
                "source": "start",
                "target": "llm_node"
            },
            {
                "source": "llm_node",
                "target": "end"
            }
        ]
    }


class BaseAgenticTestCase(TestCase):
    """Agentic 应用基础测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def tearDown(self):
        """清理测试环境"""
        User.objects.all().delete()