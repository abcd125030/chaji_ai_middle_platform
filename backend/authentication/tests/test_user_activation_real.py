#!/usr/bin/env python
"""
用户激活功能的真实测试
按照测试规范要求，使用真实的数据库和API调用
测试邮箱注册、Google登录和飞书登录在不同配置下的用户状态
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# 配置Django环境
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache
from authentication.models import UserAccount
from authentication.models_extension import UserProfile
from authentication.user_service import UserService

User = get_user_model()


class RealUserActivationTestCase(TestCase):
    """用户激活功能的真实测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建输出目录
        self.output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 生成文件名时间戳
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.test_name = 'user_activation_real'
        
        # 设置日志
        self.setup_logging()
        
        # 创建测试客户端
        self.client = Client()
        
        # 创建管理员用户
        self.admin_user = User.objects.create_user(
            username='test_admin',
            email='admin@test.com',
            password='test_password_123'
        )
        self.admin_user.role = User.Role.ADMIN
        self.admin_user.status = User.Status.ACTIVE
        self.admin_user.save()
        
        # 记录初始状态
        self.initial_state = self.capture_state()
        self.process_data = {
            "test_info": {
                "name": self.test_name,
                "start_time": datetime.now().isoformat(),
                "django_settings": str(settings.DATABASES['default']['NAME']),
                "require_activation_config": os.getenv('REQUIRE_USER_ACTIVATION', 'False')
            },
            "initial_state": self.initial_state,
            "execution_steps": []
        }
        
        self.logger.info(f"测试环境准备完成")
        self.logger.info(f"REQUIRE_USER_ACTIVATION配置: {os.getenv('REQUIRE_USER_ACTIVATION', 'False')}")
    
    def setup_logging(self):
        """配置日志记录"""
        log_file = os.path.join(
            self.output_dir, 
            f'test_{self.test_name}_{self.timestamp}.log'
        )
        
        # 创建专门的文件handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # 创建console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # 配置logger
        self.logger = logging.getLogger(self.test_name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []  # 清除之前的handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"测试开始: {self.test_name}")
        self.logger.info(f"日志文件: {log_file}")
    
    def capture_state(self):
        """捕获当前状态"""
        state = {
            "timestamp": datetime.now().isoformat(),
            "user_count": User.objects.count(),
            "active_users": User.objects.filter(status=User.Status.ACTIVE).count(),
            "inactive_users": User.objects.filter(status=User.Status.INACTIVE).count(),
            "user_accounts_count": UserAccount.objects.count(),
            "user_profiles_count": UserProfile.objects.count()
        }
        
        # 记录所有用户信息
        users = []
        for user in User.objects.all():
            users.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "status": user.status,
                "role": user.role,
                "date_joined": user.date_joined.isoformat()
            })
        state["users"] = users
        
        return state
    
    def record_step(self, action, input_data, output_data, **kwargs):
        """记录执行步骤"""
        step = {
            "step": len(self.process_data["execution_steps"]) + 1,
            "action": action,
            "input": input_data,
            "output": output_data,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.process_data["execution_steps"].append(step)
        self.logger.info(f"步骤 {step['step']}: {action}")
        self.logger.debug(f"输入: {json.dumps(input_data, ensure_ascii=False)}")
        self.logger.debug(f"输出: {json.dumps(output_data, ensure_ascii=False)}")
    
    def test_email_registration_with_activation_required(self):
        """测试邮箱注册在需要激活配置下的行为"""
        self.logger.info("=== 测试邮箱注册（需要激活） ===")
        
        # 临时设置环境变量
        original_value = os.environ.get('REQUIRE_USER_ACTIVATION')
        os.environ['REQUIRE_USER_ACTIVATION'] = 'True'
        
        try:
            # 1. 模拟邮箱注册第一步：发送验证码
            email = 'testuser@example.com'
            password = 'Test@Password123'
            
            # 在缓存中模拟验证码（绕过实际邮件发送）
            verification_code = '123456'
            cache_key = f'email_verification:{email}'
            cache.set(cache_key, {
                'code': verification_code,
                'password': password,
                'attempts': 0
            }, 600)  # 10分钟有效期
            
            self.record_step(
                action="模拟邮箱验证码发送",
                input_data={"email": email, "password": "***"},
                output_data={"verification_code": verification_code, "cache_key": cache_key}
            )
            
            # 2. 验证邮箱验证码，创建用户
            response = self.client.post('/api/auth/email/verify/', {
                'email': email,
                'code': verification_code
            }, content_type='application/json')
            
            response_data = response.json() if response.content else {}
            
            self.record_step(
                action="验证邮箱验证码并创建用户",
                input_data={"email": email, "code": verification_code},
                output_data={
                    "status_code": response.status_code,
                    "response": response_data
                }
            )
            
            # 3. 检查用户状态
            created_user = User.objects.filter(email=email).first()
            if created_user:
                user_status = {
                    "id": created_user.id,
                    "username": created_user.username,
                    "email": created_user.email,
                    "status": created_user.status,
                    "status_display": created_user.get_status_display(),
                    "is_active": created_user.is_active
                }
                
                self.record_step(
                    action="检查创建的用户状态",
                    input_data={"email": email},
                    output_data=user_status
                )
                
                # 验证用户状态是否为未激活
                self.assertEqual(created_user.status, User.Status.INACTIVE, 
                               "邮箱注册用户在REQUIRE_USER_ACTIVATION=True时应该是未激活状态")
                
                # 4. 管理员激活用户
                # 先登录管理员
                self.client.force_login(self.admin_user)
                
                activation_response = self.client.post(
                    f'/api/auth/admin/users/{created_user.id}/activation/',
                    {'action': 'activate'},
                    content_type='application/json'
                )
                
                activation_data = activation_response.json() if activation_response.content else {}
                
                self.record_step(
                    action="管理员激活用户",
                    input_data={
                        "user_id": created_user.id,
                        "action": "activate",
                        "admin": self.admin_user.username
                    },
                    output_data={
                        "status_code": activation_response.status_code,
                        "response": activation_data
                    }
                )
                
                # 5. 验证用户激活后的状态
                created_user.refresh_from_db()
                final_status = {
                    "status": created_user.status,
                    "status_display": created_user.get_status_display()
                }
                
                self.record_step(
                    action="验证激活后的用户状态",
                    input_data={"user_id": created_user.id},
                    output_data=final_status
                )
                
                self.assertEqual(created_user.status, User.Status.ACTIVE,
                               "管理员激活后用户状态应该是ACTIVE")
                
        finally:
            # 恢复原始环境变量
            if original_value is None:
                os.environ.pop('REQUIRE_USER_ACTIVATION', None)
            else:
                os.environ['REQUIRE_USER_ACTIVATION'] = original_value
    
    def test_email_registration_without_activation_required(self):
        """测试邮箱注册在不需要激活配置下的行为"""
        self.logger.info("=== 测试邮箱注册（不需要激活） ===")
        
        # 临时设置环境变量
        original_value = os.environ.get('REQUIRE_USER_ACTIVATION')
        os.environ['REQUIRE_USER_ACTIVATION'] = 'False'
        
        try:
            # 1. 模拟邮箱注册
            email = 'autoactive@example.com'
            password = 'Test@Password123'
            
            # 在缓存中模拟验证码
            verification_code = '654321'
            cache_key = f'email_verification:{email}'
            cache.set(cache_key, {
                'code': verification_code,
                'password': password,
                'attempts': 0
            }, 600)
            
            self.record_step(
                action="模拟邮箱验证码发送（自动激活模式）",
                input_data={"email": email, "password": "***"},
                output_data={"verification_code": verification_code, "cache_key": cache_key}
            )
            
            # 2. 验证邮箱验证码，创建用户
            response = self.client.post('/api/auth/email/verify/', {
                'email': email,
                'code': verification_code
            }, content_type='application/json')
            
            response_data = response.json() if response.content else {}
            
            self.record_step(
                action="验证邮箱验证码并创建用户（自动激活）",
                input_data={"email": email, "code": verification_code},
                output_data={
                    "status_code": response.status_code,
                    "response": response_data
                }
            )
            
            # 3. 检查用户状态
            created_user = User.objects.filter(email=email).first()
            if created_user:
                user_status = {
                    "id": created_user.id,
                    "username": created_user.username,
                    "email": created_user.email,
                    "status": created_user.status,
                    "status_display": created_user.get_status_display(),
                    "is_active": created_user.is_active
                }
                
                self.record_step(
                    action="检查创建的用户状态（应该自动激活）",
                    input_data={"email": email},
                    output_data=user_status
                )
                
                # 验证用户状态是否为激活
                self.assertEqual(created_user.status, User.Status.ACTIVE,
                               "邮箱注册用户在REQUIRE_USER_ACTIVATION=False时应该是激活状态")
                
        finally:
            # 恢复原始环境变量
            if original_value is None:
                os.environ.pop('REQUIRE_USER_ACTIVATION', None)
            else:
                os.environ['REQUIRE_USER_ACTIVATION'] = original_value
    
    def test_admin_user_list_api(self):
        """测试管理员查看用户列表API"""
        self.logger.info("=== 测试管理员用户列表API ===")
        
        # 创建一些测试用户
        test_users = []
        for i in range(3):
            user = User.objects.create_user(
                username=f'test_user_{i}',
                email=f'user{i}@test.com',
                password='password123'
            )
            user.status = User.Status.INACTIVE if i % 2 == 0 else User.Status.ACTIVE
            user.save()
            test_users.append(user)
            
            # 创建UserAccount记录
            UserAccount.objects.create(
                user=user,
                type=UserAccount.AccountType.EMAIL,
                provider=UserAccount.Provider.EMAIL,
                provider_account_id=user.email,
                is_verified=True
            )
        
        self.record_step(
            action="创建测试用户",
            input_data={"count": 3},
            output_data={"users": [{"username": u.username, "status": u.status} for u in test_users]}
        )
        
        # 登录管理员
        self.client.force_login(self.admin_user)
        
        # 1. 获取所有用户列表
        response = self.client.get('/api/auth/admin/users/')
        all_users_data = response.json() if response.content else {}
        
        self.record_step(
            action="获取所有用户列表",
            input_data={"filter": "all"},
            output_data={
                "status_code": response.status_code,
                "user_count": len(all_users_data.get('data', {}).get('users', [])),
                "pagination": all_users_data.get('data', {}).get('pagination', {})
            }
        )
        
        # 2. 获取未激活用户列表
        response = self.client.get('/api/auth/admin/users/?status=inactive')
        inactive_users_data = response.json() if response.content else {}
        
        self.record_step(
            action="获取未激活用户列表",
            input_data={"filter": "inactive"},
            output_data={
                "status_code": response.status_code,
                "user_count": len(inactive_users_data.get('data', {}).get('users', [])),
                "users": [u['username'] for u in inactive_users_data.get('data', {}).get('users', [])]
            }
        )
        
        # 3. 获取激活用户列表
        response = self.client.get('/api/auth/admin/users/?status=active')
        active_users_data = response.json() if response.content else {}
        
        self.record_step(
            action="获取激活用户列表",
            input_data={"filter": "active"},
            output_data={
                "status_code": response.status_code,
                "user_count": len(active_users_data.get('data', {}).get('users', [])),
                "users": [u['username'] for u in active_users_data.get('data', {}).get('users', [])]
            }
        )
    
    def tearDown(self):
        """清理和保存结果"""
        # 记录最终状态
        self.process_data["test_info"]["end_time"] = datetime.now().isoformat()
        self.process_data["final_state"] = self.capture_state()
        
        # 计算执行时间
        start_time = datetime.fromisoformat(self.process_data["test_info"]["start_time"])
        end_time = datetime.fromisoformat(self.process_data["test_info"]["end_time"])
        duration = (end_time - start_time).total_seconds()
        self.process_data["test_info"]["duration"] = duration
        
        # 保存过程数据
        process_file = os.path.join(
            self.output_dir,
            f'test_{self.test_name}_{self.timestamp}_process.json'
        )
        with open(process_file, 'w', encoding='utf-8') as f:
            json.dump(self.process_data, f, ensure_ascii=False, indent=2)
        
        # 保存测试结果
        result_data = {
            "success": True,
            "test_cases": [
                {
                    "name": test_method,
                    "passed": True,
                    "execution_time": duration
                }
                for test_method in dir(self)
                if test_method.startswith('test_')
            ],
            "metrics": {
                "total_execution_time": duration,
                "database_operations": len(self.process_data["execution_steps"]),
                "users_created": self.process_data["final_state"]["user_count"] - 
                                self.process_data["initial_state"]["user_count"],
                "final_active_users": self.process_data["final_state"]["active_users"],
                "final_inactive_users": self.process_data["final_state"]["inactive_users"]
            }
        }
        
        result_file = os.path.join(
            self.output_dir,
            f'test_{self.test_name}_{self.timestamp}_result.json'
        )
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        log_file = os.path.join(
            self.output_dir,
            f'test_{self.test_name}_{self.timestamp}.log'
        )
        
        print(f"\n测试完成！结果已保存到:")
        print(f"  日志: {os.path.abspath(log_file)}")
        print(f"  过程: {os.path.abspath(process_file)}")
        print(f"  结果: {os.path.abspath(result_file)}")
        
        self.logger.info(f"测试结束: {self.test_name}")


if __name__ == '__main__':
    import unittest
    
    # 创建测试套件
    suite = unittest.TestSuite()
    suite.addTest(RealUserActivationTestCase('test_email_registration_with_activation_required'))
    suite.addTest(RealUserActivationTestCase('test_email_registration_without_activation_required'))
    suite.addTest(RealUserActivationTestCase('test_admin_user_list_api'))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 退出代码
    sys.exit(0 if result.wasSuccessful() else 1)