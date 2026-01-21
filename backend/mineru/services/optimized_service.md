# 优化版 MinerU 服务（OptimizedMinerUService）

## 定位与作用
- 文件：`backend/mineru/services/optimized_service.py`
- 目标：提供“生产化”的 MinerU 文档解析服务，集成 OSS 存储与结果缓存，统一完成解析执行、结果上报、数据库更新与资源清理（`d:\my_github\chaji_ai_middle_platform\backend\mineru\services\optimized_service.py:25`）

## 核心特性
- 存储适配与 OSS 集成：按需把原始文件与解析产物上传到 OSS，并以 URL/Key 形式保存到结果中（`services/optimized_service.py:71–79, 90–113`）
- 结果缓存：对同一文件（按哈希）命中缓存直接返回，处理时长记为 0 且不重复解析（`services/optimized_service.py:62–69, 129–156`）
- 完整的任务副作用：在服务内部更新 `PDFParseTask` 状态与统计，并创建 `ParseResult` 记录（`services/optimized_service.py:114–117, 270–301`）
- 自动清理：启用 OSS 时清空本地输出目录，避免磁盘膨胀（`services/optimized_service.py:108–113`）
- 与 CLI 解耦的封装：内部统一构建并调用 `mineru` 命令，兼容不同版本的参数风格（`services/optimized_service.py:168–216`）

## 处理流程（`process_document`）
- 初始化与缓存检查：获取存储适配器，生成文件哈希，检查是否有缓存（`services/optimized_service.py:58–66`）。命中缓存时直接更新任务为 `completed` 并创建结果记录（`services/optimized_service.py:129–156`）。
- 上传原始文件（可选）：`USE_OSS=True` 时先把上传文件存到 OSS，任务的 `file_path` 保存为 OSS Key（`services/optimized_service.py:70–79`）。
- 本地解析准备：基于扩展名创建临时文件，仅在处理过程中保存本地（`services/optimized_service.py:80–83, 158–166`）。
- 调用 MinerU 解析：构建命令并运行，记录耗时、输出与错误（`services/optimized_service.py:178–216`）。
- 上传解析结果（可选）：`USE_OSS=True` 时上传产物至 OSS，结果中添加 `markdown_url`、`json_url`、`files`、`urls` 等（`services/optimized_service.py:90–107`），并清理本地输出目录（`services/optimized_service.py:108–113`）。
- 更新任务与结果：标记 `completed`、写入 `processing_time`、`text_preview`、`output_dir`/URL 等，并创建 `ParseResult`（`services/optimized_service.py:114–117, 270–301`）。
- 异常处理：任何异常都会更新任务为 `failed` 并上报错误信息（`services/optimized_service.py:124–127, 303–307`），临时文件在 `finally` 分支中清理（`services/optimized_service.py:119–123`）。

## 命令调用差异
- 优化版构建命令：`mineru -p <temp_file> -o <output_dir> --method <parse_method>`（不含 `pdf` 子命令）（`services/optimized_service.py:178–184`）。
- 基础版 `MinerUService` 使用 `mineru pdf` 子命令（`backend/mineru/services.py:86–93`）。
- 注：不同 MinerU 版本支持不同参数风格；优化版注释中说明 v2.2 的表格合并与新模型会自动启用，无需额外参数（`services/optimized_service.py:186–189`）。

## 结果收集与统计
- 收集输出目录下的文件，提取 `markdown_path`/`json_path` 与预览内容（截取前 500 字符）（`services/optimized_service.py:218–268`）。
- 统计包括：文本块、图片数、表格数、跨页表格标记（`services/optimized_service.py:230–236, 257–262`）。

## 文件内容读取（API）
- `get_file_content(task, file_type='markdown'|'json')`：
  - OSS 模式：通过适配器下载文件并返回文本（`services/optimized_service.py:325–335`）。
  - 本地模式：直接读文件路径（`services/optimized_service.py:337–343`）。
  - 无结果或文件缺失会抛错（`services/optimized_service.py:320–321, 345`）。

## 与基础版的对比
- 基础版 `MinerUService.parse_document` 只做解析与结果字典返回，不更新数据库，也不包含 OSS 与缓存（`backend/mineru/services.py:52–141`）。
- 优化版 `OptimizedMinerUService.process_document` 完整地处理缓存、OSS、任务状态与结果入库，适合在 Celery 任务中统一调用（`backend/mineru/tasks.py:55–58`）。

## 在任务中的使用
- Celery 任务 `process_document_task` 直接调用优化版服务（`backend/mineru/tasks.py:55–58`）。
- 成功与失败的任务状态、重试与日志都在任务层完成，服务层确保解析与存储一致性。

## 配置依赖
- 读取 `settings.MINERU_SETTINGS`：
  - `USE_OSS` 控制是否上传到 OSS（默认 `True`）（`services/optimized_service.py:31–33`）。
  - `TEMP_DIR` 控制本地临时目录（`services/optimized_service.py:35–36`）。
- 存储适配器 `MinerUStorageAdapter` 提供 `generate_file_hash`、`check_cache`、`save_upload_file`、`save_parse_results` 等方法（`services/optimized_service.py:38–42, 62–73, 93–97`）。

## 注意与建议
- MinerU CLI 版本匹配：优化版不使用 `pdf` 子命令；若你的 MinerU 版本仅支持 `mineru pdf` 风格，可在 `_execute_mineru_parse` 中注入兼容（`services/optimized_service.py:178–184`）。
- 清理策略：开启 OSS 时本地输出会被删除；如需保留本地备份可在保存后跳过清理或改为延迟清理（`services/optimized_service.py:108–113`）。
- 统计口径：基于 Markdown 的简单计数，复杂版式可能需更精准的解析统计。
- Windows 路径：`TEMP_DIR` 默认 `/tmp/mineru`，在 Windows 环境建议改为如 `C:\\mineru\\tmp` 并在配置中设置。