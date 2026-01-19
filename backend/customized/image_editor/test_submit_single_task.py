#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图片编辑任务提交测试脚本
用于在服务器端测试单个任务提交

使用方法：
1. 设置环境变量：
   export IMAGE_EDITOR_APP_ID="your_app_id"
   export IMAGE_EDITOR_APP_SECRET="your_app_secret"
   export API_BASE_URL="http://localhost:8000"  # 或服务器地址
   export IMAGE_EDITOR_TEST_IMAGE="https://example.com/test.jpg"  # 测试图片URL
   export IMAGE_EDITOR_TEST_PROMPT="你的提示词"  # 可选，不设置使用默认值
   
2. 运行脚本：
   python test_submit_single_task.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# 添加项目路径到系统路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Django环境初始化
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()


class ImageEditorTester:
    """图片编辑任务提交测试器"""
    
    def __init__(self):
        """初始化测试器，从环境变量读取配置"""
        # 从环境变量获取配置
        self.app_id = os.environ.get('IMAGE_EDITOR_APP_ID')
        self.app_secret = os.environ.get('IMAGE_EDITOR_APP_SECRET')
        self.base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000')
        
        # 验证必要的环境变量
        if not self.app_id or not self.app_secret:
            print("错误：请设置环境变量 IMAGE_EDITOR_APP_ID 和 IMAGE_EDITOR_APP_SECRET")
            print("示例：")
            print('  export IMAGE_EDITOR_APP_ID="your_app_id"')
            print('  export IMAGE_EDITOR_APP_SECRET="your_app_secret"')
            sys.exit(1)
        
        self.access_token = None
        self.refresh_token = None
        
        # API端点
        self.auth_url = f"{self.base_url}/api/service/auth/"
        self.submit_url = f"{self.base_url}/api/customized/image_editor/submit/"
        self.query_url = f"{self.base_url}/api/customized/image_editor/result/"
        
        print(f"初始化完成")
        print(f"- API基础地址: {self.base_url}")
        print(f"- App ID: {self.app_id}")
        print(f"- App Secret: {'*' * (len(self.app_secret) - 4)}{self.app_secret[-4:]}")
        print("-" * 50)
    
    def authenticate(self):
        """进行身份认证，获取JWT令牌"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始身份认证...")
        
        auth_data = {
            "appid": self.app_id,
            "secret": self.app_secret
        }
        
        try:
            response = requests.post(
                self.auth_url,
                json=auth_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                self.refresh_token = data.get('refresh_token')
                expires_in = data.get('expires_in', 0)
                
                print(f"✓ 认证成功")
                print(f"  - Access Token: {self.access_token[:20]}...")
                print(f"  - Token有效期: {expires_in}秒")
                return True
            else:
                print(f"✗ 认证失败")
                print(f"  - 状态码: {response.status_code}")
                print(f"  - 响应: {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ 认证请求异常: {str(e)}")
            return False
    
    def submit_task(self, image_url=None, prompt=None, callback_url=None):
        """提交图片编辑任务"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 提交任务...")
        
        # 从环境变量获取测试数据，如果没有则使用默认值
        if image_url is None:
            image_url = os.environ.get('IMAGE_EDITOR_TEST_IMAGE', 
                                       "https://test-gift-card-cdn.chagee.com/game-cute-pet-cup/temp/test.jpg")
        if prompt is None:
            prompt = os.environ.get('IMAGE_EDITOR_TEST_PROMPT',
                                   "完全参考图片宠物品种和动作, 调整图片风格变为油画刮刀风格，刮刀笔触适中，色彩饱满偏暖，姿态鲜活自然")
        
        task_data = {
            "image": image_url,
            "prompt": prompt
        }
        
        # 添加回调URL（如果有）
        if callback_url:
            task_data["callback_url"] = callback_url
        
        print(f"  - 图片URL: {image_url}")
        print(f"  - 提示词: {prompt[:50]}...")
        if callback_url:
            print(f"  - 回调URL: {callback_url}")
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                self.submit_url,
                json=task_data,
                headers=headers
            )
            
            print(f"  - 响应状态码: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                print(f"✓ 任务提交成功")
                print(f"  - 任务ID: {data.get('data', {}).get('task_id')}")
                print(f"  - 预估时间: {data.get('data', {}).get('estimated_time_seconds')}秒")
                print(f"  - 响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
                return data.get('data', {}).get('task_id')
            else:
                print(f"✗ 任务提交失败")
                print(f"  - 响应: {response.text}")
                return None
                
        except Exception as e:
            print(f"✗ 提交请求异常: {str(e)}")
            return None
    
    def query_task(self, task_id):
        """查询任务状态"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 查询任务状态...")
        print(f"  - 任务ID: {task_id}")
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        query_data = {
            "task_id": task_id
        }
        
        try:
            response = requests.post(
                self.query_url,
                json=query_data,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                task_data = data.get('data', {})
                
                print(f"✓ 查询成功")
                print(f"  - 状态: {task_data.get('status')}")
                print(f"  - 进度: {task_data.get('progress', 0)}%")
                
                if task_data.get('status') == 'success':
                    print(f"  - 结果图片路径: {task_data.get('result_image_path')}")
                    if task_data.get('actual_prompt'):
                        print(f"  - 实际使用提示词: {task_data.get('actual_prompt')[:100]}...")
                elif task_data.get('status') == 'failed':
                    print(f"  - 错误码: {task_data.get('error_code')}")
                    print(f"  - 错误信息: {task_data.get('error_message')}")
                    
                return task_data
            else:
                print(f"✗ 查询失败")
                print(f"  - 状态码: {response.status_code}")
                print(f"  - 响应: {response.text}")
                return None
                
        except Exception as e:
            print(f"✗ 查询请求异常: {str(e)}")
            return None
    
    def test_complete_flow(self):
        """测试完整流程：认证 -> 提交 -> 查询"""
        print("=" * 50)
        print("开始测试完整流程")
        print("=" * 50)
        
        # 1. 认证
        if not self.authenticate():
            print("认证失败，测试终止")
            return False
        
        # 2. 提交任务
        task_id = self.submit_task(callback_url="http://game-center.bwcj.biz/game-cute-pet-biz/api/callback/aiImg")
        if not task_id:
            print("任务提交失败，测试终止")
            return False
        
        # 3. 轮询查询任务状态
        print(f"\n开始轮询任务状态（最多等待60秒）...")
        max_wait = 60  # 最大等待时间
        interval = 3    # 查询间隔
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            task_data = self.query_task(task_id)
            
            if task_data:
                status = task_data.get('status')
                if status in ['success', 'failed']:
                    print(f"\n任务已完成，最终状态: {status}")
                    print(f"总耗时: {time.time() - start_time:.2f}秒")
                    return status == 'success'
            
            print(f"  等待{interval}秒后再次查询...")
            time.sleep(interval)
        
        print(f"\n超时：任务在{max_wait}秒内未完成")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("图片编辑任务提交测试脚本")
    print("=" * 50)
    
    tester = ImageEditorTester()
    
    # 运行测试
    success = tester.test_complete_flow()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ 测试通过")
    else:
        print("✗ 测试失败")
    print("=" * 50)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())