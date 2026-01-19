#!/usr/bin/env python
"""
SSE 客户端断开连接测试脚本

用于验证 task_stream_view 在客户端断开后的行为
"""

import os
import sys
import django
import time
import threading
import requests
import json
from datetime import datetime

# 设置 Django 环境
sys.path.insert(0, '/Users/chagee/Repos/X/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from webapps.chat.models import ChatSession, ChatMessage
from agentic.models import AgentTask
from agentic.services import AgentService

User = get_user_model()


class SSEDisconnectTester:
    """SSE 断开连接测试器"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = []
        
    def create_test_task(self):
        """创建一个测试任务"""
        # 获取或创建测试用户
        user, _ = User.objects.get_or_create(
            username='sse_test_user',
            defaults={'email': 'sse_test@example.com'}
        )
        
        # 创建测试会话
        session = ChatSession.objects.create(
            user=user,
            title='SSE Disconnect Test',
            ai_conversation_id='test-' + str(int(time.time()))
        )
        
        # 创建一个长时间运行的任务
        import uuid
        task_id = str(uuid.uuid4())
        
        # 创建 AgentTask
        agent_task = AgentTask.objects.create(
            task_id=task_id,
            graph_id='test-graph',
            status=AgentTask.TaskStatus.RUNNING,
            input_data={'query': 'Test SSE disconnect'},
            output_data={},
            created_by=user
        )
        
        print(f"创建测试任务: {task_id}")
        return task_id, user
    
    def simulate_client_disconnect(self, task_id, disconnect_after=3):
        """模拟客户端断开连接"""
        print(f"\n测试场景：客户端在 {disconnect_after} 秒后断开连接")
        
        # 记录开始时间
        start_time = time.time()
        events_received = []
        
        try:
            # 发起 SSE 连接
            url = f"{self.base_url}/api/tasks/{task_id}/stream/"
            headers = {
                'Accept': 'text/event-stream',
                # 添加认证 token（根据实际情况调整）
            }
            
            print(f"连接到: {url}")
            response = requests.get(url, stream=True, headers=headers, timeout=30)
            
            # 读取事件流
            disconnect_time = start_time + disconnect_after
            for line in response.iter_lines():
                current_time = time.time()
                
                if current_time >= disconnect_time:
                    print(f"主动断开连接 (运行了 {current_time - start_time:.1f} 秒)")
                    response.close()  # 模拟客户端断开
                    break
                
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        try:
                            event_data = json.loads(decoded_line[6:])
                            events_received.append(event_data)
                            print(f"收到事件: {event_data.get('type', 'unknown')}")
                        except json.JSONDecodeError:
                            pass
                            
        except requests.exceptions.Timeout:
            print("连接超时")
        except requests.exceptions.ConnectionError:
            print("连接错误")
        except Exception as e:
            print(f"发生异常: {e}")
        
        # 记录结果
        duration = time.time() - start_time
        result = {
            'test_name': 'client_disconnect',
            'disconnect_after': disconnect_after,
            'total_duration': duration,
            'events_received': len(events_received),
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"\n测试结果:")
        print(f"- 总运行时间: {duration:.1f} 秒")
        print(f"- 接收事件数: {len(events_received)}")
        
        return result
    
    def monitor_server_behavior(self, task_id, monitor_duration=30):
        """监控服务器端行为"""
        print(f"\n监控服务器行为 {monitor_duration} 秒...")
        
        start_time = time.time()
        check_times = []
        
        agent_service = AgentService()
        
        while time.time() - start_time < monitor_duration:
            try:
                # 检查任务状态
                progress = agent_service.get_task_progress(task_id)
                if progress:
                    check_times.append({
                        'time': time.time() - start_time,
                        'status': progress['status'],
                        'actions': len(progress.get('action_history', []))
                    })
                
                # 检查数据库中的日志（可选）
                # 这里可以添加检查日志表的逻辑
                
            except Exception as e:
                print(f"检查出错: {e}")
            
            time.sleep(2)
        
        print(f"服务器端检查次数: {len(check_times)}")
        return check_times
    
    def run_disconnect_test(self):
        """运行断开连接测试"""
        print("="*60)
        print("SSE 客户端断开连接测试")
        print("="*60)
        
        # 创建测试任务
        task_id, user = self.create_test_task()
        
        # 测试1：快速断开（3秒）
        result1 = self.simulate_client_disconnect(task_id, disconnect_after=3)
        self.results.append(result1)
        
        # 等待一段时间，观察服务器是否继续处理
        print("\n等待 10 秒，观察服务器行为...")
        time.sleep(10)
        
        # 检查任务是否还在运行
        agent_service = AgentService()
        progress = agent_service.get_task_progress(task_id)
        if progress:
            print(f"任务状态: {progress['status']}")
            print(f"任务是否完成: {progress['is_completed']}")
        
        # 清理测试数据
        self.cleanup_test_data(task_id)
        
        return self.results
    
    def cleanup_test_data(self, task_id):
        """清理测试数据"""
        try:
            AgentTask.objects.filter(task_id=task_id).delete()
            print(f"清理任务: {task_id}")
        except Exception as e:
            print(f"清理失败: {e}")
    
    def parallel_disconnect_test(self, num_clients=3):
        """并行断开测试"""
        print(f"\n并行测试：{num_clients} 个客户端同时连接并断开")
        
        threads = []
        results = []
        
        def client_worker(client_id, task_id):
            """客户端工作线程"""
            disconnect_after = 2 + client_id  # 不同时间断开
            result = self.simulate_client_disconnect(task_id, disconnect_after)
            result['client_id'] = client_id
            results.append(result)
        
        # 创建共享的测试任务
        task_id, _ = self.create_test_task()
        
        # 启动多个客户端
        for i in range(num_clients):
            thread = threading.Thread(target=client_worker, args=(i, task_id))
            threads.append(thread)
            thread.start()
            time.sleep(0.5)  # 稍微错开启动时间
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 分析结果
        print(f"\n并行测试结果:")
        for r in results:
            print(f"- 客户端 {r['client_id']}: 断开时间={r['disconnect_after']}s, 事件数={r['events_received']}")
        
        # 清理
        self.cleanup_test_data(task_id)
        
        return results
    
    def save_results(self):
        """保存测试结果"""
        output_dir = '/Users/chagee/Repos/X/backend/agentic/tests/outputs'
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"sse_disconnect_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'test_time': datetime.now().isoformat(),
                'results': self.results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n测试结果已保存到: {filepath}")
        return filepath


def main():
    """主测试函数"""
    tester = SSEDisconnectTester()
    
    # 运行测试
    try:
        # 单客户端断开测试
        tester.run_disconnect_test()
        
        # 并行断开测试（可选）
        # tester.parallel_disconnect_test(num_clients=3)
        
        # 保存结果
        tester.save_results()
        
    except KeyboardInterrupt:
        print("\n测试被中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()