#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_node_real_execution.py

真实执行测试：不使用mock，真正测试节点内部的运行逻辑。
这个测试会真正调用LLM服务和执行工具，用于验证节点的实际工作流程。

遵循 backend/单元测试规范.md
"""

import os
import json
import logging
from datetime import datetime
from django.test import TestCase
from django.conf import settings
from django.db import transaction

# 导入需要测试的模块
from agentic.nodes.planner import planner_node
from agentic.nodes.reflection import reflection_node
from agentic.core.schemas import RuntimeState, ActionSummary

# 导入配置相关模块
from router.models import LLMModel
from tools.core.registry import ToolRegistry


class NodeRealExecutionTestCase(TestCase):
    """
    节点真实执行测试基类
    
    不使用任何mock，真正调用LLM服务和工具执行器，
    测试节点内部的完整运行逻辑。
    """
    
    @classmethod
    def setUpTestData(cls):
        """
        在整个测试类运行前执行一次，用于准备共享的、不变的"背景"数据。
        从生产数据库读取真实配置，填充到测试数据库。
        """
        print("\n" + "="*50)
        print(f"[{cls.__name__}] Running setUpTestData: Loading REAL configurations...")
        
        try:
            # 使用事务确保数据加载的原子性
            with transaction.atomic():
                # 从真实配置中加载LLM模型配置
                # 注意：这里需要确保测试环境有可用的API密钥
                
                # 从环境变量或配置文件读取真实的API配置
                from django.db import connections
                from django.conf import settings
                
                # 如果配置了真实数据库，从中读取配置
                if hasattr(settings, 'PRODUCTION_DB_ALIAS'):
                    with connections['production'].cursor() as cursor:
                        # 读取LLM模型配置
                        cursor.execute("""
                            SELECT v.vendor_id, v.display_name, 
                                   ve.endpoint, ve.service_type,
                                   vk.api_key,
                                   lm.name, lm.model_id, lm.model_type, lm.params
                            FROM router_llmmodel lm
                            JOIN router_vendorendpoint ve ON lm.endpoint_id = ve.id
                            JOIN router_vendor v ON ve.vendor_id = v.id
                            LEFT JOIN router_vendorapikey vk ON vk.vendor_id = v.id
                            WHERE lm.is_active = true
                            LIMIT 5
                        """)
                        
                        for row in cursor.fetchall():
                            # 在测试数据库中创建相同的配置
                            # ... 创建Vendor, Endpoint, APIKey, LLMModel
                            pass
                else:
                    # 如果没有生产数据库，使用环境变量创建最小配置
                    from router.vendor_models import Vendor
                    from router.models import VendorEndpoint, VendorAPIKey
                    
                    # 检查是否有真实的API密钥
                    qwen_api_key = os.getenv('QWEN_API_KEY')
                    if qwen_api_key:
                        print(f"[{cls.__name__}] Found QWEN_API_KEY in environment")
                        
                        # 创建Qwen供应商配置
                        qwen_vendor = Vendor.objects.create(
                            vendor_id='qwen',
                            display_name='通义千问',
                            description='阿里云通义千问模型（真实API）'
                        )
                        
                        qwen_endpoint = VendorEndpoint.objects.create(
                            vendor=qwen_vendor,
                            endpoint=os.getenv('QWEN_ENDPOINT', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
                            service_type='text'
                        )
                        
                        VendorAPIKey.objects.create(
                            vendor=qwen_vendor,
                            api_key=qwen_api_key,
                            description='真实Qwen API密钥'
                        )
                        
                        # 创建真实的LLM模型配置
                        LLMModel.objects.create(
                            name='qwen-plus',
                            model_id='qwen-plus',
                            model_type='text',
                            endpoint=qwen_endpoint,
                            api_standard='openai',
                            params={
                                'temperature': 0.7,
                                'max_tokens': 2000
                            }
                        )
                        
                        print(f"[{cls.__name__}] Created REAL Qwen configuration")
                    else:
                        print(f"[{cls.__name__}] WARNING: No QWEN_API_KEY found, tests may fail")
                        # 创建一个占位配置
                        raise ValueError("需要设置QWEN_API_KEY环境变量才能运行真实测试")
                
                print(f"[{cls.__name__}] setUpTestData completed successfully.")
                
        except Exception as e:
            print(f"[{cls.__name__}] CRITICAL: Failed to set up test data: {e}")
            raise
        print("="*50)

    def setUp(self):
        """
        在每个 test_ 方法执行前运行。
        """
        # 文件和日志设置
        self.output_dir = os.path.join(settings.BASE_DIR, 'agentic', 'tests', 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 使用符合规范的文件命名格式
        test_method_name = self._testMethodName
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y%m%d')
        time_str = timestamp.strftime('%H%M%S')
        
        # 生成符合规范的文件名
        self.process_filename = f'process-{date_str}-{time_str}-{test_method_name}.json'
        self.log_filename = f'log-{date_str}-{time_str}-{test_method_name}.log'
        self.result_filename = f'result-{date_str}-{time_str}-{test_method_name}.json'
        
        self.setup_logging()
        self.logger.info(f"Test method '{test_method_name}' starting...")
        
        # 状态捕获和数据记录
        self.initial_state = self.capture_state("initial")
        self.process_data = {
            "test_info": {
                "name": f"{self.__class__.__name__}.{test_method_name}",
                "start_time": datetime.now().isoformat(),
                "test_type": "REAL_EXECUTION",
                "mock_used": False
            },
            "initial_state": self.initial_state,
            "execution_steps": []
        }
        
        # 设置环境变量
        os.environ['ENABLE_PLANNER_CHAIN'] = 'false'  # 使用原始实现

    def setup_logging(self):
        """配置日志记录器"""
        log_file = os.path.join(self.output_dir, self.log_filename)
        
        # 避免重复添加handler
        self.logger = logging.getLogger(self.log_filename)
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            
            # 文件处理器
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            
            # 控制台处理器
            sh = logging.StreamHandler()
            sh.setFormatter(formatter)
            self.logger.addHandler(sh)
            
    def capture_state(self, stage: str):
        """
        捕获当前数据库和配置的状态。
        """
        self.logger.info(f"Capturing {stage} state...")
        
        # 捕获LLM模型配置
        llm_configs = list(LLMModel.objects.values('name', 'model_id', 'model_type'))
        
        # 捕获工具注册表状态
        registry = ToolRegistry()
        tools_snapshot = registry.list_tools_with_details(category='libs')
        
        return {
            "llm_models": llm_configs,
            "registered_tools": len(tools_snapshot),
            "timestamp": datetime.now().isoformat()
        }

    def record_step(self, action, input_data, output_data, **kwargs):
        """记录执行步骤"""
        step_number = len(self.process_data["execution_steps"]) + 1
        step_data = {
            "step": step_number,
            "action": action,
            "input": input_data if isinstance(input_data, (str, dict, list)) else str(input_data),
            "output": output_data if isinstance(output_data, (str, dict, list)) else str(output_data),
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.process_data["execution_steps"].append(step_data)
        self.logger.info(f"Step {step_number}: {action} recorded.")
    
    def tearDown(self):
        """
        在每个 test_ 方法执行后运行。
        """
        end_time = datetime.now()
        start_time_iso = self.process_data["test_info"]["start_time"]
        start_time = datetime.fromisoformat(start_time_iso)
        duration = (end_time - start_time).total_seconds()

        self.process_data["test_info"]["end_time"] = end_time.isoformat()
        self.process_data["test_info"]["duration"] = duration
        self.process_data["final_state"] = self.capture_state("final")
        
        # 保存过程数据
        process_file = os.path.join(self.output_dir, self.process_filename)
        try:
            with open(process_file, 'w', encoding='utf-8') as f:
                json.dump(self.process_data, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n✅ Process data saved to: {os.path.abspath(process_file)}")
        except Exception as e:
            self.logger.error(f"Failed to write process file: {e}")

        self.logger.info(f"Test method finished. Duration: {duration:.2f}s")
        print(f"\n[INFO] Test outputs saved to directory: {os.path.abspath(self.output_dir)}")


class TestPlannerRealExecution(NodeRealExecutionTestCase):
    """
    测试Planner节点的真实执行
    """
    
    def test_planner_real_planning(self):
        """测试planner节点真实的规划能力（调用真实LLM）"""
        self.logger.info("="*50)
        self.logger.info("Testing REAL planner node execution")
        self.logger.info("This test will make REAL API calls!")
        self.logger.info("="*50)
        
        # 创建一个简单的测试任务
        state = RuntimeState(
            task_goal="计算123加456的结果",
            action_summaries=[],
            action_history=[],
            preprocessed_files={},
            todo_items=[],
            full_action_data={}
        )
        
        # 记录初始状态
        self.record_step(
            action="initialize_runtime_state",
            input_data={
                "task_goal": state.task_goal,
                "test_type": "REAL_LLM_CALL"
            },
            output_data={"state_initialized": True}
        )
        
        # 节点配置
        nodes_map = {
            'planner': {
                'model_name': 'qwen-plus',  # 使用真实的模型
                'type': 'planner'
            }
        }
        
        try:
            self.logger.info("Calling planner_node with REAL LLM...")
            
            # 真实调用planner节点 - 不使用mock！
            result = planner_node(
                state=state,
                nodes_map=nodes_map,
                edges_map=None,
                user=None,
                session_id="test_real_session_001"
            )
            
            # 记录真实的LLM响应
            self.record_step(
                action="planner_real_llm_response",
                input_data={"prompt_sent": True},
                output_data=result
            )
            
            # 验证返回结果
            self.assertIn('current_plan', result)
            plan = result['current_plan']
            
            # 记录LLM的真实决策
            self.logger.info(f"\n🤖 LLM Real Decision:")
            self.logger.info(f"  Thought: {plan.thought}")
            self.logger.info(f"  Action: {plan.action}")
            if plan.tool_name:
                self.logger.info(f"  Tool: {plan.tool_name}")
                self.logger.info(f"  Tool Input: {plan.tool_input}")
            
            # 验证基本结构
            self.assertIsNotNone(plan.thought)
            self.assertIn(plan.action, ['CALL_TOOL', 'FINISH'])
            
            # 保存真实测试结果
            test_result = {
                "test_name": "planner_real_planning",
                "timestamp": datetime.now().isoformat(),
                "llm_model_used": "qwen-plus",
                "task_goal": state.task_goal,
                "llm_response": {
                    "thought": plan.thought,
                    "action": plan.action,
                    "tool_name": plan.tool_name,
                    "tool_input": plan.tool_input if plan.tool_input else None
                },
                "status": "success"
            }
            
            result_file = os.path.join(self.output_dir, self.result_filename)
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(test_result, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"\n✅ Real LLM test completed successfully!")
            self.logger.info(f"Result saved to: {result_file}")
            
        except Exception as e:
            self.logger.error(f"Real execution failed: {e}")
            self.record_step(
                action="test_failed",
                input_data={},
                output_data={"error": str(e)}
            )
            # 如果是API密钥问题，给出明确提示
            if "api" in str(e).lower() or "key" in str(e).lower():
                self.logger.error("\n⚠️ API密钥可能未配置或无效")
                self.logger.error("请设置环境变量: export QWEN_API_KEY='your-api-key'")
            raise
    
    def test_planner_with_complex_task(self):
        """测试planner处理复杂任务的真实能力"""
        self.logger.info("="*50)
        self.logger.info("Testing planner with COMPLEX task (REAL LLM)")
        self.logger.info("="*50)
        
        # 创建一个更复杂的任务
        state = RuntimeState(
            task_goal="分析最近三个月的销售数据趋势，找出表现最好的产品类别，并给出下季度的销售策略建议",
            action_summaries=[],
            action_history=[],
            preprocessed_files={
                'tables': {
                    'q1_sales.xlsx': {
                        'rows': 500,
                        'columns': ['日期', '产品类别', '销量', '收入']
                    },
                    'q2_sales.xlsx': {
                        'rows': 600,
                        'columns': ['日期', '产品类别', '销量', '收入']
                    }
                }
            },
            todo_items=[],
            full_action_data={}
        )
        
        nodes_map = {
            'planner': {
                'model_name': 'qwen-plus',
                'type': 'planner'
            }
        }
        
        try:
            # 真实调用planner
            result = planner_node(
                state=state,
                nodes_map=nodes_map,
                edges_map=None,
                user=None,
                session_id="test_complex_001"
            )
            
            plan = result['current_plan']
            
            # 分析LLM的规划质量
            self.logger.info(f"\n📊 Complex Task Planning Result:")
            self.logger.info(f"  Thought length: {len(plan.thought)} chars")
            self.logger.info(f"  Action type: {plan.action}")
            
            # 检查是否正确识别了需要分析数据
            if plan.action == 'CALL_TOOL':
                self.logger.info(f"  Selected tool: {plan.tool_name}")
                # 验证是否选择了合适的工具
                self.assertIsNotNone(plan.tool_name)
            
            # 检查思考过程的质量
            thought_keywords = ['销售', '数据', '分析', '趋势', '产品']
            thought_quality = sum(1 for kw in thought_keywords if kw in plan.thought)
            self.logger.info(f"  Thought quality score: {thought_quality}/{len(thought_keywords)}")
            
            # 至少应该包含一些关键词
            self.assertGreater(thought_quality, 0, "LLM应该理解任务内容")
            
            self.logger.info(f"\n✅ Complex task planning test completed!")
            
        except Exception as e:
            self.logger.error(f"Complex task test failed: {e}")
            raise


if __name__ == "__main__":
    # 直接运行测试
    import unittest
    
    # 检查环境变量
    if not os.getenv('QWEN_API_KEY'):
        print("\n" + "="*60)
        print("⚠️  警告：未设置QWEN_API_KEY环境变量")
        print("这个测试需要真实的API密钥才能运行")
        print("请执行: export QWEN_API_KEY='your-api-key'")
        print("="*60 + "\n")
        exit(1)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPlannerRealExecution)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 打印结果摘要
    if result.wasSuccessful():
        print("\n" + "="*50)
        print("✅ ALL REAL EXECUTION TESTS PASSED!")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("❌ SOME TESTS FAILED")
        print("="*50)