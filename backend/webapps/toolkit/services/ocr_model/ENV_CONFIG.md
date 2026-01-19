# OCR 服务环境变量配置说明

## 配置项

### 1. OCR 模型 API 地址（OCRModelService 使用）

```bash
# OCR模型API地址（远程DeepSeek-OCR服务）
OCR_API_URL=http://172.22.217.66:9123

# OCR请求超时时间（秒）
OCR_API_TIMEOUT=300
```

**说明：**
- `OCR_API_URL`: OCRModelService 直接调用的远程 OCR 模型 API 地址
- 这个地址是内网部署的 DeepSeek-OCR 服务
- Django OCR 视图会通过 OCRModelService 调用这个 API

### 2. Django OCR API 地址（Step1 使用）

```bash
# Django OCR服务地址（本地localhost）
DJANGO_OCR_API_URL=http://localhost:8000/api/toolkit/ocr
```

**说明：**
- `DJANGO_OCR_API_URL`: Step1 文本提取器通过 HTTP 请求调用的 Django OCR 视图地址
- 默认为 `http://localhost:8000/api/toolkit/ocr`
- Step1 → HTTP 请求 → Django 视图 → OCRModelService → 远程 OCR API

## 调用链路

```
┌─────────┐  HTTP请求   ┌────────────┐  调用Service  ┌──────────────┐  HTTP请求   ┌─────────────┐
│  Step1  │ ─────────> │ Django OCR │ ───────────> │ OCRModel     │ ─────────> │ DeepSeek    │
│文本提取器│            │   视图     │              │   Service    │            │ OCR API     │
└─────────┘            └────────────┘              └──────────────┘            └─────────────┘
   使用:                 URL路由:                    读取配置:                   内网地址:
DJANGO_OCR_             /api/toolkit/ocr/          OCR_API_URL             172.22.217.66:9123
API_URL
```

## 完整 .env 示例

```bash
# ===========================================
# OCR 服务配置
# ===========================================

# 1. Django OCR API地址（Step1使用）
DJANGO_OCR_API_URL=http://localhost:8000/api/toolkit/ocr

# 2. OCR模型API地址（OCRModelService使用）
OCR_API_URL=http://172.22.217.66:9123
OCR_API_TIMEOUT=300
```

## 不同部署场景

### 场景1：开发环境（默认）
```bash
# Step1通过localhost调用Django视图
DJANGO_OCR_API_URL=http://localhost:8000/api/toolkit/ocr

# Django视图通过内网调用OCR模型
OCR_API_URL=http://172.22.217.66:9123
```

### 场景2：生产环境
```bash
# Step1调用生产环境的Django API
DJANGO_OCR_API_URL=http://your-domain.com/api/toolkit/ocr

# Django视图调用OCR模型（内网地址不变）
OCR_API_URL=http://172.22.217.66:9123
```

### 场景3：Docker容器
```bash
# Step1调用Django容器
DJANGO_OCR_API_URL=http://django-backend:8000/api/toolkit/ocr

# Django调用OCR模型容器
OCR_API_URL=http://ocr-service:9123
```

## API 端点说明

Django OCR 服务提供以下端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/toolkit/ocr/health/` | GET | 健康检查 |
| `/api/toolkit/ocr/image/` | POST | 识别单张图片 |
| `/api/toolkit/ocr/images/batch/` | POST | 批量识别图片 |
| `/api/toolkit/ocr/info/` | GET | 获取服务信息 |

## 测试配置

### 测试 Django OCR 视图
```bash
curl -X GET http://localhost:8000/api/toolkit/ocr/health/
```

### 测试远程 OCR API
```bash
curl -X GET http://172.22.217.66:9123/health
```

## 常见问题

### Q: Step1 为什么不直接调用 OCRModelService？

A: 通过 HTTP 请求调用 Django 视图的好处：
1. **解耦合**: Step1 不直接依赖 OCRModelService 实现
2. **可测试**: 可以独立测试 Django API 和 Step1
3. **灵活部署**: Step1 可以在不同的进程/容器中运行
4. **统一接口**: 其他服务也可以通过 HTTP 调用 OCR 功能

### Q: 如何切换 OCR API 地址？

A: 修改 `.env` 文件中的 `OCR_API_URL` 即可：
```bash
# 切换到测试环境
OCR_API_URL=http://test-ocr-server:9123

# 切换回生产环境
OCR_API_URL=http://172.22.217.66:9123
```

### Q: Django OCR 视图可以独立使用吗？

A: 可以！任何客户端都可以通过 HTTP 调用 Django OCR 视图：
- 前端应用
- 其他 Python 脚本
- 命令行工具（curl）
- 其他微服务
