# Web 到 Backend 数据迁移实施方案

## 目标架构
将 Web 项目的数据存储完全迁移到 Backend，Web 层仅作为业务展示层和请求转发层。

```
用户 → 前端 → Web(路由转发) → Backend(业务逻辑+数据存储) → PostgreSQL
```

## 架构优势
1. **数据统一管理** - 单一数据源，避免数据不一致
2. **认证简化** - 统一的用户认证和授权系统
3. **运维简化** - 单一数据库实例，统一的监控和备份
4. **安全性提升** - 真实后端地址隐藏，通过 Web 层做安全过滤
5. **部署灵活** - Web 层轻量化，可快速部署到不同域名

## 实施步骤

### Phase 1: 数据模型迁移（第1-2周）

#### 1.1 分析现有 Prisma Schema
- 梳理 `/web/prisma/schema.prisma` 中的所有模型
- 识别与 Backend 现有模型的关联关系
- 确定迁移优先级

#### 1.2 创建 Django Models
```python
# backend/web_data/models.py
# 将 Prisma schema 转换为 Django models

# 示例：UserWebProfile
class UserWebProfile(models.Model):
    user_ai_id = models.CharField(primary_key=True, max_length=255)
    display_name = models.CharField(max_length=100, null=True, blank=True)
    avatar_url = models.TextField(null=True, blank=True)
    role = models.CharField(max_length=100, null=True, blank=True)
    preferences = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_web_profile'
```

#### 1.3 数据迁移脚本
- 编写数据导出脚本（从 Web 的 PostgreSQL）
- 编写数据导入脚本（到 Backend 的 PostgreSQL）
- 确保数据完整性和一致性

### Phase 2: API 接口开发（第2-3周）

#### 2.1 Backend API 开发
为每个业务模块创建 RESTful API：
- `/api/v1/users/` - 用户相关
- `/api/v1/chat/` - 聊天会话相关
- `/api/v1/agents/` - Agent 相关
- `/api/v1/workflows/` - 工作流相关
- `/api/v1/wishlist/` - 申请列表相关

#### 2.2 API 文档编写
使用 Django REST Framework 的 Swagger/OpenAPI 自动生成文档

### Phase 3: Web 层改造（第3-4周）

#### 3.1 移除 Prisma 依赖
- 删除 `/web/prisma` 目录
- 从 `package.json` 移除 Prisma 相关依赖
- 清理生成的 Prisma Client 代码

#### 3.2 实现 API 代理层
```typescript
// web/src/lib/backend-api.ts
class BackendAPI {
  private baseURL = process.env.BACKEND_URL;
  
  async request(endpoint: string, options?: RequestInit) {
    const token = await getAuthToken();
    return fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options?.headers
      }
    });
  }
  
  // 具体业务方法
  async getUserProfile(userId: string) {
    return this.request(`/api/v1/users/${userId}`);
  }
}
```

#### 3.3 修改现有 API Routes
将 `/web/src/app/api/` 下的所有路由改为调用 Backend API：

```typescript
// 原来：直接操作数据库
export async function GET(request: Request) {
  const session = await prisma.chatSession.findMany();
  return Response.json(session);
}

// 改为：调用 Backend API
export async function GET(request: Request) {
  const response = await backendAPI.getChatSessions();
  return Response.json(response);
}
```

### Phase 4: 性能优化（第4-5周）

#### 4.1 Backend 性能优化
- 添加 Redis 缓存层
- 优化数据库查询（添加索引、优化 N+1 查询）
- 实现分页和懒加载

#### 4.2 Web 层优化
- 实现请求合并（Batch API calls）
- 添加客户端缓存（SWR 或 React Query）
- 优化 SSR 性能

### Phase 5: 切换和验证（第5-6周）

#### 5.1 灰度发布
- 使用特性开关（Feature Flag）逐步切换
- 先在测试环境验证
- 逐步扩大用户范围

#### 5.2 数据一致性验证
- 对比新旧系统的数据
- 监控关键业务指标
- 收集用户反馈

#### 5.3 回滚方案
- 保留原 Web 数据库备份
- 准备快速回滚脚本
- 制定应急预案

## 技术要点

### 认证统一
```python
# Backend 提供统一认证接口
class AuthenticationAPI(APIView):
    def post(self, request):
        # 验证用户凭证
        # 返回 JWT token
        pass
```

### 错误处理
```typescript
// Web 层统一错误处理
class APIError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public details?: any
  ) {
    super(message);
  }
}

// 统一错误响应格式
function handleAPIError(error: APIError) {
  return Response.json(
    { error: error.message, details: error.details },
    { status: error.statusCode }
  );
}
```

### 监控和日志
- Backend: 使用 Django Logging + Sentry
- Web: 使用 Next.js 日志 + 前端监控
- 链路追踪: 使用 OpenTelemetry

## 风险和应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 数据迁移失败 | 高 | 多次测试迁移脚本，保留完整备份 |
| 性能下降 | 中 | 提前做压力测试，准备缓存方案 |
| API 不兼容 | 中 | 版本化 API，保持向后兼容 |
| 认证问题 | 高 | 充分测试，准备回滚方案 |

## 时间线

- **第1-2周**: 数据模型迁移
- **第2-3周**: Backend API 开发
- **第3-4周**: Web 层改造
- **第4-5周**: 性能优化
- **第5-6周**: 切换和验证
- **第6周后**: 监控和持续优化

## 成功标准

1. 所有数据成功迁移到 Backend
2. Web 层不再直接访问数据库
3. 系统性能不低于原有水平
4. 用户无感知切换
5. 运维成本降低 30%

## 后续优化

1. **引入 GraphQL** - 减少接口调用次数
2. **微服务化** - 将 Backend 按业务领域拆分
3. **容器化部署** - 使用 K8s 提升部署效率
4. **API 网关** - 统一入口，便于管理和监控