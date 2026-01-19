# 文档作用
描述服务层能力和文件关联

# 书写格式
按以下格式书写
```
[服务名称]
[直接代码文件]
[关联的代码文件]
[服务用途和能力描述]
[服务处理流程图]
```

# 规范
- 禁止细述代码
- 禁止对服务用途发散

# 服务能力描述

## MultiAuthService
### 直接代码文件
- authentication/services/multi_auth_service.py

### 关联的代码文件
- authentication/models.py (User, UserAccount)
- authentication/services/utils/user_utils.py
- authentication/services/utils/token_utils.py

### 服务用途和能力描述
多账号认证核心服务，提供OAuth用户的创建、登录、绑定和解绑功能，支持多种登录方式的统一管理。**创建新用户时调用UserProfileManager.determine_user_status()决定激活状态**。

### 服务处理流程图
```
OAuth登录 → 查找已有账号 → 存在则更新令牌
                ↓
           不存在 → 查找用户 → 创建新用户(根据配置决定激活状态) → 创建账号关联
                      ↓
                  已有用户 → 创建账号关联
```

## OAuthService
### 直接代码文件
- authentication/services/oauth_service.py

### 关联的代码文件
- authentication/services/multi_auth_service.py
- authentication/services/utils/token_utils.py
- authentication/services/utils/state_utils.py

### 服务用途和能力描述
OAuth认证服务基类及具体实现（GoogleAuthService、FeishuAuthService），处理OAuth授权流程、令牌交换和用户信息获取。

### 服务处理流程图
```
生成授权URL → 用户授权 → 接收授权码 → 交换访问令牌 → 获取用户信息 → 创建/登录用户(新用户根据配置设置激活状态)
```

## EmailAuthService
### 直接代码文件
- authentication/services/email_service.py

### 关联的代码文件
- authentication/models.py (User, UserAccount)
- authentication/services/utils/state_utils.py
- authentication/services/utils/user_utils.py
- authentication/services/utils/token_utils.py

### 服务用途和能力描述
邮箱认证服务，处理邮箱注册、登录、验证码发送和验证，支持新用户注册和已有用户登录。**创建新用户时调用UserProfileManager.determine_user_status()决定激活状态**。

### 服务处理流程图
```
邮箱登录 → 用户存在 → 验证密码 → 生成令牌
          ↓
      用户不存在 → 发送验证码 → 验证码验证 → 创建用户(根据REQUIRE_USER_ACTIVATION设置状态) → 生成令牌
```

## UserManagementService
### 直接代码文件
- authentication/services/user_management_service.py

### 关联的代码文件
- authentication/models.py (User, UserAccount)
- authentication/models_extension.py (UserProfile)

### 服务用途和能力描述
用户管理服务，提供用户激活、停用、封禁、查询、统计和角色管理功能，支持批量查询和分页。**核心激活方法：activate_user()和deactivate_user()，管理员通过这些方法手动激活或停用用户**。

### 服务处理流程图
```
管理操作请求 → 验证用户存在 → 检查当前状态 → 更新状态(ACTIVE/INACTIVE/BANNED) → 记录日志 → 返回结果
```

## TokenManager
### 直接代码文件
- authentication/services/utils/token_utils.py

### 关联的代码文件
- rest_framework_simplejwt

### 服务用途和能力描述
令牌管理工具，生成JWT令牌、PKCE验证码、状态令牌，计算令牌过期时间。

### 服务处理流程图
```
用户对象 → 生成RefreshToken → 生成AccessToken → 返回令牌对
```

## StateManager
### 直接代码文件
- authentication/services/utils/state_utils.py

### 关联的代码文件
- authentication/models.py (OAuthState)
- django.core.cache

### 服务用途和能力描述
状态管理工具，处理OAuth状态存储验证、邮箱验证码缓存、验证尝试次数控制。

### 服务处理流程图
```
创建状态 → 存储到数据库/缓存 → 验证时查询 → 使用后清理
```

## UserProfileManager
### 直接代码文件
- authentication/services/utils/user_utils.py

### 关联的代码文件
- authentication/models.py (User, UserAccount)
- authentication/models_extension.py (UserProfile)
- authentication/user_service.py
- 环境变量: REQUIRE_USER_ACTIVATION, REQUIRE_INVITATION_CODE

### 服务用途和能力描述
用户配置文件管理工具，确保UserProfile创建、**根据REQUIRE_USER_ACTIVATION和REQUIRE_INVITATION_CODE环境变量确定新用户激活状态（核心方法：determine_user_status）**、管理账号关联、生成唯一用户名。

### 服务处理流程图
```
determine_user_status() → 判断provider类型 → 飞书返回ACTIVE
                              ↓
                          其他provider → 检查环境变量 → 需要激活/邀请码返回INACTIVE
                                            ↓
                                        无特殊要求返回ACTIVE

ensure_user_profile() → 获取或创建UserProfile → 新建时应用配额模板(飞书:enterprise_user/其他:free_user)
```

## JoinWishService
### 直接代码文件
- authentication/services/join_wish_service.py

### 关联的代码文件
- authentication/models_extension.py (UserProfile)
- authentication/models.py (User)
- django.core.mail (邮件发送)
- 环境变量: EMAIL_HOST_USER, DEFAULT_FROM_EMAIL, SITE_NAME

### 服务用途和能力描述
Join Wish申请服务，处理用户加入意愿表单提交、邮件通知、申请审核和批量激活。**将申请数据存储在UserProfile.context_data的join_wish字段中**，支持管理员查看待审核列表和批量激活用户。

### 服务处理流程图
```
用户提交申请 → 保存到UserProfile.context_data → 发送确认邮件给用户 → 发送通知邮件给管理员
                                      ↓
                            管理员审核 → 批准申请 → 激活用户账号 → 发送激活通知邮件
```