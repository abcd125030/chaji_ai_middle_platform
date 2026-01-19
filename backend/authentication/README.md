# Authentication 应用

## 功能说明
多账号认证系统，支持邮箱、飞书等多种登录方式。

## 核心模型
- `User`: 用户主表（扩展了 Django User）
- `UserAccount`: 用户账号关联表（支持多种登录方式）
- `FeishuAuth`: 飞书认证（保留用于兼容）
- `EmailVerification`: 邮箱验证
- `OAuthState`: OAuth 状态管理

## 迁移说明
详见 `/backend/UNIFIED_MIGRATION_GUIDE.md`