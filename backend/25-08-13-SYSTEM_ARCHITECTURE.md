# Backend 系统架构图

## 系统启动架构和执行流程

```mermaid
graph TB
    subgraph "外部请求层"
        Client[客户端]
        WebUI[Web界面]
        API[REST API]
    end

    subgraph "应用服务层"
        subgraph "Django Application"
            ASGI[Daphne ASGI Server<br/>端口: 6066]
            Django[Django Framework<br/>+ DRF API]
            Auth[认证服务<br/>飞书OAuth]
        end
        
        PM2[PM2进程管理器<br/>ChageeX]
    end

    subgraph "数据库层"
        subgraph "PostgreSQL集群"
            PGBouncer[PgBouncer连接池<br/>端口: 6432<br/>事务级池化]
            PostgreSQL[(PostgreSQL<br/>端口: 5432<br/>主数据库)]
            
            PGBouncer -->|池化连接<br/>800连接池| PostgreSQL
        end
        
        subgraph "Redis缓存"
            RedisCache[Redis DB1<br/>缓存层]
            RedisQueue[Redis DB0<br/>消息队列]
        end
    end

    subgraph "异步任务处理层"
        CeleryBeat[Celery Beat<br/>定时任务调度]
        
        subgraph "Celery Workers Pool"
            WorkerGroup1[Worker组 1-10<br/>gevent协程池<br/>100并发/worker]
            WorkerGroup2[Worker组 11-20<br/>gevent协程池<br/>100并发/worker]
            WorkerGroup3[Worker组 21-30<br/>gevent协程池<br/>100并发/worker]
            WorkerGroup4[Worker组 31-40<br/>gevent协程池<br/>100并发/worker]
        end
        
        subgraph "任务类型"
            ImageTask[图片编辑任务<br/>process_image_edit]
            AgentTask[智能代理任务<br/>run_graph_task]
            DocTask[文档解析任务<br/>process_document]
            CleanTask[清理维护任务]
        end
    end

    subgraph "AI服务层"
        Volcengine[火山引擎API<br/>图片编辑/分割]
        LLMService[LLM服务<br/>GPT/Claude等]
        MinerU[MinerU服务<br/>PDF解析]
    end

    subgraph "系统管理层"
        Systemd[Systemd服务<br/>celery_gevent.service]
        Scripts[启动脚本<br/>prod_start_*.sh]
        Logs[日志系统<br/>Django/Celery/PM2]
    end

    %% 连接关系
    Client --> ASGI
    WebUI --> ASGI
    API --> ASGI
    
    ASGI --> Django
    Django --> Auth
    Django -->|直连/池化| PGBouncer
    Django -->|缓存| RedisCache
    Django -->|任务推送| RedisQueue
    
    PM2 -.->|管理| ASGI
    
    RedisQueue -->|任务分发| WorkerGroup1
    RedisQueue -->|任务分发| WorkerGroup2
    RedisQueue -->|任务分发| WorkerGroup3
    RedisQueue -->|任务分发| WorkerGroup4
    
    CeleryBeat -->|定时任务| RedisQueue
    
    WorkerGroup1 --> ImageTask
    WorkerGroup2 --> AgentTask
    WorkerGroup3 --> DocTask
    WorkerGroup4 --> CleanTask
    
    ImageTask --> Volcengine
    AgentTask --> LLMService
    DocTask --> MinerU
    
    WorkerGroup1 -->|结果存储| PostgreSQL
    WorkerGroup2 -->|结果存储| PostgreSQL
    WorkerGroup3 -->|结果存储| PostgreSQL
    WorkerGroup4 -->|结果存储| PostgreSQL
    
    Systemd -.->|管理| WorkerGroup1
    Systemd -.->|管理| WorkerGroup2
    Systemd -.->|管理| WorkerGroup3
    Systemd -.->|管理| WorkerGroup4
    Scripts -.->|启动| WorkerGroup1
    Scripts -.->|启动| WorkerGroup2
    Scripts -.->|启动| WorkerGroup3
    Scripts -.->|启动| WorkerGroup4
    
    WorkerGroup1 -.->|日志| Logs
    WorkerGroup2 -.->|日志| Logs
    WorkerGroup3 -.->|日志| Logs
    WorkerGroup4 -.->|日志| Logs
    Django -.->|日志| Logs

    style Client fill:#e1f5fe
    style WebUI fill:#e1f5fe
    style API fill:#e1f5fe
    style Django fill:#fff3e0
    style ASGI fill:#fff3e0
    style Auth fill:#fff3e0
    style PGBouncer fill:#e8f5e9
    style PostgreSQL fill:#e8f5e9
    style RedisCache fill:#ffebee
    style RedisQueue fill:#ffebee
    style WorkerGroup1 fill:#f3e5f5
    style WorkerGroup2 fill:#f3e5f5
    style WorkerGroup3 fill:#f3e5f5
    style WorkerGroup4 fill:#f3e5f5
    style Volcengine fill:#fce4ec
    style LLMService fill:#fce4ec
    style MinerU fill:#fce4ec
```

## 系统启动顺序

```mermaid
sequenceDiagram
    participant Init as 系统初始化
    participant DB as PostgreSQL
    participant PGB as PgBouncer
    participant Redis as Redis
    participant Django as Django App
    participant PM2 as PM2
    participant Celery as Celery Workers
    participant System as 系统就绪

    Init->>DB: 1. 启动PostgreSQL (5432)
    DB-->>Init: 数据库就绪
    
    Init->>PGB: 2. 启动PgBouncer (6432)
    PGB->>DB: 建立连接池
    PGB-->>Init: 连接池就绪
    
    Init->>Redis: 3. 启动Redis (6379)
    Redis-->>Init: 缓存和队列就绪
    
    Init->>PM2: 4. PM2启动Django
    PM2->>Django: 启动Daphne ASGI (6066)
    Django->>PGB: 测试数据库连接
    Django->>Redis: 测试Redis连接
    Django-->>PM2: Django应用就绪
    
    Init->>Celery: 5. 启动Celery Workers
    loop 启动40个Workers
        Celery->>Celery: 启动Worker (100并发/gevent)
        Note over Celery: 间隔0.5秒错开启动
    end
    Celery->>Redis: 连接任务队列
    Celery->>PGB: 连接数据库
    Celery-->>Init: Workers就绪
    
    Init->>System: 6. 系统启动完成
    Note over System: 总并发能力: 4000<br/>QPS: 170+
```

## 任务执行流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant API as Django API
    participant DB as PostgreSQL
    participant Queue as Redis Queue
    participant Worker as Celery Worker
    participant AI as AI服务
    participant Cache as Redis Cache

    User->>API: 1. 提交任务请求
    API->>DB: 2. 创建任务记录<br/>(状态: pending)
    API->>Queue: 3. 推送任务到队列
    API->>User: 4. 返回任务ID
    
    Worker->>Queue: 5. 获取任务 (预取4个)
    Worker->>DB: 6. 更新状态<br/>(状态: processing)
    Worker->>Cache: 7. 检查缓存
    
    alt 缓存命中
        Cache->>Worker: 返回缓存结果
    else 缓存未命中
        Worker->>AI: 8. 调用AI服务
        AI->>Worker: 9. 返回处理结果
        Worker->>Cache: 10. 更新缓存
    end
    
    Worker->>DB: 11. 保存结果<br/>(状态: completed)
    Worker->>User: 12. 执行回调(如配置)
    
    User->>API: 13. 查询任务状态
    API->>DB: 14. 获取任务结果
    API->>User: 15. 返回处理结果
```

## 关键性能指标

### 并发能力
- **总并发数**: 40 workers × 100 gevent = 4000
- **QPS**: 170+ 请求/秒
- **任务处理**: 4000 并发任务

### 连接池配置
| 组件 | 配置 | 说明 |
|------|------|------|
| PgBouncer | 800连接池 | 事务级池化 |
| PostgreSQL | 1200最大连接 | 数据库上限 |
| Redis | 500连接池 | 任务队列+缓存 |
| Django | 150连接池 | 直连模式时 |

### 超时配置
| 任务类型 | 软超时 | 硬超时 | 说明 |
|----------|--------|--------|------|
| 默认任务 | 120秒 | 180秒 | 通用任务 |
| 图片处理 | 180秒 | 240秒 | AI处理耗时 |
| 文档解析 | 300秒 | 360秒 | 大文件处理 |

### 内存管理
- **Worker重启**: 每处理500个任务后重启
- **PM2内存限制**: 2GB上限，自动重启
- **预取优化**: prefetch_multiplier=4

## 故障恢复机制

1. **进程级恢复**
   - PM2自动重启Django (最多10次)
   - Systemd自动重启Celery (5秒延迟)
   - Worker子进程自动重建

2. **连接级恢复**
   - PgBouncer连接健康检查
   - Redis连接自动重连
   - TCP Keepalive保活

3. **任务级恢复**
   - 任务超时自动终止
   - 卡住任务定期检查
   - 失败任务重试机制

## 部署检查清单

- [ ] PostgreSQL服务运行在5432端口
- [ ] PgBouncer服务运行在6432端口
- [ ] Redis服务运行在6379端口
- [ ] 环境变量USE_PGBOUNCER=true
- [ ] Django应用通过PM2管理
- [ ] 40个Celery Workers已启动
- [ ] 日志目录权限正确
- [ ] 系统资源充足(16GB+ RAM)