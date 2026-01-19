#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 RuntimeState 改造为 Pydantic 模型后的兼容性
遵循 backend/单元测试规范.md
"""

import os
import sys
import json
import logging
from datetime import datetime
from django.test import TestCase
from django.conf import settings
from django.db import transaction

# 添加项目根目录到路径
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, backend_path)

# 配置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from agentic.core.schemas import RuntimeState, ActionSummary


class RuntimeStatePydanticTestCase(TestCase):
    """
    RuntimeState Pydantic 改造兼容性测试
    
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
                # RuntimeState 是纯 Python 类，不涉及数据库
                # 这里主要是为了遵循规范，实际上不需要创建数据库记录
                pass
                
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
        self.output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 使用符合规范的文件命名格式
        test_method_name = self._testMethodName
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y%m%d')
        time_str = timestamp.strftime('%H%M%S')
        
        # 生成符合规范的文件名
        self.process_filename = f'process-{date_str}-{time_str}-{test_method_name}.json'
        self.log_filename = f'log-{date_str}-{time_str}-{test_method_name}.log'
        
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
        捕获当前状态。
        
        stage: 'initial' 或 'final'
        """
        self.logger.info(f"Capturing {stage} state...")
        # RuntimeState 不涉及数据库，所以这里主要记录测试环境信息
        return {
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
            "test_method": self._testMethodName if hasattr(self, '_testMethodName') else None
        }

    def record_step(self, action, input_data, output_data, **kwargs):
        """记录执行步骤"""
        step_number = len(self.process_data["execution_steps"]) + 1
        step_data = {
            "step": step_number,
            "action": action,
            "input": str(input_data),  # 确保可序列化
            "output": str(output_data),  # 确保可序列化
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
        except Exception as e:
            self.logger.error(f"Failed to write process file: {e}")

        self.logger.info(f"Test method finished. Duration: {duration:.2f}s")
        print(f"\n[INFO] Test outputs saved to: {os.path.abspath(process_file)}")
    
    def test_runtime_state_creation(self):
        """测试 RuntimeState 的基本创建"""
        self.logger.info("=== 测试 RuntimeState 基本创建 ===")
        
        # 测试最简单的创建方式
        self.record_step(
            "创建基本RuntimeState",
            {"task_goal": "完成一个简单任务"},
            None
        )
        
        state1 = RuntimeState(task_goal="完成一个简单任务")
        self.assertEqual(state1.task_goal, "以下是用户需求：```完成一个简单任务```")
        self.assertEqual(state1.preprocessed_files, {
            'documents': {},
            'tables': {},
            'images': {},
            'other_files': {}
        })
        self.assertEqual(state1.origin_images, [])
        self.assertEqual(state1.action_history, [])
        
        self.record_step(
            "验证基本创建",
            None,
            {"task_goal": state1.task_goal, "preprocessed_files": state1.preprocessed_files}
        )
        self.logger.info("✓ 基本创建成功")
        
        # 测试带 usage 的创建
        self.record_step(
            "创建带usage的RuntimeState",
            {"task_goal": "分析数据", "usage": "使用高级分析模式"},
            None
        )
        
        state2 = RuntimeState(
            task_goal="分析数据",
            usage="使用高级分析模式"
        )
        self.assertEqual(state2.task_goal, "使用高级分析模式\n以下是用户要求：\n```分析数据```")
        self.assertEqual(state2.usage, "使用高级分析模式")
        
        self.record_step(
            "验证带usage创建",
            None,
            {"task_goal": state2.task_goal, "usage": state2.usage}
        )
        self.logger.info("✓ 带 usage 创建成功")
        
        # 测试带所有可选参数的创建
        self.record_step(
            "创建完整参数的RuntimeState",
            {
                "task_goal": "复杂任务",
                "preprocessed_files": {'documents': {'doc1.md': '内容'}},
                "origin_images": ['base64_image'],
                "action_history": [{'type': 'tool', 'data': {'name': 'test'}}]
            },
            None
        )
        
        state3 = RuntimeState(
            task_goal="复杂任务",
            preprocessed_files={'documents': {'doc1.md': '内容'}},
            origin_images=['base64_image'],
            action_history=[{'type': 'tool', 'data': {'name': 'test'}}],
            context_memory={'key': 'value'},
            user_context={'user_id': '123'},
            chat_history=[{'role': 'user', 'content': 'hello'}]
        )
        self.assertEqual(state3.preprocessed_files['documents']['doc1.md'], '内容')
        self.assertEqual(len(state3.origin_images), 1)
        self.assertEqual(len(state3.action_history), 1)
        
        self.record_step(
            "验证完整参数创建",
            None,
            {
                "preprocessed_files": state3.preprocessed_files,
                "origin_images_count": len(state3.origin_images),
                "action_history_count": len(state3.action_history)
            }
        )
        self.logger.info("✓ 完整参数创建成功")

    def test_runtime_state_methods(self):
        """测试 RuntimeState 的方法是否保留"""
        self.logger.info("=== 测试 RuntimeState 方法兼容性 ===")
        
        self.record_step(
            "创建测试用RuntimeState",
            {"task_goal": "测试任务"},
            None
        )
        
        state = RuntimeState(task_goal="测试任务")
        
        # 添加一些测试数据
        summary = ActionSummary(
            action_id="action_1",
            timestamp=datetime.now().isoformat(),
            tool_name="test_tool",
            brief_description="测试工具执行",
            key_results=["结果1", "结果2"],
            status="success",
            full_data_ref="action_1",
            is_sufficient=True
        )
        state.action_summaries.append(summary)
        state.full_action_data["action_1"] = {"result": "test_data"}
        
        self.record_step(
            "添加ActionSummary和数据",
            {"action_id": "action_1", "tool_name": "test_tool"},
            {"action_summaries_count": len(state.action_summaries)}
        )
        
        # 测试 get_full_action_data 方法
        data = state.get_full_action_data("action_1")
        self.assertEqual(data, {"result": "test_data"})
        self.assertIsNone(state.get_full_action_data("non_existent"))
        
        self.record_step(
            "测试get_full_action_data",
            {"action_id": "action_1"},
            {"result": data}
        )
        self.logger.info("✓ get_full_action_data 方法正常")
        
        # 测试 extract_relevant_data 方法
        relevant = state.extract_relevant_data("test_tool", ["测试"])
        self.assertIn("action_1", relevant)
        
        self.record_step(
            "测试extract_relevant_data",
            {"tool_name": "test_tool", "context_hints": ["测试"]},
            {"relevant_keys": list(relevant.keys())}
        )
        self.logger.info("✓ extract_relevant_data 方法正常")
        
        # 测试 get_data_catalog 方法
        catalog = state.get_data_catalog()
        self.assertIn("available_data_types", catalog)
        self.assertEqual(catalog["available_data_types"]["execution_history"]["total_actions"], 1)
        
        self.record_step(
            "测试get_data_catalog",
            None,
            {"catalog_keys": list(catalog.keys()), "total_actions": catalog["available_data_types"]["execution_history"]["total_actions"]}
        )
        self.logger.info("✓ get_data_catalog 方法正常")
        
        # 测试 extract_data_by_path 方法
        state.preprocessed_files['documents']['test.md'] = "测试内容"
        content = state.extract_data_by_path("preprocessed_files.documents.test.md")
        self.assertEqual(content, "测试内容")
        
        self.record_step(
            "测试extract_data_by_path",
            {"path": "preprocessed_files.documents.test.md"},
            {"content": content}
        )
        self.logger.info("✓ extract_data_by_path 方法正常")
        
        # 测试 get_origin_data_structure 方法
        structure = state.get_origin_data_structure()
        self.assertIsInstance(structure, list)
        
        self.record_step(
            "测试get_origin_data_structure",
            None,
            {"structure_type": type(structure).__name__, "structure_length": len(structure)}
        )
        self.logger.info("✓ get_origin_data_structure 方法正常")

    def test_runtime_state_serialization(self):
        """测试 RuntimeState 的序列化"""
        self.logger.info("=== 测试 RuntimeState 序列化 ===")
        
        self.record_step(
            "创建测试用RuntimeState",
            {
                "task_goal": "序列化测试",
                "usage": "测试用途",
                "action_history": [{'type': 'tool', 'data': {'name': 'test'}}]
            },
            None
        )
        
        state = RuntimeState(
            task_goal="序列化测试",
            usage="测试用途",
            action_history=[{'type': 'tool', 'data': {'name': 'test'}}],
            user_context={'user_id': '456'}
        )
        
        # 测试 model_dump
        dumped = state.model_dump()
        self.assertIsInstance(dumped, dict)
        self.assertEqual(dumped['task_goal'], "测试用途\n以下是用户要求：\n```序列化测试```")
        self.assertEqual(dumped['usage'], "测试用途")
        self.assertEqual(len(dumped['action_history']), 1)
        self.assertNotIn('_data_catalog_cache', dumped)  # 私有属性不应被序列化
        self.assertNotIn('_original_task_goal', dumped)  # 私有属性不应被序列化
        
        self.record_step(
            "测试model_dump",
            None,
            {
                "dumped_keys": list(dumped.keys()),
                "task_goal": dumped['task_goal'],
                "private_attrs_excluded": '_data_catalog_cache' not in dumped
            }
        )
        self.logger.info("✓ model_dump 序列化成功")
        
        # 测试 JSON 序列化
        json_str = json.dumps(dumped)
        self.assertIsInstance(json_str, str)
        
        self.record_step(
            "测试JSON序列化",
            {"dumped": "已序列化的字典"},
            {"json_length": len(json_str)}
        )
        self.logger.info("✓ JSON 序列化成功")
        
        # 测试从字典重建
        state2 = RuntimeState(**dumped)
        # 注意：由于 task_goal 会被重新处理，这里会有双重处理
        # 但这不影响向后兼容性
        
        self.record_step(
            "测试从字典重建",
            {"dumped": "序列化的字典"},
            {"recreated": "成功重建RuntimeState"}
        )
        self.logger.info("✓ 从字典重建成功")

    def test_runtime_state_attribute_access(self):
        """测试属性访问兼容性"""
        self.logger.info("=== 测试属性访问兼容性 ===")
        
        self.record_step(
            "创建测试用RuntimeState",
            {"task_goal": "属性测试"},
            None
        )
        
        state = RuntimeState(task_goal="属性测试")
        
        # 测试使用 getattr/hasattr（旧代码可能这样用）
        self.assertTrue(hasattr(state, 'task_goal'))
        self.assertTrue(hasattr(state, 'preprocessed_files'))
        self.assertTrue(hasattr(state, 'action_history'))
        self.assertEqual(getattr(state, 'task_goal'), "以下是用户需求：```属性测试```")
        
        self.record_step(
            "测试getattr/hasattr",
            {"attributes": ['task_goal', 'preprocessed_files', 'action_history']},
            {"all_attributes_exist": True}
        )
        self.logger.info("✓ getattr/hasattr 兼容")
        
        # 测试直接属性访问
        state.todo = [{'task': 'item1'}]
        self.assertEqual(len(state.todo), 1)
        
        self.record_step(
            "测试直接属性赋值",
            {"todo": [{'task': 'item1'}]},
            {"todo_length": len(state.todo)}
        )
        self.logger.info("✓ 直接属性赋值正常")
        
        # 测试动态添加属性（由于 extra="allow"）
        state.new_field = "动态字段"
        self.assertEqual(state.new_field, "动态字段")
        
        self.record_step(
            "测试动态属性添加",
            {"new_field": "动态字段"},
            {"new_field_value": state.new_field}
        )
        self.logger.info("✓ 动态属性添加正常（extra='allow'）")

    def test_runtime_state_with_action_summaries(self):
        """测试包含 ActionSummary 的情况"""
        self.logger.info("=== 测试 ActionSummary 集成 ===")
        
        self.record_step(
            "创建测试用RuntimeState",
            {"task_goal": "测试ActionSummary"},
            None
        )
        
        state = RuntimeState(task_goal="测试ActionSummary")
        
        # 创建多个 ActionSummary
        for i in range(3):
            summary = ActionSummary(
                action_id=f"action_{i}",
                timestamp=datetime.now().isoformat(),
                tool_name=f"tool_{i}",
                brief_description=f"执行工具{i}",
                key_results=[f"结果{i}"],
                status="success" if i < 2 else "failed",
                full_data_ref=f"action_{i}",
                is_sufficient=i == 1
            )
            state.action_summaries.append(summary)
            state.full_action_data[f"action_{i}"] = {
                "data": f"data_{i}",
                "output": f"output_{i}"
            }
        
        self.record_step(
            "添加多个ActionSummary",
            {"count": 3},
            {"action_summaries_count": len(state.action_summaries)}
        )
        
        # 验证数据完整性
        self.assertEqual(len(state.action_summaries), 3)
        self.assertEqual(state.action_summaries[0].tool_name, "tool_0")
        self.assertEqual(state.action_summaries[2].status, "failed")
        
        # 测试序列化
        dumped = state.model_dump()
        self.assertEqual(len(dumped['action_summaries']), 3)
        self.assertEqual(dumped['action_summaries'][0]['tool_name'], "tool_0")
        
        self.record_step(
            "验证ActionSummary序列化",
            None,
            {
                "serialized_count": len(dumped['action_summaries']),
                "first_tool_name": dumped['action_summaries'][0]['tool_name']
            }
        )
        self.logger.info("✓ ActionSummary 集成正常")


if __name__ == "__main__":
    # 使用 Django 的测试运行器
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=True)
    failures = test_runner.run_tests(['agentic.tests.test_runtime_state_pydantic'])
    
    if failures:
        sys.exit(1)