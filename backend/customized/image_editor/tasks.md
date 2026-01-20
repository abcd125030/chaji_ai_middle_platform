用途概述

- 承载图片编辑流程的核心异步任务，包括配置重载、结果文件读写、任务回调（即时/批量）与任务处理编排
- 集成缓存、数据库批量写入与基于 Redis 的回调队列，提升在高并发下的稳健性与观测性
主要任务与函数

- reload_worker_config （ backend/customized/image_editor/tasks.py:25–38 ）
  - Celery 任务名 image_editor.reload_worker_config
  - 在每个 worker 中清除并重新加载图片编辑配置，确保配置更新快速传播
- save_image_to_file （ backend/customized/image_editor/tasks.py:40–125 ）
  - 将 base64 图片保存到 MEDIA_ROOT/image_editor/ ，并按较小边等比缩放到基准 350 ，非 PNG 自动转为 RGB
  - 返回相对路径与“调整后”的 base64 ，便于回调或后续处理
- load_image_from_file （ backend/customized/image_editor/tasks.py:127–152 ）
  - 从 MEDIA_ROOT 读取文件并编码为 base64 ，用于在成功回调时传递文件内容
  - 包含路径不存在与异常的日志记录
- execute_callback （ backend/customized/image_editor/tasks.py:154–174, 176–261 ）
  - 按配置决定使用“批量回调”或“立即回调”；缺少 callback_url 则更新状态为 not_required
  - 成功任务优先用文件内容（若存在），失败任务包含错误详情与完成时间
  - 批量模式：将回调数据写入 Redis 全局队列，并输出队列统计
  - 失败或不启用批量模式时，降级为“立即回调”
- _send_immediate_callback （ backend/customized/image_editor/tasks.py:275–354 ）
  - 即时发送成功/失败回调，记录尝试次数、发生时间、响应码与错误信息
  - 通过 db_optimizer （批量写入优化器）更新数据库中的回调相关字段，并强制刷新
- process_image_edit_task （ backend/customized/image_editor/tasks.py:355–? ）
  - 处理单个图片编辑任务：支持传入 task_id （从数据库获取）或完整任务字典（避免数据库读）
  - 以 started_at 为计时起点，初始化各阶段字段；中间状态的数据库写入被注释，仅在最终成功/失败时写入
  - 下游逻辑通常包括图片验证、宠物检测、文生图生成、背景移除与最终回调（具体实现未完整展示）
关键集成点


- 数据库批量写入优化器（ db_optimizer ， backend/customized/image_editor/tasks.py:15 ）
  - 用于合并更新与限流，减少高并发下数据库压力
- 配置管理器（ config_manager ， backend/customized/image_editor/tasks.py:16 ）
  - 提供配置重载与缓存管理能力，配合 reload_worker_config 完成多进程一致性
- 回调封装（ AICallback ， backend/customized/image_editor/tasks.py:13, 290–303 ）
  - 根据 callback_url 选择环境与密钥，统一构造成功/失败的回调载荷并发送
回调策略与可靠性

- 批量回调：将回调写入 Redis 队列，由独立任务批量分散发送，避免洪峰（配合 tasks_batch.py ）
- 即时回调：直接发送并记录详细状态，失败时按需重试或标记
- 队列观测：批量模式下输出队列 pending/processing 统计，便于调优（ backend/customized/image_editor/tasks.py:250–254 ）
日志与观测

- 关键步骤均记录 INFO/DEBUG/ERROR 日志：图片尺寸调整、文件读写、回调发送、失败原因、耗时（如 callback_duration ）
- 便于线下复现与线上告警，建议结合日志检索与指标上报使用
使用与运行（Windows）

- 启动 Celery worker（默认队列 celery ）：
  - ```
    celery -A backend worker -l info 
    -Q celery
    ```
- 启动 Celery Beat（用于周期性触发批量检查与清理）：
  - ```
    celery -A backend beat -l info
    ```
- 手动触发配置重载（示例）：
  - 在 Django Shell 中：
    ```
    python manage.py shell
    ```
    ```
    from customized.image_editor.
    tasks import reload_worker_config
    reload_worker_config.delay
    (config_name="default")
    ```
注意事项

- MEDIA_ROOT 配置：文件读写依赖 settings.MEDIA_ROOT ，请确保在目标环境正确设置
- 幂等与一致性：批量写入优化器为兼容代理不使用事务，跨多字段更新的原子性要求需另行设计（如版本号/条件更新）
- 回调负载大小：成功回调包含图片 base64 或文件内容，注意外部服务的接收限制与网络带宽
- 批量/即时模式切换：通过 BATCH_CALLBACK_CONFIG.ENABLED 控制，失败任务在批量模式下仍可优先发送
