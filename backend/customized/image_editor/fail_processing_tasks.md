# 用途概述

- 批量将状态为 `processing` 的图片编辑任务标记为 `failed`，用于清理卡住任务或系统异常后的恢复
- 支持直连 PostgreSQL 与通过 PgBouncer 的连接模式
- 执行前展示前 10 个待处理任务的关键信息并进行交互式确认，降低误操作风险

## 关键流程

- 连接配置与初始化（`fail_processing_tasks.py:16–23, 25–28`）：根据命令行参数或环境变量选择 PgBouncer（端口 `6432`），设置 `USE_PGBOUNCER` 和 `DB_PORT`，然后初始化 Django
- 数据查询与预览（`fail_processing_tasks.py:62–81`）：查询 `status='processing'` 的任务，统计数量并展示 `task_id`、`user`、`created_at`、`prompt` 等信息（最多 10 条）
- 安全确认（`fail_processing_tasks.py:83–87`）：通过 `input` 二次确认，仅当输入 `yes` 才继续
- 批量更新（`fail_processing_tasks.py:92–101`）：使用 ORM 一次性更新为 `failed`，并设置 `error_code='SYSTEM_TIMEOUT'`、`error_message`、`error_details` 及 `completed_at=timezone.now()`
- 缓存清理（可选，`fail_processing_tasks.py:109–131, 132–135`）：若存在 `TaskCacheManager`，逐个清理已失败任务的缓存键；异常与缺失会被忽略，不影响状态更新
- 结果统计（`fail_processing_tasks.py:140–149`）：打印当前 `processing`、`success`、`failed` 与 `total` 的数量

## 适用场景

- 队列或工作进程异常导致任务长时间停留在 `processing`
- 系统重启或故障恢复后，需要统一重置卡住的任务状态
- 维护窗口中将不可恢复的“处理中”任务明确标记失败以释放资源、保持一致性

## 运行方式（Windows）

- 直连数据库：
  ```bat
  python d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\fail_processing_tasks.py
  ```
- 使用 PgBouncer（命令行参数）：
  ```bat
  python d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\fail_processing_tasks.py --pgbouncer
  ```
- 使用 PgBouncer（环境变量）：
  ```bat
  set USE_PGBOUNCER=true
  python d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\fail_processing_tasks.py
  ```

## 安全提醒

- 操作不可逆：会把所有 `processing` 任务改为 `failed`，务必先确认数量与预览信息
- 建议在维护窗口执行，并做好数据库备份或先在测试环境验证
- 幂等性：已失败的任务不再匹配 `processing` 条件，重复执行不会二次处理