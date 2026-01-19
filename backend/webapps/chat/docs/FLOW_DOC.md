# Chat 模块视图流程概览 (ASCII Flow)

该文档描述 `views.py` 中各个接口的处理步骤及核心决策点，便于快速理解端到端执行路径。

---
## 总体交互关系
```
+---------+        +----------------------+        +-----------------+        +------------------+
|  Client |  --->  | Django REST Endpoints|  --->  |  Services/Utils |  --->  |  Models / DB     |
+---------+        +----------------------+        +-----------------+        +------------------+
     ^                                                         |
     |                                                         v
     |<--------------------- (JSON Response) ------------------+

异步链路：
Client -> messages_view(POST) -> ChatService.process_message -> (后台异步执行) ->
  AgentService 更新任务状态 -> 前端轮询 check_task_status_view / check_incomplete_tasks_view 或回调通知。
```

---
## 1. /sessions (GET / POST)
### GET 获取会话列表
```
Client
  | GET /sessions
  v
[Django View sessions_view]
  | 认证 IsAuthenticated
  | 查询 ChatSession(user=request.user)
  | 预取 messages, 按 last_interacted_at 倒序
  | 序列化 SessionListSerializer(many=True)
  v
Response 200 (List)
```

### POST 创建新会话
```
Client
  | POST /sessions {title?, ai_conversation_id?}
  v
[Django View]
  | 若缺 ai_conversation_id => 生成 UUID
  | serializer = ChatSessionSerializer(data)
  | is_valid ?
  |   yes -> save(user=request.user) -> 201 + session
  |   no  -> 400 + errors
  v
Response
```

---
## 2. /sessions/<id> (GET / PUT / DELETE)
```
Client -> session_detail_view
  | 认证 + get_object_or_404(ChatSession, id, user)
  | 方法分支:
      GET: 序列化 ChatSessionSerializer -> 200
      PUT: partial update -> is_valid? -> 200 / 400
      DELETE: session.delete() -> 204
```

---
## 3. /sessions/<id>/messages (GET / POST / DELETE)
### GET 分页消息
```
Client
  | GET /messages?page=1&page_size=50
  v
[View messages_view]
  | 校验 session 权限
  | total = 未删除消息数
  | 查询未删除消息按 created_at DESC 切片
  | 反转列表以保持正序
  | 序列化 ChatMessageSerializer
  v
Response 200 {messages, pagination(meta)}
```

### POST 发送消息（异步处理）
```
Client
  | POST /messages (JSON 或 multipart/form-data)
  |   message/content, activeMode?, files?, callback_url?
  v
[View]
  | 解析 Content-Type
  | 提取 message；为空 => 400
  | ChatService.process_message(...)
  | result.success ?
      yes -> 返回 202 {task_id, assistant_message_id, status=processing}
      no  -> 500 {error}

后续：
  Agent 后台异步执行 -> 更新任务进度 ->
    前端轮询 /check_task_status/<task_id>
    或批量恢复 /check_incomplete_tasks
    或回调 callback_url
```

### DELETE 软删除消息
```
Client
  | DELETE /messages {afterIndex?, isFirstMessage?, index?}
  v
[参数解析优先级]
  if afterIndex is not None:
      if isFirstMessage && afterIndex == -1:
          标记所有未删除消息 is_deleted=True
      elif afterIndex >= 0:
          标记 (afterIndex+1 ... end) 未删除消息
  elif index is not None: (旧格式)
      标记 (index ... end)
  else -> 400

  所有删除均为软删除: is_deleted=True, deleted_at=now
```

---
## 4. /check_incomplete_tasks (POST) 恢复未完成任务
```
Client
  | POST /check_incomplete_tasks
  v
[View]
  | time_window = now - 24h
  | incomplete = ChatMessage[ user, is_complete=False, task_id!=NULL, created_at>=time_window ]
  | init AgentService
  | For each message:
      progress = get_task_progress(task_id)
      if progress is None: skip
      if progress.is_completed:
          提取 output_data.final_conclusion -> 填充 message.content
          过滤 action_history -> task_steps (前端可展示步骤)
          抽取 web_search 结果 -> final_web_search_results
          尝试推断会话标题
          标记 is_complete=True 保存
      elif progress.action_history 存在:
          增量保存部分步骤 + partial content
      异常: 捕获并记录日志
  | 汇总 updated_messages
  v
Response 200 {updated, updated_messages[]}
```

---
## 5. /check_task_status/<task_id> (GET)
```
Client -> check_task_status_view
  | 调 AgentService.get_task_progress(task_id)
  | progress 为 None -> exists=False, status=NOT_FOUND
  | 否则 -> exists=True, status, is_completed, has_progress
  | 异常 -> 500 {status=ERROR}
```

---
## 6. /session_by_conversation_id/<conversation_id> (GET)
```
Client -> session_by_conversation_id_view
  | get_object_or_404(ChatSession, ai_conversation_id, user)
  | 序列化返回 200
```

---
## 7. /sessions/{id}/snapshot (GET / POST)
### GET 创建快照
```
Client
  | GET /snapshot
  v
[View]
  | snapshot = create_session_snapshot(session_id)
  | success? 200 {snapshot} / 500
```

### POST 从快照恢复
```
Client
  | POST /snapshot {snapshot, clear_existing?}
  v
[View]
  | 校验 snapshot.session_id == session.id
  | clear_existing? -> 删除现有消息
  | For msg in snapshot.messages:
       若含 task_steps_compressed -> 解压
       ChatMessage.create(...)
  | 返回恢复条数
  | 异常统一 500
```

---
## 异步消息生命周期总览
```
User 输入 -> messages_view POST -> 202 Accepted + task_id
    |                     \
    |                      后台队列/代理执行 (ChatService -> AgentService)
    |                                   |
轮询 check_task_status -----------------/
    |         或批量 check_incomplete_tasks
    v
消息模型 ChatMessage: content / task_steps / final_web_search_results 更新 -> 前端刷新
```

---
## 关键字段语义
```
ChatSession:
  - last_interacted_at: 最近一次消息交互时间，用于排序
  - ai_conversation_id: 前端/外部系统引用的稳定 ID

ChatMessage:
  - is_complete: 异步 Agent 是否已结束
  - task_steps: 过滤后的 action_history（便于前端展示）
  - final_web_search_results: web_search 工具的归档结果
  - is_deleted: 软删除标记
```

---
## 扩展改造建议
```
1. 软删除恢复接口：提供 undo 删除能力。
2. 乐观更新：POST /messages 先写入一条占位消息，再由回调填充。
3. WebSocket 推送：替代轮询 check_task_status / check_incomplete_tasks。
4. Snapshot 版本控制：快照 schema_version + 消息 hash 校验一致性。
5. 分页优化：改用游标分页(cursor) 避免深翻页性能问题。
```

---
## 参考
- 代码位置: `backend/webapps/chat/views.py`
- 服务类: `ChatService`, `AgentService`
- 工具函数: `create_session_snapshot`, `decompress_data`, `filter_action_for_frontend`
