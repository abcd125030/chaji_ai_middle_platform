"""
测试模块: DBCheckpoint 增强功能

测试增强的 Agentic 工作流状态持久化功能，包括：
- 带时间戳的工作流目录创建
- 步骤文件保存
- 序列化功能
- 降级加载策略

功能分支: 002-agentic-uuid-yyyymmdd
"""

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from django.test import TestCase
from django.contrib.auth import get_user_model
from agentic.models import AgentTask, Graph
from agentic.core.checkpoint import DBCheckpoint
from agentic.core.schemas import RuntimeState

User = get_user_model()


class TestTimestampedWorkflowDirectory(TestCase):
    """
    测试带时间戳的工作流目录创建功能 (T008)

    验证：
    - 目录名格式正确 (yyyymmdd_HHMMSS_{task_uuid})
    - metadata.json 初始化
    - 错误处理
    """

    @classmethod
    def setUpTestData(cls):
        """设置测试数据（整个测试类共享）"""
        cls.user = User.objects.create_user(username='test_user', password='test_pass')
        cls.graph = Graph.objects.create(
            name='test_graph',
            description='测试图'
        )

    def setUp(self):
        """每个测试方法前执行"""
        self.checkpoint = DBCheckpoint()
        # 生成测试用的UUID
        self.test_task_uuid = uuid.uuid4()
        self.test_session_uuid = uuid.uuid4()

        self.task = AgentTask.objects.create(
            user=self.user,
            session_id=self.test_session_uuid,
            graph=self.graph,
            input_data={'goal': '测试目录创建功能'}
        )
        # 手动设置task_id以便测试
        self.task.task_id = self.test_task_uuid
        self.task.save()
        self.output_dir = Path(__file__).parent / "outputs"
        self.output_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """每个测试方法后执行，清理创建的目录"""
        try:
            # 清理测试创建的工作流目录
            user_uuid = str(self.user.id)
            session_uuid = str(self.task.session_id)
            session_path = self.checkpoint._get_session_path(user_uuid, session_uuid)

            if session_path.exists():
                import shutil
                shutil.rmtree(session_path, ignore_errors=True)
        except Exception as e:
            print(f"清理失败: {e}")

    def test_create_timestamped_workflow_directory(self):
        """测试创建带时间戳的工作流目录"""
        user_uuid = str(self.user.id)
        session_uuid = str(self.task.session_id)
        task_id = str(self.task.task_id)

        # 创建工作流目录
        workflow_dir = self.checkpoint.create_workflow_directory(
            task_id=task_id,
            user_uuid=user_uuid,
            session_uuid=session_uuid
        )

        # 验证目录存在
        self.assertTrue(workflow_dir.exists())

        # 验证目录名格式: yyyymmdd_HHMMSS_{task_uuid}
        dir_name = workflow_dir.name
        pattern = rf'^\d{{8}}_\d{{6}}_{task_id}$'
        self.assertIsNotNone(re.match(pattern, dir_name),
                           f"目录名格式不正确: {dir_name}")

        # 提取时间戳部分 (格式: YYYYMMDD_HHMMSS_{UUID})
        parts = dir_name.split('_')
        date_part = parts[0]  # YYYYMMDD
        time_part = parts[1]  # HHMMSS

        # 验证日期格式 (YYYYMMDD)
        self.assertEqual(len(date_part), 8)
        self.assertTrue(date_part.isdigit())

        # 验证时间格式 (HHMMSS)
        self.assertEqual(len(time_part), 6)
        self.assertTrue(time_part.isdigit())

        # 保存测试结果
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        result_file = self.output_dir / f"process-{timestamp}-test_directory_creation.json"
        with open(result_file, 'w') as f:
            json.dump({
                "test": "test_create_timestamped_workflow_directory",
                "status": "success",
                "workflow_dir": str(workflow_dir),
                "dir_name": dir_name,
                "timestamp_format": f"{date_part}_{time_part}"
            }, f, indent=2, ensure_ascii=False)

        print(f"\n测试结果已保存: {result_file}")

    def test_metadata_initialization(self):
        """测试 metadata.json 初始化"""
        user_uuid = str(self.user.id)
        session_uuid = str(self.task.session_id)
        task_id = self.task.task_id

        # 创建工作流目录
        workflow_dir = self.checkpoint.create_workflow_directory(
            task_id=task_id,
            user_uuid=user_uuid,
            session_uuid=session_uuid
        )

        # 验证 metadata.json 存在
        metadata_file = workflow_dir / "metadata.json"
        self.assertTrue(metadata_file.exists())

        # 加载并验证 metadata 内容
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # 验证必需字段
        self.assertEqual(metadata['task_id'], task_id)
        self.assertEqual(metadata['session_id'], session_uuid)
        self.assertEqual(metadata['user_id'], user_uuid)
        self.assertEqual(metadata['total_steps'], 0)
        self.assertEqual(metadata['node_types_executed'], [])
        self.assertEqual(metadata['workflow_status'], 'running')

        # 验证时间戳字段存在且格式正确
        self.assertIn('workflow_start_time', metadata)
        self.assertIn('workflow_start_timestamp', metadata)
        self.assertIn('last_update_time', metadata)

        # 验证 ISO 8601 时间格式
        datetime.fromisoformat(metadata['workflow_start_time'])
        datetime.fromisoformat(metadata['last_update_time'])

        # 验证 Unix 时间戳
        self.assertIsInstance(metadata['workflow_start_timestamp'], (int, float))

        print(f"\nmetadata.json 内容验证通过")

    def test_directory_creation_failure_handling(self):
        """测试目录创建失败的错误处理"""
        # 使用无效的路径测试错误处理
        invalid_task_id = "invalid/task\\id"  # 包含文件系统不允许的字符

        with self.assertRaises(Exception):
            self.checkpoint.create_workflow_directory(
                task_id=invalid_task_id,
                user_uuid=str(self.user.id),
                session_uuid=str(self.task.session_id)
            )

        print(f"\n错误处理测试通过：正确捕获了无效目录名异常")


class TestStepFileSaving(TestCase):
    """
    测试步骤文件保存功能 (T009)

    验证：
    - 规划器步骤保存 (1_planner.json)
    - 工具调用步骤保存 (2_call_tool_{toolname}.json)
    - 反思步骤保存 (3_reflection.json)
    - 输出步骤保存 (4_output.json)
    - 步骤编号连续性
    """

    @classmethod
    def setUpTestData(cls):
        """设置测试数据"""
        cls.user = User.objects.create_user(username='test_user_step', password='test_pass')
        cls.graph = Graph.objects.create(
            name='test_graph_step',
            description='测试图-步骤'
        )

    def setUp(self):
        """每个测试前执行"""
        self.checkpoint = DBCheckpoint()
        # 生成测试用的UUID
        self.test_task_uuid = uuid.uuid4()
        self.test_session_uuid = uuid.uuid4()

        self.task = AgentTask.objects.create(
            user=self.user,
            session_id=self.test_session_uuid,
            graph=self.graph,
            input_data={'goal': '测试步骤保存功能'}
        )
        self.task.task_id = self.test_task_uuid
        self.task.save()

        # 创建工作流目录
        self.workflow_dir = self.checkpoint.create_workflow_directory(
            task_id=self.task.task_id,
            user_uuid=str(self.user.id),
            session_uuid=str(self.task.session_id)
        )

        self.output_dir = Path(__file__).parent / "outputs"
        self.output_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """清理"""
        try:
            user_uuid = str(self.user.id)
            session_uuid = str(self.task.session_id)
            session_path = self.checkpoint._get_session_path(user_uuid, session_uuid)

            if session_path.exists():
                import shutil
                shutil.rmtree(session_path, ignore_errors=True)
        except Exception as e:
            print(f"清理失败: {e}")

    def test_save_planner_step(self):
        """测试保存规划器步骤"""
        planner_output = {
            "thought": "需要分析用户需求",
            "action": "CALL_TOOL",
            "tool_name": "WebSearch",
            "tool_input": {"query": "AI技术2025"}
        }

        success = self.checkpoint.save_step(
            task_id=self.task.task_id,
            step_number=1,
            node_type="planner",
            node_output=planner_output
        )

        self.assertTrue(success)

        # 验证文件存在且名称正确
        step_file = self.workflow_dir / "1_planner.json"
        self.assertTrue(step_file.exists())

        # 验证文件内容
        with open(step_file, 'r') as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data['thought'], planner_output['thought'])
        self.assertEqual(saved_data['action'], planner_output['action'])

        print(f"\n规划器步骤保存成功: {step_file}")

    def test_save_tool_step(self):
        """测试保存工具调用步骤"""
        tool_output = {
            "tool_output": {
                "status": "success",
                "data": {
                    "results": [
                        {"title": "AI技术进展", "url": "https://example.com"}
                    ]
                }
            }
        }

        success = self.checkpoint.save_step(
            task_id=self.task.task_id,
            step_number=2,
            node_type="call_tool",
            node_output=tool_output,
            tool_name="WebSearch"
        )

        self.assertTrue(success)

        # 验证文件存在且名称正确
        step_file = self.workflow_dir / "2_call_tool_WebSearch.json"
        self.assertTrue(step_file.exists())

        print(f"\n工具调用步骤保存成功: {step_file}")

    def test_save_reflection_step(self):
        """测试保存反思步骤"""
        reflection_output = {
            "reflection": "搜索结果符合预期，可以继续处理",
            "should_continue": True
        }

        success = self.checkpoint.save_step(
            task_id=self.task.task_id,
            step_number=3,
            node_type="reflection",
            node_output=reflection_output
        )

        self.assertTrue(success)

        # 验证文件存在且名称正确
        step_file = self.workflow_dir / "3_reflection.json"
        self.assertTrue(step_file.exists())

        print(f"\n反思步骤保存成功: {step_file}")

    def test_save_output_step(self):
        """测试保存输出步骤"""
        output_data = {
            "output_tool_decision": {
                "tool_name": "ReportGenerator",
                "tool_input": {"content": "生成的报告内容"}
            }
        }

        success = self.checkpoint.save_step(
            task_id=self.task.task_id,
            step_number=4,
            node_type="output",
            node_output=output_data,
            tool_name="ReportGenerator"
        )

        self.assertTrue(success)

        # 验证文件存在且名称正确
        step_file = self.workflow_dir / "4_output_ReportGenerator.json"
        self.assertTrue(step_file.exists())

        print(f"\n输出步骤保存成功: {step_file}")

    def test_sequential_numbering(self):
        """测试步骤编号连续性"""
        # 保存多个步骤
        steps = [
            (1, "planner", {"thought": "步骤1"}, None),
            (2, "call_tool", {"tool_output": "结果2"}, "Tool1"),
            (3, "reflection", {"reflection": "步骤3"}, None),
            (4, "call_tool", {"tool_output": "结果4"}, "Tool2"),
            (5, "output", {"output": "最终结果"}, "Generator"),
        ]

        for step_number, node_type, output, tool_name in steps:
            success = self.checkpoint.save_step(
                task_id=self.task.task_id,
                step_number=step_number,
                node_type=node_type,
                node_output=output,
                tool_name=tool_name
            )
            self.assertTrue(success)

        # 验证所有文件都存在且编号连续
        step_files = self.checkpoint.list_step_files(self.task.task_id)
        self.assertEqual(len(step_files), 5)

        # 验证步骤号连续
        step_numbers = [f['step_number'] for f in step_files]
        self.assertEqual(step_numbers, [1, 2, 3, 4, 5])

        # 保存测试结果
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        result_file = self.output_dir / f"process-{timestamp}-test_step_saving.json"
        with open(result_file, 'w') as f:
            json.dump({
                "test": "test_sequential_numbering",
                "status": "success",
                "total_steps": len(step_files),
                "step_numbers": step_numbers,
                "step_files": [f['file_path'] for f in step_files]
            }, f, indent=2, ensure_ascii=False)

        print(f"\n步骤编号连续性测试通过，结果已保存: {result_file}")


class TestSerialization(TestCase):
    """
    测试序列化功能 (T010)

    验证：
    - Pydantic 模型序列化
    - 复杂对象序列化
    - JSON 文件有效性
    """

    @classmethod
    def setUpTestData(cls):
        """设置测试数据"""
        cls.user = User.objects.create_user(username='test_user_serial', password='test_pass')
        cls.graph = Graph.objects.create(
            name='test_graph_serial',
            description='测试图-序列化'
        )

    def setUp(self):
        """每个测试前执行"""
        self.checkpoint = DBCheckpoint()
        # 生成测试用的UUID
        self.test_task_uuid = uuid.uuid4()
        self.test_session_uuid = uuid.uuid4()

        self.task = AgentTask.objects.create(
            user=self.user,
            session_id=self.test_session_uuid,
            graph=self.graph,
            input_data={'goal': '测试序列化功能'}
        )
        self.task.task_id = self.test_task_uuid
        self.task.save()

        # 创建工作流目录
        self.workflow_dir = self.checkpoint.create_workflow_directory(
            task_id=self.task.task_id,
            user_uuid=str(self.user.id),
            session_uuid=str(self.task.session_id)
        )

        self.output_dir = Path(__file__).parent / "outputs"
        self.output_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """清理"""
        try:
            user_uuid = str(self.user.id)
            session_uuid = str(self.task.session_id)
            session_path = self.checkpoint._get_session_path(user_uuid, session_uuid)

            if session_path.exists():
                import shutil
                shutil.rmtree(session_path, ignore_errors=True)
        except Exception as e:
            print(f"清理失败: {e}")

    def test_serialize_pydantic_models(self):
        """测试 Pydantic 模型序列化"""
        # 创建 RuntimeState 对象
        state = RuntimeState(
            task_goal="测试 Pydantic 序列化",
            action_history=[[]],
            preprocessed_files={},
            origin_images=[],
            usage={"tokens": 100},
            todo=[{"task": "测试任务", "status": "pending"}],
            full_action_data={}
        )

        # 使用 checkpoint 的序列化方法
        serialized = self.checkpoint._serialize_output(state)

        # 验证序列化结果是字典
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized['task_goal'], "测试 Pydantic 序列化")
        self.assertIn('usage', serialized)

        # 验证可以 JSON 序列化
        json_str = json.dumps(serialized, ensure_ascii=False)
        self.assertIsNotNone(json_str)

        print(f"\nPydantic 模型序列化测试通过")

    def test_serialize_complex_objects(self):
        """测试复杂对象序列化"""
        complex_data = {
            "nested_dict": {
                "level1": {
                    "level2": {
                        "value": "深层嵌套"
                    }
                }
            },
            "list_of_dicts": [
                {"id": 1, "name": "项目1"},
                {"id": 2, "name": "项目2"}
            ],
            "mixed_types": {
                "string": "文本",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "null": None,
                "list": [1, 2, 3]
            }
        }

        # 序列化
        serialized = self.checkpoint._serialize_output(complex_data)

        # 验证结构保持不变
        self.assertEqual(serialized['nested_dict']['level1']['level2']['value'], "深层嵌套")
        self.assertEqual(len(serialized['list_of_dicts']), 2)
        self.assertEqual(serialized['mixed_types']['number'], 42)

        # 验证可以 JSON 序列化
        json_str = json.dumps(serialized, ensure_ascii=False)
        self.assertIsNotNone(json_str)

        print(f"\n复杂对象序列化测试通过")

    def test_json_validity(self):
        """测试生成的 JSON 文件可解析性"""
        # 保存一个复杂的步骤
        complex_output = {
            "data": {
                "items": [
                    {"id": i, "value": f"值{i}"} for i in range(10)
                ],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "count": 10
                }
            },
            "nested": {
                "deep": {
                    "structure": {
                        "test": "深层测试"
                    }
                }
            }
        }

        self.checkpoint.save_step(
            task_id=self.task.task_id,
            step_number=1,
            node_type="planner",
            node_output=complex_output
        )

        # 读取并解析文件
        step_file = self.workflow_dir / "1_planner.json"
        self.assertTrue(step_file.exists())

        with open(step_file, 'r') as f:
            loaded_data = json.load(f)

        # 验证数据完整性
        self.assertEqual(len(loaded_data['data']['items']), 10)
        self.assertEqual(loaded_data['nested']['deep']['structure']['test'], "深层测试")

        print(f"\nJSON 文件有效性测试通过")


class TestFallbackLoading(TestCase):
    """
    测试降级加载策略 (T011 的一部分)

    验证：
    - 从带时间戳目录加载
    - 从旧格式目录加载（向后兼容）
    - 从数据库加载（最终降级）
    """

    @classmethod
    def setUpTestData(cls):
        """设置测试数据"""
        cls.user = User.objects.create_user(username='test_user_load', password='test_pass')
        cls.graph = Graph.objects.create(
            name='test_graph_load',
            description='测试图-加载'
        )

    def setUp(self):
        """每个测试前执行"""
        self.checkpoint = DBCheckpoint()
        # 生成测试用的UUID
        self.test_task_uuid = uuid.uuid4()
        self.test_session_uuid = uuid.uuid4()

        self.task = AgentTask.objects.create(
            user=self.user,
            session_id=self.test_session_uuid,
            graph=self.graph,
            input_data={'goal': '测试降级加载功能'}
        )
        self.task.task_id = self.test_task_uuid
        self.task.save()

        self.output_dir = Path(__file__).parent / "outputs"
        self.output_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """清理"""
        try:
            user_uuid = str(self.user.id)
            session_uuid = str(self.task.session_id)
            session_path = self.checkpoint._get_session_path(user_uuid, session_uuid)

            if session_path.exists():
                import shutil
                shutil.rmtree(session_path, ignore_errors=True)
        except Exception as e:
            print(f"清理失败: {e}")

    def test_load_from_timestamped_directory(self):
        """测试从带时间戳目录加载"""
        # 创建工作流目录和保存状态
        workflow_dir = self.checkpoint.create_workflow_directory(
            task_id=self.task.task_id,
            user_uuid=str(self.user.id),
            session_uuid=str(self.task.session_id)
        )

        # 创建测试状态
        test_state = RuntimeState(
            task_goal="测试从时间戳目录加载",
            action_history=[[]],
            preprocessed_files={},
            origin_images=[],
            usage={},
            todo=[],
            full_action_data={}
        )

        # 保存状态到带时间戳目录
        self.checkpoint.save(self.task.task_id, test_state)

        # 使用降级加载
        loaded_state = self.checkpoint.load_with_fallback(self.task.task_id)

        # 验证加载成功
        self.assertIsNotNone(loaded_state)
        self.assertEqual(loaded_state.task_goal, "测试从时间戳目录加载")

        print(f"\n从带时间戳目录加载测试通过")

    def test_load_from_database(self):
        """测试从数据库加载（最终降级）"""
        # 直接在数据库中保存状态（不创建文件）
        test_snapshot = {
            "task_goal": "测试从数据库加载",
            "action_history": [[]],
            "preprocessed_files": {},
            "origin_images": [],
            "usage": {},
            "todo": [],
            "full_action_data": {}
        }

        self.task.state_snapshot = test_snapshot
        self.task.save()

        # 使用降级加载
        loaded_state = self.checkpoint.load_with_fallback(self.task.task_id)

        # 验证加载成功
        self.assertIsNotNone(loaded_state)
        self.assertEqual(loaded_state.task_goal, "测试从数据库加载")

        print(f"\n从数据库降级加载测试通过")
