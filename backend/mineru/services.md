# MinerU 命令行服务（CLI 封装）

## 角色与用途
- 提供一个基于命令行的 MinerU 解析服务封装：写入临时文件、调用 `mineru` CLI 完成解析、收集输出并返回统计结果（`backend/mineru/services.py:15–17`）
- 同时承担上传文件落盘、文件校验、输出结果读取等通用辅助能力，供视图与异步任务复用

## 配置来源
- 读取 `settings.MINERU_SETTINGS`，包含：
  - `OUTPUT_DIR`、`UPLOAD_DIR`、`TEMP_DIR`：输出、上传、临时工作目录（`backend/mineru/services.py:19–23`）
  - `MAX_FILE_SIZE`：最大文件大小（字节）（`backend/mineru/services.py:227–229`）
  - `ALLOWED_FILE_TYPES`：允许的扩展名集合（`backend/mineru/services.py:237–238`）
- 初始化时确保上述目录存在（`backend/mineru/services.py:24–27`）

## 核心方法
- `check_mineru_command()`：检测本机 `mineru` CLI 是否可用，通过 `mineru --version` 判断（`backend/mineru/services.py:28–40`）
- `convert_to_pdf(file_bytes, file_ext)`：非 PDF 文件直接返回原始字节，交由 MinerU CLI 自动转换（`backend/mineru/services.py:42–50`）
- `parse_document(file_bytes, file_ext, task_id, parse_method='auto', debug_enabled=False, enable_table_merge=True, use_new_table_model=True)`：
  - 将上传二进制写到 `TEMP_DIR` 临时文件（`backend/mineru/services.py:71–80`）
  - 为该任务创建 `OUTPUT_DIR/<年>/<月>/<task_id>` 输出目录（`backend/mineru/services.py:82–85`）
  - 构建并执行 CLI 命令，成功后收集结果并返回；异常时清理输出并抛错（`backend/mineru/services.py:86–141`）
- `_collect_results(output_path, processing_time)`：遍历输出目录，收集 `markdown_path`、`json_path` 与简单统计（文本块/图片/表格/跨页表格），并截取 Markdown 前 500 字符作为预览（`backend/mineru/services.py:143–194`）
- `get_output_files(task_id, year, month)`：用于按既有任务路径重新收集输出（`backend/mineru/services.py:196–204`）
- `save_uploaded_file(file_bytes, filename, task_id)`：将上传文件落盘并返回路径（`backend/mineru/services.py:209–219`）
- `validate_file(file_bytes)`：校验大小与类型，返回 `(是否有效, 信息, 扩展名)`（`backend/mineru/services.py:221–240`）

## CLI 调用细节
- 命令模板（含子命令 `pdf` 与参数）：
  - 可执行：`mineru`
  - 子命令：`pdf`
  - 输入文件：`-p <临时文件路径>`
  - 输出目录：`-o <输出目录>`
  - 解析方法：`--method <auto|ocr|txt>`
  - 调试：`--debug`（可选）
  - 表格增强：`--table-merge true` 与 `--table-model new`（可选，面向 v2.2 特性）（`backend/mineru/services.py:86–105`）
- 执行方式：`subprocess.run(..., capture_output=True, text=True, timeout=300)`，非零返回码视为失败并抛出异常（`backend/mineru/services.py:110–121`）
- 成功后记录耗时并进入结果收集流程（`backend/mineru/services.py:121–126`）

## 与系统其他模块的关系
- 视图层用于校验与落盘：`PDFParseTaskViewSet.upload` 与 `create_task_from_base64` 会调用 `MinerUService.validate_file` 和 `save_uploaded_file`（`backend/mineru/views.py:55–76`, `backend/mineru/views.py:206–229`）
- 实际解析在异步任务里走优化版服务：`OptimizedMinerUService.process_document`（带 OSS/缓存/更丰富统计），与本文件的命令行封装相比更偏生产化（`backend/mineru/tasks.py:55–64`, `backend/mineru/services/optimized_service.py`）
- 两条路径差异：本文件侧重本地输出目录管理、直接 CLI 调用、简化统计；优化版支持 OSS、缓存命中、结果上传与清理，本地输出可被清空并以 URL 保存

## 典型调用路径（上传→解析→收集）
- 认证用户在前端调用 `POST /api/mineru/tasks/upload/` 上传文件
- 视图使用 `MinerUService.validate_file` 进行类型/大小校验，并用 `save_uploaded_file` 落盘（`backend/mineru/views.py:55–76`）
- 异步任务读取文件并调用优化服务 `OptimizedMinerUService.process_document` 完成解析，更新任务与结果表（`backend/mineru/tasks.py:55–64`）
- 用户通过 `GET /api/mineru/tasks/{id}/download/` 或状态接口查看结果（`backend/mineru/views.py:130–163`, `backend/mineru/views.py:93–129`）

## 注意点与建议
- CLI 兼容性：本文件使用 `mineru pdf` 子命令，优化版使用 `mineru` 直接参数方式；请确保你的 MinerU 版本支持相应调用风格（`backend/mineru/services.py:88–93`, `backend/mineru/services/optimized_service.py:179–185`）
- 文件名安全：`save_uploaded_file` 直接使用传入的 `filename` 作为落盘名，建议在上游规范化文件名，避免特殊字符或路径穿越
- 超时与重试：命令执行超时固定为 300 秒；生产环境中建议在任务层面增加重试与告警（`backend/mineru/services.py:114–115`, `backend/mineru/tasks.py:15–87`）
- 统计口径：表格/图片/文本块统计基于 Markdown 简单计数，可能不完全准确；优化版服务提供更丰富统计（`backend/mineru/services.py:177–184`, `backend/mineru/services/optimized_service.py:230–268`）

## 在 Windows 下手动验证 CLI（示例命令）
```powershell
# 查看 MinerU 版本
mineru --version

# 基本解析（替换真实路径）
mineru pdf -p C:\path\to\file.pdf -o C:\path\to\output --method auto --debug
```

如需我对该服务与优化版服务的调用方式做统一（例如都使用同一套 CLI 参数风格），或增强文件名安全/错误处理，我可以准备一份改动预览供你审阅并接受。