# AICallback 模块说明

## 作用概述
- 封装图片编辑任务的回调客户端，用于将任务执行结果推送到外部业务系统的回调接口
- 负责环境推断、签名生成、回调数据构造（成功/失败两类）以及 HTTP 请求发送

## 关键功能
- 环境与密钥管理：按传入的 `callback_url` 或 `env` 推断环境，设置基础地址与密钥，并生成默认回调接口 `.../api/callback/aiImg`（`backend/customized/image_editor/aiCallback.py`:18–66）
- 签名生成：按约定 `nonce=...&secretKey=...&timestamp=...` 计算 SHA-256 摘要并 Base64 编码，用于回调鉴权（`aiCallback.py`:68–87）
- 成功回调数据：构造包含 `task_id/status/data(image, original_prompt)/processing_time/created_at/completed_at` 的载荷，顶层 `code=0`，含 `timestamp/signature/nonce`（`aiCallback.py`:90–158）
- 失败回调数据：构造包含 `task_id/status=failed/error(code/message/details)/created_at/completed_at` 的载荷，顶层 `code` 取错误码去掉 `E` 的数值（`aiCallback.py`:160–225）
- 发送请求：以 `POST application/json` 向目标地址发送数据并记录响应（`aiCallback.py`:227–264）

## 项目中的用法
- 单任务立即回调（成功）：
  - `create_success_callback_data(...)` → `send_callback(...)`
  - 引用位置：`backend/customized/image_editor/tasks.py`:295–303
- 单任务立即回调（失败）：
  - `create_failed_callback_data(...)` → `send_callback(...)`
  - 引用位置：`backend/customized/image_editor/tasks.py`:300–303
- 批量回调（Redis 队列）：
  - 批处理器取队列项后，对每个任务使用 `AICallback` 构造并发送（`backend/customized/image_editor/tasks_batch.py`:96–112）

## 数据格式要点
- 顶层：`params/code/data/message/timestamp`，以及同级的 `timestamp/signature/nonce`
- 成功数据 `data`：
  - `task_id/status/data(image, original_prompt)/processing_time/created_at/completed_at`
- 失败数据 `data`：
  - `task_id/status=failed/error(code/message/details)/created_at/completed_at`
- 日志对超长 `image` 字段做截断降低日志体积（`aiCallback.py`:147–156, 247–255）

## 注意事项
- 密钥与环境地址目前硬编码，用于测试/内网；生产应改为环境变量或配置中心管理（`aiCallback.py`:29–39）
- `nonce` 固定为 `11886`，需与接收方验签规则一致（`aiCallback.py`:118–121, 190–195）
- 生产基础地址使用 `http`（内网）；跨公网建议切换为 `https`（`aiCallback.py`:31）
- 签名为纯 SHA-256 摘要的 Base64（非 HMAC）；需确保与接收方校验逻辑匹配（`aiCallback.py`:80–87）

## 相关文件
- `backend/customized/image_editor/aiCallback.py`
- `backend/customized/image_editor/tasks.py`
- `backend/customized/image_editor/tasks_batch.py`