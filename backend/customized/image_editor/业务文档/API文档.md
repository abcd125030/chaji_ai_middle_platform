# 图片风格编辑 API 文档

**版本**: 1.0.4  
**更新日期**: 2025-08-11

## 概述
本文档描述了图片风格编辑服务的 API 接口规范。该服务提供异步的图片风格编辑功能，通过文本提示词（prompt）和原始图片，使用 AI 模型生成风格化的图片。

## 服务域名
- **生产环境**: `https://aigc.chagee.com/_X/`
- **测试环境**: `http://139.196.110.242:8015/`

## 认证方式
所有接口均需要通过 Bearer Token 进行认证。

### 获取认证 Token
**接口地址**: `/api/service/auth/`  
**请求方式**: POST  
**请求示例**:
```bash
# 测试环境
curl -X POST 'http://139.196.110.242:8015/api/service/auth/' \
  -H 'Content-Type: application/json' \
  -d '{
    "appid": "your-app-id",
    "secret": "your-app-secret"
  }'

# 生产环境
curl -X POST 'https://aigc.chagee.com/_X/api/service/auth/' \
  -H 'Content-Type: application/json' \
  -d '{
    "appid": "your-app-id",
    "secret": "your-app-secret"
  }'
```

**成功响应示例**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 1800
}
```

**认证失败响应示例**:
```json
{
  "error": "Invalid appid/secret"
}
```

或

```json
{
  "error": "用户使用了错误的secret"
}
```

**服务内部错误响应**:
当认证服务本身出现内部错误时（如数据库连接失败、JWT生成异常等），会返回HTTP 500状态码，响应体可能为：
```json
{
  "error": "Internal server error"
}
```

**Token 有效期**:
- Access Token: 30 分钟（1800 秒）
- Refresh Token: 7 天

> 注：`expires_in` 字段返回的是秒数，1800 秒 = 30 分钟

## API 接口

### 1. 提交图片编辑任务

**接口地址**: `/api/customized/image_editor/submit/`  
**请求方式**: POST  
**Content-Type**: application/json  
**认证**: Bearer Token

#### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| prompt | string | 是 | 风格描述提示词，用于指导 AI 如何修改图片风格 |
| image | string | 是 | 需要编辑的图片 URL<br>**要求**：<br>- 必须是公网可访问的 HTTPS/HTTP 地址<br>- 图片格式：仅支持 JPG、PNG<br>- 图片尺寸：宽和高必须大于 14 像素<br>- 宽高比：宽/高 必须在 (1/3, 3) 范围内<br>- 文件大小：不超过 10MB |
| callback_url | string | 否 | 任务完成后的回调地址，即您的服务端接收结果的接口地址（强烈推荐使用） |

**请求示例**:
```bash
curl -X POST 'http://139.196.110.242:8015/api/customized/image_editor/submit/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <your-access-token>' \
  -d '{
    "prompt": "将这张照片转换为梵高的星空风格，保持原有的构图和主体",
    "image": "https://your-cdn.com/images/example.jpg",
    "callback_url": "https://your-domain.com/api/callback/image_editor"
  }'
```

#### 响应参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| code | integer | 业务状态码，0表示成功，非0表示具体的业务错误码 |
| data | object | 响应数据 |
| data.task_id | string | 任务唯一标识符（UUID格式） |
| data.status | string | 任务状态，固定返回 "processing" |
| data.estimated_time | integer | 预估处理时间（秒） |
| data.created_at | string | 任务创建时间（ISO 8601格式） |
| message | string | 响应消息 |
| timestamp | integer | 时间戳（Unix时间戳） |

**成功响应示例**:
```json
{
  "code": 0,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "estimated_time": 30,
    "created_at": "2024-01-01T12:00:00Z"
  },
  "message": "success",
  "timestamp": 1704067200
}
```

**错误响应示例**:
```json
{
  "code": 1003,
  "data": {},
  "message": "请求参数无效",
  "timestamp": 1704067200
}
```

### 2. 查询任务结果（仅供必要时使用）

> **注意**: 主要通过回调接收结果，此接口仅供特殊情况下主动查询使用。

**接口地址**: `/api/customized/image_editor/result/`  
**请求方式**: POST  
**Content-Type**: application/json  
**认证**: Bearer Token

#### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:
```bash
curl -X POST 'http://139.196.110.242:8015/api/customized/image_editor/result/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <your-access-token>' \
  -d '{
    "task_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

#### 响应参数

##### 成功状态响应

| 参数名 | 类型 | 描述 |
|--------|------|------|
| code | integer | 业务状态码，0表示成功，非0表示具体的业务错误码 |
| data | object | 响应数据 |
| data.task_id | string | 任务ID |
| data.status | string | 任务状态: "success" |
| data.data | object | 结果数据 |
| data.data.image | string | Base64 编码的生成图片（PNG 格式，包含透明通道） |
| data.data.original_prompt | string | 原始提示词 |
| data.processing_time | float | 实际处理时长（秒） |
| data.created_at | string | 任务创建时间 |
| data.completed_at | string | 任务完成时间 |
| message | string | 响应消息 |
| timestamp | integer | 时间戳（Unix时间戳） |

**成功响应示例**:
```json
{
  "code": 0,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "success",
    "data": {
      "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
      "original_prompt": "将这张照片转换为梵高的星空风格，保持原有的构图和主体"
    },
    "processing_time": 25.6,
    "created_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:00:25.600Z"
  },
  "message": "success",
  "timestamp": 1704067200
}
```

##### 处理中状态响应

```json
{
  "code": 0,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "created_at": "2024-01-01T12:00:00Z"
  },
  "message": "任务处理中",
  "timestamp": 1704067200
}
```

##### 失败状态响应

| 参数名 | 类型 | 描述 |
|--------|------|------|
| code | integer | 业务状态码，非0表示具体的业务错误码 |
| data | object | 响应数据 |
| data.task_id | string | 任务ID |
| data.status | string | 任务状态: "failed" |
| data.error | object | 错误信息 |
| data.error.code | string | 错误代码 |
| data.error.message | string | 错误描述 |
| data.error.details | string | 详细错误信息（可选） |
| message | string | 响应消息 |
| timestamp | integer | 时间戳（Unix时间戳） |

**失败响应示例（质量检查失败）**:
```json
{
  "code": 2001,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "failed",
    "error": {
      "code": "E2001",
      "message": "生成结果与原图偏差过大",
      "details": "图像相似度评分低于阈值"
    }
  },
  "message": "生成结果与原图偏差过大",
  "timestamp": 1704067200
}
```

**失败响应示例（模型调用失败）**:
```json
{
  "code": 3001,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "failed",
    "error": {
      "code": "E3001",
      "message": "AI模型生成失败",
      "details": "AI模型服务异常，请稍后重试"
    }
  },
  "message": "AI模型生成失败",
  "timestamp": 1704067200
}
```

### 3. 批量提交任务

**接口地址**: `/api/customized/image_editor/batch_submit/`  
**请求方式**: POST  
**Content-Type**: application/json  
**认证**: Bearer Token

#### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| tasks | array | 是 | 任务数组，每个元素包含 prompt 和 image |
| callback_url | string | 否 | 批量任务完成后的回调地址（强烈推荐使用） |

**请求限制**:
- 单次最多提交 100 个任务
- 请求体大小不超过 50MB

**tasks数组中每个元素的参数要求**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| prompt | string | 是 | 风格描述提示词，用于指导 AI 如何修改图片风格 |
| image | string | 是 | 需要编辑的图片 URL<br>**要求**：<br>- 必须是公网可访问的 HTTPS/HTTP 地址<br>- 图片格式：仅支持 JPG、PNG<br>- 图片尺寸：宽和高必须大于 14 像素<br>- 宽高比：宽/高 必须在 (1/3, 3) 范围内<br>- 文件大小：不超过 10MB |

**请求示例**:
```json
{
  "tasks": [
    {
      "prompt": "梵高风格",
      "image": "https://your-cdn.com/images/example1.jpg"
    },
    {
      "prompt": "水墨画风格",
      "image": "https://your-cdn.com/images/example2.jpg"
    }
  ],
  "callback_url": "https://your-domain.com/api/callback/batch_image_editor"
}
```

**响应参数**

| 参数名 | 类型 | 描述 |
|--------|------|------|
| code | integer | 业务状态码，0表示成功，非0表示具体的业务错误码 |
| data | object | 响应数据 |
| data.batch_id | string | 批量任务ID |
| data.tasks | array | 任务数组 |
| data.tasks[].task_id | string | 任务唯一标识符 |
| data.tasks[].status | string | 任务状态 |
| data.total_count | integer | 总任务数 |
| message | string | 响应消息 |
| timestamp | integer | 时间戳（Unix时间戳） |

**响应示例**:
```json
{
  "code": 0,
  "data": {
    "batch_id": "batch-550e8400-e29b-41d4-a716-446655440000",
    "tasks": [
      {
        "task_id": "550e8400-e29b-41d4-a716-446655440001",
        "status": "processing"
      },
      {
        "task_id": "550e8400-e29b-41d4-a716-446655440002",
        "status": "processing"
      }
    ],
    "total_count": 2
  },
  "message": "success",
  "timestamp": 1704067200
}
```

**重要说明**:
- 返回的 `tasks` 数组中的任务顺序与请求中的 `tasks` 数组顺序**严格一一对应**
- 第 N 个请求任务对应第 N 个返回的 task_id
- 请妥善保存任务顺序关系，以便后续处理回调结果

### 4. 批量查询结果（仅供必要时使用）

> **注意**: 主要通过回调接收结果，此接口仅供特殊情况下主动查询使用。

**接口地址**: `/api/customized/image_editor/batch_result/`  
**请求方式**: POST  
**Content-Type**: application/json  
**认证**: Bearer Token

#### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| task_ids | array | 是 | 任务ID数组，最多100个 |

**请求示例**:
```json
{
  "task_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

#### 响应参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| code | integer | 业务状态码，0表示成功，非0表示具体的业务错误码 |
| data | object | 响应数据 |
| data.results | array | 任务结果数组 |
| data.results[].task_id | string | 任务ID |
| data.results[].status | string | 任务状态 |
| data.results[].data | object | 任务数据（仅在成功时存在） |
| data.results[].data.image | string | Base64 编码的生成图片 |
| data.results[].data.original_prompt | string | 原始提示词 |
| data.results[].error | object | 错误信息（仅在失败时存在） |
| data.results[].error.code | string | 错误代码 |
| data.results[].error.message | string | 错误描述 |
| data.results[].error.details | string | 详细错误信息 |
| data.results[].processing_time | float | 实际处理时长（秒） |
| data.results[].created_at | string | 任务创建时间 |
| data.results[].completed_at | string | 任务完成时间 |
| message | string | 响应消息 |
| timestamp | integer | 时间戳（Unix时间戳） |

**响应示例**:
```json
{
  "code": 0,
  "data": {
    "results": [
      {
        "task_id": "550e8400-e29b-41d4-a716-446655440001",
        "status": "success",
        "data": {
          "image": "data:image/png;base64,...",
          "original_prompt": "梵高风格"
        },
        "processing_time": 25.6,
        "created_at": "2024-01-01T12:00:00Z",
        "completed_at": "2024-01-01T12:00:25.600Z"
      },
      {
        "task_id": "550e8400-e29b-41d4-a716-446655440002",
        "status": "failed",
        "error": {
          "code": "E2001",
          "message": "生成结果与原图偏差过大",
          "details": "图像相似度评分低于阈值"
        },
        "created_at": "2024-01-01T12:00:00Z"
      }
    ]
  },
  "message": "success",
  "timestamp": 1704067200
}
```

## 错误代码说明

### 通用错误代码（1xxx）

| 错误代码 | 描述 | HTTP 状态码 |
|----------|------|-------------|
| 1001 | 认证失败 | 401 |
| 1002 | 权限不足 | 403 |
| 1003 | 请求参数无效 | 400 |
| 1004 | 任务不存在 | 404 |
| 1005 | 请求频率过高（超过 QPS 限制） | 429 |
| 1006 | 服务器内部错误 | 500 |
| 1007 | 服务暂时不可用 | 503 |
| 1008 | 请求体过大 | 413 |
| 1009 | Token已过期 | 401 |

### 生成质量错误代码（2xxx）

| 错误代码 | 描述 | 说明 |
|----------|------|------|
| 2001 | 生成结果与原图偏差过大 | 图像相似度检测未通过，主体不一致（如原图为金鱼但生成了狗） |
| 2002 | 生成结果质量不符合预期 | 图像质量评分过低 |
| 2003 | 生成内容包含不当元素 | 内容审核未通过 |
| 2004 | 风格转换效果不明显 | 风格特征检测未达标 |
| 2005 | 生成结果不符合提示词要求 | 生成的图片与提示词描述不匹配 |

### 任务执行错误代码（3xxx）

| 错误代码 | 描述 | 说明 |
|----------|------|------|
| 3001 | 模型调用失败 | AI 模型服务异常 |
| 3002 | 图片下载失败 | 无法从提供的 URL 下载图片 |
| 3003 | 图片格式不支持 | 仅支持 JPG、PNG 格式 |
| 3004 | 图片尺寸不符合要求 | 宽高必须大于 14px，宽高比需在 (1/3, 3) 范围内 |
| 3005 | 任务超时 | 处理时间超过最大限制 |
| 3006 | 资源不足 | GPU/内存资源不足 |
| 3007 | 依赖服务异常 | 外部依赖服务不可用 |
| 3008 | 图片文件过大 | 图片文件大小超过 10MB 限制 |
| 3009 | 网络连接失败 | 无法建立网络连接 |
| 3010 | 图片URL无效 | 提供的图片URL格式不正确 |
| 3011 | 图片下载超时 | 下载图片时超过时间限制 |
| 3012 | 图片不存在 | 图片资源404错误 |
| 3013 | 提示词不合法 | 提示词包含敏感词或格式错误 |
| 3014 | 提示词过长 | 提示词超过最大长度限制 |
| 3015 | 背景移除失败 | 无法成功移除图片背景 |
| 3016 | 背景移除超时 | 背景移除处理超时 |
| 3017 | 图片解码失败 | 图片文件损坏或编码异常 |

### 宠物检测错误代码（4xxx）

| 错误代码 | 描述 | 说明 |
|----------|------|------|
| 4001 | 非宠物图片 | 检测到图片主体不是宠物 |
| 4002 | 无法识别图片内容 | 图片内容模糊或无法识别 |
| 4003 | 图片质量过低 | 图片分辨率或清晰度不足以进行检测 |
| 4004 | 多个主体检测 | 图片中包含多个主体，无法确定主要宠物 |
| 4005 | 宠物检测服务异常 | 宠物检测模型服务不可用 |
| 4006 | 宠物类型不支持 | 检测到的宠物类型暂不支持处理 |
| 4007 | 图中存在人类 | 不允许处理该图片 |

## 回调机制

### 单任务回调

当任务处理完成后，系统会向您（上游业务方）提供的 `callback_url` 发送 POST 请求。

**回调请求格式 (成功)**:
```json
{
  "code": 0,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "success",
    "data": {
      "image": "data:image/png;base64,...",
      "original_prompt": "原始提示词"
    },
    "processing_time": 25.6,
    "created_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:00:25.600Z"
  },
  "message": "success",
  "timestamp": 1704067200
}
```

**回调请求格式 (失败)**:
```json
{
  "code": 3001,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "failed",
    "error": {
      "code": "E3001",
      "message": "AI模型生成失败",
      "details": "模型服务暂时不可用"
    },
    "created_at": "2024-01-01T12:00:00Z"
  },
  "message": "AI模型生成失败",
  "timestamp": 1704067200
}
```

注意：回调中的顶层 `code` 字段会根据实际错误动态设置：
- 成功时为 `0`
- 失败时为对应错误码的数字部分（如 E3001 对应 3001）

**注意事项**:
- 每个任务完成后会独立触发回调
- 回调中的 `task_id` 可用于识别是批量提交中的哪个任务
- 任务可能不按提交顺序完成，请根据 `task_id` 匹配原始请求

**回调要求**:
- 您的回调接口应在 5 秒内响应
- 响应状态码应为 200
- 如果回调失败，系统会重试 3 次，间隔分别为 1 秒、5 秒、10 秒

> 注：`callback_url` 是您（上游业务方）的服务端地址，用于接收任务完成后的结果通知

## 性能指标

- **并发能力**: 支持 167 QPS（每秒请求数）
- **限流配置**:
  - 默认用户：167 QPS
  - VIP 用户：10 QPS
  - 批量接口：1 QPS
  - 单 IP 限制：20 QPS
- **平均处理时间**: 15-30 秒
- **最大处理时间**: 60 秒
- **支持输入图片格式**: JPG、PNG
- **输出图片格式**: PNG（带透明通道）
- **图片尺寸要求**: 
  - 最小：宽高均需大于 14 像素
  - 宽高比：必须在 (1/3, 3) 范围内
- **最大文件大小**: 10MB

## 最佳实践

1. **图片预处理**
   - 确保图片宽高比在 (1/3, 3) 范围内
   - 建议将图片压缩到 2048×2048 以内以获得最佳性能
   - 使用 JPG 格式可减少文件大小
   - 确保图片 URL 长期有效，避免处理时失效

2. **错误处理**
   - 实现指数退避的重试机制
   - 对于 2xxx 错误码，建议调整 prompt 后重试
   - 对于 3xxx 错误码，建议稍后重试

3. **并发控制**
   - 使用批量接口减少请求次数
   - 建议控制并发请求数，避免瞬时压力过大
   - 注意 QPS 限制，超过限制会返回 429 错误码
   - 建议实现客户端限流，避免频繁触发服务端限流

4. **监控建议**
   - 记录任务 ID 用于问题追踪
   - 监控任务成功率和平均处理时间

## 安全使用指南

### 认证安全
1. **密钥管理**
   - 请妥善保管您的 appid 和 secret，避免泄露
   - 不要将密钥硬编码在前端代码中
   - 建议使用环境变量或配置中心管理密钥

2. **调用建议**
   - 请从您的后端服务调用本接口，不要从前端直接调用
   - 确保您的服务器在内网环境中

### 数据安全
1. **图片数据处理**
   - 确保图片 URL 使用 HTTPS 传输（如果可能）
   - 建议对包含敏感信息的图片在上传到 CDN 前进行脱敏处理
   - 请勿在日志中记录完整的图片 URL（可能包含敏感参数）

2. **回调接口安全**
   - 请确保您的回调接口使用 HTTPS
   - 建议验证回调请求的来源（我们的回调请求将从以下 IP 段发出：[待定]）
   - 建议在回调接口实现幂等性，避免重复处理

### 使用建议
- 请避免重复提交相同的任务
- 建议在客户端实现请求去重和缓存机制
- 发生错误时，请参考错误码进行合理的重试
- 遇到 429 错误（请求频率过高）时，建议等待 1 秒后再重试
- 合理控制请求速率，避免超过 QPS 限制

## API 状态查询

- 生产环境状态页面: https://aigc.chagee.com/_X/api/customized/image_editor/status
- 测试环境状态页面: http://139.196.110.242:8015/api/customized/image_editor/status