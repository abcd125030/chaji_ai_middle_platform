## 文件概览

- 这是一个基于飞书开放平台 SDK 的长连接事件处理脚本，用于接收 IM 消息与公司圈动态，并与 Django 环境协作
- 启动时加载 `.env` 环境变量、初始化 Django，再创建飞书 WebSocket 客户端并注册事件处理器
- 当前包含两个“占位”函数，实际的“发飞书通知”和“文件下载/解压”尚未实现

## 启动与环境

- 加载 `.env`： `load_dotenv(BASE_DIR / '.env')` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:7-8`
- Django 初始化： `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')` 与 `django.setup()` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:14-16`
- 日志器：使用 `logging.getLogger('django')` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:29`

## 环境变量使用

- 机器人群聊 ID： `ROBOT_CHAT_ID` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:42`
- 拼写疑似错误的未使用变量： `TOEKN_URL` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:43`
- 应用凭据：优先 `FEISHU_APP_ID`/`FEISHU_APP_SECRET`，回退到 `APP_ID`/`APP_SECRET` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:45-46`
- 其他服务接口： `AUTH_APP_ID`/`AUTH_APP_SECRET`/`SERVICE_AUTH`/`Excel_DATABASE` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:109-115` 与 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:131`

## 事件注册与客户端

- 事件处理器注册 IM 与公司圈： `register_p2_im_message_receive_v1` 与 `register_p2_moments_post_created_v1` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:165-168`
- WebSocket 客户端启动： `lark.ws.Client(...).start()` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:173-176`
- 主入口检查凭据并启动：在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:180-188`

## 核心：IM 消息处理逻辑

- 入口函数： `do_p2_im_message_receive_v1(data)` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:52`
- 解析消息：
  - 将 SDK 对象序列化为 JSON 并二次解析： `lark.JSON.marshal(data)` → `json.loads(...)` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:54-61`
  - 读取 `message_id`/`chat_id`/`sender`/`message_type`/`content` 等字段 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:64-71`
- 只处理来自指定群的消息： `if message_chat_id == ROBOT_CHAT_ID` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:72`
- 仅接收“文件消息”且必须是 `.zip`：
  - 解析 `content` 取 `file_key`/`file_name` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:82-85`
  - 非 `.zip` 明确提示 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:139-141`
- 下载与防重复：
  - 按日期构建保存路径 `download_file/<yyyy-MM-dd>-<file_name>` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:86-93`
  - 300 秒内相同 `save_path` 跳过重复下载 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:94-99`
  - 实际下载调用的是占位函数 `download_file_total(...)` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:100-102`
- 后续处理（依赖下载+解压已完成）：
  - 校验文件是否存在 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:103-106`
  - 获取业务服务访问令牌：向 `SERVICE_AUTH` 发起 `appid`/`secret` 登录 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:109-121`
  - 预期解压目录： `extract_dir = os.path.splitext(save_path)[0]` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:123`
  - 收集解压出的 `.xlsx` 列表并提交到 `Excel_DATABASE` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:125-136`
- 错误处理：
  - 针对 JSON 解析、`KeyError`、其他异常分别记录日志并调用占位的 `send_feishu(...)` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:58-61, 142-151, 152-160`

## 占位实现

- `send_feishu(msg)` 仅写日志，不会真正发消息 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:32-35`
- `download_file_total(...)` 仅写日志，不会真正下载/解压 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:37-40`
- 因此后续“解压后找 `.xlsx`”与对数据库服务的推送，依赖这些占位实现被替换为真实逻辑

## 潜在问题与建议

- 未完成异常处理尾部代码： `except KeyboardInterrupt: logger.info(` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:188-189` 显示不完整，需补全日志消息或关闭括号
- 未实际解压 ZIP： `extract_dir` 的使用假定已解压，需在下载后执行真实解压，否则 `os.listdir(extract_dir)` 会报错
- 非标准路径处理：将 Windows 路径中的 `\` 替换为 `+` 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:125` 不常见，建议使用规范路径或在传输层约定清晰的编码
- 环境变量命名不统一：
  - `TOEKN_URL` 拼写错误且未使用 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:43`
  - `Excel_DATABASE` 大小写风格不一致，建议统一为类似 `EXCEL_DATABASE_URL`
- 目录相对路径： `download_file` 建在当前工作目录 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:89-93`，建议改为基于 `BASE_DIR` 的绝对路径，避免不同启动目录导致混乱
- `lark.EventDispatcherHandler.builder("", "")` 使用空字符串作为校验/加密参数 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:165`，若 SDK 需要这些参数，应从环境变量加载
- 仅在 `message_json` 是字符串时处理事件 在 `d:\my_github\chaji_ai_middle_platform\backend\lark_oapi_main.py:55-61`，建议兼容对象类型或统一为字符串后再解析
- 发送通知函数为占位：当前不会真正通知用户处理结果，建议替换为真实的飞书发送 API 或企业内部通知机制

## 整体流程总结

- 启动加载配置并初始化 Django
- 建立飞书 WebSocket 长连接
- 收到 IM 文件消息时：
  - 只接受 `.zip`
  - 生成保存路径并做 300 秒防重复
  - 调用占位下载，随后尝试读取解压目录下 `.xlsx`
  - 通过鉴权服务获取令牌并向数据服务提交文件列表
  - 记录日志并调用占位的“发通知”
- 同时注册公司圈动态事件处理（具体逻辑在 `webapps.moments.handlers.post_created.handle_post_created`）