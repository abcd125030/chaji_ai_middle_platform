# Web页面到Agent数据的完整字段映射关系表

## 概述
此文档详细记录了从前端聊天页面到后端Agent处理系统的完整数据流转过程，包括每个层级的字段映射关系及后端数据表来源。

生成日期: 2025-09-23

## 数据流转架构图
```
前端页面(page.tsx) → 前端API路由(route.ts) → 后端Django视图(views.py) → ChatService → AgentService → AgentTask/Celery任务
```

## 一、前端页面到前端API路由的字段映射

### 1.1 发送消息时的请求体结构

| 前端页面字段 | 前端API字段 | 字段类型 | 说明 | 示例值 |
|------------|------------|---------|------|--------|
| message | message | string | 用户输入的消息内容 | "帮我分析这个文档" |
| activeMode | mode | string | 用户选择的对话模式 | "research" / "" |
| uploadedFiles | files | Array<Object> | 上传的文件列表 | 见下表 |

### 1.2 文件对象结构

| 前端文件字段 | API传递字段 | 字段类型 | 说明 |
|-------------|------------|---------|------|
| file.name | files[].name | string | 文件名 |
| file.type | files[].type | string | MIME类型 |
| file.size | files[].size | number | 文件大小(字节) |
| file.data | files[].data | string | Base64编码的文件内容 |

## 二、前端API到后端Django的字段映射

### 2.1 消息创建请求

| 前端API字段 | 后端接收字段 | Django处理方式 | 字段类型 | 说明 |
|------------|-------------|---------------|---------|------|
| message | message/content | request.data.get('message') | string | 消息内容(兼容两种字段名) |
| mode | activeMode | request.data.get('activeMode') | string | 执行模式 |
| files | files | request.data.get('files') | Array | Base64文件数组 |
| sessionId(URL参数) | session_id | URL路径参数 | UUID | 会话ID |

### 2.2 文件转换处理

| 原始字段 | 转换后字段 | 存储位置 | 说明 |
|---------|-----------|---------|------|
| files[].data | SimpleUploadedFile | 内存对象 | Base64转为Django文件对象 |
| files[].name | file.name | media/agent_uploads/ | 文件名 |
| files[].type | file.content_type | 文件元数据 | MIME类型 |

## 三、Django视图到ChatService的字段映射

### 3.1 process_message方法参数

| Django视图字段 | ChatService参数 | 字段类型 | 数据来源 | 说明 |
|---------------|----------------|---------|---------|------|
| session对象 | session | ChatSession | 数据库查询 | 会话实例 |
| message | message | string | 请求体 | 用户消息 |
| file_paths_info | files | List[Dict] | 文件保存结果 | 文件路径信息 |
| active_mode | active_mode | string | 请求体 | 执行模式 |
| request.user | user | User | 认证信息 | 当前用户 |

### 3.2 文件路径信息结构

| 字段名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| path | string | 服务器文件路径 | "/media/agent_uploads/doc_xxx.pdf" |
| name | string | 原始文件名 | "report.pdf" |
| size | number | 文件大小 | 1024000 |
| type | string | MIME类型 | "application/pdf" |

## 四、ChatService到AgentService的字段映射

### 4.1 start_agent_task方法参数

| ChatService字段 | AgentService参数 | 字段类型 | 数据处理 | 说明 |
|----------------|-----------------|---------|---------|------|
| str(session.id) | session_id | string | UUID转字符串 | 会话ID |
| messages列表 | messages | List[Dict] | 数据库查询构建 | 历史消息 |
| files | files | List[Dict] | 直接传递 | 文件信息 |
| graph_name | graph_name | string | 硬编码/配置 | "Super-Router Agent" |
| usage | usage | string/None | 根据mode判断 | "deep_research" / None |
| user | user | User | 直接传递 | 用户对象 |

### 4.2 消息列表结构

| 字段 | 类型 | 数据来源表 | 说明 |
|------|------|-----------|------|
| role | string | ChatMessage.role | "user" / "assistant" |
| content | string | ChatMessage.content | 消息内容 |

## 五、AgentService内部处理与数据存储

### 5.1 AgentTask数据模型字段

| 字段名 | 类型 | 数据来源 | 数据库表 | 说明 |
|-------|------|---------|----------|------|
| task_id | UUID | uuid.uuid4() | agentic_agenttask | 任务唯一ID |
| user | ForeignKey | 参数传入 | agentic_agenttask | 关联用户 |
| graph | ForeignKey | Graph.objects.get() | agentic_graph | 关联的图 |
| status | CharField | 初始值"PENDING" | agentic_agenttask | 任务状态 |
| session_id | UUID | 参数传入 | agentic_agenttask | 会话ID |
| session_task_history | JSONField | 历史查询 | agentic_agenttask | 历史任务ID列表 |
| input_data | JSONField | 构建的字典 | agentic_agenttask | 输入数据 |
| state_snapshot | JSONField | 构建的状态 | agentic_agenttask | 状态快照 |
| created_at | DateTime | auto_now_add | agentic_agenttask | 创建时间 |
| updated_at | DateTime | auto_now | agentic_agenttask | 更新时间 |

### 5.2 input_data结构

| 字段 | 类型 | 数据来源 | 说明 |
|------|------|---------|------|
| task_goal | string | messages最后一条 | 当前任务目标 |
| preprocessed_files_summary | Dict | 文件预处理结果 | 文件摘要信息 |
| usage | string/null | 参数传入 | 任务用途标签 |

### 5.3 state_snapshot结构

| 字段 | 类型 | 内容说明 |
|------|------|----------|
| preprocessed_files | Dict | 预处理后的文件内容 |
| conversation_history | List | 历史对话(不含最后一条) |
| current_step | null/string | 当前执行步骤 |
| execution_history | List | 执行历史记录 |

## 六、ChatMessage数据模型字段映射

### 6.1 ChatMessage表结构

| 字段名 | 类型 | 数据来源 | 数据库表 | 说明 |
|-------|------|---------|----------|------|
| id | AutoField | 自动生成 | webapps_chatmessage | 主键 |
| session | ForeignKey | 会话对象 | webapps_chatsession | 关联会话 |
| role | CharField | "user"/"assistant" | webapps_chatmessage | 消息角色 |
| content | TextField | 用户输入/AI回复 | webapps_chatmessage | 消息内容 |
| files_info | JSONField | 文件处理结果 | webapps_chatmessage | 文件信息JSON |
| task_id | CharField | AgentTask.task_id | webapps_chatmessage | 关联的任务ID |
| task_steps | JSONField | 任务执行步骤 | webapps_chatmessage | 任务步骤JSON |
| final_web_search_results | JSONField | 搜索结果汇总 | webapps_chatmessage | 网页搜索结果 |
| is_complete | BooleanField | 任务完成状态 | webapps_chatmessage | 是否完成 |
| is_deleted | BooleanField | 软删除标记 | webapps_chatmessage | 是否删除 |
| deleted_at | DateTimeField | 删除时间 | webapps_chatmessage | 删除时间戳 |
| created_at | DateTimeField | auto_now_add | webapps_chatmessage | 创建时间 |
| updated_at | DateTimeField | auto_now | webapps_chatmessage | 更新时间 |

## 七、ChatSession数据模型字段映射

### 7.1 ChatSession表结构

| 字段名 | 类型 | 数据来源 | 数据库表 | 说明 |
|-------|------|---------|----------|------|
| id | UUIDField | uuid.uuid4() | webapps_chatsession | 会话ID |
| user | ForeignKey | 认证用户 | auth_user | 关联用户 |
| ai_conversation_id | CharField | 生成/传入 | webapps_chatsession | AI会话ID |
| title | CharField | 自动生成/用户设置 | webapps_chatsession | 会话标题 |
| last_message_preview | CharField | 最后消息截取 | webapps_chatsession | 消息预览 |
| last_interacted_at | DateTimeField | 每次交互更新 | webapps_chatsession | 最后交互时间 |
| is_pinned | BooleanField | 用户设置 | webapps_chatsession | 置顶标记 |
| is_archived | BooleanField | 用户设置 | webapps_chatsession | 归档标记 |
| tags | JSONField | 用户设置 | webapps_chatsession | 标签列表 |
| created_at | DateTimeField | auto_now_add | webapps_chatsession | 创建时间 |
| updated_at | DateTimeField | auto_now | webapps_chatsession | 更新时间 |

## 八、Celery任务参数映射

### 8.1 run_graph_task参数

| 参数名 | 类型 | 数据来源 | 说明 |
|-------|------|---------|------|
| task_id | string | AgentTask.task_id | 任务UUID字符串 |
| graph_name | string | 配置/参数 | 图名称 |
| initial_task_goal | string | 最后一条消息 | 任务目标 |
| preprocessed_files | Dict | 文件预处理结果 | 处理后的文件 |
| origin_images | List[string] | 图片文件路径 | 原始图片列表 |
| conversation_history | List[Dict] | 历史消息 | 对话历史 |
| usage | string/None | 模式判断结果 | 用途标签 |
| session_task_history | List[string] | 历史任务查询 | 历史任务ID |

## 九、数据流转关键节点总结

1. **前端发送**: Base64编码文件 + 文本消息 + 模式选择
2. **API路由**: 透传到后端，建立SSE连接
3. **Django视图**: Base64解码，文件保存，创建消息记录
4. **ChatService**: 构建消息历史，调用Agent服务
5. **AgentService**: 文件预处理，创建任务，启动Celery
6. **AgentTask**: 存储任务状态和进度
7. **Celery**: 异步执行，更新状态，SSE推送进度
8. **数据库存储**: 
   - ChatSession: 会话元数据
   - ChatMessage: 消息内容和任务关联
   - AgentTask: 任务执行状态
   - ActionSteps: 任务执行步骤记录

## 十、状态流转

### 任务状态
```
PENDING → RUNNING → COMPLETED/FAILED/CANCELLED
```

### 消息完成状态
```
is_complete: false → true (任务完成时更新)
```

### 软删除状态
```
is_deleted: false → true (用户删除消息时)
```

## 注意事项

1. **文件处理**: 前端Base64编码 → 后端解码保存 → Agent预处理(文档转Markdown等)
2. **会话管理**: 使用UUID标识，支持多会话并发
3. **任务追踪**: 通过task_id关联ChatMessage和AgentTask
4. **历史记录**: 保留session_task_history用于上下文传递
5. **软删除**: 消息不物理删除，仅标记is_deleted
6. **SSE流式**: 任务进度通过SSE实时推送到前端