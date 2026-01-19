# TODO List - 2025-09-07

## TODO状态在会话延续中的智能管理

### 背景描述
当前系统在用户同一会话中发送新prompt时，会创建新的task但会丢失之前的TODO进度。虽然checkpoint能够保存和恢复TODO，但在`executor.py`的`_create_state_with_history`方法中没有合并历史TODO。同时，Planner通过`if not state.todo`判断是否生成新TODO的逻辑过于简单，无法区分用户是要继续之前的任务还是开始新任务。这导致用户体验不连续，可能重复执行已完成的任务或错误地沿用不相关的旧TODO。

### 环境背景
- 检查Django服务：`ps aux | grep "manage.py runserver"`
- 检查Celery：`ps aux | grep celery`
- PM2服务状态：`pm2 list`
- 数据库连接：PostgreSQL localhost:5432

### 任务清单
- [ ] 在RuntimeState中添加任务延续标记（is_continuation、todo_context等字段）
- [ ] 修改executor.py的_create_state_with_history方法，合并历史TODO
- [ ] 实现智能判断逻辑，识别用户意图（继续任务vs新任务）
- [ ] 更新checkpoint.py，确保新字段能够持久化和恢复
- [ ] 调整Planner节点逻辑，根据任务模式决定是否生成新TODO

### 相关文件

#### 需要阅读了解上下文的文件
- `/Users/chagee/Repos/X/backend/agentic/schemas.py:73` - RuntimeState类定义，todo字段
- `/Users/chagee/Repos/X/backend/agentic/executor.py:233-276` - _create_state_with_history方法
- `/Users/chagee/Repos/X/backend/agentic/executor.py:217-231` - _load_session_states方法
- `/Users/chagee/Repos/X/backend/agentic/graph_nodes.py:1213-1240` - Planner判断是否生成TODO的逻辑
- `/Users/chagee/Repos/X/backend/agentic/checkpoint.py:93-112` - save方法，TODO持久化
- `/Users/chagee/Repos/X/backend/agentic/checkpoint.py:155-162` - load方法，TODO恢复
- `/Users/chagee/Repos/X/backend/agentic/models.py` - AgentTask模型，session_task_history字段

#### 需要修改的文件
1. `/Users/chagee/Repos/X/backend/agentic/schemas.py`
   - RuntimeState类添加is_continuation和todo_context字段
   - 影响范围：中等

2. `/Users/chagee/Repos/X/backend/agentic/executor.py`
   - _create_state_with_history方法添加TODO合并逻辑
   - 添加智能判断函数determine_task_mode
   - 影响范围：高

3. `/Users/chagee/Repos/X/backend/agentic/checkpoint.py`
   - save和load方法支持新字段
   - 影响范围：低

4. `/Users/chagee/Repos/X/backend/agentic/graph_nodes.py`
   - planner_node调整TODO生成判断逻辑
   - 影响范围：中等

### 修改示例

#### 1. RuntimeState扩展
```python
# schemas.py
class RuntimeState:
    def __init__(self, task_goal: str, ..., is_continuation: bool = False):
        # ... 现有字段
        self.is_continuation: bool = is_continuation
        self.todo_context: Dict[str, Any] = {
            'original_goal': None,
            'created_at': None,
            'parent_task_id': None
        }
```

#### 2. 历史TODO合并
```python
# executor.py - _create_state_with_history方法
def _create_state_with_history(self, ...):
    # 合并TODO（取最新的）
    combined_todo = []
    latest_todo_context = {}
    for state in reversed(historical_states):
        if hasattr(state, 'todo') and state.todo:
            combined_todo = state.todo
            if hasattr(state, 'todo_context'):
                latest_todo_context = state.todo_context
            break
    
    # 判断是否继续任务
    is_continuation = self._determine_continuation(
        historical_states, new_goal, combined_todo
    )
    
    return RuntimeState(
        task_goal=enhanced_task_goal,
        preprocessed_files=preprocessed_files,
        todo=combined_todo if is_continuation else [],
        is_continuation=is_continuation,
        todo_context=latest_todo_context if is_continuation else {}
    )
```

#### 3. 智能判断函数
```python
# executor.py - 新增方法
def _determine_continuation(self, historical_states, new_goal, existing_todo):
    """判断是否为任务延续"""
    # 关键词检测
    continuation_keywords = ['继续', '接着', '剩余', '未完成', 'continue']
    if any(kw in new_goal.lower() for kw in continuation_keywords):
        return True
    
    # 检查TODO完成状态
    if existing_todo:
        incomplete = sum(1 for t in existing_todo if not t.get('completed', False))
        if incomplete > 0 and len(new_goal) < 50:  # 简短指令可能是继续
            return True
    
    return False
```

#### 4. Planner逻辑调整
```python
# graph_nodes.py - planner_node
if not state.todo and len(state.action_summaries) == 0:
    # 完全新任务，生成TODO
    needs_todo = True
elif state.todo and not state.is_continuation:
    # 有TODO但不是继续任务，可能需要新TODO
    all_completed = all(t.get('completed', False) for t in state.todo)
    needs_todo = all_completed
elif state.is_continuation:
    # 明确是继续任务，使用现有TODO
    needs_todo = False
    logger.info(f"[PLANNER] 继续执行现有TODO，剩余 {sum(1 for t in state.todo if not t.get('completed', False))} 个任务")
```

### 禁止事项
1. ❌ 不要改变现有的TODO数据结构（保持List[Dict[str, Any]]）
2. ❌ 不要影响不使用TODO的任务流程
3. ❌ 不要强制所有任务都必须有TODO
4. ❌ 不要改变checkpoint的基础序列化机制
5. ❌ 不要破坏向后兼容性（旧的snapshot应能正常加载）
6. ❌ 不要在判断逻辑中硬编码特定业务场景
7. ❌ 不要让is_continuation成为必需字段（使用默认值False）

### 测试要点
1. 新会话首次执行 → 生成新TODO
2. 用户说"继续" → 使用现有TODO
3. 用户提出完全不同的任务 → 生成新TODO
4. TODO全部完成后新请求 → 生成新TODO
5. 系统重启后恢复 → TODO和continuation状态正确恢复

### 风险评估
- **高风险**：判断逻辑误判可能导致错误的TODO使用
- **中风险**：性能影响（需要分析历史状态）
- **低风险**：向后兼容性（有默认值处理）

### 实施优先级
1. P0：基础TODO合并（防止丢失）- 2小时
2. P1：简单continuation判断 - 1小时
3. P2：智能判断优化 - 3小时
4. P3：用户提示确认机制 - 可选