# 用途概述

- 管理“批量回调”发送的异步任务，避免高并发下集中推送引发的拥塞
- 通过分布式锁、节流与分散调度，将队列中的回调按批次有序发送到各自的 `callback_url`
- 提供周期性检查与卡住任务清理，提升整体回调的可靠性与可观测性

## 核心任务

- `trigger_batch_send`（`customized/image_editor/tasks_batch.py:13–73`）
  - 获取分布式发送锁，确保只有一个 worker 执行批量调度（`:24–26`）
  - 检查与遵守发送间隔，必要时等待（`:29–34`）
  - 获取一批回调并分散调度，每条以 `countdown` 延时创建独立的 `send_single_callback` 任务（`:35–59`）
  - 若队列仍有剩余，根据本批耗时和最小间隔再次触发下一批（`:60–67`）
- `send_single_callback`（`customized/image_editor/tasks_batch.py:75–135`）
  - 针对单条数据构造回调载荷并发送（依赖 `AICallback`，`:96–111`）
  - 成功则从 `PROCESSING_KEY` 队列移除并统计为 `sent`；失败会按递增 `countdown` 重试，最终失败则移除避免永久占用（`:113–135`）
- `check_and_flush_callbacks`（`customized/image_editor/tasks_batch.py:137–211`）
  - 周期性检查队列状态（建议由 Celery Beat 每几秒运行一次，`:144–149`）
  - 根据条件触发批量发送：达到批次大小、超过最大延迟、或中等规模等待较久（`:175–189`, `:190–198`）
- `cleanup_stuck_callbacks`（`customized/image_editor/tasks_batch.py:213–249`）
  - 定期扫描 `PROCESSING_KEY` 队列中超过 5 分钟的“卡住”任务，移除并重新入队以恢复处理（`:237–245`）

## 关键机制

- 分布式锁与节流：使用 Redis 实现发送锁与发送间隔控制，确保调度“单活”（`trigger_batch_send`，`...:24–34`）
- 分散调度与限速：每条回调间隔约 `200ms`，通过 `countdown` 分布到未来时刻，避免瞬时洪峰（`...:46–56`）
- 队列分层：使用 `QUEUE_KEY`（待发送）、`PROCESSING_KEY`（发送中）区分状态，避免重复与“幽灵任务”（`send_single_callback` 中移除/更新，`...:106–118, 132–135`）
- 重试策略：单条回调最多重试 2 次，`countdown` 按 `30*(retries+1)` 递增（`...:127–131`）
- 观测与日志：批量触发原因、队列长度与等待时长会记录日志，便于调优与排障（`...:169–198`）

## 依赖与集成

- 依赖 `callback_batcher_redis.get_redis_batcher()` 提供队列、锁与参数（如 `batch_size`、`max_delay`、`min_interval`）（`...:19–23, 61–66, 150–156`）
- 依赖 `AICallback` 封装回调载荷与发送逻辑，自动推断环境与密钥（`...:96–111`）
- 任务默认投递到 `queue='celery'`，如生产环境并发较大，建议考虑独立队列

## 适用场景

- 短时间内回调量突增，需要分批次、分散节流地对外推送
- 需要自动触发与恢复机制，减少人工干预与失败积压
- 多 worker 并行环境，需保证批量调度“单活”以避免重复

## 配置建议

- Celery Beat 调度（示例）：
  ```python
  'check-and-flush-callbacks': {
      'task': 'customized.image_editor.tasks_batch.check_and_flush_callbacks',
      'schedule': 3.0,
      'options': {'queue': 'celery'}
  }
  ```
- 队列隔离：大流量场景将批量回调任务迁移到专用队列（如 `callbacks`），提升可控性
- 速率与延迟：动态调整 `send_interval`（当前固定为 `0.2s`，`...:46`）、`batch_size` 与 `max_delay` 以适配不同流量

## 潜在优化点

- 自适应速率：根据队列长度与失败率调整 `send_interval` 与下一批 `countdown`
- 并发上限：对 `send_single_callback` 增加并发控制（例如队列并发、主机级限流）
- 指标上报：完善成功/失败、重试次数、平均延迟指标，便于监控与告警
- 错误分类：区分 `4xx/5xx/网络错误` 并采用不同重试或降级策略

## 总结

- 为“批量回调发送”提供稳健的任务编排与自恢复机制：锁定调度唯一性、分散限速发送、周期性自触发以及卡住任务的自动救治，在高并发环境中保持回调通道的稳定与可观测。