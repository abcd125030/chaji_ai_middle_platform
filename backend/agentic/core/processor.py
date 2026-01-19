# -*- coding: utf-8 -*-
# backend/agentic/core/processor.py

"""
Agent 图的执行器模块 (GraphExecutor)

该模块是 AI Agent 系统的核心执行引擎，负责加载、管理和执行基于图结构的 Agent 工作流。
它实现了一个状态机模式，通过节点间的有向边来控制执行流程，支持动态工具调用、
状态持久化、错误恢复和任务生命周期管理。

=== 核心功能 ===
1. 图结构解析与执行：加载图定义，解析节点和边的关系
2. 状态管理：维护运行时状态，支持检查点保存与恢复
3. 工具编排：动态加载和执行工具，处理工具调用链
4. 流程控制：根据节点输出和边条件决定执行路径
5. 任务生命周期：管理任务状态（运行中、完成、失败）
6. 日志记录：记录详细的执行步骤和操作历史
7. 输出工具重试机制：支持指数退避重试和备选工具切换（P0修复）
8. 错误恢复：自动分类错误类型并采取恢复措施（P0修复）

=== 输入参数 ===
- task_id: 任务唯一标识符
- graph_name: 要执行的图定义名称  
- initial_task_goal: 初始任务目标描述
- preprocessed_files: 预处理的文件数据字典
- origin_images: 原始图片文件路径列表
- conversation_history: 对话历史记录
- usage: 任务使用场景标识
- user_id: 用户ID
- session_id: 会话ID

=== 输出结果 ===
- RuntimeState: 包含任务最终状态的运行时对象
  - task_goal: 任务目标
  - action_history: 执行历史记录
  - tool_outputs: 工具执行结果
  - final_answer: 最终答案（如果任务完成）
  - todo: 待办任务列表
  - preprocessed_files: 处理过的文件数据

=== 内部处理流程 ===
1. 初始化阶段：
   - 加载或创建 AgentTask 实例
   - 从检查点恢复状态或创建新状态
   - 加载图定义和节点映射
   - 构建边关系映射

2. 执行循环：
   - 从 "planner" 节点开始执行
   - 根据节点类型调用相应处理逻辑
   - 动态确定下一个执行节点
   - 保存检查点和执行日志
   - 直到到达 "END" 节点

3. 节点处理逻辑：
   - planner: 分析任务，制定执行计划
   - tool: 执行具体工具调用
   - reflection: 反思执行结果，决定后续行动
   - output: 选择输出格式工具，生成最终结果
   - 自定义节点: 通过 python_callable 动态加载执行

4. 状态持久化：
   - 每步执行后保存检查点
   - 记录详细的 ActionSteps 日志
   - 更新任务状态到数据库

=== 主要函数调用关系 ===
GraphExecutor.__init__()
├── checkpoint.load() - 加载检查点状态
├── _load_session_states() - 加载会话历史
├── _create_state_with_history() / create_initial_state() - 创建运行时状态
└── Graph.objects.get() - 加载图定义

GraphExecutor.run()
├── ensure_db_connection_safe() - 确保数据库连接
└── while current_node_name != "END":
    ├── _load_callable() - 动态加载节点函数
    ├── node_function() - 执行节点逻辑
    │   ├── planner_chain() - 规划节点
    │   ├── _tool_executor_node() - 工具节点
    │   ├── reflection_node() - 反思节点
    │   └── output_node() - 输出节点
    ├── checkpoint.save() - 保存检查点
    ├── ActionSteps.objects.create() - 记录执行日志
    └── _find_next_node_name() - 确定下一节点

=== 外部函数依赖 ===
1. 数据库模型依赖：
   - Graph, Node, Edge: 图结构定义模型
   - AgentTask: 任务实例模型
   - ActionSteps: 执行步骤日志模型

2. 核心组件依赖：
   - DBCheckpoint: 检查点管理器
   - RuntimeState: 运行时状态模式
   - PlannerOutput: 规划器输出模式
   - ToolRegistry: 工具注册表

3. 工具系统依赖：
   - tools.libs: 工具库包
   - load_callable(): 动态加载Python可调用对象
   - execute_tool(): 执行工具调用
   - serialize_output(): 序列化输出结果

4. 节点函数依赖：
   - planner_chain(): 规划链节点
   - reflection_node(): 反思节点
   - output_node(): 输出选择节点
   - 各种工具节点: 通过ToolRegistry动态加载

5. 数据库与事务：
   - Django ORM: 数据持久化
   - transaction.atomic(): 事务管理
   - ensure_db_connection_safe(): 数据库连接管理

6. 日志与监控：
   - logging.getLogger(): Python日志系统
   - ActionSteps日志类型: PLANNER, TOOL_CALL, TOOL_RESULT, REFLECTION, FINAL_ANSWER

=== 错误处理机制 ===
- 节点执行失败时更新任务状态为 FAILED
- 使用数据库事务确保操作原子性
- 检查点机制支持任务中断后恢复
- 详细的异常日志记录便于调试

=== 性能优化 ===
- 使用 select_related 和 prefetch_related 减少数据库查询
- 构建节点和边的内存映射加速查找
- 检查点增量保存减少存储开销
"""

import sys
import json
import os
import inspect
import re
import portalocker
import tempfile
from typing import Dict, Any, Callable, Optional, List
from pathlib import Path
from datetime import datetime

from django.db import transaction, models  # 用于数据库事务管理，确保操作的原子性
from django.conf import settings
from backend.utils.db_connection import ensure_db_connection_safe
from django.contrib.auth import get_user_model  # 导入 get_user_model 函数，用于获取正确的用户模型
from pydantic import BaseModel  # 用于数据模型定义和验证

from ..models import Graph, Node, Edge, AgentTask, ActionSteps  # 导入 Django 模型，用于与数据库交互
from .checkpoint import DBCheckpoint  # 导入检查点机制，用于保存和恢复 Agent 状态
from .schemas import RuntimeState, PlannerOutput  # 导入 Agent 运行时状态和输出的 Pydantic 模式
from tools.core.registry import ToolRegistry  # 导入工具注册表，用于查找和实例化工具
# 任务分类器已移动到 planner_chain 内部作为第一个运行点

import tools.libs  # 显式导入 tools.libs 包，确保工具被注册
# tools.outputs 已经移除，输出工具现在在 tools.libs.generator 中

# 导入新的组件工具 - 延迟部分导入以避免循环导入
from ..utils import (
    serialize_output,
    get_tool_config,
    load_session_states,
    create_state_with_history,
    create_initial_state,
    load_callable,
    find_next_node_name
)
from ..utils.logger_config import log_state_change

import logging
logger = logging.getLogger("django")

class GraphExecutor:
    """
    Agent 图的执行器。负责加载图定义、管理运行时状态、
    循环执行节点并进行持久化。
    """
    def __init__(
        self,
        task_id: str,
        graph_name: Optional[str] = None,
        initial_task_goal: Optional[str] = None,
        preprocessed_files: Optional[Dict[str, Any]] = None,
        origin_images: Optional[List[str]] = None,
        conversation_history: Optional[List[Dict]] = None,
        usage: Optional[str] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ):
        """
        初始化 GraphExecutor 实例。

        参数:
        task_id (str): 任务的唯一标识符。
        graph_name (Optional[str]): 要执行的图的名称。
        initial_task_goal (Optional[str]): 新任务的初始目标。对于恢复任务，此参数可以为 None。
        preprocessed_files (Optional[Dict[str, Any]]): 预处理过的文件数据，例如用户上传的文档内容。
        conversation_history (Optional[List[Dict]]): 对话历史.
        usage (Optional[str]): 任务的使用情况或上下文信息。
        user_id (Optional[int]): 创建任务的用户ID。
        session_id (Optional[str]): 会话ID.
        """
        self.task_id = str(task_id)
        self.user_id = user_id  # 保存用户ID
        self.checkpoint = DBCheckpoint()  # 初始化检查点对象，用于状态的保存和加载

        # 加载任务，任务应已由 Service 层创建
        # 使用 select_related 预加载关联的 graph 和 user，避免后续的延迟加载
        try:
            self.agent_task = AgentTask.objects.select_related('graph', 'user').get(task_id=self.task_id)
        except AgentTask.DoesNotExist:
            raise ValueError(f"Task with id {self.task_id} not found.")

        self.graph_name = self.agent_task.graph.name  # 从 AgentTask 获取图的名称

        # 加载或初始化 RuntimeState (运行时状态)
        loaded_state = self.checkpoint.load(self.task_id)  # 尝试从检查点加载状态
        if loaded_state:
            # 如果加载了旧状态，需要检查是否是新任务
            if initial_task_goal:
                # 有新的task_goal，说明这是同一session下的新任务
                # 应该将loaded_state作为历史状态，用create_state_with_history创建新状态
                # 基于历史状态创建新任务日志将在后续添加
                
                # 将loaded_state作为历史状态
                historical_states = [loaded_state]
                
                # 尝试加载其他历史任务的状态
                additional_states = self._load_session_states()
                if additional_states:
                    # 合并历史状态（去重）
                    historical_states.extend(additional_states)
                
                # 使用现有的方法基于历史创建新状态
                self.state = self._create_state_with_history(
                    historical_states,
                    initial_task_goal,
                    preprocessed_files,
                    origin_images,
                    conversation_history,
                    usage
                )
            else:
                # 没有新的task_goal，说明是恢复中断的任务
                self.state = loaded_state
                # 恢复中断任务日志将在后续添加
        else:
            # 如果是新任务且没有提供初始目标，则抛出错误
            if not initial_task_goal:
                raise ValueError("initial_task_goal must be provided for new tasks.")
            
            # 尝试加载session历史状态
            historical_states = self._load_session_states()
            
            if historical_states:
                # 基于历史状态创建新状态
                self.state = self._create_state_with_history(
                    historical_states, 
                    initial_task_goal, 
                    preprocessed_files,
                    origin_images,
                    conversation_history,
                    usage
                )
            else:
                # 完全新建state（首次对话）
                self.state = create_initial_state(
                    initial_task_goal=initial_task_goal,
                    preprocessed_files=preprocessed_files,
                    origin_images=origin_images,
                    conversation_history=conversation_history,
                    usage=usage,
                    user_id=self.user_id
                )

        # 启动时，将任务状态更新为 RUNNING (运行中)
        if self.agent_task.status != AgentTask.TaskStatus.RUNNING:
            self.agent_task.status = AgentTask.TaskStatus.RUNNING
            self.agent_task.save(update_fields=['status', 'updated_at']) # 保存状态更新到数据库

        # 加载图定义
        # 注意：这里使用传入的 graph_name，而不是 self.agent_task.graph.name
        # 这允许在初始化时指定一个不同的图定义，尽管通常它们会一致。
        # 使用 prefetch_related 预加载关联的 nodes 和 edges
        self.graph_def = Graph.objects.prefetch_related(
            'nodes',
            'edges__source',
            'edges__target'
        ).get(name=graph_name if graph_name else self.graph_name)

        # 构建节点名称到节点对象的映射，方便通过名称查找节点
        self.nodes_map = {
            node.name: node for node in self.graph_def.nodes.all()
        }

        # 初始化边的映射，键为源节点名称，值为一个列表，用于存储从该源节点发出的所有边
        # 使用 select_related 预加载 source 和 target 节点，避免后续的延迟加载
        all_edges = list(self.graph_def.edges.select_related('source', 'target').all())
        
        self.edges_map = {}
        for edge in all_edges:
            if edge.source.name not in self.edges_map:
                self.edges_map[edge.source.name] = []
            self.edges_map[edge.source.name].append(edge)

        # === 002分支集成：初始化工作流目录相关属性 ===
        self.base_path = Path(settings.MEDIA_ROOT) / "oss-bucket"
        self.step_counter = 0  # 步骤计数器

        # 创建带时间戳的工作流目录
        # 使用user.id而不是user_ai_id（User模型没有user_ai_id字段）
        user_uuid = str(self.agent_task.user.id) if self.agent_task.user else "anonymous"
        session_uuid = str(self.agent_task.session_id) if self.agent_task.session_id else self.task_id

        self.workflow_dir = self.create_workflow_directory(
            task_id=self.task_id,
            user_uuid=user_uuid,
            session_uuid=session_uuid
        )
        logger.info(f"[GRAPHEXECUTOR] 工作流目录已创建: {self.workflow_dir}")

    def _load_callable(self, callable_path: str) -> Callable:
        """
        动态加载 Python 可调用对象（函数或类）。
        使用组件工具中的 load_callable 函数。
        """
        return load_callable(callable_path)

    def _load_session_states(self) -> List[RuntimeState]:
        """
        加载session中所有历史任务的states。
        使用组件工具中的 load_session_states 函数。
        """
        return load_session_states(self.agent_task, self.checkpoint)

    def _create_state_with_history(self, historical_states: List[RuntimeState], new_goal: str, preprocessed_files: dict, origin_images: List[str], conversation_history: List[Dict], usage: str) -> RuntimeState:
        """
        基于历史状态创建新的RuntimeState。
        使用组件工具中的 create_state_with_history 函数。
        """
        return create_state_with_history(
            historical_states=historical_states,
            new_goal=new_goal,
            preprocessed_files=preprocessed_files,
            origin_images=origin_images,
            conversation_history=conversation_history,
            usage=usage,
            user_id=self.user_id
        )

    def _serialize_output(self, data: Any) -> Any:
        """
        递归地序列化 Pydantic 模型和具有 `to_dict` 方法的对象。
        使用组件工具中的 serialize_output 函数。
        """
        return serialize_output(data)

    # === 002分支集成：工作流目录和步骤文件保存方法 ===

    def _get_session_path(self, user_uuid: str, session_uuid: str) -> Path:
        """获取session的存储路径（不包含session_uuid子目录）"""
        return self.base_path / user_uuid / "sessions"

    def _ensure_directory(self, path: Path) -> None:
        """确保目录存在"""
        path.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, file_path: Path, data: dict) -> bool:
        """原子性写入文件，防止写入中断导致文件损坏"""
        try:
            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(
                dir=file_path.parent,
                prefix=".tmp_",
                suffix=".json"
            )

            try:
                # 写入数据到临时文件
                with os.fdopen(temp_fd, 'w') as f:
                    # 获取文件锁，防止并发写入
                    portalocker.lock(f, portalocker.LockFlags.EXCLUSIVE)
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    portalocker.unlock(f)

                # 原子性重命名（POSIX保证rename是原子操作）
                os.replace(temp_path, file_path)
                return True

            except Exception as e:
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e

        except Exception as e:
            logger.error(f"[GRAPHEXECUTOR] 原子写入失败 {file_path}: {e}")
            return False

    def _sanitize_tool_name(self, tool_name: str, max_length: int = 50) -> str:
        """
        规范化工具名称用于文件命名。

        参数:
            tool_name (str): 原始工具名称
            max_length (int): 最大长度限制，默认50字符

        返回:
            str: 规范化后的工具名称
        """
        # 替换特殊字符为下划线
        sanitized = re.sub(r'[^\w\-]', '_', tool_name)
        # 移除连续下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        # 限制长度
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized

    def _update_metadata(self, workflow_dir: Path, node_type: str) -> bool:
        """
        更新 metadata.json 中的统计信息。

        参数:
            workflow_dir (Path): 工作流目录路径
            node_type (str): 当前执行的节点类型

        返回:
            bool: 更新成功返回 True，失败返回 False
        """
        try:
            metadata_path = workflow_dir / "metadata.json"

            # 读取现有 metadata
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    portalocker.lock(f, portalocker.LockFlags.SHARED)
                    metadata = json.load(f)
                    portalocker.unlock(f)
            else:
                logger.warning(f"[GRAPHEXECUTOR] metadata.json 不存在: {metadata_path}")
                return False

            # 更新统计信息
            metadata["total_steps"] = metadata.get("total_steps", 0) + 1
            metadata["last_update_time"] = datetime.now().isoformat()

            # 更新已执行的节点类型列表
            if "node_types_executed" not in metadata:
                metadata["node_types_executed"] = []
            if node_type not in metadata["node_types_executed"]:
                metadata["node_types_executed"].append(node_type)

            # 原子写入更新后的 metadata
            if self._atomic_write(metadata_path, metadata):
                logger.debug(f"[GRAPHEXECUTOR] 更新 metadata: total_steps={metadata['total_steps']}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"[GRAPHEXECUTOR] 更新 metadata 失败: {e}")
            return False

    def create_workflow_directory(
        self,
        task_id: str,
        user_uuid: str,
        session_uuid: str
    ) -> Path:
        """
        创建带时间戳的工作流目录。

        功能描述:
        - 生成格式为 `yyyymmdd_HHMMSS_{task_uuid}` 的目录名
        - 在 session 路径下创建该目录
        - 初始化 metadata.json 文件
        - 返回创建的目录路径

        参数:
            task_id (str): 任务唯一标识,用于生成目录名和记录元数据
            user_uuid (str): 用户UUID,用于构建存储路径
            session_uuid (str): 会话UUID,用于构建存储路径

        返回:
            Path: 创建的工作流目录路径对象

        异常:
            OSError: 如果目录创建失败(权限不足、磁盘空间不足等)
            ValueError: 如果参数不合法(UUID格式错误等)
        """
        try:
            # 生成时间戳前缀
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 构建目录名: yyyymmdd_HHMMSS_{task_uuid}
            dirname = f"{timestamp}_{task_id}"

            # 获取session路径
            session_path = self._get_session_path(user_uuid, session_uuid)

            # 确保session目录存在
            self._ensure_directory(session_path)

            # 构建完整的工作流目录路径
            workflow_dir = session_path / dirname

            # 检查目录是否已存在（理论上不应该，但作为防御性编程）
            if workflow_dir.exists():
                logger.warning(f"[GRAPHEXECUTOR] 工作流目录已存在: {workflow_dir}")
                return workflow_dir

            # 创建工作流目录
            workflow_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[GRAPHEXECUTOR] 创建工作流目录: {workflow_dir}")

            # 初始化 metadata.json
            metadata = {
                "task_id": task_id,
                "session_id": session_uuid,
                "user_id": user_uuid,
                "workflow_start_time": datetime.now().isoformat(),
                "workflow_start_timestamp": datetime.now().timestamp(),
                "last_update_time": datetime.now().isoformat(),
                "total_steps": 0,
                "node_types_executed": [],
                "workflow_status": "running"
            }

            metadata_path = workflow_dir / "metadata.json"
            if self._atomic_write(metadata_path, metadata):
                logger.info(f"[GRAPHEXECUTOR] 初始化 metadata.json: {metadata_path}")
            else:
                logger.warning(f"[GRAPHEXECUTOR] metadata.json 初始化失败，但目录已创建")

            return workflow_dir

        except Exception as e:
            logger.error(f"[GRAPHEXECUTOR] 创建工作流目录失败 - task_id: {task_id}, error: {e}")
            raise

    def save_step(
        self,
        task_id: str,
        step_number: int,
        node_type: str,
        node_output: dict,
        tool_name: Optional[str] = None
    ) -> bool:
        """
        保存单个执行步骤到文件。

        功能描述:
        - 根据节点类型和步骤号生成文件名
        - 序列化节点输出数据
        - 使用原子写入保存到工作流目录
        - 更新 metadata.json 中的统计信息

        参数:
            task_id (str): 任务唯一标识,用于定位工作流目录
            step_number (int): 步骤序号,从 1 开始,与 ActionSteps.step_order 同步
            node_type (str): 节点类型,值为 "planner" | "call_tool" | "reflection" | "output"
            node_output (dict): 节点输出数据,将被序列化为 JSON
            tool_name (Optional[str]): 工具名称,仅 call_tool 和 output 节点需要

        返回:
            bool: 保存成功返回 True，失败返回 False
        """
        try:
            # 验证工作流目录存在
            if not hasattr(self, 'workflow_dir') or not self.workflow_dir.exists():
                logger.error(f"[GRAPHEXECUTOR] 工作流目录不存在，无法保存步骤: task_id={task_id}")
                return False

            # 规范化工具名称（如果提供）
            sanitized_tool = None
            if tool_name:
                sanitized_tool = self._sanitize_tool_name(tool_name)

            # 构建文件名
            if node_type == "planner":
                filename = f"{step_number}_planner.json"
            elif node_type == "call_tool" and sanitized_tool:
                filename = f"{step_number}_call_tool_{sanitized_tool}.json"
            elif node_type == "reflection":
                filename = f"{step_number}_reflection.json"
            elif node_type == "output" and sanitized_tool:
                filename = f"{step_number}_output_{sanitized_tool}.json"
            else:
                logger.warning(f"[GRAPHEXECUTOR] 未知节点类型或缺少工具名: node_type={node_type}, tool_name={tool_name}")
                filename = f"{step_number}_{node_type}.json"

            # 构建完整文件路径
            file_path = self.workflow_dir / filename

            # 准备要保存的数据
            step_data = {
                "step_number": step_number,
                "node_type": node_type,
                "tool_name": tool_name,
                "timestamp": datetime.now().isoformat(),
                "output": node_output
            }

            # 原子写入步骤文件
            if self._atomic_write(file_path, step_data):
                logger.info(f"[GRAPHEXECUTOR] 保存步骤文件: {filename}")

                # 更新 metadata.json
                self._update_metadata(self.workflow_dir, node_type)
                return True
            else:
                logger.error(f"[GRAPHEXECUTOR] 步骤文件写入失败: {filename}")
                return False

        except Exception as e:
            logger.error(f"[GRAPHEXECUTOR] save_step 失败 - step: {step_number}, node_type: {node_type}, error: {e}")
            return False

    # === 002分支集成结束 ===

    def _tool_executor_node(self, state: RuntimeState, current_plan: PlannerOutput) -> Dict[str, Any]:
        """
        执行工具调用的内部节点。
        使用组件工具中的 execute_tool 函数。
        """
        # 延迟导入以避免循环导入
        from ..utils.processor_tool_executor import execute_tool
        
        return execute_tool(
            state=state,
            current_plan=current_plan,
            user_id=self.user_id,
            nodes_map=self.nodes_map
        )

    def _find_next_node_name(self, current_node_name: str, node_output: Dict[str, Any]) -> str:
        """
        根据当前节点名称和其输出，确定下一个节点的名称。
        使用组件工具中的 find_next_node_name 函数。
        """
        return find_next_node_name(current_node_name, node_output, self.edges_map)

    def run(self) -> RuntimeState:
        """
        执行 Agent 图的主循环。
        从入口节点开始，根据节点逻辑和边定义，依次执行图中的节点，
        直到达到 "END" 节点或发生错误。

        返回:
        RuntimeState: 任务完成后的最终运行时状态。
        """
        # 确保数据库连接在 gevent 环境下正常工作
        ensure_db_connection_safe()

        # 提取分类所需的参数
        task_goal = self.state.task_goal
        preprocessed_files = self.state.preprocessed_files if hasattr(self.state, 'preprocessed_files') else None
        mode = self.state.usage if hasattr(self.state, 'usage') else None
        
        # 获取用户对象
        user = None
        if self.user_id:
            User = get_user_model()
            try:
                user = User.objects.get(id=self.user_id)
            except User.DoesNotExist:
                user = None
        
        # 如果没有用户ID或用户不存在，从AgentTask中获取用户
        if not user and self.agent_task.user:
            user = self.agent_task.user

        # 图执行开始日志将在后续添加
        
        # 基本流程: planner chain -> call tool -> reflection
        # 任务分类已移到 planner_chain 内部作为第一个运行点
        current_node_name = "planner"

        # 不再需要 QA 记录，由业务层自行处理

        # 初始化步骤计数器
        # 如果是恢复任务，从已有的日志中获取最大步骤数
        try:
            max_step = ActionSteps.objects.filter(task=self.agent_task).aggregate(
                max_step=models.Max('step_order')
            )['max_step']
            step_counter = (max_step or 0) + 1
        except Exception as e:
            step_counter = 1

        # 基本执行流程：planner chain -> call tool -> reflection
        # planner chain 内部会先执行 classifier（如果需要），然后执行 analyzer -> strategist -> executor
        
        # 在执行器级别维护current_plan和current_tool_output
        current_plan = None
        current_tool_output = None

        while current_node_name != "END":  # 循环直到当前节点为 "END"
            with transaction.atomic():  # 使用 Django 事务，确保数据库操作的原子性

                node_def = self.nodes_map.get(current_node_name)  # 获取当前节点的定义
                if not node_def:
                    raise ValueError(f"Node '{current_node_name}' not found in graph definition.")

                node_output = {}  # 初始化节点输出

                # 根据节点类型执行不同的逻辑
                if node_def.node_type == "tool":
                    # T007: 通过node_def.config标准判断是否为输出工具（移除output_tool_input临时变量）
                    is_output_tool = node_def.config.get('is_output_tool', False)

                    if is_output_tool and hasattr(self.state, 'output_tool_input') and self.state.output_tool_input:
                        # T014: 集成重试和恢复机制
                        logger.info(f"""
[PROCESSOR] 开始执行输出工具（带重试机制）
工具名称: {current_node_name}
任务ID: {self.task_id}
""")

                        from tools.core.registry import ToolRegistry
                        from agentic.services_output_tool.output_tool_executor import OutputToolExecutor, RetryConfig
                        registry = ToolRegistry()

                        # 创建执行器实例
                        retry_count = node_def.config.get('retry_count', 3)
                        executor = OutputToolExecutor(
                            retry_config=RetryConfig(max_attempts=retry_count)
                        )

                        # 定义工具执行函数（包装为可调用对象）
                        def execute_tool(**kwargs):
                            tool_class = registry.get_tool(current_node_name)
                            tool_instance = tool_class()
                            return tool_instance.execute(kwargs)

                        # T014: 使用重试机制执行工具
                        success, tool_result, error_details = executor.execute_with_retry(
                            tool_func=execute_tool,
                            tool_name=current_node_name,
                            tool_args=self.state.output_tool_input,
                            task_id=self.task_id
                        )

                        if success and tool_result and tool_result.get('status') == 'success':
                            # 执行成功（可能经过重试）
                            final_answer = tool_result.get('output', '')
                            title = tool_result.get('metadata', {}).get('title', '任务完成')

                            node_output = {
                                'final_answer': final_answer,
                                'title': title,
                                'output_tool_used': current_node_name
                            }

                            # T008: 记录为tool_output而非final_answer，避免重复
                            # 仅在END节点记录final_answer
                            tool_output_entry = {
                                "type": "tool_output",  # T008: 改为tool_output
                                "data": {
                                    "output": final_answer,
                                    "title": title
                                },
                                "tool_name": current_node_name
                            }

                            if not self.state.action_history:
                                self.state.action_history = [[tool_output_entry]]
                            elif not isinstance(self.state.action_history[-1], list):
                                raise ValueError("action_history 必须是嵌套列表格式")
                            else:
                                self.state.action_history[-1].append(tool_output_entry)

                            # T015: 保存重试历史到state（供END节点保存）
                            retry_history = executor.get_retry_history()
                            if retry_history:
                                if not hasattr(self.state, 'retry_history'):
                                    self.state.retry_history = []
                                self.state.retry_history.extend(retry_history)

                            # T016: 创建增强的TOOL_RESULT日志（包含重试元数据）
                            import time
                            execution_time_ms = retry_history[-1].get('execution_time_ms', 0) if retry_history else 0
                            retry_attempt = len(retry_history)
                            error_recovered = retry_attempt > 1

                            try:
                                ensure_db_connection_safe()
                                ActionSteps.objects.create(
                                    task=self.agent_task,
                                    step_order=step_counter,
                                    log_type=ActionSteps.LogType.TOOL_RESULT,
                                    details={
                                        "tool_output": {"output": final_answer, "title": title},
                                        "tool_name": current_node_name,
                                        "is_output_tool": True,  # T016: 标识为输出工具
                                        "retry_attempt": retry_attempt,  # T016: 重试次数
                                        "execution_time_ms": execution_time_ms,  # T016: 执行耗时
                                        "error_recovered": error_recovered  # T016: 是否从错误中恢复
                                    }
                                )
                                step_counter += 1
                            except Exception as e:
                                logger.error(f"[PROCESSOR] 创建TOOL_RESULT日志失败: {str(e)}")

                            logger.info(f"""
[PROCESSOR] 输出工具执行成功
工具名称: {current_node_name}
输出长度: {len(final_answer)}字符
标题: {title}
重试次数: {retry_attempt}
错误恢复: {error_recovered}
""")
                        else:
                            # T017: 所有重试失败，需要恢复机制
                            logger.error(f"""
[PROCESSOR] 输出工具执行失败（所有重试已耗尽）
工具名称: {current_node_name}
错误类型: {error_details.get('error_type') if error_details else 'Unknown'}
错误消息: {error_details.get('error_message') if error_details else 'Unknown'}
""")

                            # T013: 尝试备选工具
                            # 获取所有可用的generator工具
                            all_generator_tools = []
                            all_tools_info = registry.list_tools_with_details(category='generator')
                            for tool_info in all_tools_info:
                                all_generator_tools.append({
                                    "name": tool_info['name'],
                                    "priority": 1  # 简单优先级
                                })

                            # 尝试备选工具
                            alternative_tool = executor.try_alternative_tool(
                                available_tools=all_generator_tools,
                                failed_tools=[current_node_name]
                            )

                            if alternative_tool:
                                logger.warning(f"""
[PROCESSOR] 尝试使用备选输出工具
原工具: {current_node_name}
备选工具: {alternative_tool}
""")
                                # 递归重试备选工具（最多一次）
                                alternative_success, alternative_result, _ = executor.execute_with_retry(
                                    tool_func=lambda **kwargs: registry.get_tool(alternative_tool)().execute(kwargs),
                                    tool_name=alternative_tool,
                                    tool_args=self.state.output_tool_input,
                                    task_id=self.task_id
                                )

                                if alternative_success and alternative_result.get('status') == 'success':
                                    # 备选工具成功
                                    final_answer = alternative_result.get('output', '')
                                    title = alternative_result.get('metadata', {}).get('title', '任务完成')
                                    node_output = {
                                        'final_answer': final_answer,
                                        'title': title,
                                        'output_tool_used': alternative_tool
                                    }
                                    logger.info(f"[PROCESSOR] 备选工具 {alternative_tool} 执行成功")
                                else:
                                    # T017: 备选工具也失败，标记任务FAILED
                                    self.agent_task.status = AgentTask.TaskStatus.FAILED
                                    if not hasattr(self.state, 'error_details'):
                                        self.state.error_details = error_details
                                    node_output = {
                                        'final_answer': '任务失败：所有输出工具执行失败。',
                                        'title': '任务失败',
                                        'error_details': error_details
                                    }
                                    logger.error(f"[PROCESSOR] 备选工具 {alternative_tool} 也失败，任务标记为FAILED")
                            else:
                                # T017: 无备选工具，直接标记任务FAILED
                                self.agent_task.status = AgentTask.TaskStatus.FAILED
                                if not hasattr(self.state, 'error_details'):
                                    self.state.error_details = error_details
                                node_output = {
                                    'final_answer': '任务失败：输出工具执行失败且无备选方案。',
                                    'title': '任务失败',
                                    'error_details': error_details
                                }
                                logger.error(f"[PROCESSOR] 无备选工具可用，任务标记为FAILED")

                        # 清理 output_tool_input，避免影响后续执行
                        self.state.output_tool_input = None
                    else:
                        # 普通工具节点，通过内部的 tool executor 执行
                        if not current_plan:
                            raise ValueError("Tool executor called without current_plan")
                        node_output = self._tool_executor_node(self.state, current_plan)
                        current_tool_output = node_output.get("tool_output")
                else:
                    # 加载并执行外部定义的节点函数
                    node_function = self._load_callable(node_def.python_callable)

                    # 为 "planner" 和 "reflection" 节点传递图结构信息 (nodes_map, edges_map)
                    # 这些节点可能需要图的整体结构来做出决策
                    try:
                        if current_node_name == "planner":
                            node_output = node_function(self.state, self.nodes_map, self.edges_map, user=user, session_id=self.agent_task.session_id)
                            # 从输出中提取current_plan
                            if "current_plan" in node_output:
                                current_plan = node_output["current_plan"]
                                
                                # 如果planner选择了执行某个TODO任务，将其状态标记为processing
                                if self.state.todo and current_plan and current_plan.action == "CALL_TOOL" and current_plan.tool_name:
                                    for todo_item in self.state.todo:
                                        if (todo_item.get('status', 'pending') == 'pending' and 
                                            current_plan.tool_name in todo_item.get('suggested_tools', [])):
                                            # 检查依赖是否满足
                                            dependencies = todo_item.get('dependencies', [])
                                            dependencies_met = True
                                            if dependencies:
                                                for dep_id in dependencies:
                                                    dep_task = next((t for t in self.state.todo if t.get('id') == dep_id), None)
                                                    if not dep_task or dep_task.get('status') != 'completed':
                                                        dependencies_met = False
                                                        break
                                            
                                            if dependencies_met:
                                                # 将任务标记为processing
                                                old_status = todo_item.get('status', 'pending')
                                                todo_item['status'] = 'processing'
                                                log_state_change(f"todo[{todo_item.get('id')}].status", old_status, 'processing', "Start TODO task")
                                                # 【新增】记录任务开始时间，用于超时检测
                                                from datetime import datetime
                                                todo_item['started_at'] = datetime.now().isoformat()
                                                break
                        elif current_node_name == "reflection":
                            node_output = node_function(self.state, self.nodes_map, self.edges_map, current_plan, current_tool_output, user=user, session_id=self.agent_task.session_id)
                        elif current_node_name == "output":
                            # output 需要特殊处理
                            # 从 current_plan 中提取 output_guidance
                            output_guidance = None
                            
                            if current_plan and hasattr(current_plan, 'output_guidance'):
                                output_guidance = current_plan.output_guidance
                            
                            # 调用 output_node
                            node_output = node_function(
                                self.state,
                                self.nodes_map,
                                user=user,
                                session_id=self.agent_task.session_id,
                                output_guidance=output_guidance
                            )
                            
                            # output 节点应返回选择的输出工具信息，用于边导航
                            # node_output 格式: {'output_tool_decision': {'tool_name': xxx, 'tool_input': xxx}}
                            # 保存工具输入以供后续工具节点使用
                            if isinstance(node_output, dict) and 'output_tool_decision' in node_output:
                                tool_decision = node_output['output_tool_decision']
                                self.state.output_tool_input = tool_decision.get('tool_input', {})
                                # 选择输出工具日志将在后续添加
                                # find_next_node_name 将根据 OUTPUT:tool_name 条件边导航到相应工具
                        else:
                            # 其他节点只接收运行时状态作为参数（也传递用户和会话信息）
                            # 检查函数签名，如果支持用户和会话参数则传递
                            sig = inspect.signature(node_function)
                            params = sig.parameters
                            if 'user' in params and 'session_id' in params:
                                node_output = node_function(self.state, user=user, session_id=self.agent_task.session_id)
                            else:
                                node_output = node_function(self.state)
                    except Exception as node_e:
                        
                        # 如果是 planner 节点失败，尝试设置任务为失败状态
                        if current_node_name == "planner":
                            self.agent_task.status = AgentTask.TaskStatus.FAILED
                            # 在保存前确保数据库连接
                            ensure_db_connection_safe()
                            self.agent_task.save(update_fields=['status', 'updated_at'])
                            
                            # QA 记录已移除，由业务层自行处理
                        
                        # 重新抛出异常，让上层处理
                        raise


                # 格式化节点输出
                node_output_summary = {}
                if isinstance(node_output, dict):
                    node_output_summary = {
                        "keys": list(node_output.keys()),
                        "type": type(node_output).__name__
                    }
                    # 对于特定的输出添加更多细节
                    if "current_plan" in node_output:
                        plan = node_output["current_plan"]
                        if hasattr(plan, "action") and hasattr(plan, "tool_name"):
                            node_output_summary["plan"] = {
                                "action": plan.action,
                                "tool": plan.tool_name
                            }
                    if "tool_output" in node_output:
                        tool_out = node_output["tool_output"]
                        if isinstance(tool_out, dict):
                            node_output_summary["tool_status"] = tool_out.get("status")
                else:
                    node_output_summary = {
                        "type": type(node_output).__name__,
                        "value": str(node_output)[:100]
                    }
                


                # 保存检查点
                self.checkpoint.save(self.task_id, self.state)  # 保存当前的运行时状态到检查点

                # 创建 AgenticLog 记录
                try:
                    log_type = None
                    details = {}

                    # 根据节点名称和输出确定日志类型和详细信息
                    if current_node_name == "planner":
                        log_type = ActionSteps.LogType.PLANNER
                        if current_plan:
                            details = {
                                "thought": str(current_plan.thought),
                                "action": str(current_plan.action),
                                "tool_name": str(current_plan.tool_name) if current_plan.tool_name else None,
                                "tool_input": current_plan.tool_input if current_plan.tool_input else None,
                                # 不再记录 planner 的 final_answer，因为实际的 final_answer 由 output_node 生成
                                # "final_answer": str(current_plan.final_answer) if hasattr(current_plan, 'final_answer') and current_plan.final_answer else None
                            }
                            # TODO相关数据已弃用，TODO管理应通过todo_generator工具实现
                    elif node_def.node_type == "tool":
                        # 为工具执行创建两条日志：TOOL_CALL 和 TOOL_RESULT
                        if current_plan:
                            # 创建 TOOL_CALL 日志
                            ensure_db_connection_safe()
                            ActionSteps.objects.create(
                                task=self.agent_task,
                                step_order=step_counter,
                                log_type=ActionSteps.LogType.TOOL_CALL,
                                details={
                                    "tool_name": str(current_plan.tool_name),
                                    "tool_input": current_plan.tool_input,
                                    "thought": str(current_plan.thought)
                                }
                            )
                            step_counter += 1

                        # 创建 TOOL_RESULT 日志
                        log_type = ActionSteps.LogType.TOOL_RESULT
                        if isinstance(node_output, dict) and 'tool_output' in node_output:
                            details = {
                                "tool_output": node_output['tool_output'],
                                "tool_name": str(current_plan.tool_name) if current_plan else None
                            }
                    elif current_node_name == "reflection":
                        log_type = ActionSteps.LogType.REFLECTION
                        # 从 node_output 中提取反思信息
                        if isinstance(node_output, dict):
                            details = {
                                "reflection_content": node_output.get('reflection', ''),
                                "next_action": node_output.get('next_action', ''),
                                "node_output": self._serialize_output(node_output)
                            }

                    # 创建日志记录（如果有有效的日志类型）
                    if log_type:
                        ensure_db_connection_safe()
                        ActionSteps.objects.create(
                            task=self.agent_task,
                            step_order=step_counter,
                            log_type=log_type,
                            details=details
                        )
                        step_counter += 1
                    
                    # 检查TODO变化并记录
                    if self.state.todo:  # Pydantic模型字段总是存在，只需检查是否为空
                        # 检查是否是首次创建TODO或TODO有变化
                        todo_changed = False
                        
                        # 检查是否有新的TODO列表被创建（通过TodoGenerator）
                        if log_type == ActionSteps.LogType.TOOL_RESULT and details.get('tool_name') == 'TodoGenerator':
                            todo_changed = True
                        
                        # 检查是否有TODO任务状态变化（通过reflection节点）
                        elif current_node_name == "reflection":
                            # 统计完成的任务数
                            completed_count = sum(1 for t in self.state.todo if t.get('status') == 'completed')
                            total_count = len(self.state.todo)
                            
                            # 获取上一次记录的TODO状态（如果有）
                            last_todo_step = ActionSteps.objects.filter(
                                task=self.agent_task,
                                log_type='todo_update'
                            ).order_by('-step_order').first()
                            
                            if last_todo_step and last_todo_step.details:
                                last_completed = last_todo_step.details.get('completed_count', 0)
                                if completed_count != last_completed:
                                    todo_changed = True
                            elif completed_count > 0:
                                # 首次有任务完成
                                todo_changed = True
                        
                        # 如果TODO有变化，创建专门的TODO更新日志
                        if todo_changed:
                            ensure_db_connection_safe()
                            
                            # 准备TODO摘要信息
                            todo_summary = {
                                'total_count': len(self.state.todo),
                                'completed_count': sum(1 for t in self.state.todo if t.get('status') == 'completed'),
                                'todo_list': [
                                    {
                                        'id': t.get('id'),
                                        'task': t.get('task'),
                                        'status': t.get('status', 'pending'),
                                        'suggested_tools': t.get('suggested_tools', []),
                                        'completion_details': t.get('completion_details', {})
                                    }
                                    for t in self.state.todo
                                ]
                            }
                            
                            # 创建TODO更新日志
                            ActionSteps.objects.create(
                                task=self.agent_task,
                                step_order=step_counter,
                                log_type='todo_update',  # 新的日志类型
                                details=todo_summary
                            )
                            step_counter += 1

                except Exception as e:
                    # 不中断执行，只记录错误
                    pass

                # === 002分支集成：保存步骤文件 ===
                # 在节点执行完成后，保存步骤文件到工作流目录
                try:
                    # 递增步骤计数器（保持与ActionSteps的step_order同步）
                    self.step_counter += 1

                    # 确定节点类型和工具名称
                    step_node_type = None
                    step_tool_name = None

                    if node_def.node_type == "router":
                        # Router类型节点：planner, reflection, output等
                        # 使用节点名称作为步骤类型，保持可读性
                        step_node_type = current_node_name  # "planner", "reflection", "output"
                    elif node_def.node_type == "tool":
                        is_output_tool = node_def.config.get('is_output_tool', False)
                        if is_output_tool:
                            step_node_type = "output"
                            step_tool_name = current_node_name
                        else:
                            step_node_type = "call_tool"
                            step_tool_name = current_node_name
                    elif node_def.node_type == "llm":
                        # LLM节点也应该记录
                        step_node_type = "llm"
                        step_tool_name = current_node_name

                    # 调用save_step保存步骤文件
                    if step_node_type:
                        self.save_step(
                            task_id=self.task_id,
                            step_number=self.step_counter,
                            node_type=step_node_type,
                            node_output=self._serialize_output(node_output),
                            tool_name=step_tool_name
                        )
                except Exception as save_e:
                    # 步骤文件保存失败不应中断执行流程
                    logger.warning(f"[GRAPHEXECUTOR] 步骤文件保存失败（非致命错误）: {save_e}")

                # 确定下一个节点
                previous_node_name = current_node_name
                current_node_name = self._find_next_node_name(current_node_name, node_output)  # 调用方法确定下一个节点

                if current_node_name == "END":
                    # T009: 调用标准化的任务完成方法
                    self._finalize_task(node_output, current_plan, step_counter)
                    break  # 退出循环

        return self.state  # 返回最终的运行时状态

    def _finalize_task(
        self,
        node_output: Dict[str, Any],
        current_plan: Any,
        step_counter: int
    ) -> None:
        """
        T009: 标准化END节点的任务完成逻辑

        负责在任务到达END节点时执行所有必要的完成操作:
        1. 标记任务状态为COMPLETED
        2. 提取并记录最终答案到action_history
        3. 更新chat_history
        4. 创建FINAL_ANSWER类型的ActionSteps日志
        5. 保存完整的output_data到AgentTask

        Args:
            node_output: 前一个节点(通常是输出工具)的输出
            current_plan: 当前执行计划(用于回退方案)
            step_counter: 当前步骤计数器

        Returns:
            None (直接修改self.agent_task和self.state)

        Raises:
            ValueError: 如果action_history格式不正确
        """
        logger.info(f"""
[PROCESSOR] 任务到达END节点，开始完成流程
任务ID: {self.task_id}
当前步骤: {step_counter}
""")

        # 将任务状态设置为完成
        self.agent_task.status = AgentTask.TaskStatus.COMPLETED

        # 默认的最终答案和标题
        final_conclusion = "任务完成。"
        final_title = None

        # 检查是否有来自输出工具节点的输出
        # 前一个节点应该是某个输出工具（如 report_generator、text_generator 等）
        # node_output 中应该包含 final_answer 和 title
        if isinstance(node_output, dict) and 'final_answer' in node_output:
            final_conclusion = node_output.get('final_answer', '任务完成。')
            final_title = node_output.get('title', None)

            # 向 action_history 添加 final_answer 条目
            # action_history 必须是嵌套列表结构：添加到最后一个子列表（当前对话）
            if not self.state.action_history:
                # 如果为空，初始化为嵌套结构
                self.state.action_history = [[{
                    "type": "final_answer",
                    "data": {
                        "output": final_conclusion,  # 统一使用output字段
                        "title": final_title
                    }
                }]]
            elif not isinstance(self.state.action_history[-1], list):
                # 格式不合法
                raise ValueError("action_history 必须是嵌套列表格式")
            else:
                # 添加到最后一个子列表
                self.state.action_history[-1].append({
                    "type": "final_answer",
                    "data": {
                        "output": final_conclusion,  # 统一使用output字段
                        "title": final_title
                    }
                })

            # 将AI的回复添加到chat_history中，用于后续对话的上下文
            if not self.state.chat_history:
                self.state.chat_history = []

            # 添加AI的回复到对话历史
            self.state.chat_history.append({
                "role": "assistant",
                "content": final_conclusion
            })

        elif current_plan and hasattr(current_plan, 'final_answer') and current_plan.final_answer:
            # 回退方案：如果 planner 提供了 final_answer（不应该发生）
            logger.warning(f"""
[PROCESSOR] 使用回退方案: 从planner获取final_answer
任务ID: {self.task_id}
注意: 正常流程应该由输出工具提供final_answer
""")
            final_conclusion = current_plan.final_answer
            if hasattr(current_plan, 'title') and current_plan.title:
                final_title = current_plan.title

        logger.info(f"""
[PROCESSOR] 最终答案已提取
任务ID: {self.task_id}
答案长度: {len(final_conclusion)}字符
标题: {final_title}
""")

        # 创建最终答案日志
        try:
            ensure_db_connection_safe()
            ActionSteps.objects.create(
                task=self.agent_task,
                step_order=step_counter,
                log_type=ActionSteps.LogType.FINAL_ANSWER,
                details={
                    "final_answer": final_conclusion,
                    "task_goal": self.state.task_goal,
                    "completion_status": "success"
                }
            )
        except Exception as e:
            logger.error(f"""
[PROCESSOR] 创建FINAL_ANSWER日志失败
任务ID: {self.task_id}
错误: {str(e)}
""")

        # 将最终输出数据保存到 AgentTask
        # 处理 action_history 的两种格式：扁平列表和嵌套列表
        processed_history = []
        for item in self.state.action_history:
            if isinstance(item, list):
                # 嵌套列表格式：展开子列表中的每个字典
                for log in item:
                    if isinstance(log, dict):
                        processed_history.append({
                            "type": log.get("type"),
                            "data": self._serialize_output(log.get("data"))
                        })
            elif isinstance(item, dict):
                # 扁平列表格式：直接处理字典
                processed_history.append({
                    "type": item.get("type"),
                    "data": self._serialize_output(item.get("data"))
                })

        # T015: 构建output_data，包含retry_history和error_details
        output_data = {
            "final_conclusion": final_conclusion,
            "task_goal": self.state.task_goal,
            "title": final_title,
            "action_history": processed_history
        }

        # T015: 添加重试历史（如果有）
        if hasattr(self.state, 'retry_history') and self.state.retry_history:
            output_data["retry_history"] = self.state.retry_history
            logger.info(f"""
[PROCESSOR] 保存重试历史
重试记录数: {len(self.state.retry_history)}
""")

        # T017: 添加错误详情（如果任务失败）
        if hasattr(self.state, 'error_details') and self.state.error_details:
            output_data["error_details"] = self.state.error_details
            logger.error(f"""
[PROCESSOR] 保存错误详情
错误类型: {self.state.error_details.get('error_type')}
错误消息: {self.state.error_details.get('error_message')}
恢复尝试次数: {self.state.error_details.get('recovery_attempts')}
""")

        self.agent_task.output_data = output_data

        # 在保存前确保数据库连接
        ensure_db_connection_safe()
        self.agent_task.save(update_fields=['status', 'output_data', 'updated_at'])

        logger.info(f"""
[PROCESSOR] 任务完成流程执行完毕
任务ID: {self.task_id}
状态: COMPLETED
历史记录条数: {len(processed_history)}
""")

    def _get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """
        获取工具的配置。
        使用组件工具中的 get_tool_config 函数。
        """
        return get_tool_config(tool_name, self.nodes_map)