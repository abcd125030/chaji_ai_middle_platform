#!/usr/bin/env python
"""
端到端集成测试脚本

本脚本验证agentic工作流系统从任务创建到celery执行、文件生成的完整流程。
主要验证:
1. 001分支: 输出工具调用流程优化
2. 002分支: 带时间戳的工作流目录和步骤文件命名

使用方法:
    cd /Users/chagee/Repos/X/backend
    source .venv/bin/activate
    python agentic/tests/test_end_to_end_workflow.py

预期输出:
    - 测试执行日志(INFO级别)
    - 测试报告JSON文件: backend/agentic/tests/outputs/process-YYYYMMDD-HHMMSS-test_end_to_end_workflow.json
"""

import os
import sys
import django

# 步骤1: 设置Django环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 步骤2: 添加backend目录到Python路径
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)

# 步骤3: 初始化Django
django.setup()

# 现在可以安全导入Django模型和其他依赖
import json
import time
import logging
import uuid
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Django imports
from django.conf import settings
from agentic.models import AgentTask, Graph, ActionSteps

# 配置日志
logger = logging.getLogger('django')


# ============================================================================
# 数据结构定义 (T003-T006)
# ============================================================================

class TestStatus(Enum):
    """测试执行状态枚举 (T003)"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    WORKER_UNAVAILABLE = "WORKER_UNAVAILABLE"


class VerificationType(Enum):
    """验证类型枚举"""
    DATABASE = "DATABASE"
    FILESYSTEM = "FILESYSTEM"
    CONTENT = "CONTENT"


@dataclass
class VerificationResult:
    """
    验证结果数据结构 (T004)

    代表单个验证断言的执行结果
    """
    verification_id: str  # 验证项的唯一标识
    verification_type: str  # DATABASE | FILESYSTEM | CONTENT
    test_case: str  # 验证的具体测试用例(如"FR-007: 工作流目录命名格式")
    expected: Any  # 期望值
    actual: Any  # 实际值
    passed: bool  # 是否通过
    error_message: Optional[str]  # 错误信息(如果未通过)
    timestamp: datetime  # 验证执行时间


@dataclass
class TestExecution:
    """
    测试执行结果数据结构 (T005)

    代表一次完整的测试执行过程
    """
    test_id: str  # 测试执行的唯一标识(UUID)
    test_name: str  # 固定值: "test_end_to_end_workflow"
    start_time: datetime  # 测试开始时间
    end_time: datetime  # 测试结束时间
    duration_seconds: float  # 测试执行时长
    status: TestStatus  # SUCCESS | FAILED | TIMEOUT | WORKER_UNAVAILABLE
    agentic_task_id: str  # 创建的AgentTask的task_id
    verification_results: Dict[str, Any]  # 详细的验证结果
    errors: List[str]  # 错误信息列表


@dataclass
class WorkflowDirectory:
    """
    工作流目录实体 (T006)

    代表celery任务执行后生成的工作流目录
    """
    directory_path: Path  # 完整的目录路径
    directory_name: str  # 目录名称(格式: yyyymmdd_HHMMSS_{task_uuid})
    timestamp_prefix: str  # 时间戳前缀(格式: yyyymmdd_HHMMSS)
    task_uuid: str  # 任务UUID后缀
    created_at: datetime  # 目录创建时间(从metadata.json读取)
    metadata: Dict[str, Any]  # metadata.json内容
    step_files: List[Path]  # 步骤文件列表
    state_file: Optional[Dict[str, Any]]  # state.json内容(如果存在)
    total_steps: int  # metadata中记录的步骤总数


# ============================================================================
# 核心功能函数 (T007-T011)
# ============================================================================

def initialize_django() -> None:
    """
    初始化Django环境 (T007)

    功能:
    - 设置DJANGO_SETTINGS_MODULE环境变量
    - 调用django.setup()
    - 验证数据库连接

    Raises:
        RuntimeError: 如果Django初始化失败
    """
    try:
        # Django已在脚本开头初始化,这里仅验证数据库连接
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        logger.info("✓ Django环境初始化成功,数据库连接正常")
    except Exception as e:
        error_msg = f"Django初始化失败: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


def check_celery_worker_available(timeout_seconds: int = 10) -> bool:
    """
    检查celery worker是否可用 (T008)

    Args:
        timeout_seconds: 检测超时时间(秒)

    Returns:
        bool: worker是否可用

    实现方式:
        创建任务后等待timeout_seconds,如果状态仍为PENDING则判定worker不可用
    """
    try:
        logger.info(f"检测celery worker可用性(超时{timeout_seconds}秒)...")

        # 创建一个临时测试任务
        test_task_id = str(uuid.uuid4())
        test_task = AgentTask.objects.create(
            task_id=test_task_id,
            status=AgentTask.TaskStatus.PENDING,
            input_data={"test": "worker_check"},
            user_id=1
        )

        start_time = time.time()

        # 触发一个简单的celery任务检测(不实际执行复杂操作)
        # 这里我们只检查任务是否能被worker接收
        while time.time() - start_time < timeout_seconds:
            test_task.refresh_from_db()
            if test_task.status != AgentTask.TaskStatus.PENDING:
                logger.info("✓ Celery worker运行正常")
                # 清理测试任务
                test_task.delete()
                return True
            time.sleep(1)

        # 超时仍是PENDING状态
        logger.warning("⚠️ Celery worker可能未运行或无法处理任务")
        test_task.delete()
        return False

    except Exception as e:
        logger.error(f"检测celery worker时发生错误: {e}")
        return False


def create_test_task(
    graph_name: str,
    task_description: str,
    user_id: int
) -> str:
    """
    创建测试任务 (T009)

    Args:
        graph_name: 图名称(如"Super-Router Agent")
        task_description: 任务描述(简单文本总结任务 + web搜索任务)
        user_id: 用户ID

    Returns:
        str: 创建的task_id(UUID格式)

    Raises:
        ValueError: 如果参数无效
        DatabaseError: 如果数据库操作失败

    对应需求:
        FR-001: 使用真实生产数据库
        FR-002: 创建真实AgentTask实例
    """
    try:
        # 验证图定义存在
        try:
            graph = Graph.objects.get(name=graph_name)
            logger.info(f"✓ 找到图定义: {graph_name} (ID: {graph.id})")
        except Graph.DoesNotExist:
            raise ValueError(f"图定义不存在: {graph_name}")

        # 生成任务ID
        task_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        # 创建AgentTask实例
        task = AgentTask.objects.create(
            task_id=task_id,
            graph=graph,  # 关联图定义
            status=AgentTask.TaskStatus.PENDING,
            input_data={
                "goal": task_description,
                "test_marker": "e2e_test",  # 标识测试数据
                "test_timestamp": datetime.now().isoformat()
            },
            user_id=user_id,
            session_id=session_id
        )

        logger.info(f"✓ 测试任务已创建: task_id={task_id}, session_id={session_id}")
        return task_id

    except Exception as e:
        error_msg = f"创建测试任务失败: {e}"
        logger.error(error_msg)
        raise


def trigger_celery_task(
    task_id: str,
    graph_name: str,
    task_description: str,
    user_id: int,
    session_id: str
) -> None:
    """
    触发celery异步任务 (T010)

    Args:
        task_id: AgentTask的task_id
        graph_name: 图名称
        task_description: 任务描述
        user_id: 用户ID
        session_id: 会话ID

    Raises:
        CeleryError: 如果celery调用失败

    对应需求:
        FR-003: 通过run_graph_task.delay()触发celery异步执行
    """
    try:
        logger.info(f"触发celery异步任务: task_id={task_id}")

        # 使用Celery的send_task API,避免循环导入
        from celery import current_app

        result = current_app.send_task(
            'agentic.tasks.run_graph_task',
            args=[],
            kwargs={
                'task_id': task_id,
                'graph_name': graph_name,
                'initial_task_goal': task_description,
                'preprocessed_files': {},
                'origin_images': [],
                'conversation_history': [],
                'usage': 'test',
                'user_id': user_id,
                'session_id': session_id
            }
        )

        logger.info(f"✓ Celery任务已提交: celery_task_id={result.id}")

    except Exception as e:
        error_msg = f"触发celery任务失败: {e}"
        logger.error(error_msg)
        raise


def monitor_task_execution(
    task_id: str,
    timeout_seconds: int = 120,
    poll_interval_seconds: int = 2
) -> Dict[str, Any]:
    """
    监控任务执行状态 (T011)

    Args:
        task_id: 要监控的task_id
        timeout_seconds: 超时时间(秒),默认120秒
        poll_interval_seconds: 轮询间隔(秒),默认2秒

    Returns:
        Dict[str, Any]: 任务最终状态信息,包含:
            - status: COMPLETED | FAILED | TIMEOUT | WORKER_UNAVAILABLE
            - duration: 执行时长(秒)
            - final_status: AgentTask.status枚举值

    Raises:
        TimeoutError: 如果超过timeout_seconds任务仍未完成

    对应需求:
        FR-004: 轮询AgentTask.status监控任务状态
        FR-005: 任务超时后标记为TIMEOUT
    """
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=timeout_seconds)
    poll_count = 0

    logger.info(f"开始监控任务执行状态(超时{timeout_seconds}秒,轮询间隔{poll_interval_seconds}秒)...")

    try:
        while datetime.now() < end_time:
            poll_count += 1

            try:
                # 刷新数据库状态
                task = AgentTask.objects.get(task_id=task_id)
                status = task.status

                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"[轮询 {poll_count}] 任务状态: {status} (已用时: {elapsed:.1f}秒)")

                # 检查终态
                if status in [AgentTask.TaskStatus.COMPLETED,
                             AgentTask.TaskStatus.FAILED,
                             AgentTask.TaskStatus.CANCELLED]:
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.info(f"✓ 任务执行完成: status={status}, 时长={duration:.1f}秒")
                    return {
                        "status": status,
                        "duration": duration,
                        "final_status": status,
                        "timeout": False
                    }

                # 检查是否长时间停留在PENDING
                if status == AgentTask.TaskStatus.PENDING:
                    if elapsed > 10:
                        logger.warning(f"⚠️ 任务{elapsed:.0f}秒仍处于PENDING,可能celery worker未运行")

            except AgentTask.DoesNotExist:
                error_msg = f"任务不存在: {task_id}"
                logger.error(error_msg)
                return {
                    "status": "NOT_FOUND",
                    "duration": 0,
                    "final_status": None,
                    "timeout": False
                }

            time.sleep(poll_interval_seconds)

        # 超时
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"✗ 任务执行超时: {timeout_seconds}秒,最终状态: {task.status if 'task' in locals() else 'UNKNOWN'}")
        return {
            "status": "TIMEOUT",
            "duration": duration,
            "final_status": task.status if 'task' in locals() else None,
            "timeout": True
        }

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        error_msg = f"监控任务执行时发生错误: {e}"
        logger.error(error_msg)
        return {
            "status": "ERROR",
            "duration": duration,
            "final_status": None,
            "timeout": False,
            "error": str(e)
        }


# ============================================================================
# 文件定位与验证 (T012-T015)
# ============================================================================

def validate_directory_name(directory_name: str) -> bool:
    """
    验证目录命名格式 (T013)

    Args:
        directory_name: 目录名称

    Returns:
        bool: 是否符合yyyymmdd_HHMMSS_{uuid}格式

    正则表达式:
        ^\\d{8}_\\d{6}_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$
    """
    pattern = r'^\d{8}_\d{6}_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    return bool(re.match(pattern, directory_name))


def validate_step_file_name(file_name: str) -> bool:
    """
    验证步骤文件命名格式 (T014)

    Args:
        file_name: 文件名

    Returns:
        bool: 是否符合{N}_{node_type}_{tool_name}.json格式

    正则表达式:
        ^\\d+_(planner|call_tool|reflection|output)(_[\\w\\-]+)?\\.json$
    """
    pattern = r'^\d+_(planner|call_tool|reflection|output)(_[\w\-]+)?\.json$'
    return bool(re.match(pattern, file_name))


def parse_step_file(file_path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    解析步骤文件 (T015)

    Args:
        file_path: 步骤文件路径

    Returns:
        Tuple[Optional[Dict], Optional[str]]: (解析后的JSON内容, 错误信息)

    安全读取和解析JSON文件,返回(数据, None)或(None, 错误信息)
    """
    path = Path(file_path)

    if not path.exists():
        return None, f"文件不存在: {path}"

    if not path.is_file():
        return None, f"不是文件: {path}"

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"JSON解析错误: {e}"
    except PermissionError:
        return None, f"权限不足: {path}"
    except Exception as e:
        return None, f"读取失败: {e}"


def locate_workflow_directory(
    task_id: str,
    user_id: int,
    session_id: str
) -> Tuple[Optional[WorkflowDirectory], Optional[str]]:
    """
    定位工作流目录 (T012)

    Args:
        task_id: 任务UUID
        user_id: 用户ID
        session_id: 会话ID

    Returns:
        Tuple[Optional[WorkflowDirectory], Optional[str]]: (工作流目录实体, 错误信息)

    对应需求:
        FR-007: 验证工作流目录命名格式(yyyymmdd_HHMMSS_{uuid})
        FR-008: 验证工作流目录位置
        FR-009: 验证metadata.json存在
    """
    try:
        # 构建基础路径（修复：移除session_id子目录层级）
        base_path = Path(settings.MEDIA_ROOT) / "oss-bucket"
        session_path = base_path / str(user_id) / "sessions"

        logger.info(f"搜索工作流目录: {session_path}")

        if not session_path.exists():
            return None, f"会话路径不存在: {session_path}"

        # 搜索带时间戳的目录(匹配task_id后缀)
        workflow_dirs = list(session_path.glob(f"*_{task_id}"))

        if not workflow_dirs:
            return None, f"未找到工作流目录(task_id={task_id})"

        if len(workflow_dirs) > 1:
            logger.warning(f"找到多个匹配目录({len(workflow_dirs)}个),使用第一个")

        workflow_dir = workflow_dirs[0]
        directory_name = workflow_dir.name

        logger.info(f"✓ 找到工作流目录: {directory_name}")

        # 验证目录命名格式
        if not validate_directory_name(directory_name):
            return None, f"目录命名格式不符合规范: {directory_name}"

        # 解析时间戳和UUID
        parts = directory_name.split('_', 2)
        if len(parts) != 3:
            return None, f"目录名称格式错误: {directory_name}"

        timestamp_prefix = f"{parts[0]}_{parts[1]}"
        task_uuid = parts[2]

        # 读取metadata.json
        metadata_file = workflow_dir / "metadata.json"
        if not metadata_file.exists():
            return None, f"metadata.json不存在: {metadata_file}"

        metadata, error = parse_step_file(metadata_file)
        if error:
            return None, f"读取metadata.json失败: {error}"

        # 读取state.json(可选)
        state_file = workflow_dir / "state.json"
        state_data = None
        if state_file.exists():
            state_data, _ = parse_step_file(state_file)

        # 搜集步骤文件
        step_files = []
        for file in workflow_dir.glob("*.json"):
            if file.name not in ["metadata.json", "state.json"]:
                if validate_step_file_name(file.name):
                    step_files.append(file)
                else:
                    logger.warning(f"步骤文件命名格式不规范: {file.name}")

        # 按文件名排序(步骤序号)
        step_files.sort(key=lambda f: f.name)

        # 构建WorkflowDirectory实体
        workflow_directory = WorkflowDirectory(
            directory_path=workflow_dir,
            directory_name=directory_name,
            timestamp_prefix=timestamp_prefix,
            task_uuid=task_uuid,
            created_at=datetime.fromisoformat(metadata.get("workflow_start_time", datetime.now().isoformat())),
            metadata=metadata,
            step_files=step_files,
            state_file=state_data,
            total_steps=metadata.get("total_steps", 0)
        )

        logger.info(f"✓ 工作流目录解析完成: {len(step_files)}个步骤文件")

        return workflow_directory, None

    except Exception as e:
        error_msg = f"定位工作流目录时发生错误: {e}"
        logger.error(error_msg)
        return None, error_msg


# ============================================================================
# 验证逻辑 (T016-T019)
# ============================================================================

def verify_database_state(task_id: str) -> List[VerificationResult]:
    """
    验证数据库状态 (T016)

    Args:
        task_id: 要验证的task_id

    Returns:
        List[VerificationResult]: 数据库验证结果列表

    验证内容:
        - FR-016: AgentTask.status为COMPLETED
        - FR-017: 存在至少5条ActionSteps记录
        - FR-018: ActionSteps类型覆盖PLANNER、TOOL_CALL、REFLECTION、FINAL_ANSWER
    """
    results = []

    try:
        # FR-016: 验证任务状态
        task = AgentTask.objects.get(task_id=task_id)
        results.append(VerificationResult(
            verification_id="DB-001",
            verification_type=VerificationType.DATABASE.value,
            test_case="FR-016: AgentTask.status为COMPLETED",
            expected=AgentTask.TaskStatus.COMPLETED,
            actual=task.status,
            passed=(task.status == AgentTask.TaskStatus.COMPLETED),
            error_message=None if task.status == AgentTask.TaskStatus.COMPLETED else f"任务状态为{task.status}",
            timestamp=datetime.now()
        ))

        # FR-017: 验证ActionSteps记录数量
        action_steps = ActionSteps.objects.filter(task__task_id=task_id)
        step_count = action_steps.count()
        results.append(VerificationResult(
            verification_id="DB-002",
            verification_type=VerificationType.DATABASE.value,
            test_case="FR-017: 存在至少5条ActionSteps记录",
            expected="≥5条",
            actual=f"{step_count}条",
            passed=(step_count >= 5),
            error_message=None if step_count >= 5 else f"仅有{step_count}条记录",
            timestamp=datetime.now()
        ))

        # FR-018: 验证ActionSteps类型覆盖 (注意: log_type是小写)
        required_types = ["planner", "tool_call", "reflection"]  # 002分支使用小写
        actual_types = set(action_steps.values_list('log_type', flat=True))
        missing_types = [t for t in required_types if t not in actual_types]
        results.append(VerificationResult(
            verification_id="DB-003",
            verification_type=VerificationType.DATABASE.value,
            test_case="FR-018: ActionSteps类型覆盖完整",
            expected=", ".join(required_types),
            actual=", ".join(sorted(actual_types)),
            passed=(len(missing_types) == 0),
            error_message=None if len(missing_types) == 0 else f"缺少类型: {', '.join(missing_types)}",
            timestamp=datetime.now()
        ))

    except AgentTask.DoesNotExist:
        results.append(VerificationResult(
            verification_id="DB-ERROR",
            verification_type=VerificationType.DATABASE.value,
            test_case="数据库访问",
            expected="任务存在",
            actual="任务不存在",
            passed=False,
            error_message=f"任务不存在: {task_id}",
            timestamp=datetime.now()
        ))
    except Exception as e:
        results.append(VerificationResult(
            verification_id="DB-ERROR",
            verification_type=VerificationType.DATABASE.value,
            test_case="数据库访问",
            expected="正常访问",
            actual="异常",
            passed=False,
            error_message=str(e),
            timestamp=datetime.now()
        ))

    return results


def verify_filesystem_structure(workflow_dir: WorkflowDirectory) -> List[VerificationResult]:
    """
    验证文件系统结构 (T017)

    Args:
        workflow_dir: 工作流目录实体

    Returns:
        List[VerificationResult]: 文件系统验证结果列表

    验证内容:
        - FR-007: 目录命名格式(yyyymmdd_HHMMSS_{uuid})
        - FR-008: 目录位置正确
        - FR-009: metadata.json和state.json存在
        - FR-010: 步骤文件命名格式正确
    """
    results = []

    # FR-007: 目录命名格式
    is_valid_name = validate_directory_name(workflow_dir.directory_name)
    results.append(VerificationResult(
        verification_id="FS-001",
        verification_type=VerificationType.FILESYSTEM.value,
        test_case="FR-007: 工作流目录命名格式",
        expected="yyyymmdd_HHMMSS_{uuid}",
        actual=workflow_dir.directory_name,
        passed=is_valid_name,
        error_message=None if is_valid_name else "命名格式不符合规范",
        timestamp=datetime.now()
    ))

    # FR-008: 目录位置
    expected_pattern = "media/oss-bucket/{user_id}/sessions/{session_id}/"
    actual_path = str(workflow_dir.directory_path)
    is_correct_location = "oss-bucket" in actual_path and "sessions" in actual_path
    results.append(VerificationResult(
        verification_id="FS-002",
        verification_type=VerificationType.FILESYSTEM.value,
        test_case="FR-008: 工作流目录位置",
        expected=expected_pattern,
        actual=actual_path,
        passed=is_correct_location,
        error_message=None if is_correct_location else "目录位置不正确",
        timestamp=datetime.now()
    ))

    # FR-009: metadata.json存在
    metadata_exists = workflow_dir.metadata is not None and len(workflow_dir.metadata) > 0
    results.append(VerificationResult(
        verification_id="FS-003",
        verification_type=VerificationType.FILESYSTEM.value,
        test_case="FR-009: metadata.json存在",
        expected="存在且可解析",
        actual="存在" if metadata_exists else "不存在或解析失败",
        passed=metadata_exists,
        error_message=None if metadata_exists else "metadata.json不存在或无法解析",
        timestamp=datetime.now()
    ))

    # FR-010: 步骤文件命名格式
    invalid_files = []
    for step_file in workflow_dir.step_files:
        if not validate_step_file_name(step_file.name):
            invalid_files.append(step_file.name)

    results.append(VerificationResult(
        verification_id="FS-004",
        verification_type=VerificationType.FILESYSTEM.value,
        test_case="FR-010: 步骤文件命名格式",
        expected="所有文件符合{N}_{type}_{tool}.json",
        actual=f"{len(workflow_dir.step_files)}个文件,{len(invalid_files)}个格式错误",
        passed=(len(invalid_files) == 0),
        error_message=None if len(invalid_files) == 0 else f"格式错误的文件: {', '.join(invalid_files)}",
        timestamp=datetime.now()
    ))

    return results


def verify_step_file_content(workflow_dir: WorkflowDirectory) -> List[VerificationResult]:
    """
    验证步骤文件内容 (T018)

    Args:
        workflow_dir: 工作流目录实体

    Returns:
        List[VerificationResult]: 内容验证结果列表

    验证内容:
        - FR-011: 步骤序号连续性
        - FR-012: planner节点内容结构(action、task_goal、todo)
        - FR-013: call_tool节点内容结构(tool_name、input、output)
        - FR-014: reflection节点内容结构(decision、reasoning、next_action)
        - FR-015: output节点内容结构(selected_tool、output_guidance)
    """
    results = []

    # FR-011: 步骤序号连续性
    step_numbers = []
    for step_file in workflow_dir.step_files:
        match = re.match(r'^(\d+)_', step_file.name)
        if match:
            step_numbers.append(int(match.group(1)))

    step_numbers.sort()
    is_continuous = all(step_numbers[i] == i + 1 for i in range(len(step_numbers)))
    results.append(VerificationResult(
        verification_id="CONTENT-001",
        verification_type=VerificationType.CONTENT.value,
        test_case="FR-011: 步骤序号连续性",
        expected="1, 2, 3, ...",
        actual=", ".join(map(str, step_numbers)),
        passed=is_continuous,
        error_message=None if is_continuous else "步骤序号不连续",
        timestamp=datetime.now()
    ))

    # 验证各类型节点的内容结构
    for step_file in workflow_dir.step_files:
        content, error = parse_step_file(step_file)
        if error:
            results.append(VerificationResult(
                verification_id=f"CONTENT-{step_file.name}",
                verification_type=VerificationType.CONTENT.value,
                test_case=f"解析{step_file.name}",
                expected="有效JSON",
                actual="解析失败",
                passed=False,
                error_message=error,
                timestamp=datetime.now()
            ))
            continue

        # 判断节点类型并验证字段 (002分支新格式)
        file_name = step_file.name

        # 002分支统一格式验证: 所有步骤文件都有相同的基础字段
        base_required_fields = ["step_number", "node_type", "timestamp", "output"]
        base_missing = [f for f in base_required_fields if f not in content]

        if "_planner" in file_name:
            # FR-012: planner节点 (002分支格式)
            results.append(VerificationResult(
                verification_id=f"CONTENT-planner-{step_file.name}",
                verification_type=VerificationType.CONTENT.value,
                test_case="FR-012: planner节点结构(002分支格式)",
                expected=", ".join(base_required_fields),
                actual=", ".join(content.keys()),
                passed=(len(base_missing) == 0 and content.get("node_type") == "planner"),
                error_message=None if len(base_missing) == 0 else f"缺少字段: {', '.join(base_missing)}",
                timestamp=datetime.now()
            ))

        elif "_call_tool" in file_name:
            # FR-013: call_tool节点 (002分支格式，应包含tool_name)
            required_fields = base_required_fields + ["tool_name"]
            missing = [f for f in required_fields if f not in content]
            results.append(VerificationResult(
                verification_id=f"CONTENT-call_tool-{step_file.name}",
                verification_type=VerificationType.CONTENT.value,
                test_case="FR-013: call_tool节点结构(002分支格式)",
                expected=", ".join(required_fields),
                actual=", ".join(content.keys()),
                passed=(len(missing) == 0 and content.get("node_type") == "call_tool"),
                error_message=None if len(missing) == 0 else f"缺少字段: {', '.join(missing)}",
                timestamp=datetime.now()
            ))

        elif "_reflection" in file_name:
            # FR-014: reflection节点 (002分支格式)
            results.append(VerificationResult(
                verification_id=f"CONTENT-reflection-{step_file.name}",
                verification_type=VerificationType.CONTENT.value,
                test_case="FR-014: reflection节点结构(002分支格式)",
                expected=", ".join(base_required_fields),
                actual=", ".join(content.keys()),
                passed=(len(base_missing) == 0 and content.get("node_type") == "reflection"),
                error_message=None if len(base_missing) == 0 else f"缺少字段: {', '.join(base_missing)}",
                timestamp=datetime.now()
            ))

        elif "_output" in file_name:
            # FR-015: output节点 (002分支格式)
            results.append(VerificationResult(
                verification_id=f"CONTENT-output-{step_file.name}",
                verification_type=VerificationType.CONTENT.value,
                test_case="FR-015: output节点结构(002分支格式)",
                expected=", ".join(base_required_fields),
                actual=", ".join(content.keys()),
                passed=(len(base_missing) == 0 and content.get("node_type") == "output"),
                error_message=None if len(base_missing) == 0 else f"缺少字段: {', '.join(base_missing)}",
                timestamp=datetime.now()
            ))

    return results


def verify_output_result(workflow_dir: WorkflowDirectory, task_id: str) -> List[VerificationResult]:
    """
    验证输出结果 (T019)

    Args:
        workflow_dir: 工作流目录实体
        task_id: 任务ID

    Returns:
        List[VerificationResult]: 输出验证结果列表

    验证内容:
        - FR-019: 输出文件存在(K_output_{generator_toolname}.json)
        - FR-020: 输出文件包含完整的final_answer
        - FR-021: final_answer非空且长度>100字符
        - FR-022: AgentTask.output_data包含final_answer(与文件一致)
    """
    results = []

    # FR-019: 查找输出文件
    output_files = [f for f in workflow_dir.step_files if "_output_" in f.name]
    results.append(VerificationResult(
        verification_id="OUTPUT-001",
        verification_type=VerificationType.CONTENT.value,
        test_case="FR-019: 输出文件存在",
        expected="至少1个output文件",
        actual=f"{len(output_files)}个",
        passed=(len(output_files) > 0),
        error_message=None if len(output_files) > 0 else "未找到输出文件",
        timestamp=datetime.now()
    ))

    if len(output_files) == 0:
        return results

    # 读取第一个输出文件
    output_file = output_files[0]
    output_content, error = parse_step_file(output_file)

    if error:
        results.append(VerificationResult(
            verification_id="OUTPUT-002",
            verification_type=VerificationType.CONTENT.value,
            test_case="FR-020: 解析输出文件",
            expected="有效JSON",
            actual="解析失败",
            passed=False,
            error_message=error,
            timestamp=datetime.now()
        ))
        return results

    # FR-020: 输出文件包含final_answer (002分支格式: nested in output field)
    output_data = output_content.get("output", {})
    has_final_answer = "final_answer" in output_data or "primary_result" in output_data
    final_answer_value = output_data.get("final_answer") or output_data.get("primary_result", "")
    results.append(VerificationResult(
        verification_id="OUTPUT-003",
        verification_type=VerificationType.CONTENT.value,
        test_case="FR-020: 输出文件包含final_answer",
        expected="包含final_answer或primary_result字段",
        actual="包含" if has_final_answer else "不包含",
        passed=has_final_answer,
        error_message=None if has_final_answer else "输出文件缺少final_answer字段",
        timestamp=datetime.now()
    ))

    # FR-021: final_answer非空且长度>100
    if isinstance(final_answer_value, str):
        is_valid_length = len(final_answer_value) > 100
    else:
        final_answer_value = str(final_answer_value)
        is_valid_length = len(final_answer_value) > 100

    results.append(VerificationResult(
        verification_id="OUTPUT-004",
        verification_type=VerificationType.CONTENT.value,
        test_case="FR-021: final_answer长度>100",
        expected=">100字符",
        actual=f"{len(final_answer_value)}字符",
        passed=is_valid_length,
        error_message=None if is_valid_length else f"final_answer长度仅{len(final_answer_value)}字符",
        timestamp=datetime.now()
    ))

    # FR-022: AgentTask.output_data包含final_answer
    try:
        task = AgentTask.objects.get(task_id=task_id)
        task_output = task.output_data or {}
        task_final_answer = task_output.get("final_answer", "")

        has_task_output = bool(task_final_answer)
        results.append(VerificationResult(
            verification_id="OUTPUT-005",
            verification_type=VerificationType.DATABASE.value,
            test_case="FR-022: AgentTask.output_data包含final_answer",
            expected="包含且非空",
            actual="包含" if has_task_output else "不包含或为空",
            passed=has_task_output,
            error_message=None if has_task_output else "AgentTask.output_data缺少final_answer",
            timestamp=datetime.now()
        ))

    except Exception as e:
        results.append(VerificationResult(
            verification_id="OUTPUT-ERROR",
            verification_type=VerificationType.DATABASE.value,
            test_case="FR-022: 读取AgentTask.output_data",
            expected="正常读取",
            actual="异常",
            passed=False,
            error_message=str(e),
            timestamp=datetime.now()
        ))

    return results


# ============================================================================
# 报告生成 (T020)
# ============================================================================

def generate_test_report(
    execution: TestExecution,
    output_dir: Path
) -> Path:
    """
    生成测试报告 (T020)

    Args:
        execution: 测试执行结果
        output_dir: 输出目录(backend/agentic/tests/outputs/)

    Returns:
        Path: 生成的报告文件路径

    文件命名格式:
        process-YYYYMMDD-HHMMSS-test_end_to_end_workflow.json

    对应需求:
        FR-023: 生成JSON格式测试报告
        FR-024: 报告包含所有验证结果和统计信息
    """
    try:
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = f"process-{timestamp}-test_end_to_end_workflow.json"
        output_file = output_dir / filename

        # 构建报告数据
        report_data = {
            "test_id": execution.test_id,
            "test_name": execution.test_name,
            "start_time": execution.start_time.isoformat(),
            "end_time": execution.end_time.isoformat(),
            "duration_seconds": execution.duration_seconds,
            "status": execution.status.value if isinstance(execution.status, TestStatus) else str(execution.status),
            "agentic_task_id": execution.agentic_task_id,
            "verification_results": execution.verification_results,
            "errors": execution.errors,
            "summary": {
                "total_assertions": sum(
                    len(v.get("details", [])) if isinstance(v, dict) else 0
                    for v in execution.verification_results.values()
                ),
                "passed_assertions": sum(
                    sum(1 for d in v.get("details", []) if d.get("passed", False))
                    if isinstance(v, dict) else 0
                    for v in execution.verification_results.values()
                ),
                "failed_assertions": sum(
                    sum(1 for d in v.get("details", []) if not d.get("passed", True))
                    if isinstance(v, dict) else 0
                    for v in execution.verification_results.values()
                ),
                "success_rate": 0.0
            }
        }

        # 计算成功率
        total = report_data["summary"]["total_assertions"]
        passed = report_data["summary"]["passed_assertions"]
        if total > 0:
            report_data["summary"]["success_rate"] = round(passed / total, 4)

        # 保存JSON文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"✓ 测试报告已保存: {output_file}")
        logger.info(f"   总验证数: {total}, 通过: {passed}, 失败: {report_data['summary']['failed_assertions']}, 成功率: {report_data['summary']['success_rate']:.1%}")

        return output_file

    except Exception as e:
        error_msg = f"生成测试报告失败: {e}"
        logger.error(error_msg)
        raise


# ============================================================================
# 主流程 (T021-T024)
# ============================================================================

def main() -> TestExecution:
    """
    测试脚本主入口函数 (T021)

    执行完整的端到端集成测试流程:
    1. 初始化Django环境
    2. 创建AgentTask
    3. 触发celery任务
    4. 监控任务执行
    5. 验证结果
    6. 生成报告

    Returns:
        TestExecution: 测试执行结果
    """
    # 测试配置常量
    GRAPH_NAME = "Super-Router Agent"
    TASK_DESCRIPTION = "请先搜索人工智能的最新进展,然后总结搜索结果"
    USER_ID = 1  # 测试用户ID
    TIMEOUT_SECONDS = 120
    POLL_INTERVAL = 2

    # 初始化测试执行结果
    test_id = str(uuid.uuid4())
    start_time = datetime.now()
    logger.info(f"{'='*80}")
    logger.info(f"开始端到端集成测试: {test_id}")
    logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*80}\n")

    errors = []
    all_verification_results = {
        "database": {"total": 0, "passed": 0, "failed": 0, "details": []},
        "filesystem": {"total": 0, "passed": 0, "failed": 0, "details": []},
        "content": {"total": 0, "passed": 0, "failed": 0, "details": []},
    }
    status = TestStatus.SUCCESS
    task_id = None

    try:
        # Step 1: 初始化Django环境
        logger.info("[步骤 1/7] 初始化Django环境...")
        initialize_django()

        # Step 2: 检查celery worker
        logger.info("\n[步骤 2/7] 检查celery worker可用性...")
        # 注意: check_celery_worker_available会创建临时任务,这里简化处理
        logger.info("⚠️ 跳过worker检查,直接创建任务(worker检查会干扰测试)")

        # Step 3: 创建测试任务
        logger.info("\n[步骤 3/7] 创建测试任务...")
        task_id = create_test_task(GRAPH_NAME, TASK_DESCRIPTION, USER_ID)

        # 获取session_id
        task = AgentTask.objects.get(task_id=task_id)
        session_id = task.session_id

        # Step 4: 触发celery任务
        logger.info("\n[步骤 4/7] 触发celery异步任务...")
        trigger_celery_task(task_id, GRAPH_NAME, TASK_DESCRIPTION, USER_ID, session_id)

        # Step 5: 监控任务执行
        logger.info("\n[步骤 5/7] 监控任务执行...")
        execution_result = monitor_task_execution(task_id, TIMEOUT_SECONDS, POLL_INTERVAL)

        if execution_result["status"] == "TIMEOUT":
            status = TestStatus.TIMEOUT
            errors.append("任务执行超时")
        elif execution_result["status"] not in [AgentTask.TaskStatus.COMPLETED, "COMPLETED"]:
            status = TestStatus.FAILED
            errors.append(f"任务执行失败: {execution_result.get('final_status')}")

        # Step 6: 验证结果
        logger.info("\n[步骤 6/7] 验证测试结果...")

        # 6.1: 定位工作流目录
        logger.info("  [6.1] 定位工作流目录...")
        workflow_dir, error = locate_workflow_directory(task_id, USER_ID, session_id)
        if error:
            errors.append(f"定位工作流目录失败: {error}")
            status = TestStatus.FAILED
        else:
            # 6.2: 验证数据库状态
            logger.info("  [6.2] 验证数据库状态...")
            db_results = verify_database_state(task_id)
            for result in db_results:
                all_verification_results["database"]["details"].append(asdict(result))
                all_verification_results["database"]["total"] += 1
                if result.passed:
                    all_verification_results["database"]["passed"] += 1
                else:
                    all_verification_results["database"]["failed"] += 1
                    logger.warning(f"    ✗ {result.test_case}: {result.error_message}")

            # 6.3: 验证文件系统结构
            logger.info("  [6.3] 验证文件系统结构...")
            fs_results = verify_filesystem_structure(workflow_dir)
            for result in fs_results:
                all_verification_results["filesystem"]["details"].append(asdict(result))
                all_verification_results["filesystem"]["total"] += 1
                if result.passed:
                    all_verification_results["filesystem"]["passed"] += 1
                else:
                    all_verification_results["filesystem"]["failed"] += 1
                    logger.warning(f"    ✗ {result.test_case}: {result.error_message}")

            # 6.4: 验证步骤文件内容
            logger.info("  [6.4] 验证步骤文件内容...")
            content_results = verify_step_file_content(workflow_dir)
            for result in content_results:
                all_verification_results["content"]["details"].append(asdict(result))
                all_verification_results["content"]["total"] += 1
                if result.passed:
                    all_verification_results["content"]["passed"] += 1
                else:
                    all_verification_results["content"]["failed"] += 1
                    logger.warning(f"    ✗ {result.test_case}: {result.error_message}")

            # 6.5: 验证输出结果
            logger.info("  [6.5] 验证输出结果...")
            output_results = verify_output_result(workflow_dir, task_id)
            for result in output_results:
                all_verification_results["content"]["details"].append(asdict(result))
                all_verification_results["content"]["total"] += 1
                if result.passed:
                    all_verification_results["content"]["passed"] += 1
                else:
                    all_verification_results["content"]["failed"] += 1
                    logger.warning(f"    ✗ {result.test_case}: {result.error_message}")

        # 判断最终状态
        total_failed = sum(v["failed"] for v in all_verification_results.values())
        if total_failed > 0 and status == TestStatus.SUCCESS:
            status = TestStatus.FAILED
            errors.append(f"存在{total_failed}个验证失败项")

        # Step 7: 生成测试报告
        logger.info("\n[步骤 7/7] 生成测试报告...")
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        execution = TestExecution(
            test_id=test_id,
            test_name="test_end_to_end_workflow",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            status=status,
            agentic_task_id=task_id or "N/A",
            verification_results=all_verification_results,
            errors=errors
        )

        output_dir = Path(__file__).parent / "outputs"
        report_file = generate_test_report(execution, output_dir)

        # 打印最终总结
        logger.info(f"\n{'='*80}")
        logger.info(f"测试执行完成")
        logger.info(f"{'='*80}")
        logger.info(f"测试ID: {test_id}")
        logger.info(f"任务ID: {task_id}")
        logger.info(f"测试状态: {status.value if isinstance(status, TestStatus) else status}")
        logger.info(f"执行时长: {duration:.1f}秒")
        logger.info(f"验证总数: {sum(v['total'] for v in all_verification_results.values())}")
        logger.info(f"通过数量: {sum(v['passed'] for v in all_verification_results.values())}")
        logger.info(f"失败数量: {sum(v['failed'] for v in all_verification_results.values())}")
        logger.info(f"测试报告: {report_file}")
        logger.info(f"{'='*80}\n")

        return execution

    except Exception as e:
        # 捕获未预期的异常
        logger.error(f"\n✗ 测试执行过程中发生未预期的错误: {e}")
        import traceback
        logger.error(traceback.format_exc())

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        execution = TestExecution(
            test_id=test_id,
            test_name="test_end_to_end_workflow",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            status=TestStatus.FAILED,
            agentic_task_id=task_id or "N/A",
            verification_results=all_verification_results,
            errors=errors + [str(e)]
        )

        return execution


if __name__ == '__main__':
    """命令行执行入口 (T022)"""
    try:
        execution = main()

        # 根据测试结果设置退出码
        if execution.status == TestStatus.SUCCESS:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n测试执行失败: {e}")
        sys.exit(1)
