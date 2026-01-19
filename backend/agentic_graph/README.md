# Agentic Graph

新的 Graph 处理引擎，与原 agentic 应用隔离。

## 目录结构

```
agentic_graph/
├── core/           # 核心模块：RuntimeState、Graph、Node、Edge 等
├── services/       # 服务层：Processor、Executor、Checkpoint 等
├── utils/          # 工具函数：数据转换、验证、辅助功能等
├── outputs/        # 输出工具：各种 output 类型的工具实现
├── models.py       # 数据模型
├── views.py        # API 视图
├── urls.py         # URL 路由
├── apps.py         # 应用配置
└── tests.py        # 单元测试
```

## 设计原则

1. **状态中心化**：所有数据通过 RuntimeState 传递
2. **节点单一职责**：每个节点只修改 state，不输出自定义数据结构  
3. **处理器简化**：Processor 只负责传递，不处理数据
4. **数据流明确**：action_history 记录完整执行历史和上下文

## 与原 agentic 应用的关系

- 独立的应用，不依赖原 agentic 的代码
- 可以复用 tools 应用中的工具
- 共享数据库，但使用独立的表结构
- 逐步迁移，平滑过渡