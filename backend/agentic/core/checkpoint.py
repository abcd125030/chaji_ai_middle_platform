"""
Agent状态检查点管理模块

该模块实现了Agent运行时状态的持久化存储和恢复机制，采用文件系统+数据库的双写策略，
确保Agent任务状态的高可靠性保存和快速恢复。

主要功能：
========
1. Agent状态的原子性保存和加载
2. 文件系统优先、数据库降级的存储策略
3. 版本轮转机制，保留多个历史版本
4. 复杂对象的递归序列化处理
5. 并发安全的文件操作

输入数据结构：
============
- task_id: str - Agent任务唯一标识
- state: RuntimeState - Agent运行时状态对象，包含：
  * task_goal: str - 任务目标
  * action_history: List[Dict] - 执行历史记录
  * preprocessed_files: Dict - 预处理文件信息
  * origin_images: List - 原始图像列表
  * usage: Dict - 资源使用统计
  * todo: List[Dict] - TODO任务清单
  * full_action_data: Dict - 完整动作数据

输出数据结构：
============
- 保存操作：无返回值，通过日志和异常处理报告结果
- 加载操作：Optional[RuntimeState] - 恢复的状态对象，失败时返回None

存储策略：
=========
1. 主存储：文件系统
   - 路径格式：/media/oss-bucket/{user_uuid}/sessions/{session_uuid}/state.json
   - 优势：读写性能高，便于调试和维护
   - 特性：原子写入，版本轮转，文件锁保护

2. 备份存储：数据库
   - 字段：AgentTask.state_snapshot (JSONField)
   - 作用：过渡期兼容，系统降级保障
   - 策略：双写模式，读取时优先文件系统

内部处理流程：
============

保存流程 (save方法)：
------------------
1. 根据task_id查询AgentTask获取用户和会话信息
2. 递归序列化RuntimeState对象中的复杂数据结构
3. 文件系统保存：
   - 构建存储路径：{base_path}/{user_uuid}/sessions/{session_uuid}/
   - 执行版本轮转（保留最近N个版本）
   - 原子性写入新的state.json文件
   - 保存元数据文件metadata.json
4. 数据库保存（双写策略）：
   - 更新AgentTask.state_snapshot字段
5. 异常处理：文件保存失败时降级到仅数据库保存

加载流程 (load方法)：
------------------
1. 根据task_id查询AgentTask获取路径信息
2. 文件系统加载（优先）：
   - 尝试读取主state.json文件
   - 失败时依次尝试备份版本(.1, .2, .3等)
   - 使用文件锁确保读取一致性
3. 数据库降级加载：
   - 文件不存在时从AgentTask.state_snapshot加载
   - 可选地将数据库数据同步到文件系统
4. 状态对象重建：
   - 将JSON数据反序列化为RuntimeState对象
   - 恢复TODO任务、动作摘要等复杂结构
   - 设置私有属性如_original_task_goal

函数调用关系：
============

外部调用入口：
- save(task_id, state) - 保存Agent状态
- load(task_id) - 加载Agent状态

内部辅助方法：
- _serialize_output(data) - 递归序列化复杂对象
- _get_session_path(user_uuid, session_uuid) - 构建存储路径
- _ensure_directory(path) - 确保目录存在
- _atomic_write(file_path, data) - 原子性文件写入
- _rotate_versions(file_path) - 版本轮转管理

外部依赖关系：
============

Django依赖：
- django.conf.settings - 获取MEDIA_ROOT配置
- AgentTask模型 - 任务信息查询和状态保存

Schema依赖：
- RuntimeState - Agent运行时状态数据结构
- PlannerOutput, ReflectionOutput - 输出模式定义（导入但未直接使用）

数据处理依赖：
- pydantic.BaseModel - 模型序列化支持
- pandas (可选) - DataFrame/Series序列化支持

系统依赖：
- pathlib.Path - 路径操作
- json - JSON序列化
- fcntl - 文件锁操作
- tempfile - 临时文件创建
- os - 文件系统操作

核心特性：
=========
1. 原子性：使用临时文件+重命名确保写入原子性
2. 并发安全：文件锁机制防止并发读写冲突
3. 版本管理：自动轮转保留多个历史版本
4. 容错性：多级降级策略确保数据不丢失
5. 可扩展性：支持复杂对象的递归序列化
6. 性能优化：文件系统优先，减少数据库压力

使用场景：
=========
- Agent任务执行过程中的状态保存
- Agent任务重启后的状态恢复
- 系统故障后的数据恢复
- 调试和分析Agent执行历史
"""

from typing import Optional, Any
import sys
import os
import json
import portalocker
import tempfile
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

from django.conf import settings
from ..models import AgentTask
from .schemas import RuntimeState, PlannerOutput, ReflectionOutput

import logging
logger = logging.getLogger("django")

class DBCheckpoint:
    """
    用于 Agent 运行时状态的检查点。
    支持文件系统存储（优先）和数据库存储（备份/降级）的双写机制。
    
    存储策略：
    1. 文件系统（主要）：/backend/media/oss-bucket/{user_uuid}/sessions/{session_uuid}/state.json
    2. 数据库（备份）：AgentTask.state_snapshot 字段（过渡期保留）
    
    特点：
    - 每个session只维护一个state文件，避免O(n)存储增长
    - 支持原子性写入，防止文件损坏
    - 实现版本管理，保留最近N个版本
    - 文件优先、数据库降级的读取策略
    """
    
    def __init__(self):
        """初始化检查点管理器"""
        # 基础存储路径
        self.base_path = Path(settings.MEDIA_ROOT) / "oss-bucket"
        # 保留的历史版本数
        self.max_versions = 3
        # 是否启用双写（过渡期设为True）
        self.enable_db_write = True
    
    def _serialize_output(self, data: Any) -> Any:
        """
        递归地序列化 Pydantic 模型和具有 `to_dict` 方法的对象。
        此方法确保数据可以被正确地存储或传输，特别是当数据包含复杂对象时。

        参数:
        data (Any): 需要序列化的数据。

        返回:
        Any: 序列化后的数据，通常是 Python 基本类型（字典、列表、字符串、数字等）。
        """
        # 处理 None 值
        if data is None:
            return None
            
        # 处理 Pydantic HttpUrl 类型
        try:
            from pydantic import HttpUrl
            if isinstance(data, HttpUrl):
                return str(data)
        except ImportError:
            pass
            
        if isinstance(data, BaseModel):
            # 如果是 Pydantic 模型，使用 model_dump() 方法将其转换为字典
            # 然后递归序列化结果以处理嵌套的复杂对象
            return self._serialize_output(data.model_dump())

        # 动态处理 pandas 对象，如果 pandas 模块已加载
        if 'pandas' in sys.modules:
            import pandas as pd
            if isinstance(data, pd.DataFrame):
                # 对于 DataFrame，使用 'records' 方向转换为字典列表
                return self._serialize_output(data.to_dict(orient='records'))
            if isinstance(data, pd.Series):
                # 对于 Series，转换为字典
                return self._serialize_output(data.to_dict())

        if hasattr(data, 'to_dict') and callable(getattr(data, 'to_dict')):
            # 对于其他具有 to_dict 方法的对象，递归序列化其 to_dict() 的结果
            return self._serialize_output(data.to_dict())
        if isinstance(data, list):
            # 如果是列表，递归序列化列表中的每个元素
            return [self._serialize_output(item) for item in data]
        if isinstance(data, dict):
            # 如果是字典，递归序列化字典中的每个值
            return {k: self._serialize_output(v) for k, v in data.items()}
        
        # 处理其他可能的特殊类型
        if hasattr(data, '__str__') and not isinstance(data, (str, int, float, bool)):
            # 对于其他复杂对象，尝试转换为字符串
            try:
                # 先尝试 JSON 序列化测试
                import json
                json.dumps(data)
                return data
            except (TypeError, ValueError):
                # 如果无法 JSON 序列化，则转换为字符串
                return str(data)
        
        # 对于基本类型（如字符串、数字、布尔值、None），直接返回
        return data
    
    def _get_session_path(self, user_uuid: str, session_uuid: str) -> Path:
        """获取session的存储路径（已弃用，保留用于向后兼容）"""
        return self.base_path / user_uuid / "sessions" / session_uuid

    def _get_workflow_directory(self, task_id: str, user_uuid: str, create_if_missing: bool = True) -> Path:
        """
        获取或创建工作流目录（统一目录结构）

        目录格式: sessions/{timestamp}_{task_id}/

        Args:
            task_id: 任务ID
            user_uuid: 用户ID
            create_if_missing: 如果目录不存在是否创建

        Returns:
            Path: 工作流目录路径
        """
        sessions_base = self.base_path / user_uuid / "sessions"

        # 首先尝试查找现有的工作流目录（匹配 *_{task_id} 模式）
        if sessions_base.exists():
            matching_dirs = list(sessions_base.glob(f"*_{task_id}"))
            if matching_dirs:
                return matching_dirs[0]

        # 如果不存在且需要创建，则创建新目录
        if create_if_missing:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            workflow_dir = sessions_base / f"{timestamp}_{task_id}"
            workflow_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[CHECKPOINT] 创建工作流目录: {workflow_dir}")
            return workflow_dir

        # 如果不存在且不创建，返回预期路径（用于错误提示）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return sessions_base / f"{timestamp}_{task_id}"

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
            logger.error(f"原子写入失败 {file_path}: {e}")
            return False
    
    def _rotate_versions(self, file_path: Path) -> None:
        
        """
        版本轮转，保留最近N个版本
        
        对指定文件进行版本轮转管理，将当前文件重命名为版本1，原有版本依次向后推移，
        超过最大版本数的文件将被删除。
        - file_path (Path): 需要进行版本轮转的文件路径
        - None
        示例：
        假设 max_versions = 3，file_path = "data.txt"
        轮转前: data.txt, data.txt.1, data.txt.2, data.txt.3
        轮转后: data.txt.1, data.txt.2, data.txt.3 (原data.txt.3被删除)
        异常处理：
        - 如果文件不存在，直接返回
        - 轮转过程中的异常会被捕获并记录警告日志
        
        """
        try:
            if not file_path.exists():
                return
            
            # 轮转现有版本
            for i in range(self.max_versions - 1, 0, -1):
                old_version = Path(f"{file_path}.{i}")
                new_version = Path(f"{file_path}.{i+1}")
                
                if old_version.exists():
                    if new_version.exists():
                        new_version.unlink()  # 删除最老的版本
                    old_version.rename(new_version)
            
            # 当前文件变为版本1
            file_path.rename(Path(f"{file_path}.1"))
            
        except Exception as e:
            logger.warning(f"版本轮转失败: {e}")
    
    def save(self, task_id: str, state: RuntimeState):
        """
        保存 Agent 的当前运行时状态。
        实现双写策略：同时写入文件系统和数据库（过渡期）。
        """
        try:
            # 获取任务信息
            agent_task = AgentTask.objects.get(task_id=task_id)
            
            # 获取用户和会话信息
            user_uuid = str(agent_task.user.id) if agent_task.user else "anonymous"
            session_uuid = str(agent_task.session_id) if agent_task.session_id else task_id
            
            # 在序列化前记录状态信息
            logger.debug(f"[CHECKPOINT] Saving state for task {task_id}, session {session_uuid}")
            logger.debug(f"[CHECKPOINT] Action history length: {len(state.action_history)}")
            # 处理 action_history 的两种格式
            action_types = []
            for item in state.action_history:
                if isinstance(item, list):
                    # 嵌套列表格式
                    for log in item:
                        if isinstance(log, dict):
                            action_types.append(log.get("type"))
                elif isinstance(item, dict):
                    # 扁平列表格式
                    action_types.append(item.get("type"))
            logger.debug(f"[CHECKPOINT] Action types in history: {action_types}")
            
            # 记录TODO任务状态
            if state.todo:  # Pydantic模型字段总是存在，只需检查是否为空
                todo_count = len(state.todo)
                completed_count = sum(1 for t in state.todo if t.get('status') == 'completed')
                logger.info(f"[CHECKPOINT] 保存 {todo_count} 个TODO任务，进度: {completed_count}/{todo_count}")
            
            # 处理 action_history - 必须是嵌套列表格式
            processed_history = []
            
            # 验证 action_history 必须是列表
            if not isinstance(state.action_history, list):
                logger.error(f"[CHECKPOINT] action_history 必须是列表，实际类型: {type(state.action_history)}")
                raise ValueError("action_history 必须是列表格式")
            
            # 如果是空列表，初始化为包含一个空子列表
            if not state.action_history:
                processed_history = [[]]
            else:
                # 检查第一个元素以确定格式
                if isinstance(state.action_history[0], dict):
                    # 检测到扁平结构，视为不合法
                    logger.error(f"[CHECKPOINT] 检测到不合法的扁平 action_history 结构")
                    raise ValueError("action_history 不能使用扁平结构，必须是嵌套列表格式 [[{...}], [{...}]]")
                
                # 处理嵌套列表格式
                for item in state.action_history:
                    if not isinstance(item, list):
                        logger.error(f"[CHECKPOINT] action_history 子项必须是列表，实际类型: {type(item)}")
                        raise ValueError(f"action_history 的每个子项必须是列表，发现: {type(item)}")
                    
                    # 处理子列表中的每个字典
                    sub_list = []
                    for log in item:
                        if isinstance(log, dict):
                            sub_list.append({
                                "type": log.get("type"),
                                "data": self._serialize_output(log.get("data")),
                                "tool_name": log.get("tool_name") if log.get("tool_name") else None
                            })
                    processed_history.append(sub_list)
            
            serialized_state = {
                "task_goal": state.task_goal,
                "action_history": processed_history,
                # Pydantic模型的字段都有默认值，直接访问即可
                "preprocessed_files": self._serialize_output(state.preprocessed_files),
                "origin_images": self._serialize_output(state.origin_images),
                "usage": state.usage,
                # TODO任务清单
                "todo": self._serialize_output(state.todo),
                # 摘要相关字段
                "full_action_data": self._serialize_output(state.full_action_data),
                # 对话历史和上下文
                "chat_history": self._serialize_output(state.chat_history),
                "context_memory": self._serialize_output(state.context_memory),
                "user_context": self._serialize_output(state.user_context),
                # 私有属性需要特殊访问
                "_original_task_goal": getattr(state, '_original_task_goal', None)
            }
            
            # 1. 保存到文件系统（主要存储）- 使用统一的工作流目录
            workflow_dir = self._get_workflow_directory(task_id, user_uuid, create_if_missing=True)

            state_file = workflow_dir / "state.json"

            # 如果文件已存在，先进行版本轮转
            if state_file.exists():
                self._rotate_versions(state_file)

            # 原子性写入新的state文件
            file_saved = self._atomic_write(state_file, serialized_state)

            if file_saved:
                logger.info(f"[CHECKPOINT] 文件保存成功: {state_file}")

                # 更新元数据（如果已存在则合并更新）
                metadata_file = workflow_dir / "metadata.json"
                existing_metadata = {}
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            existing_metadata = json.load(f)
                    except:
                        pass

                # 合并元数据
                metadata = {
                    **existing_metadata,  # 保留现有元数据
                    "task_id": task_id,
                    "session_id": session_uuid,
                    "user_id": user_uuid,
                    "last_update": datetime.now().isoformat(),
                    "action_count": len(state.action_history),
                    "todo_count": len(state.todo) if state.todo else 0
                }
                self._atomic_write(metadata_file, metadata)
            
            # 2. 保存到数据库（过渡期备份）
            if self.enable_db_write:
                agent_task.state_snapshot = serialized_state
                agent_task.save()
                logger.debug(f"[CHECKPOINT] 数据库保存成功 for task_id: {task_id}")
            
            print(f"Checkpoint saved for task_id: {task_id}, session: {session_uuid}")
        except AgentTask.DoesNotExist:
            logger.error(f"AgentTask with task_id {task_id} not found for saving checkpoint.")
        except Exception as e:
            logger.error(f"Error saving checkpoint for task_id {task_id}: {e}")
            # 如果文件保存失败，确保至少保存到数据库
            try:
                if self.enable_db_write and 'agent_task' in locals() and 'serialized_state' in locals():
                    agent_task.state_snapshot = serialized_state
                    agent_task.save()
                    logger.info(f"[CHECKPOINT] 降级到数据库保存成功")
            except Exception as db_error:
                logger.error(f"数据库保存也失败: {db_error}")

    def load(self, task_id: str) -> Optional[RuntimeState]:
        """
        加载 Agent 的运行时状态。
        优先从文件系统加载，如果文件不存在则从数据库加载（降级策略）。
        """
        try:
            # 先只获取必要字段（延迟加载state_snapshot）
            agent_task = AgentTask.objects.defer('state_snapshot').get(task_id=task_id)
            
            # 获取用户和会话信息
            user_uuid = str(agent_task.user.id) if agent_task.user else "anonymous"
            session_uuid = str(agent_task.session_id) if agent_task.session_id else task_id
            snapshot = None
            
            # 1. 优先尝试从文件系统加载（使用统一的工作流目录）
            workflow_dir = self._get_workflow_directory(task_id, user_uuid, create_if_missing=False)
            state_file = workflow_dir / "state.json"

            if state_file.exists():
                try:
                    with open(state_file, 'r') as f:
                        portalocker.lock(f, portalocker.LockFlags.SHARED)
                        snapshot = json.load(f)
                        portalocker.unlock(f)
                    
                    logger.info(f"[CHECKPOINT] 从文件加载成功: {state_file}")
                    
                except Exception as e:
                    logger.warning(f"文件加载失败，尝试从备份版本加载: {e}")
                    
                    # 尝试从最近的备份版本加载
                    for i in range(1, self.max_versions + 1):
                        backup_file = Path(f"{state_file}.{i}")
                        if backup_file.exists():
                            try:
                                with open(backup_file, 'r') as f:
                                    snapshot = json.load(f)
                                logger.info(f"[CHECKPOINT] 从备份版本{i}加载成功")
                                break
                            except Exception as backup_error:
                                logger.warning(f"备份版本{i}加载失败: {backup_error}")
                                continue
            
            # 2. 如果文件系统加载失败，从数据库加载（降级）
            if snapshot is None and agent_task.state_snapshot:
                snapshot = agent_task.state_snapshot
                logger.info(f"[CHECKPOINT] 从数据库加载（文件不存在）")

                # 可选：将数据库中的数据同步到文件系统（使用工作流目录）
                if snapshot:
                    try:
                        workflow_dir_sync = self._get_workflow_directory(task_id, user_uuid, create_if_missing=True)
                        state_file_sync = workflow_dir_sync / "state.json"
                        self._atomic_write(state_file_sync, snapshot)
                        logger.info(f"[CHECKPOINT] 已将数据库快照同步到文件系统: {state_file_sync}")
                    except Exception as sync_error:
                        logger.warning(f"同步到文件系统失败: {sync_error}")
            
            if snapshot:
                
                # 获取预处理文件和使用情况
                preprocessed_files = snapshot.get("preprocessed_files")
                origin_images = snapshot.get("origin_images", [])
                usage = snapshot.get("usage")
                
                action_history = snapshot.get("action_history", [])
                
                # 从snapshot中提取原始task_goal
                # 优先使用_original_task_goal，如果没有则使用task_goal
                original_task_goal = snapshot.get("_original_task_goal")
                if not original_task_goal:
                    original_task_goal = snapshot.get("task_goal")
                
                # 如果都没有，说明快照不完整（可能是新任务）
                if not original_task_goal:
                    logger.debug(f"[CHECKPOINT] 快照中没有task_goal - task_id: {task_id}")
                    return None

                loaded_state = RuntimeState(
                    task_goal=original_task_goal,
                    preprocessed_files=preprocessed_files,
                    origin_images=origin_images,
                    usage=usage,
                    action_history=action_history
                )
                
                # 确保 action_history 的嵌套列表结构
                if not loaded_state.action_history:
                    # 空列表：初始化为包含一个空子列表
                    loaded_state.action_history = [[]]
                    logger.info("[CHECKPOINT] 初始化 action_history 为嵌套列表结构 [[]]")
                else:
                    # 验证格式
                    if not isinstance(loaded_state.action_history[0], list):
                        # 检测到扁平结构，视为不合法
                        logger.error(f"[CHECKPOINT] 加载时检测到不合法的扁平 action_history 结构")
                        # 强制转换为嵌套格式（容错处理）
                        if all(isinstance(item, dict) for item in loaded_state.action_history):
                            logger.warning("[CHECKPOINT] 将扁平结构强制转换为嵌套格式")
                            loaded_state.action_history = [loaded_state.action_history]
                        else:
                            raise ValueError("action_history 格式不合法，必须是嵌套列表格式")
                    
                    # 为新任务追加空列表（如果最后一个子列表不为空）
                    if loaded_state.action_history[-1]:
                        loaded_state.action_history.append([])
                        logger.info("[CHECKPOINT] 为新任务追加空列表到 action_history")
                
                # 恢复TODO任务清单
                if "todo" in snapshot:
                    loaded_state.todo = snapshot["todo"]
                    if loaded_state.todo:
                        logger.info(f"[CHECKPOINT] 恢复了 {len(loaded_state.todo)} 个TODO任务")
                        # 统计完成情况
                        completed_count = sum(1 for t in loaded_state.todo if t.get('status') == 'completed')
                        logger.info(f"[CHECKPOINT] TODO进度: {completed_count}/{len(loaded_state.todo)}")
                
                
                if "full_action_data" in snapshot:
                    loaded_state.full_action_data = snapshot["full_action_data"]
                
                logger.info(f"[CHECKPOINT] 状态加载完成 - task_id: {task_id}, session: {session_uuid}")
                return loaded_state
            
            logger.info(f"[CHECKPOINT] 没有找到快照 - task_id: {task_id}")
            return None
        except AgentTask.DoesNotExist:
            logger.warning(f"[CHECKPOINT] AgentTask不存在 - task_id: {task_id}")
            return None
        except KeyError as e:
            # 对于新任务，快照中可能没有task_goal等字段，这是正常的
            logger.debug(f"[CHECKPOINT] 快照字段缺失（新任务） - task_id {task_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"[CHECKPOINT] 加载失败 - task_id {task_id}: {e}")
            return None

    # ==================== 增强的工作流状态持久化方法 ====================
    # 以下方法实现带时间戳的工作流目录和步骤文件保存功能
    # 功能分支: 002-agentic-uuid-yyyymmdd

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
                logger.warning(f"[CHECKPOINT] 工作流目录已存在: {workflow_dir}")
                return workflow_dir

            # 创建工作流目录
            workflow_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[CHECKPOINT] 创建工作流目录: {workflow_dir}")

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
                logger.info(f"[CHECKPOINT] 初始化 metadata.json: {metadata_path}")
            else:
                logger.warning(f"[CHECKPOINT] metadata.json 初始化失败，但目录已创建")

            return workflow_dir

        except Exception as e:
            logger.error(f"[CHECKPOINT] 创建工作流目录失败 - task_id: {task_id}, error: {e}")
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
            bool: 保存成功返回 True,失败返回 False

        异常:
            ValueError: 如果 node_type 不合法,或 call_tool/output 节点缺少 tool_name
            IOError: 如果文件写入失败(权限、磁盘空间等)
        """
        try:
            # 验证 node_type 合法性
            valid_node_types = ["planner", "call_tool", "reflection", "output"]
            if node_type not in valid_node_types:
                raise ValueError(f"无效的 node_type: {node_type}, 必须是 {valid_node_types} 之一")

            # 验证 tool_name 必填性（对于特定节点类型）
            if node_type in ["call_tool", "output"] and not tool_name:
                raise ValueError(f"{node_type} 节点必须提供 tool_name")

            # 获取工作流目录
            workflow_dir = self.get_workflow_directory(task_id)
            if not workflow_dir:
                logger.error(f"[CHECKPOINT] 找不到工作流目录 - task_id: {task_id}")
                return False

            # 生成标准化文件名
            if node_type == "planner":
                filename = f"{step_number}_planner.json"
            elif node_type == "call_tool":
                sanitized_tool = self._sanitize_tool_name(tool_name)
                filename = f"{step_number}_call_tool_{sanitized_tool}.json"
            elif node_type == "reflection":
                filename = f"{step_number}_reflection.json"
            elif node_type == "output":
                if tool_name:
                    sanitized_tool = self._sanitize_tool_name(tool_name)
                    filename = f"{step_number}_output_{sanitized_tool}.json"
                else:
                    filename = f"{step_number}_output.json"

            # 构建文件路径
            step_file_path = workflow_dir / filename

            # 序列化节点输出
            serialized_data = self._serialize_output(node_output)

            # 使用原子写入保存文件
            if not self._atomic_write(step_file_path, serialized_data):
                logger.error(f"[CHECKPOINT] 保存步骤文件失败 - {step_file_path}")
                return False

            logger.info(f"[CHECKPOINT] 保存步骤文件: {filename} (type: {node_type}, step: {step_number})")

            # 更新 metadata.json 统计信息
            self._update_metadata(workflow_dir, node_type)

            return True

        except Exception as e:
            logger.error(f"[CHECKPOINT] save_step 失败 - task_id: {task_id}, step: {step_number}, error: {e}")
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
        import re
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
                logger.warning(f"[CHECKPOINT] metadata.json 不存在: {metadata_path}")
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
                logger.debug(f"[CHECKPOINT] 更新 metadata: total_steps={metadata['total_steps']}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"[CHECKPOINT] 更新 metadata 失败: {e}")
            return False

    def load_with_fallback(self, task_id: str) -> Optional[RuntimeState]:
        """
        使用降级策略加载状态。

        功能描述:
        - 按优先级尝试多个加载路径
        - 支持向后兼容旧格式检查点
        - 可选地将数据库状态同步到文件系统

        加载顺序:
        1. 带时间戳目录的 state.json (新格式)
        2. 旧格式 UUID 目录的 state.json (向后兼容)
        3. 数据库 AgentTask.state_snapshot 字段 (最终降级)

        参数:
            task_id (str): 任务唯一标识

        返回:
            Optional[RuntimeState]: 成功返回状态对象,失败返回 None
        """
        try:
            agent_task = AgentTask.objects.get(task_id=task_id)
            user_uuid = str(agent_task.user.id) if agent_task.user else "anonymous"
            session_uuid = str(agent_task.session_id) if agent_task.session_id else task_id
            session_path = self._get_session_path(user_uuid, session_uuid)
            snapshot = None
            load_source = None

            # 路径 1: 带时间戳目录（优先）
            timestamped_dirs = list(session_path.glob(f"*_{task_id}"))
            if timestamped_dirs:
                # 按时间戳排序，选择最新的
                timestamped_dirs.sort(reverse=True)
                state_file = timestamped_dirs[0] / "state.json"
                if state_file.exists():
                    try:
                        with open(state_file, 'r') as f:
                            portalocker.lock(f, portalocker.LockFlags.SHARED)
                            snapshot = json.load(f)
                            portalocker.unlock(f)
                        load_source = "timestamped_directory"
                        logger.info(f"[CHECKPOINT] 从带时间戳目录加载: {state_file}")
                    except Exception as e:
                        logger.warning(f"[CHECKPOINT] 带时间戳目录加载失败: {e}")

            # 路径 2: 旧格式目录（向后兼容）
            if snapshot is None:
                old_format_dir = session_path / task_id
                state_file = old_format_dir / "state.json"
                if state_file.exists():
                    try:
                        with open(state_file, 'r') as f:
                            portalocker.lock(f, portalocker.LockFlags.SHARED)
                            snapshot = json.load(f)
                            portalocker.unlock(f)
                        load_source = "old_format_directory"
                        logger.info(f"[CHECKPOINT] 从旧格式目录加载: {state_file}")
                    except Exception as e:
                        logger.warning(f"[CHECKPOINT] 旧格式目录加载失败: {e}")

            # 路径 3: 数据库备份（最终降级）
            if snapshot is None and agent_task.state_snapshot:
                snapshot = agent_task.state_snapshot
                load_source = "database"
                logger.info(f"[CHECKPOINT] 从数据库加载")

            # 如果成功加载，反序列化为 RuntimeState
            if snapshot:
                # 使用现有的反序列化逻辑
                loaded_state = RuntimeState(
                    task_goal=snapshot.get("task_goal", ""),
                    action_history=snapshot.get("action_history", [[]]),
                    preprocessed_files=snapshot.get("preprocessed_files", {}),
                    origin_images=snapshot.get("origin_images", []),
                    usage=snapshot.get("usage", {}),
                    todo=snapshot.get("todo", []),
                    full_action_data=snapshot.get("full_action_data", {})
                )

                logger.info(f"[CHECKPOINT] 状态加载成功 (source: {load_source}) - task_id: {task_id}")
                return loaded_state

            logger.info(f"[CHECKPOINT] 没有找到快照 - task_id: {task_id}")
            return None

        except AgentTask.DoesNotExist:
            logger.warning(f"[CHECKPOINT] AgentTask不存在 - task_id: {task_id}")
            return None
        except Exception as e:
            logger.error(f"[CHECKPOINT] load_with_fallback 失败 - task_id {task_id}: {e}")
            return None

    def get_workflow_directory(self, task_id: str) -> Optional[Path]:
        """
        获取任务的工作流目录路径（辅助方法）。

        功能描述:
        - 查找任务对应的工作流目录
        - 优先返回带时间戳的新格式目录
        - 降级到旧格式目录

        参数:
            task_id (str): 任务唯一标识

        返回:
            Optional[Path]: 找到目录返回路径,否则返回 None
        """
        try:
            agent_task = AgentTask.objects.get(task_id=task_id)
            user_uuid = str(agent_task.user.id) if agent_task.user else "anonymous"
            session_uuid = str(agent_task.session_id) if agent_task.session_id else task_id
            session_path = self._get_session_path(user_uuid, session_uuid)

            # 优先查找带时间戳目录
            timestamped_dirs = list(session_path.glob(f"*_{task_id}"))
            if timestamped_dirs:
                # 按时间戳排序，选择最新的
                timestamped_dirs.sort(reverse=True)
                logger.debug(f"[CHECKPOINT] 找到带时间戳目录: {timestamped_dirs[0]}")
                return timestamped_dirs[0]

            # 降级到旧格式目录
            old_format_dir = session_path / task_id
            if old_format_dir.exists():
                logger.debug(f"[CHECKPOINT] 找到旧格式目录: {old_format_dir}")
                return old_format_dir

            logger.debug(f"[CHECKPOINT] 未找到工作流目录 - task_id: {task_id}")
            return None

        except AgentTask.DoesNotExist:
            logger.warning(f"[CHECKPOINT] AgentTask不存在 - task_id: {task_id}")
            return None
        except Exception as e:
            logger.error(f"[CHECKPOINT] get_workflow_directory 失败 - task_id: {task_id}, error: {e}")
            return None

    def list_step_files(self, task_id: str) -> list:
        """
        列出任务的所有步骤文件信息（辅助方法）。

        功能描述:
        - 获取工作流目录下的所有步骤文件
        - 返回文件元数据(步骤号、节点类型、工具名称、文件路径)
        - 按步骤号排序

        参数:
            task_id (str): 任务唯一标识

        返回:
            list: 步骤文件信息列表,每个元素包含:
                - step_number (int): 步骤号
                - node_type (str): 节点类型
                - tool_name (Optional[str]): 工具名称
                - file_path (str): 文件路径
                - file_size (int): 文件大小(字节)
        """
        try:
            workflow_dir = self.get_workflow_directory(task_id)
            if not workflow_dir:
                logger.warning(f"[CHECKPOINT] 找不到工作流目录 - task_id: {task_id}")
                return []

            # 查找所有步骤文件（排除 state.json 和 metadata.json）
            step_files = []
            for file_path in workflow_dir.glob("*_*.json"):
                if file_path.name in ["state.json", "metadata.json"]:
                    continue

                try:
                    # 从文件名解析元数据
                    parts = file_path.stem.split('_')
                    step_number = int(parts[0])
                    node_type = parts[1] if len(parts) > 1 else "unknown"
                    tool_name = '_'.join(parts[2:]) if len(parts) > 2 else None

                    # 获取文件大小
                    file_size = file_path.stat().st_size

                    step_files.append({
                        "step_number": step_number,
                        "node_type": node_type,
                        "tool_name": tool_name,
                        "file_path": str(file_path),
                        "file_size": file_size
                    })

                except Exception as e:
                    logger.warning(f"[CHECKPOINT] 解析步骤文件失败: {file_path}, error: {e}")
                    continue

            # 按步骤号排序
            step_files.sort(key=lambda x: x["step_number"])

            logger.debug(f"[CHECKPOINT] 找到 {len(step_files)} 个步骤文件 - task_id: {task_id}")
            return step_files

        except Exception as e:
            logger.error(f"[CHECKPOINT] list_step_files 失败 - task_id: {task_id}, error: {e}")
            return []