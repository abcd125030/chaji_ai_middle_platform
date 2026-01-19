# 后端认证文档

## 概述
`backend/authentication/` 模块实现用户认证功能。

## 模型 (`models.py`)

### 扩展用户模型
- 基于Django的`AbstractUser`扩展，增加了以下字段：
	- `auth_type`：认证类型（邮箱注册、飞书登录等）
	- `external_id`：外部平台ID
	- `avatar_url`：用户头像URL

### OAuth模型
- **OAuthState**：存储OAuth状态参数，防止CSRF攻击
- **FeishuAuth**：存储飞书用户认证数据
	- `open_id`
	- `union_id`
	- `access_token`
	- `refresh_token`
	- `token_expires_at`

## 序列化器 (`serializers.py`)

- **UserSerializer**
	- 字段：`id`、`username`、`email`、`auth_type`、`avatar_url`
- **FeishuAuthSerializer**
	- 字段：`user`、`open_id`、`union_id`、`token_expires_at`
- **FeishuLoginSerializer**
	- 验证飞书登录的`code`和`state`参数
- **TokenSerializer**
	- 字段：`access`、`refresh`、`token_type`

## 视图 (`views.py`)

### FeishuLoginView
- **GET方法**
	- 生成飞书授权URL，包含：
		- `client_id`
		- `response_type`
		- `state`
		- `redirect_uri`
		- `scope`
		- PKCE参数（如果启用）

- **POST方法**
	1. 处理飞书回调
	2. 验证状态参数
	3. 获取访问令牌
	4. 获取用户信息
	5. 创建/更新用户
	6. 生成JWT令牌
	7. 清理状态和验证码

### 辅助方法
- `_get_feishu_token`：从飞书API请求访问令牌
- `_get_feishu_user_info`：使用访问令牌获取用户信息
- `_get_or_create_user`：创建/更新用户和飞书认证记录

## URL配置 (`urls.py`)

### 飞书路由
- `/feishu/login/`：授权URL生成
- `/feishu/callback/`：回调处理

### JWT路由
- `/token/refresh/`：令牌刷新
- `/token/verify/`：令牌验证