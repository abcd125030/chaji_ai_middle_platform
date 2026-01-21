# MinerU 客户端（HTTP 示例）

## 用途
- 充当 MinerU 推理服务的简单 HTTP 客户端，向服务端发送待解析文件并获取解析结果
- 将本地文件读取为 Base64，按服务端约定的 JSON 结构调用 `POST /predict` 接口

## 核心函数
- `to_b64(file_path)`（`backend/mineru/sample_code_client.py:8–13`）
  - 读取文件为字节并转为 Base64 字符串，供 HTTP JSON 请求体使用
- `do_parse(file_path, url='http://127.0.0.1:8002/predict', **kwargs)`（`backend/mineru/sample_code_client.py:16–31`）
  - 发送 `POST` 请求到 `url`，请求体：
    - `file`: Base64 编码的文件内容
    - `kwargs`: 解析参数字典（例如 `parse_method='auto'`, `debug_able=False`）
  - 正常返回时将服务端返回的 JSON（包含输出目录等）与原始 `file_path` 合并后返回
  - 异常时记录错误日志（`loguru.logger`），并返回 `None`
- 脚本入口（`backend/mineru/sample_code_client.py:33–37`）
  - 构造 `files` 列表，使用 `joblib.Parallel` 与 `delayed` 并行调用 `do_parse`

## 调用协议与参数
- 服务端期望的 JSON（与 `sample_code_server.py` 对应）：
  - `file`: Base64 字符串（来自 `to_b64`）
  - `kwargs`: 字典，常见键：
    - `parse_method`: `auto|txt|ocr`（默认 `auto`）
    - `debug_able`: `true|false`（默认 `false`）
  - 可选 `pdf_name` 字段（服务端会将其用作输出目录名）；当前客户端未发送该字段，如需设定可在请求体中增加
- 默认 URL 为 `http://127.0.0.1:8002/predict`，需保证服务端监听此端口与路由；如果你的 LitServe/FastAPI 服务跑在其他端口或路径，请相应调整

## 并行处理
- 使用 `joblib.Parallel` 和 `delayed` 将多文件解析并行化
- `n_jobs = np.clip(len(files), 1, 8)` 将并行度限制在 1 到 8，避免过度并发导致服务端或本机资源耗尽

## 返回结果形态
- 服务端样例返回形如 `{"output_dir": ["/home/lisongming/tmp/<uuid>"]}`（见 `backend/mineru/sample_code_server.py:74–76`）
- 客户端将其解包为字典，并额外加入 `file_path` 字段，便于对号入座

## 注意事项
- 端口与路由一致性：确认服务端真实监听地址与路径，必要时调整 `url`（例如 `http://127.0.0.1:8000/predict`）
- 超时与稳定性：实际生产建议为 `requests.post` 增加 `timeout`，并考虑重试机制
- 传参一致性：`kwargs` 键名需与服务端一致，如 `parse_method`、`debug_able`；如需自定义输出名应传 `pdf_name`
- 安全与体积：大文件 Base64 会使请求体增大，建议结合流式上传或服务端支持的分片策略

## 示例调用（单文件）
```python
from sample_code_client import do_parse

res = do_parse(r"C:\\data\\doc.pdf",
               url="http://127.0.0.1:8002/predict",
               parse_method="auto",
               debug_able=False)
print(res)
```

## 示例（并行多文件，补全脚本入口的常见写法）
```python
from joblib import Parallel, delayed
from sample_code_client import do_parse

files = [r"C:\\data\\doc1.pdf", r"C:\\data\\doc2.pdf"]
n_jobs = 2
results = Parallel(n_jobs=n_jobs, prefer="threads", verbose=10)(
    delayed(do_parse)(p,
                      url="http://127.0.0.1:8002/predict",
                      parse_method="auto",
                      debug_able=False)
    for p in files
)
print(results)
```

## Windows 运行
- 启动客户端脚本：
```powershell
python d:\my_github\chaji_ai_middle_platform\backend\mineru\sample_code_client.py
```
- 确保服务端（LitServe/FastAPI 示例）已启动且可访问；如果服务端不在 `8002` 端口，请修改脚本中的 `url` 参数为实际地址如果服务端不在 8002 端口，请修改脚本中的 url 参数为实际地址