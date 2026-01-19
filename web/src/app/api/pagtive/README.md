# Pagtive API 中转层

## 架构设计

这是 Web 端的 API 中转层，负责将前端请求转发到 Django 后端。

### 设计原则

1. **认证转发**: 使用 `authFetch` 自动处理认证，将用户身份信息转发到后端
2. **路径映射**: 前端访问 `/api/pagtive/*`，转发到后端 `/api/chat/pagtive/*`
3. **错误处理**: 统一的错误处理和响应格式
4. **类型安全**: 使用 TypeScript 定义所有接口类型

### API 端点

#### 项目管理
- `GET /api/pagtive/projects` - 获取项目列表
- `POST /api/pagtive/projects` - 创建新项目
- `GET /api/pagtive/projects/[projectId]` - 获取项目详情
- `PUT /api/pagtive/projects/[projectId]` - 更新项目
- `DELETE /api/pagtive/projects/[projectId]` - 删除项目

#### 页面管理
- `GET /api/pagtive/projects/[projectId]/pages` - 获取页面列表
- `POST /api/pagtive/projects/[projectId]/pages` - 创建新页面
- `GET /api/pagtive/projects/[projectId]/pages/[pageId]` - 获取页面详情
- `PUT /api/pagtive/projects/[projectId]/pages/[pageId]` - 更新页面
- `DELETE /api/pagtive/projects/[projectId]/pages/[pageId]` - 删除页面

#### AI 生成
- `POST /api/pagtive/generate` - AI 生成页面内容
- `POST /api/pagtive/generate/outline` - 生成项目大纲

#### 分享功能
- `GET /api/pagtive/share/[shareId]` - 获取分享项目（无需认证）

### 使用方式

在前端页面中使用 `pagtive-api.ts` 客户端：

```typescript
import { pagtiveAPI } from '@/lib/pagtive-api';

// 获取项目列表
const projects = await pagtiveAPI.getProjects();

// 创建新项目
const newProject = await pagtiveAPI.createProject({
  project_name: '我的项目',
  project_description: '项目描述',
});

// AI 生成页面
const result = await pagtiveAPI.generate({
  projectId: 'xxx',
  prompt: '创建一个登录页面',
  template: 'generatePageCode',
});
```

### 后端接口实现

后端需要在 Django 中实现对应的接口：

1. 在 `backend/pagtive/` 目录下创建相应的视图和路由
2. 使用 Django REST Framework 实现 RESTful API
3. 复用原 Pagtive 项目的数据模型和业务逻辑

### 数据流

```
前端页面
    ↓
pagtive-api.ts (客户端)
    ↓
/api/pagtive/* (Web 中转层)
    ↓
authFetch (认证处理)
    ↓
/api/chat/pagtive/* (Django 后端)
    ↓
数据库 (PostgreSQL)
```

### 注意事项

1. **认证**: 所有需要认证的接口都通过 `authFetch` 处理
2. **CORS**: 后端需要配置 CORS 允许前端访问
3. **错误处理**: 统一返回格式 `{ error: string }` 或 `{ success: true, data: any }`
4. **性能**: 考虑添加缓存机制，减少不必要的后端请求