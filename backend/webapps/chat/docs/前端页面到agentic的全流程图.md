# 前端对话界面到agentic图运行的全流程图

## 相关业务
web/src/app/chat/page.tsx
web/src/components/ui/ChatInput.tsx
web/src/components/ui/ChatMessages.tsx
web/src/app/api/chat/sessions/route.ts
web/src/app/api/chat/sessions/[sessionId]/messages/route.ts
backend/webapps/chat/views.py
backend/agentic/

## 目的
描述chat的业务流程和数据流转

## 规范
- mermaid 流程
- 数据流转UML图，精确到字段，每个节点是一个关键的数据处理环节的对应函数

## 画流程图

### 发起一个新消息

```mermaid
sequenceDiagram
    participant User as 用户
    participant Page as ChatPage<br/>page.tsx
    participant Input as ChatInput<br/>组件
    participant API as API Route<br/>messages/route.ts
    participant Backend as Django后端<br/>views.py
    participant Service as ChatService<br/>services.py
    participant Agent as AgentService<br/>agentic/services.py
    participant Celery as Celery任务<br/>run_graph_task
    participant Executor as GraphExecutor<br/>processor.py
    participant SSE as SSE流<br/>stream接口

    User->>Page: 输入消息并点击发送
    Page->>Input: onSubmit(message, activeMode)
    
    Note over Input: 处理文件上传<br/>转换base64格式
    
    Input->>Page: 触发handleSend
    
    Page->>API: POST /api/chat/sessions/{sessionId}/messages<br/>Accept: text/event-stream<br/>{message, files, activeMode}
    
    API->>Backend: POST /webapps/chat/sessions/{sessionId}/messages/<br/>Accept: application/json
    
    Note over Backend: messages_view处理POST请求
    Backend->>Backend: 转换base64文件为SimpleUploadedFile
    Backend->>Backend: 保存文件到media/agent_uploads/
    
    Backend->>Service: process_message(session, message, files, active_mode, user)
    
    Service->>Service: 创建用户消息记录<br/>ChatMessage(role='user')
    Service->>Service: 创建助手占位消息<br/>ChatMessage(role='assistant', is_complete=False)
    Service->>Service: 更新会话last_interacted_at
    
    Service->>Agent: start_agent_task(session_id, messages, files, graph_name, usage, user)
    
    Note over Agent: 预处理文件<br/>docx/pdf→markdown<br/>excel→结构化数据<br/>图片→文字描述
    
    Agent->>Agent: 创建AgentTask实例<br/>status=PENDING
    Agent->>Agent: 构建prompt和conversation_history
    
    Agent->>Celery: run_graph_task.delay(task_id, graph_name, prompt, files, ...)
    
    Agent-->>Service: 返回{task_id, assistant_message_id, session_id}
    Service-->>Backend: 返回{success: true, task_id, ...}
    Backend-->>API: 返回JSON {task_id, session_id, status: 'processing'}
    
    API->>API: 获取task_id
    API->>Backend: GET /webapps/chat/tasks/{task_id}/stream/<br/>Accept: text/event-stream
    
    Note over Backend,SSE: 建立SSE连接
    
    Backend->>SSE: 创建SSE流响应
    API->>Page: 转发SSE流<br/>event: task_started
    
    Note over Celery,Executor: 异步执行任务
    
    Celery->>Executor: 初始化GraphExecutor
    Executor->>Executor: 加载/初始化RuntimeState
    Executor->>Executor: 加载Graph定义和节点映射
    Executor->>Executor: 设置任务状态为RUNNING
    
    loop 执行图节点
        Executor->>Executor: 执行当前节点<br/>_execute_node()
        Executor->>Executor: 更新state和action_history
        Executor->>Executor: 保存checkpoint
        Executor->>SSE: 发送进度事件<br/>event: plan/tool_output/reflection等
        SSE-->>API: 转发SSE事件
        API-->>Page: 更新UI展示进度
    end
    
    Executor->>Executor: 生成final_answer
    Executor->>Executor: 更新任务状态为COMPLETED
    
    SSE->>API: event: final_answer<br/>event: task_completed
    API->>Page: 更新消息列表<br/>显示完整回复
```

#### 数据流转详情

```mermaid
graph TB
    subgraph 前端数据结构
        A1[用户输入] -->|"{ message: string, activeMode: string }"| A2[ChatInput组件]
        A2 -->|"files: FileRecord[]"| A3[文件处理]
        A3 -->|"base64编码"| A4[API请求体]
        
        A4 -->|"{ 
            message: string, 
            activeMode: string,
            files: [{
                name: string,
                type: string,
                size: number,
                data: base64
            }]
        }"| A5[POST请求]
    end
    
    subgraph 后端数据转换
        B1[messages_view] -->|"convert_base64_to_files()"| B2[SimpleUploadedFile对象]
        B2 -->|"保存到本地"| B3[文件路径信息]
        B3 -->|"{ 
            path: string,
            name: string,
            size: number,
            type: string
        }"| B4[ChatService]
    end
    
    subgraph Agent处理
        C1[AgentService] -->|"_preprocess_files()"| C2[结构化数据]
        C2 -->|"{ 
            documents: {}, 
            tables: {},
            images: {},
            other_files: []
        }"| C3[RuntimeState]
        
        C3 -->|"{ 
            task_goal: string,
            preprocessed_files: dict,
            origin_images: list,
            conversation_history: list,
            user_context: dict
        }"| C4[GraphExecutor]
    end
    
    subgraph 执行状态
        D1[GraphExecutor] -->|"action_history"| D2[ActionSteps]
        D2 -->|"{ 
            type: string,
            content: dict,
            timestamp: datetime
        }"| D3[state_snapshot]
        
        D3 -->|"SSE事件"| D4[前端更新]
    end
```

### 打开一个已有会话（所有对话已完成）

```mermaid
sequenceDiagram
    participant User as 用户
    participant Page as ChatPage<br/>page.tsx
    participant API as API Route
    participant Backend as Django后端
    participant DB as 数据库

    User->>Page: 访问/chat页面
    
    Page->>Page: useEffect初始化
    Page->>Page: 从localStorage获取sessionId
    
    alt sessionId存在
        Page->>API: GET /api/chat/sessions/{sessionId}/messages
        API->>Backend: GET /webapps/chat/sessions/{sessionId}/messages/
        
        Backend->>DB: 查询ChatSession
        Backend->>DB: 查询ChatMessage.filter(is_deleted=False)
        
        Note over Backend: 按created_at倒序查询<br/>然后反转保持正序
        
        Backend-->>API: 返回{messages: [], pagination: {}}
        
        API-->>Page: 返回消息列表
        
        Page->>Page: transformMessages()<br/>snake_case转camelCase
        Page->>Page: setMessages(transformedMessages)
        
        Note over Page: 检查是否有未完成任务<br/>is_complete === false
        
        alt 没有未完成任务
            Page->>Page: 正常显示历史消息
            Page->>Page: 等待用户新输入
        end
    else sessionId不存在
        Page->>Page: 显示空对话界面
        Page->>Page: 等待用户首次输入
    end
```

#### 数据加载流程

```mermaid
graph LR
    subgraph 会话加载
        A1[localStorage.sessionId] --> A2{sessionId存在?}
        A2 -->|是| A3[加载会话消息]
        A2 -->|否| A4[新建会话]
        
        A3 --> A5[GET /messages]
        A5 --> A6[查询数据库]
    end
    
    subgraph 消息处理
        B1[ChatMessage表] -->|"filter(is_deleted=False)"| B2[未删除消息]
        B2 -->|"order_by('-created_at')"| B3[倒序排列]
        B3 -->|"[offset:offset+page_size]"| B4[分页切片]
        B4 -->|"reverse()"| B5[恢复正序]
    end
    
    subgraph 前端展示
        C1[接收消息数组] --> C2[转换字段格式]
        C2 --> C3[渲染ChatMessages组件]
        C3 --> C4[显示历史对话]
    end
```

### 打开一个已有会话（最后一次对话未完成）

```mermaid
sequenceDiagram
    participant User as 用户
    participant Page as ChatPage<br/>page.tsx
    participant API as API Route
    participant Backend as Django后端
    participant Service as ChatService
    participant Agent as AgentService
    participant SSE as SSE流

    User->>Page: 访问/chat页面
    Page->>Page: 从localStorage获取sessionId
    
    Page->>API: GET /api/chat/sessions/{sessionId}/messages
    API->>Backend: GET /webapps/chat/sessions/{sessionId}/messages/
    
    Backend->>Backend: 查询消息列表
    Backend-->>API: 返回消息（含未完成任务）
    API-->>Page: 返回消息列表
    
    Page->>Page: 检测到未完成任务<br/>is_complete === false && task_id存在
    
    Page->>API: POST /api/chat/check-incomplete-tasks
    API->>Backend: POST /webapps/chat/check-incomplete-tasks
    
    Backend->>Backend: 查找24小时内未完成消息
    Backend->>Service: 恢复每个未完成任务
    
    loop 处理每个未完成任务
        Service->>Agent: get_task_progress(task_id)
        Agent->>Agent: 从state_snapshot读取进度
        
        alt 任务仍在运行
            Agent-->>Service: 返回当前进度
            Service->>Service: 更新消息task_steps
        else 任务已完成
            Agent-->>Service: 返回完整结果
            Service->>Service: 更新消息内容和状态
            Service->>Service: 设置is_complete=True
        else 任务超时（3分钟未更新）
            Agent->>Agent: 标记任务为FAILED
            Service->>Service: 更新消息错误状态
        end
    end
    
    Backend-->>API: 返回恢复结果<br/>{updated: n, messages: [...]}
    API-->>Page: 返回恢复状态
    
    alt 有任务被更新
        Page->>API: 重新GET /api/chat/sessions/{sessionId}/messages
        API->>Backend: 获取更新后的消息
        Backend-->>API: 返回最新消息列表
        API-->>Page: 更新消息显示
    end
    
    alt 任务仍在执行
        Page->>Page: 建立SSE重连
        Page->>API: POST /api/chat/sessions/{sessionId}/messages<br/>message: "[RECONNECT]", task_id: xxx
        
        API->>API: 检测到重连请求
        API->>Backend: GET /webapps/chat/tasks/{task_id}/stream/?reconnect=true
        
        Backend->>SSE: 建立SSE连接
        SSE->>SSE: 继续推送未完成的进度事件
        
        loop SSE事件流
            SSE-->>API: 转发进度事件
            API-->>Page: 更新UI显示
        end
        
        SSE-->>API: event: task_completed
        API-->>Page: 更新最终结果
    end
```

#### 任务恢复机制

```mermaid
graph TB
    subgraph 未完成任务检测
        A1[加载会话消息] --> A2{检查is_complete}
        A2 -->|false| A3[发起任务恢复]
        A2 -->|true| A4[正常显示]
    end
    
    subgraph 任务状态同步
        B1[check_incomplete_tasks] --> B2[查询24小时内任务]
        B2 --> B3[获取AgentTask状态]
        
        B3 --> B4{任务状态}
        B4 -->|RUNNING| B5[从state_snapshot获取进度]
        B4 -->|COMPLETED| B6[获取完整结果]
        B4 -->|FAILED| B7[标记错误]
        B4 -->|超时| B8[自动标记失败]
    end
    
    subgraph 重连机制
        C1[检测到运行中任务] --> C2[发送RECONNECT请求]
        C2 --> C3[重新建立SSE连接]
        C3 --> C4[继续接收进度事件]
        C4 --> C5[更新UI显示]
    end
    
    subgraph 数据更新
        D1[task_steps更新] --> D2[ChatMessage.task_steps]
        D2 --> D3[保存到数据库]
        D3 --> D4[前端重新加载]
        D4 --> D5[显示最新状态]
    end
```

## 关键数据结构说明

### 前端Message接口
```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  task_id?: string;
  is_complete?: boolean;
  taskSteps?: TaskStep[];
  finalWebSearchResults?: any[];
}
```

### 后端ChatMessage模型
```python
class ChatMessage(models.Model):
    session = ForeignKey(ChatSession)
    role = CharField()  # 'user', 'assistant', 'system'
    content = TextField()
    task_id = CharField(null=True)
    is_complete = BooleanField(default=True)
    task_steps = JSONField(null=True)
    files_info = JSONField(null=True)
    is_deleted = BooleanField(default=False)
```

### AgentTask模型
```python
class AgentTask(models.Model):
    task_id = UUIDField(primary_key=True)
    graph = ForeignKey(Graph)
    status = CharField()  # PENDING, RUNNING, COMPLETED, FAILED
    state_snapshot = JSONField()
    session_task_history = JSONField()  # 会话历史任务ID列表
```

### RuntimeState结构
```python
class RuntimeState:
    """
    表示智能体图的全局运行时状态。
    维护了智能体在执行任务过程中的所有关键信息。
    """
    def __init__(self, 
                 task_goal: str,                              # 任务目标（包含usage的完整描述）
                 preprocessed_files: Optional[Dict[str, Any]], # 预处理后的文件数据
                 origin_images: Optional[List[str]],          # 原始图片（base64格式）
                 usage: Optional[str],                        # 任务类型标签
                 action_history: Optional[List[Dict[str, Any]]], # 行动历史
                 context_memory: Optional[Dict[str, Any]],    # 会话级上下文记忆
                 user_context: Optional[Dict[str, Any]],      # 用户上下文（ID、角色、权限等）
                 chat_history: Optional[List[Dict[str, str]]]): # 历史对话（OpenAI格式）
        
        # 实际存储的字段
        self.task_goal: str  # 组合了usage和原始task_goal的完整描述
        self.preprocessed_files: Dict[str, Any] = {
            'documents': {},    # markdown格式的文档内容
            'tables': {},       # 表格数据结构
            'images': {},       # 图片的文字描述
            'other_files': {}   # 其他类型文件
        }
        self.origin_images: List[str]  # base64格式的原始图片
        self.action_history: List[Dict[str, Any]]  # 包含'type'和'data'的字典列表
        self.context_memory: Dict[str, Any]  # 跨任务保持的重要信息
        self.user_context: Dict[str, Any]  # 用户相关信息
```

### ActionSteps结构（action_history中的元素）
```python
# action_history中的每个元素结构
{
    'type': str,  # 动作类型：'plan', 'tool_output', 'reflection', 'final_answer'等
    'data': {
        # PlannerOutput场景
        'thought': str,           # 规划器的推理过程
        'action': str,            # 'CALL_TOOL' 或 'FINISH'
        'tool_name': str,         # 工具名称
        'tool_input': Dict,       # 工具输入参数
        'expected_outcome': str,  # 期望结果
        
        # ToolOutput场景
        'status': str,            # 'success', 'failed', 'partial'
        'message': str,           # 执行情况描述
        'primary_result': Any,    # 主要结果
        'key_metrics': Dict,      # 关键指标
        
        # Reflection场景
        'conclusion': str,        # 结果总结
        'is_finished': bool,      # 是否正常完成
        'is_sufficient': bool,    # 结果是否充分
        
        # FinalAnswer场景
        'answer': str,            # 最终回答内容
        'title': str,             # 会话标题
    },
    'timestamp': str,  # ISO格式时间戳
    'action_id': str,  # 唯一标识符，格式为 'action_{timestamp}'
}
```