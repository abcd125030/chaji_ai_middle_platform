# RuntimeState 重构方案
日期：2025-09-16

## 重构目标
将RuntimeState从累积式数据记录模式转向结构化状态管理模式，使数据流更清晰、节点职责更明确。

## 新数据结构定义

```python
class RuntimeStateV2:
    # === 背景信息区 ===
    prompt: str                     # 用户原始消息
    user_context: Dict              # 用户上下文（从DB初始化）
    memory: List[Dict]              # 向量检索的相关历史
    origin_files: List[Dict]        # 原始文件元信息
    preprocessed_files: Dict        # 预处理后的文件数据
    chat_history: List[Dict]        # 历史对话记录
    
    # === 意图理解区 ===
    task_goal: str                  # 分析后的任务目标
    场景: str                       # 识别的场景类型
    输出风格: str                   # 期望的输出风格
    output_structure: List[Dict]    # 预期输出结构
    
    # === 执行过程区 ===
    action_history: List[Dict]      # 执行历史（新结构）
    todo: List[Dict]               # 任务清单
    contexts: List[Dict]           # 输出上下文累积
    
    # === 统计信息区 ===
    usage: Dict[str, int]          # Token使用统计
```

## action_history 新结构
```python
{
    "node": str,              # 执行节点名称
    "preparation": Dict,      # 节点准备工作数据
    "summary": str,          # 执行摘要
    "result": Dict,          # 完整结果数据
    "importance": str,       # 对最终输出的重要性 (high/medium/low)
    "usage": {               # 本次执行的token消耗
        "prompt_tokens": int,
        "completion_tokens": int
    },
    "next": List[str]        # 下一步节点列表
}
```

## origin_files 结构
```python
{
    "name": str,             # 文件名
    "type": str,             # 文件类型
    "size": int,             # 文件大小
    "mapping": {             # 对象存储信息
        "provider": str,     # aliyun|tencent|aws|gcc
        "path": str,         # 存储路径
        "public": str        # 公开链接（可选）
    }
}
```

## contexts 结构
```python
{
    "tool_name": str,        # 生成工具名
    "type": str,            # text|image
    "content": str,         # 内容（图片为base64）
    "important": bool,      # 重要性标记
    "usage_type": str,      # refactor|modify|reference
    "mapping": Dict         # 对象存储信息（同origin_files）
}
```

## 迁移计划

### 第一阶段：数据结构扩展（向后兼容）
1. 在RuntimeState中添加新字段，保留旧字段
2. 创建适配器层处理新旧格式转换
3. 逐步迁移各节点使用新字段

### 第二阶段：节点逻辑优化
1. **Planner节点**：
   - 分析生成task_goal、场景、output_structure
   - 设置action_history的next字段指导流程
   
2. **Tool节点**：
   - 只读取必要的state字段
   - 结果写入contexts而非action_history
   - 固定next为["reflection"]
   
3. **Reflection节点**：
   - 评估contexts的重要性
   - 决定是否需要继续执行
   - 更新todo状态

### 第三阶段：处理器简化
```python
class GraphProcessorV2:
    def run(self, state: RuntimeStateV2):
        while not self.is_complete(state):
            # 从最后一个action_history获取next
            next_nodes = state.action_history[-1]["next"] 
            
            for node_name in next_nodes:
                # 执行节点，节点内部处理所有逻辑
                state = self.nodes[node_name](state)
        
        # 最终输出生成
        return self.output_generator(state)
```

## 影响范围评估

### 需要修改的核心文件
1. `backend/agentic/schemas.py` - RuntimeState类定义
2. `backend/agentic/processor.py` - GraphExecutor逻辑
3. `backend/agentic/nodes/*.py` - 所有节点实现
4. `backend/agentic/tools/*.py` - 工具的state访问
5. `backend/agentic/chain_components/*.py` - 链组件

### API兼容性
- 需要版本标记区分v1/v2格式
- 提供迁移工具转换历史数据
- WebSocket消息格式可能需要调整

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 数据迁移失败 | 历史任务无法恢复 | 保留旧格式读取能力，渐进式迁移 |
| 内存增长 | 性能下降 | 实施数据压缩和清理策略 |
| 节点改造复杂 | 开发周期长 | 分批次改造，先改造核心节点 |

## 实施时间线
- **Week 1**: 数据结构设计评审和确认
- **Week 2-3**: 第一阶段实施（向后兼容）
- **Week 4-5**: 第二阶段节点改造
- **Week 6**: 第三阶段处理器优化
- **Week 7**: 测试和问题修复
- **Week 8**: 灰度发布

## 结论
这个重构方案将使整个agentic系统的数据流更清晰、可维护性更强。虽然短期内需要较大的改造成本，但长期来看将大幅简化系统复杂度，提高开发效率。