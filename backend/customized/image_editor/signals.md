# 用途概述

- 监听并响应 `ImageEditorConfig` 的保存事件（`post_save`），在配置变更后触发刷新与通知
- 清除 Django 进程中的配置缓存，并向所有 Celery worker 广播“重新加载配置”的任务
- 记录操作日志，便于审计与问题排查

## 加载与触发

- 加载时机：应用启动后在 `AppConfig.ready()` 中导入该模块，注册信号接收器（`backend/customized/image_editor/apps.py:10`）
- 触发条件：任意 `ImageEditorConfig` 对象执行 `save()` 后触发 `post_save`，调用 `reload_config_on_save`（`backend/customized/image_editor/signals.py:12–16`）

## 处理流程

- 清除配置缓存：
  - 调用 `ConfigManager.clear_cache()` 清除 `image_editor` 相关缓存（`signals.py:18–21`；缓存实现见 `config_manager.py:78–92`）
- 广播重载任务：
  - 通过 `reload_worker_config.apply_async` 向队列 `celery` 发送任务，`expires=60` 避免过期任务执行（`signals.py:23–32`）
  - 记录任务 ID 与配置名，便于追踪（`signals.py:34`）
- 异常处理：
  - 捕获并记录错误日志，避免因单次失败中断主流程（`signals.py:36`）

## 关键点与依赖

- 信号注册正确性：使用模型类注册 `sender=ImageEditorConfig`，可正常触发（`signals.py:6, 12`）
- Celery 前置条件：需有运行中的 worker 监听 `celery` 队列；任务函数 `reload_worker_config` 在 `tasks` 中实现并被信号使用（`signals.py:25–32`）
- 管理后台关联：在 Admin 中编辑并保存 `ImageEditorConfig` 会触发信号（模型在 Admin 中注册，`backend/customized/image_editor/admin.py:362`）

## 验证方法

- 在管理后台保存一条 `ImageEditorConfig` 记录后，查看日志：
  - `配置 '<name>' 已更新，清除Django进程缓存`（`signals.py:21`）
  - `已发送配置重载任务到队列: task_id=..., config=<name>`（`signals.py:34`）
- 检查 Celery 队列与 worker 日志是否出现并执行重载任务

## 常见问题与建议

- 开发模式重复注册：Django 自动重载可能导致多次导入，必要时为接收器添加 `dispatch_uid` 防重复注册
- 队列名称与过期时间：确保 worker 监听 `celery` 队列；`expires=60` 适合快速传播的配置变更，可按延迟调整
- 缓存一致性：本信号清除 Django 进程缓存；Celery 端的配置缓存由重载任务负责刷新，两者配合保证一致性

## 总结

- 将“配置变更”转换为“缓存刷新 + 异步广播”的一致性工作流，确保 Web 进程与异步 Worker 在短时间内获得一致的图片编辑配置。