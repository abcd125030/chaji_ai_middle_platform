# 知识库系统环境配置指南

本文档详细说明了知识库系统的环境变量配置方法和最佳实践。

## 配置概述

随着系统更新，大部分核心服务配置(LLM、Embedder、向量数据库)已迁移至 Django Admin 界面的 `KnowledgeConfig` 模型中进行管理，环境变量配置已大幅简化。

## 1. Django 核心配置

这些是 Django 项目运行必需的基础配置，通常在 `.env` 文件中定义。

**配置要求**:
- 生产环境必须设置 SECRET_KEY
- 必须正确配置数据库连接
- DEBUG 模式在生产环境必须关闭

*   **`DJANGO_SECRET_KEY`**
    *   **描述**: Django 项目的密钥，用于加密签名等。
    *   **必需**: 是
    *   **示例**: `your_django_secret_key_here_please_change_me`

*   **`DJANGO_DEBUG`**
    *   **描述**: 控制 Django 是否运行在调试模式。生产环境应设为 `False`。
    *   **必需**: 是
    *   **示例**: `True` (开发), `False` (生产)

*   **`DATABASE_URL`** (或单独的数据库参数)
    *   **描述**:数据库连接字符串，或单独的 `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`。
    *   **必需**: 是
    *   **示例**: `postgres://user:password@host:port/dbname`

*   **(其他 Django 相关设置)**
    *   例如 `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` 等，根据您的部署环境配置。

## 2. 内部认证服务配置

**用途**:
当客户端通过 `app_id` 和 `secret` 获取 JWT token(用作 LLM API 密钥)时，需要配置认证服务地址。

**安全建议**:
- 认证服务必须使用 HTTPS
- 建议配置访问白名单
- 定期轮换认证密钥

*   **`INTERNAL_AUTH_SERVICE_URL`**
    *   **描述**: 内部认证服务的基础 URL。`knowledge` 应用的 `views.py` 中的 `fetch_internal_jwt_token` 函数会使用此 URL，并向其 `/api/auth/token` (或类似路径，具体取决于 `fetch_internal_jwt_token` 实现) 端点发送 `app_id` 和 `secret`。
    *   **必需**: 是 (如果启用了通过客户端 `app_id`/`secret` 获取 LLM API token 的功能)
    *   **示例**: `http://127.0.0.1:8000` (本地开发时指向 Django 自身) 或 `https://auth.internal.example.com`
    *   **注意**: 此 URL 不应包含末尾的 `/api/auth/token` 路径。

## 3. 核心服务配置(Admin管理)

**变更说明**:
所有核心服务配置(LLM、Embedder、向量存储)已迁移至 Django Admin 的 `KnowledgeConfig` 模型管理。

**管理要点**:
- 必须且只能有一个激活配置
- 修改配置后建议重启服务
- 敏感信息如API密钥需妥善保管

所有这些核心配置现在通过 Django Admin 界面中的 **`KnowledgeConfig`** 模型进行管理。请登录到 Django Admin 后台，导航到 "Knowledge Configurations" 部分进行以下设置：
*   LLM 提供商、模型名称、API 密钥、基础 URL、温度等。
*   Embedder 提供商、模型名称、API 密钥、基础 URL、维度等。
*   向量存储 (Qdrant) 的主机和端口。

在系统中，必须有且仅有一个 `KnowledgeConfig` 实例被标记为 **"激活" (Is Active)**。`knowledge` 应用将自动加载并使用这个激活的配置来初始化 `mem0ai` 服务。

如果客户端在 API 请求中提供了 `app_id` 和 `secret`，系统会尝试使用这些凭证通过 `INTERNAL_AUTH_SERVICE_URL` 获取一个 JWT token，并将此 token 用作该特定请求的 LLM API 密钥，从而覆盖 `KnowledgeConfig` 中配置的 LLM API 密钥。

## 4. 环境变量配置方法

**标准配置方式**:
所有环境变量应在项目根目录的 `.env` 文件中设置

**示例配置**:

```env
# .env

# Django Core Settings
DJANGO_SECRET_KEY="your_django_secret_key_here_please_change_me"
DJANGO_DEBUG="True"
DATABASE_URL="postgres://user:password@host:port/dbname"
# ALLOWED_HOSTS="localhost,127.0.0.1,yourdomain.com"

# Knowledge App Specific Environment Variables
# (主要用于支持客户端提供的 app_id/secret 获取 LLM token 的场景)
INTERNAL_AUTH_SERVICE_URL="http://127.0.0.1:8000"
```

确保您的 Django 项目配置了从 `.env` 文件加载环境变量的机制（例如使用 `python-dotenv` 库，并在 `settings.py` 或 `manage.py` 的早期阶段加载）。

在 `settings.py` 中，您可以像这样引用这些环境变量：

```python
# settings.py
import os
from dotenv import load_dotenv

load_dotenv() # 加载 .env 文件

# Django Core
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 't')
# ... 其他 Django 设置 ...

# Knowledge App
INTERNAL_AUTH_SERVICE_URL = os.getenv('INTERNAL_AUTH_SERVICE_URL')

# ... 其他设置 ...
```

**重要**:
*   切勿将包含真实密钥或敏感信息的 `.env` 文件提交到版本控制系统（如 Git）。应将其添加到 `.gitignore` 文件中。
*   为团队成员提供一个 `.env.example` 文件，其中包含所需的变量名但不包含真实值，作为配置模板。