# -*- coding: utf-8 -*-
"""
test_planner.py

planner 节点的单元测试
遵循"在隔离环境中重建真实状态"的原则
"""

import os
import json
import logging
from datetime import datetime
from django.test import TestCase
from django.conf import settings
from django.db import transaction
from unittest.mock import MagicMock

# 导入需要测试的模块
from agentic.nodes.planner import planner_node, _original_planner_implementation
from agentic.core.schemas import RuntimeState, ActionSummary, PlannerOutput

# 导入配置相关模块
from llm.core_service import CoreLLMService
from tools.core.registry import ToolRegistry
from router.models import LLMModel


class PlannerRealTestCase(TestCase):
    """
    Planner节点的真实测试基类
    
    遵循"在隔离环境中重建真实状态"的原则。
    使用 setUpTestData 加载所有测试共享的、不变的配置数据。
    使用 setUp 和 tearDown 管理每个具体测试的生命周期和结果记录。
    """
    
    @classmethod
    def setUpTestData(cls):
        """
        在整个测试类运行前执行一次，用于准备共享的、不变的"背景"数据。
        这是填充测试数据库以模拟真实配置的最佳位置。
        """
        print("\n" + "="*50)
        print(f"[{cls.__name__}] Running setUpTestData: Populating test database with initial configuration...")
        
        try:
            # 使用事务确保数据加载的原子性
            with transaction.atomic():
                # 创建必要的Vendor和Endpoint（如果需要）
                from router.vendor_models import Vendor
                from router.models import VendorEndpoint, VendorAPIKey
                
                # 创建供应商
                qwen_vendor = Vendor.objects.create(
                    vendor_id='qwen',
                    display_name='通义千问',
                    description='阿里云通义千问模型'
                )
                
                anthropic_vendor = Vendor.objects.create(
                    vendor_id='anthropic',
                    display_name='Anthropic',
                    description='Anthropic Claude模型'
                )
                
                # 创建端点
                qwen_endpoint = VendorEndpoint.objects.create(
                    vendor=qwen_vendor,
                    endpoint='https://api.qwen.com/v1',
                    service_type='text'
                )
                
                anthropic_endpoint = VendorEndpoint.objects.create(
                    vendor=anthropic_vendor,
                    endpoint='https://api.anthropic.com/v1',
                    service_type='text'
                )
                
                # 创建API密钥
                VendorAPIKey.objects.create(
                    vendor=qwen_vendor,
                    api_key='test-qwen-key',
                    description='测试用Qwen密钥'
                )
                
                VendorAPIKey.objects.create(
                    vendor=anthropic_vendor,
                    api_key='test-anthropic-key',
                    description='测试用Anthropic密钥'
                )
                
                # 创建LLM模型配置
                LLMModel.objects.create(
                    name='qwen3-max',
                    model_id='qwen3-max',
                    model_type='text',
                    endpoint=qwen_endpoint,
                    api_standard='openai',
                    params={}
                )
                
                LLMModel.objects.create(
                    name='claude-3-5-sonnet-20241022',
                    model_id='claude-3-5-sonnet-20241022',
                    model_type='text',
                    endpoint=anthropic_endpoint,
                    api_standard='openai',
                    params={}
                )
                
                print(f"[{cls.__name__}] Created {LLMModel.objects.count()} LLM model configurations in test database.")
                print(f"[{cls.__name__}] setUpTestData completed successfully.")
                
        except Exception as e:
            print(f"[{cls.__name__}] CRITICAL: Failed to set up test data: {e}")
            raise
        print("="*50)

    def setUp(self):
        """
        在每个 test_ 方法执行前运行。
        用于设置日志、创建输出目录、记录初始状态等每个测试都需要独立完成的工作。
        """
        # --- 文件和日志设置 ---
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
        
        # --- 状态捕获和数据记录 ---
        self.initial_state = self.capture_state("initial")
        self.process_data = {
            "test_info": {
                "name": f"{self.__class__.__name__}.{test_method_name}",
                "start_time": datetime.now().isoformat()
            },
            "initial_state": self.initial_state,
            "execution_steps": []
        }
        
        # --- 设置环境变量 ---
        os.environ['ENABLE_PLANNER_CHAIN'] = 'false'  # 使用原始实现进行测试

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
        
        stage: 'initial' 或 'final'
        """
        self.logger.info(f"Capturing {stage} state...")
        
        # 捕获配置快照（跳过，因为我们使用mock）
        config_snapshot = []
        
        # 捕获工具注册表状态
        registry = ToolRegistry()
        tools_snapshot = registry.list_tools_with_details(category='libs')
        
        db_snapshot = {
            "Config": config_snapshot,
            "RegisteredTools": tools_snapshot
        }
        
        return {
            "database": db_snapshot,
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
        用于记录最终状态和保存所有输出文件。
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


class TestPlannerNode(PlannerRealTestCase):
    """
    测试 planner_node 函数的具体功能
    """
    
    def test_planner_basic_call_tool(self):
        """测试planner节点基本的工具调用功能"""
        self.logger.info("="*50)
        self.logger.info("Testing basic planner node CALL_TOOL functionality")
        
        # 创建测试用的RuntimeState
        state = RuntimeState(
            task_goal="分析用户上传的销售数据并生成报告",
            action_summaries=[],
            action_history=[],
            preprocessed_files={
                'tables': {
                    'sales_data.xlsx': {
                        'rows': 100,
                        'columns': ['日期', '产品', '销量', '金额']
                    }
                }
            }
        )
        
        # 记录输入状态
        self.record_step(
            action="prepare_runtime_state",
            input_data={
                "task_goal": state.task_goal,
                "preprocessed_files": state.preprocessed_files
            },
            output_data={"state_created": True}
        )
        
        # 创建模拟的nodes_map（包含planner节点配置）
        nodes_map = {
            'planner': {
                'model_name': 'claude-3-5-sonnet-20241022',
                'type': 'planner'
            }
        }
        
        # Mock LLM响应，避免真实调用
        mock_llm_response = PlannerOutput(
            thought="用户上传了销售数据表格，需要先获取数据进行分析",
            action="CALL_TOOL",
            tool_name="get_preprocessed_data",
            tool_input={"file_key": "sales_data.xlsx"},
            expected_outcome="获取完整的销售数据表格内容"
        )
        
        # Mock CoreLLMService
        with self.mock_llm_service(mock_llm_response):
            try:
                # 调用planner节点
                result = planner_node(
                    state=state,
                    nodes_map=nodes_map,
                    edges_map=None,
                    user=None,
                    session_id="test_session"
                )
                
                # 记录执行结果
                self.record_step(
                    action="planner_node_execution",
                    input_data={"state": state.model_dump()},
                    output_data=result
                )
                
                # 验证结果
                self.assertIn('current_plan', result)
                plan = result['current_plan']
                
                # 验证计划内容
                self.assertEqual(plan.action, "CALL_TOOL")
                self.assertEqual(plan.tool_name, "get_preprocessed_data")
                self.assertIsNotNone(plan.tool_input)
                self.assertEqual(plan.tool_input.get('file_key'), "sales_data.xlsx")
                
                # 验证action_history被更新
                self.assertEqual(len(state.action_history), 1)
                self.assertEqual(state.action_history[0]['type'], 'plan')
                
                self.logger.info("✅ Test passed: planner correctly planned CALL_TOOL action")
                
            except Exception as e:
                self.logger.error(f"Test failed with error: {e}")
                self.record_step(
                    action="test_failed",
                    input_data={},
                    output_data={"error": str(e)}
                )
                raise
    
    def test_planner_finish_action(self):
        """测试planner节点的FINISH动作"""
        self.logger.info("="*50)
        self.logger.info("Testing planner node FINISH functionality")
        
        # 创建带有执行历史的RuntimeState
        state = RuntimeState(
            task_goal="总结之前的分析结果",
            action_summaries=[
                ActionSummary(
                    action_id="action_001",
                    timestamp=datetime.now().isoformat(),
                    tool_name="data_analysis",
                    brief_description="分析了销售数据趋势",
                    key_results=["增长率15%", "Q4表现最佳"],
                    status="success",
                    full_data_ref="action_001",
                    is_sufficient=True
                )
            ],
            action_history=[
                {
                    "type": "tool",
                    "data": {
                        "tool_name": "data_analysis",
                        "output": "详细的数据分析结果..."
                    }
                }
            ]
        )
        
        # 记录输入状态
        self.record_step(
            action="prepare_runtime_state_with_history",
            input_data={
                "task_goal": state.task_goal,
                "action_summaries_count": len(state.action_summaries)
            },
            output_data={"state_created": True}
        )
        
        nodes_map = {
            'planner': {
                'model_name': 'claude-3-5-sonnet-20241022',
                'type': 'planner'
            }
        }
        
        # Mock FINISH响应
        mock_llm_response = PlannerOutput(
            thought="已经完成了数据分析，可以生成最终答案了",
            action="FINISH",
            output_guidance={
                "key_points": ["销售增长15%", "Q4表现最佳"],
                "format_requirements": "使用要点列表形式",
                "quality_requirements": "简洁明了，突出关键数据"
            }
        )
        
        with self.mock_llm_service(mock_llm_response):
            try:
                # 调用planner节点
                result = planner_node(
                    state=state,
                    nodes_map=nodes_map,
                    edges_map=None,
                    user=None,
                    session_id="test_session"
                )
                
                # 记录执行结果
                self.record_step(
                    action="planner_node_finish_execution",
                    input_data={"state": state.model_dump()},
                    output_data=result
                )
                
                # 验证结果
                self.assertIn('current_plan', result)
                plan = result['current_plan']
                
                # 验证FINISH动作
                self.assertEqual(plan.action, "FINISH")
                self.assertIsNone(plan.tool_name)
                self.assertIsNone(plan.tool_input)
                self.assertIsNotNone(plan.output_guidance)
                
                # 验证output_guidance内容
                guidance = plan.output_guidance
                self.assertIn('key_points', guidance)
                self.assertIn('format_requirements', guidance)
                
                # 验证final_answer应该为空（由finalizer生成）
                self.assertIsNone(plan.final_answer)
                
                self.logger.info("✅ Test passed: planner correctly handled FINISH action")
                
            except Exception as e:
                self.logger.error(f"Test failed with error: {e}")
                self.record_step(
                    action="test_failed",
                    input_data={},
                    output_data={"error": str(e)}
                )
                raise
    
    def test_planner_todo_generator_auto_params(self):
        """测试planner调用TodoGenerator时自动补充参数"""
        self.logger.info("="*50)
        self.logger.info("Testing TodoGenerator auto-parameter completion")
        
        state = RuntimeState(
            task_goal="创建一个详细的任务计划",
            action_summaries=[],
            action_history=[]
        )
        
        nodes_map = {
            'planner': {
                'model_name': 'claude-3-5-sonnet-20241022',
                'type': 'planner'
            }
        }
        
        # Mock TodoGenerator调用（没有available_tools参数）
        mock_llm_response = PlannerOutput(
            thought="需要创建一个详细的任务清单",
            action="CALL_TOOL",
            tool_name="TodoGenerator",
            tool_input={"task_description": "分析数据并生成报告"},
            expected_outcome="生成结构化的任务清单"
        )
        
        with self.mock_llm_service(mock_llm_response):
            try:
                # 调用planner节点
                result = planner_node(
                    state=state,
                    nodes_map=nodes_map,
                    edges_map=None,
                    user=None,
                    session_id="test_session"
                )
                
                # 记录执行结果
                self.record_step(
                    action="planner_todo_generator_execution",
                    input_data={"original_tool_input": {"task_description": "分析数据并生成报告"}},
                    output_data=result
                )
                
                # 验证结果
                plan = result['current_plan']
                self.assertEqual(plan.tool_name, "TodoGenerator")
                
                # 验证available_tools被自动添加
                self.assertIn('available_tools', plan.tool_input)
                available_tools = plan.tool_input['available_tools']
                self.assertIsInstance(available_tools, list)
                self.assertGreater(len(available_tools), 0)
                
                # 验证不包含TodoGenerator自身
                tool_names = [tool['name'] for tool in available_tools]
                self.assertNotIn('TodoGenerator', tool_names)
                
                self.logger.info(f"✅ Test passed: Auto-added {len(available_tools)} tools to TodoGenerator")
                
            except Exception as e:
                self.logger.error(f"Test failed with error: {e}")
                self.record_step(
                    action="test_failed",
                    input_data={},
                    output_data={"error": str(e)}
                )
                raise
    
    def test_planner_data_marker_replacement(self):
        """测试planner节点的数据标记替换功能"""
        self.logger.info("="*50)
        self.logger.info("Testing data marker replacement in tool_input")
        
        # 创建包含完整action数据的state
        state = RuntimeState(
            task_goal="使用之前的数据生成报告",
            action_summaries=[
                ActionSummary(
                    action_id="action_001",
                    timestamp=datetime.now().isoformat(),
                    tool_name="data_analysis",
                    brief_description="数据分析完成",
                    key_results=["关键结果1"],
                    status="success",
                    full_data_ref="action_001",
                    is_sufficient=True
                )
            ],
            full_action_data={
                "action_001": {
                    "result": "详细的分析数据内容",
                    "metrics": {"total": 1000, "average": 50}
                }
            }
        )
        
        nodes_map = {
            'planner': {
                'model_name': 'claude-3-5-sonnet-20241022',
                'type': 'planner'
            }
        }
        
        # Mock包含数据标记的响应
        mock_llm_response = PlannerOutput(
            thought="使用之前的分析结果生成报告",
            action="CALL_TOOL",
            tool_name="report_generator",
            tool_input={
                "data": "@data:action_001",
                "format": "detailed"
            },
            expected_outcome="生成详细报告"
        )
        
        with self.mock_llm_service(mock_llm_response):
            try:
                # 调用planner节点
                result = planner_node(
                    state=state,
                    nodes_map=nodes_map,
                    edges_map=None,
                    user=None,
                    session_id="test_session"
                )
                
                # 记录执行结果
                self.record_step(
                    action="planner_data_replacement_execution",
                    input_data={
                        "original_marker": "@data:action_001",
                        "full_action_data_keys": list(state.full_action_data.keys())
                    },
                    output_data=result
                )
                
                # 验证数据标记被替换
                plan = result['current_plan']
                self.assertEqual(plan.tool_name, "report_generator")
                
                # 验证@data:action_001被替换为实际数据
                tool_input = plan.tool_input
                self.assertNotEqual(tool_input['data'], "@data:action_001")
                self.assertEqual(tool_input['data'], state.full_action_data['action_001'])
                
                self.logger.info("✅ Test passed: Data markers correctly replaced")
                
            except Exception as e:
                self.logger.error(f"Test failed with error: {e}")
                self.record_step(
                    action="test_failed",
                    input_data={},
                    output_data={"error": str(e)}
                )
                raise
    
    def mock_llm_service(self, mock_response):
        """
        创建一个context manager来mock LLM服务
        """
        class MockLLMContext:
            def __init__(self, response):
                self.response = response
                self.original_get_structured_llm = None
                
            def __enter__(self):
                # 保存原始方法
                self.original_get_structured_llm = CoreLLMService.get_structured_llm
                
                # 创建mock LLM
                mock_llm = MagicMock()
                mock_llm.invoke = MagicMock(return_value=self.response)
                
                # 替换方法
                CoreLLMService.get_structured_llm = MagicMock(return_value=mock_llm)
                
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                # 恢复原始方法
                if self.original_get_structured_llm:
                    CoreLLMService.get_structured_llm = self.original_get_structured_llm
        
        return MockLLMContext(mock_response)
    
    def save_test_result(self, test_name, result_data):
        """
        保存测试结果到result文件
        """
        result_file = os.path.join(self.output_dir, self.result_filename)
        
        result_content = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "result": result_data,
            "status": "success" if not result_data.get('error') else "failed"
        }
        
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result_content, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n✅ Test result saved to: {os.path.abspath(result_file)}")
        except Exception as e:
            self.logger.error(f"Failed to write result file: {e}")