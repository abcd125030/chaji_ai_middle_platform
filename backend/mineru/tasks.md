# MinerU 任务（Celery）

## 文件定位
- 路径：`d:\my_github\chaji_ai_middle_platform\backend\mineru\tasks.py`
- 作用：定义与 MinerU 文档解析相关的 Celery 异步任务，包括解析执行、过期清理、卡住任务检测与重置

## 核心任务：文档解析
- 定义：`process_document_task(self, task_id: str)`（`backend/mineru/tasks.py:15–64`）
- 触发方式：视图在创建任务后通过 `process_document_task.delay(str(task.task_id))` 投递到队列（参考 `backend/mineru/views.py:79`, `backend/mineru/views.py:231`）
- 执行流程：
  - 加载任务并标记为 `processing`（`backend/mineru/tasks.py:22–26`）
  - 读取原始文件字节：
    - 如果 `task.file_path` 是相对路径，组合 `settings.MEDIA_ROOT` 得到绝对路径（`backend/mineru/tasks.py:36–39`）
    - 未找到文件则抛 `FileNotFoundError`（`backend/mineru/tasks.py:40–45`）
  - 交给优化服务 `OptimizedMinerUService.process_document(task, file_bytes)` 处理（`backend/mineru/tasks.py:55–58`）
    - 优化服务内部负责调用 MinerU、写结果、可能上传到 OSS，并更新数据库
  - 成功返回包含 `task_id`、`status=completed` 与 `result` 的字典（`backend/mineru/tasks.py:60–64`）
- 错误处理与重试：
  - 捕获异常后将任务状态更新为 `failed` 并记录 `error_message`（`backend/mineru/tasks.py:70–79`）
  - 支持最多 3 次重试，使用按次增加的延迟：`countdown = 60 * (retries + 1)`（`backend/mineru/tasks.py:83–85`）
  - 任务不存在会记录错误并抛出（`backend/mineru/tasks.py:66–68`）
- 日志与配置：
  - 使用 `logger = logging.getLogger('django')` 输出关键日志（`backend/mineru/tasks.py:12`）
  - 读取 `settings.MINERU_SETTINGS.get('USE_OSS', False)` 仅用于日志提示，具体 OSS 读写由优化服务负责（`backend/mineru/tasks.py:30–33`）

## 辅助任务：定期清理
- 定义：`cleanup_old_files_task()`（`backend/mineru/tasks.py:90–127`）
- 目标：清理 30 天前状态为 `completed` 或 `failed` 的旧任务（`backend/mineru/tasks.py:96–101`）
- 清理动作：
  - 删除上传文件（本地路径存在时）（`backend/mineru/tasks.py:107–110`）
  - 删除本地输出目录（`backend/mineru/tasks.py:112–114`）
  - 删除任务记录（`backend/mineru/tasks.py:115–118`）
- 返回：清理数量，并记录日志（`backend/mineru/tasks.py:122–124`）
- 说明：该清理逻辑面向本地文件；若采用 OSS，优化版服务有专属清理机制（参见 `backend/mineru/services/optimized_service.py`）

## 辅助任务：卡住任务检测
- 定义：`check_stuck_tasks()`（`backend/mineru/tasks.py:130–162`）
- 目标：找出超过 1 小时仍为 `processing` 且未更新的任务（`backend/mineru/tasks.py:136–141`）
- 处理：
  - 将其状态重置为 `pending` 并填写提示信息（`backend/mineru/tasks.py:148–151`）
  - 重新提交到解析队列（`backend/mineru/tasks.py:153–155`）
- 产出：记录重置数量与相关日志（`backend/mineru/tasks.py:157`）

## 状态流转与数据模型
- 使用的状态：`pending` → `processing` → `completed` 或 `failed`
- 模型：
  - 任务模型 `PDFParseTask`（`backend/mineru/models.py`），在解析成功时由服务层补充 `output_dir`、`processing_time`、`completed_at`、`text_preview` 等
  - 结果模型 `ParseResult`，由优化服务在成功解析时创建并存储结果路径或 OSS 键（参见 `backend/mineru/services/optimized_service.py:270–301`）

## 与优化服务的协作
- 此处任务统一使用 `OptimizedMinerUService`（`backend/mineru/tasks.py:55–58`）
  - 优势：支持 OSS 存储、缓存命中（避免重复解析）、更完善的结果统计与清理
  - 本地路径读取由任务完成，后续存储/上传交由服务层处理

## 调度与运维建议
- 使用 Celery Beat 定时触发：
  - 每日运行 `cleanup_old_files_task` 做存储回收
  - 每 10–30 分钟运行一次 `check_stuck_tasks` 保持任务队列健康
- 监控与告警：
  - 收集 `failed` 任务的 `error_message` 做异常统计
  - 关注重试次数达到上限后仍失败的任务，进行人工排查（文件缺失、CLI 超时、模型不可用等）