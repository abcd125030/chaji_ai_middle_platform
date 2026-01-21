# MinerU 样例推理服务（LitServe/FastAPI）

## 文件用途
- 这是一个独立的推理服务样例，用于把 MinerU 的解析流程封装成一个可通过 HTTP 调用的服务
- 采用 LitServe 提供的服务框架，底层是 FastAPI；可在 GPU 上运行并支持批处理
- 接收 Base64 文件，统一转换为 PDF，调用 MinerU 的 `magic_pdf` 解析管线，输出结果目录

## 关键依赖
- `litserve` 提供服务框架与批处理调度（`ls.LitAPI`, `ls.LitServer`）
- `magic_pdf.tools.cli` 的 `do_parse`、`convert_file_to_pdf` 完成解析与 Office→PDF 转换（`sample_code_server.py:29–34`）
- `ModelSingleton` 预加载所需模型（`sample_code_server.py:35–38`）
- `fitz`（PyMuPDF）将图片转 PDF（`sample_code_server.py:93–95`）
- `filetype` 通过文件头判断扩展名（`sample_code_server.py:88–101`）
- `torch` 管理 GPU 资源（`sample_code_server.py:24–27`, `sample_code_server.py:78–81`）

## 工作流程
- 初始化与加载模型
  - `setup(device)` 设置 `CUDA_VISIBLE_DEVICES` 并加载两个模型实例（`sample_code_server.py:23–38`）
- 请求解码
  - `decode_request(request)` 期望输入包含 `file`（Base64）、可选 `pdf_name`、以及 `kwargs`（默认 `{"debug_able": false, "parse_method": "auto"}`），并调用 `cvt2pdf` 将内容统一为 PDF 字节（`sample_code_server.py:40–49`）
- 推理执行
  - `predict(inputs)` 是批处理入口，当前代码只取第一条输入，生成 `pdf_name` 与输出目录后，调用 `do_parse(self.output_dir, pdf_name, pdf_bytes, [], **opts)` 并返回输出目录路径列表（`sample_code_server.py:51–66`）
  - 异常时清理输出目录并抛出 `HTTPException`；最终执行 `clean_memory()` 释放 GPU/内存（`sample_code_server.py:67–81`）
- 响应编码
  - `encode_response(response)` 返回形如 `{"output_dir": ["/home/lisongming/tmp/<uuid>"]}` 的结构（`sample_code_server.py:74–76`）
- 文件转换
  - `cvt2pdf(file_base64)` 按探测扩展名分别处理 PDF、图片（PyMuPDF 转换）、Office 文档（`convert_file_to_pdf`），并在 finally 清理临时目录（`sample_code_server.py:83–106`）
- 启动服务
  - `__main__` 创建 `ls.LitServer(MinerUAPI(...), accelerator='cuda', devices='auto', workers_per_device=1)` 并拿到 FastAPI 实例；示例添加了一个简单的 GET 路由（`sample_code_server.py:108–121`）

## 路由与返回
- LitServe 会基于 `MinerUAPI` 自动暴露推理接口（通常是一个 POST 路由用于批量推理；具体路由以 LitServe 文档配置为准）
- 请求体应满足 `decode_request` 期望的结构，例如：
  - `file`: Base64 字符串
  - `pdf_name`: 可选输出名（不传则用随机 UUID）
  - `kwargs`: 可选解析参数，如 `{"debug_able": false, "parse_method": "auto"}`
- 响应示例：`{"output_dir": ["/home/lisongming/tmp/<uuid>"]}`，表示解析产物所在目录（Markdown/JSON 等）

## 与 Django 服务的关系
- 这是独立样例服务文件，不属于 Django 路由；和 `backend/mineru/views.py`、`backend/mineru/tasks.py` 中使用的 `OptimizedMinerUService`（调用 `mineru` CLI）是两条思路
- 如需集成，可让 Celery 任务调用此推理服务的 HTTP 接口，把输出目录或结果回填到数据库

## 可改进之处
- 入参校验 bug：`predict` 中 `if not input ...` 应为 `if not inputs ...`（`sample_code_server.py:53`）
- 批处理支持：当前只处理 `inputs[0]`，如要真正批处理需遍历全部 `inputs`
- 返回结构：单输入场景可直接返回字符串而非列表，更贴合直觉
- 路由示例函数不完整：`/download_output_files` 的返回值在代码片段中未闭合，作为演示用途需补全
- 路径适配：`output_dir='/home/lisongming/tmp'` 为 Linux 路径；在 Windows 上请改为如 `C:\\mineru\\tmp`
- 设备配置：无 GPU 时将 `accelerator='cuda'` 改为 `accelerator='cpu'`

## 运行建议
- 安装依赖：`litserve`、`pymupdf`、`filetype`、`torch`，以及 MinerU 的依赖
- Windows 启动示例（PowerShell），按需调整输出目录与设备参数：
```powershell
python d:\my_github\chaji_ai_middle_platform\backend\mineru\sample_code_server.py
```
- 请求体按 `decode_request` 的字段组织；具体调用路径以服务启动后输出或 LitServe 文档为准径以服务启动后输出或 LitServe 文档为准