# MinerU 视图（Views）

## 定位与作用
- 文件：`backend/mineru/views.py`
- 定义一个 `ModelViewSet` 和一个函数式视图，提供 MinerU 文档解析的完整 REST 接口（任务创建、状态查询、结果下载、重处理、Base64 创建）
- 异步处理通过队列提交到后台任务系统（Celery）

## 权限与解析器
- 权限：所有接口要求认证，`permission_classes = [IsAuthenticated]`（`backend/mineru/views.py:26`, `backend/mineru/views.py:194`）
- 解析器：
  - 视图集级别：`parser_classes = (MultiPartParser, FormParser, JSONParser)`（`backend/mineru/views.py:27`）
  - `upload` 动作覆盖为仅接收表单/文件：`@action(..., parser_classes=[MultiPartParser, FormParser])`（`backend/mineru/views.py:39`）

## 查询与序列化器选择
- 查询集：仅返回当前用户自己的任务，`get_queryset` 过滤 `user=self.request.user`（`backend/mineru/views.py:29–31`）
- 序列化器选择：
  - 列表动作使用精简版 `TaskListSerializer`（`backend/mineru/views.py:33–37`）
  - 其他动作默认使用详细版 `PDFParseTaskSerializer`

## 接口映射（DRF 路由）
- `POST /api/mineru/tasks/upload/` → 上传文件创建任务（`upload`，`backend/mineru/views.py:39–85`）
- `GET /api/mineru/tasks/` → 列表（`list`，由 `ModelViewSet` 提供）
- `GET /api/mineru/tasks/{id}/` → 详情（`retrieve`，由 `ModelViewSet` 提供）
- `GET /api/mineru/tasks/{id}/status/` → 查询任务状态（`status`，`backend/mineru/views.py:93–129`）
- `GET /api/mineru/tasks/{id}/download/?type=markdown|json` → 下载结果（`download`，`backend/mineru/views.py:130–163`）
- `POST /api/mineru/tasks/{id}/reprocess/` → 重新处理（`reprocess`，`backend/mineru/views.py:165–190`）
- `POST /api/mineru/create-from-base64/` → 通过 Base64 创建任务（函数式视图，`backend/mineru/views.py:193–237`）
- 路由前缀 `'/api/mineru/'` 来自项目总路由配置（`backend/backend/urls.py:23`）

## 处理流程（关键动作）
- 上传文件创建任务（`upload`）
  - 使用 `FileUploadSerializer` 校验请求（`backend/mineru/views.py:42–48`）
  - 读取文件字节并调用 `MinerUService.validate_file` 验证类型/大小（`backend/mineru/views.py:51–58`）
  - 创建 `PDFParseTask` 记录、`save_uploaded_file` 落盘并保存路径（`backend/mineru/views.py:60–76`）
  - 投递异步任务 `process_document_task.delay(...)`（`backend/mineru/views.py:79`）
  - 返回任务的序列化结果（`backend/mineru/views.py:81–84`）
- Base64 创建任务（`create_task_from_base64`）
  - 解析与校验请求体（`backend/mineru/views.py:197–211`）
  - 创建任务、保存文件、投递异步任务（`backend/mineru/views.py:212–232`）
  - 返回任务数据（`backend/mineru/views.py:233–236`）
- 状态查询（`status`）
  - 计算并返回进度与提示消息；完成时附带 `ParseResult`（`backend/mineru/views.py:93–129`）
- 结果下载（`download`）
  - 仅在任务 `completed` 时允许，按 `type` 返回 Markdown 或 JSON 文件（`backend/mineru/views.py:135–151`）
- 重新处理（`reprocess`）
  - 阻止正在处理中的任务重入（`backend/mineru/views.py:170–174`）
  - 重置状态、清理旧结果并重新投递（`backend/mineru/views.py:176–190`）

## 错误与返回
- 参数错误返回 `400`（如序列化器校验失败、文件类型不支持）
- 处理异常返回 `500`（上传/解析过程中的非预期异常）
- 下载阶段找不到文件抛 `404`（`backend/mineru/views.py:152–163`）

## 与后端任务和服务的关系
- 异步处理由 Celery 任务 `process_document_task` 执行，调用优化版服务进行真实解析与入库（`backend/mineru/views.py:18`, 参见 `backend/mineru/tasks.py:55–58`）
- 同步路径中仅做校验与落盘，解析不在请求线程内完成，提高响应速度与稳定性

## 注意点
- 下载接口当前按本地文件路径读取并返回；若启用 OSS 存储并将 `ParseResult` 路径保存为 URL，需要在下载逻辑中适配存储类型，或提供直链下载（现有逻辑假设本地路径可读）
- 列表动作使用精简序列化器，详情动作返回完整字段，这是典型的 REST 输出优化策略