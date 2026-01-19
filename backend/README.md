# X Backend

基于 Django Rest Framework 开发的后端服务，提供认证和 API 接口。

## 主要功能

- 用户认证系统
  - 飞书第三方登录 (OAuth 2.0 with PKCE)
  - JWT token 认证
- RESTful API
- 跨域资源共享 (CORS)

## 技术栈

- Python 3.8+
- Django 5.1.5
- Django Rest Framework
- PostgreSQL
- JWT Authentication

## 从零开始的部署指南

### 1. 安装 Python

确保您的系统已安装 Python 3.8 或更高版本。

#### Windows
1. 访问 [Python 官网](https://www.python.org/downloads/)
2. 下载最新的 Python 安装程序
3. 运行安装程序，勾选 "Add Python to PATH"
4. 验证安装：`python --version`

#### macOS
使用 Homebrew：
```bash
brew install python
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

### 2. 安装和配置 PostgreSQL

#### Windows
1. 从 [PostgreSQL 官网](https://www.postgresql.org/download/windows/) 下载安装程序
2. 运行安装程序，记住设置的超级用户密码
3. 添加 PostgreSQL bin 目录到系统 PATH
4. 使用 pgAdmin 或命令行创建数据库：
```bash
psql -U postgres
CREATE DATABASE X;
```

#### macOS
使用 Homebrew：
```bash
# 安装 PostgreSQL
brew install postgresql@14

# 启动 PostgreSQL 服务
brew services start postgresql@14

# 创建数据库
createdb X
```

#### Linux (Ubuntu/Debian)
```bash
# 安装 PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# 启动 PostgreSQL 服务
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 切换到 postgres 用户
sudo -u postgres psql

# 创建数据库和用户
CREATE DATABASE X;
CREATE USER your_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE X TO your_user;
```

### 3. 克隆项目并配置环境

```bash
# 克隆项目
git clone [项目地址]
cd backend

# 创建并激活虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 升级 pip
python -m pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

### 4. 环境变量配置

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，设置必要的环境变量：
```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True

# 服务器设置
SERVER_HOST=http://localhost:8000
SERVER_PROTOCOL=http

# PostgreSQL 数据库设置
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres          # 或您创建的用户名
DB_PASSWORD=your_password
DB_DATABASE=X

# 飞书应用设置
FEISHU_APP_ID=your-feishu-app-id
FEISHU_APP_SECRET=your-feishu-app-secret

# 跨域设置
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

### 5. 数据库迁移

```bash
# 创建迁移文件（如果有模型更改）
python manage.py makemigrations

# 应用迁移
python manage.py migrate
```
# 静态文件迁移 
python manage.py collectstatic

### 6. 运行开发服务器
pm2 start ecosystem.config.js
```bash
# python manage.py runserver
```

### 7. 创建超级用户
python manage.py createsuperuser
输入用户名
输入邮箱
输入密码

访问 http://localhost:8000 验证服务是否正常运行。

## 项目结构

```
backend/
├── authentication/     # 认证应用
├── backend/           # 项目配置
├── .env              # 环境变量
├── .env.example      # 环境变量模板
├── manage.py         # Django 管理脚本
└── requirements.txt  # 项目依赖
```

## API 文档

### 认证相关接口

- 飞书登录
  - GET `/api/auth/feishu/login/` - 获取飞书授权 URL
  - POST `/api/auth/feishu/callback/` - 处理飞书回调

- JWT Token
  - POST `/api/auth/token/refresh/` - 刷新 access token
  - POST `/api/auth/token/verify/` - 验证 token

## 开发规范

- 遵循 PEP 8 编码规范
- 编写单元测试
- 使用 black 进行代码格式化
- 保持代码文档更新

## 测试

```bash
pytest
```

## 常见问题解决

### 数据库连接问题

1. 确保 PostgreSQL 服务正在运行
2. 验证数据库连接信息是否正确
3. 检查防火墙设置
4. PostgreSQL 配置文件 (pg_hba.conf) 是否允许连接

### 权限问题

1. Windows: 使用管理员权限运行命令提示符
2. Linux/macOS: 确保当前用户有足够权限

## 安全注意事项

- 在生产环境中必须：
  - 设置安全的 `SECRET_KEY`
  - 关闭 `DEBUG` 模式
  - 配置允许的 `ALLOWED_HOSTS`
  - 使用 HTTPS
  - 定期更新依赖包
  - 设置强密码策略
  - 定期备份数据库

## License

MIT