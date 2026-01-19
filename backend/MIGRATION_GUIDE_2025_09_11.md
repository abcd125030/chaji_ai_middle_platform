# 服务器迁移操作指南 - 2025-09-11

## 重要说明
- 旧服务器：当前运行生产环境的服务器
- 新服务器：要迁移到的目标服务器
- 本指南假设新旧服务器都使用PostgreSQL数据库

## 一、旧服务器操作步骤

### 1. 准备阶段（不影响服务运行）

#### 1.1 备份当前代码
```bash
cd /path/to/project
git status  # 确认当前分支和状态
git add .
git commit -m "chore: 生产环境迁移前备份"
git push origin main  # 或你的生产分支
```

#### 1.2 备份数据库（完整备份）
```bash
# 创建备份目录
mkdir -p ~/backups/$(date +%Y%m%d)
cd ~/backups/$(date +%Y%m%d)

# 备份整个数据库
pg_dump -h localhost -U postgres -d X --verbose --no-owner --no-acl > X_full_backup_$(date +%Y%m%d_%H%M%S).sql

# 验证备份文件
ls -lh X_full_backup_*.sql
head -100 X_full_backup_*.sql  # 检查备份文件内容
```

#### 1.3 导出环境配置
```bash
# 备份环境变量文件
cp /path/to/project/backend/.env ~/backups/$(date +%Y%m%d)/env_backup.txt

# 记录当前Python包版本
cd /path/to/project/backend
source .venv/bin/activate
pip freeze > ~/backups/$(date +%Y%m%d)/requirements_current.txt
```

#### 1.4 记录服务状态
```bash
# 记录PM2服务状态
pm2 list > ~/backups/$(date +%Y%m%d)/pm2_status.txt
pm2 show django >> ~/backups/$(date +%Y%m%d)/pm2_status.txt
pm2 show celery_worker_1 >> ~/backups/$(date +%Y%m%d)/pm2_status.txt
pm2 show celery_beat >> ~/backups/$(date +%Y%m%d)/pm2_status.txt

# 记录端口占用
lsof -i :8000 > ~/backups/$(date +%Y%m%d)/port_status.txt
lsof -i :3000 >> ~/backups/$(date +%Y%m%d)/port_status.txt
```

### 2. 停机维护阶段（需要停止服务）

#### 2.1 设置维护页面（可选）
```bash
# 如果有Nginx，可以设置维护页面
# sudo vim /etc/nginx/sites-available/default
# 添加维护页面配置
```

#### 2.2 停止服务
```bash
# 停止前端服务
cd /path/to/project/web
pm2 stop next-app  # 或你的前端服务名

# 停止后端服务
cd /path/to/project/backend
pm2 stop django
pm2 stop celery_worker_1 celery_worker_2 celery_beat

# 确认服务已停止
pm2 list
ps aux | grep -E "django|celery|node"
```

#### 2.3 最终数据备份
```bash
# 再次备份数据库（包含最新数据）
pg_dump -h localhost -U postgres -d X --verbose --no-owner --no-acl > ~/backups/$(date +%Y%m%d)/X_final_backup_$(date +%Y%m%d_%H%M%S).sql

# 压缩备份文件
cd ~/backups/$(date +%Y%m%d)
tar -czf X_migration_backup_$(date +%Y%m%d).tar.gz *.sql *.txt
```

#### 2.4 传输数据到新服务器
```bash
# 使用scp传输备份文件到新服务器
scp ~/backups/$(date +%Y%m%d)/X_migration_backup_*.tar.gz user@new-server:/home/user/migration/

# 或使用rsync（更可靠）
rsync -avzP ~/backups/$(date +%Y%m%d)/X_migration_backup_*.tar.gz user@new-server:/home/user/migration/
```

## 二、新服务器操作步骤

### 1. 环境准备

#### 1.1 安装基础软件
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python和依赖
sudo apt install -y python3.12 python3.12-venv python3.12-dev
sudo apt install -y build-essential libpq-dev

# 安装PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 安装Redis
sudo apt install -y redis-server

# 安装Node.js (使用nvm)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20

# 安装pnpm
npm install -g pnpm

# 安装pm2
npm install -g pm2

# 安装Nginx
sudo apt install -y nginx
```

#### 1.2 创建数据库
```bash
# 切换到postgres用户
sudo -u postgres psql

# 在psql中执行
CREATE DATABASE X;
CREATE USER postgres WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE X TO postgres;
\q

# 配置PostgreSQL允许密码认证
sudo vim /etc/postgresql/14/main/pg_hba.conf
# 修改local和host的认证方式为md5
sudo systemctl restart postgresql
```

#### 1.3 克隆代码
```bash
# 创建项目目录
mkdir -p /home/user/projects
cd /home/user/projects

# 克隆代码仓库
git clone https://github.com/your-repo/X.git
cd X

# 切换到正确的分支
git checkout main  # 或你的生产分支
```

### 2. 后端部署

#### 2.1 解压备份文件
```bash
cd /home/user/migration
tar -xzf X_migration_backup_*.tar.gz
```

#### 2.2 恢复数据库
```bash
# 恢复数据库
psql -h localhost -U postgres -d X < X_final_backup_*.sql

# 验证数据
psql -h localhost -U postgres -d X -c "SELECT COUNT(*) FROM django_migrations;"
psql -h localhost -U postgres -d X -c "\dt"  # 查看所有表
```

#### 2.3 设置后端环境
```bash
cd /home/user/projects/X/backend

# 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt  # 或 requirements-minimal.txt

# 复制环境变量文件
cp /home/user/migration/env_backup.txt .env
# 编辑.env文件，更新数据库连接等配置
vim .env
```

#### 2.4 处理迁移文件
```bash
# 由于我们已经重置了迁移，直接使用新的迁移文件
# 检查迁移状态
python manage.py showmigrations

# 如果有未应用的迁移
python manage.py migrate --fake-initial

# 收集静态文件
python manage.py collectstatic --noinput
```

#### 2.5 测试后端服务
```bash
# 测试Django能否正常启动
python manage.py runserver 0.0.0.0:8000

# 在另一个终端测试API
curl http://localhost:8000/api/health/  # 或其他测试端点

# 测试成功后Ctrl+C停止
```

### 3. 前端部署

#### 3.1 设置前端环境
```bash
cd /home/user/projects/X/web

# 安装依赖
pnpm install

# 复制环境变量
cp .env.example .env.local
vim .env.local
# 更新以下配置：
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
# 其他必要的环境变量
```

#### 3.2 构建前端
```bash
# 构建生产版本
pnpm build

# 测试运行
pnpm start

# 在另一个终端测试
curl http://localhost:3000

# 测试成功后Ctrl+C停止
```

### 4. 启动生产服务

#### 4.1 使用PM2启动服务
```bash
# 启动后端
cd /home/user/projects/X/backend
pm2 start ecosystem.production.config.js

# 启动前端  
cd /home/user/projects/X/web
pm2 start ecosystem.config.js --env production

# 保存PM2配置
pm2 save
pm2 startup  # 设置开机自启
```

#### 4.2 配置Nginx
```bash
sudo vim /etc/nginx/sites-available/X

# 添加配置（示例）：
server {
    listen 80;
    server_name your-domain.com;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# 启用站点
sudo ln -s /etc/nginx/sites-available/X /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. 验证部署

#### 5.1 功能测试
```bash
# 检查服务状态
pm2 list
pm2 logs --lines 50

# 检查端口
netstat -tulpn | grep -E "3000|8000"

# 测试API
curl http://your-domain.com/api/health/

# 测试前端
curl http://your-domain.com/

# 检查日志
tail -f /home/user/projects/X/backend/logs/django.log
tail -f ~/.pm2/logs/django-out.log
```

#### 5.2 数据验证
```bash
# 登录数据库检查数据
psql -h localhost -U postgres -d X

# 检查重要表的数据
SELECT COUNT(*) FROM auth_user;
SELECT COUNT(*) FROM chat_sessions_session;
# 等等...
```

## 三、切换流程

### 1. DNS切换（推荐）
- 在DNS服务商处将域名指向新服务器IP
- TTL设置较短（如5分钟）以便快速切换
- 监控新服务器流量

### 2. 回滚方案
如果新服务器出现问题：
1. 立即将DNS切回旧服务器
2. 在旧服务器上重启服务：
```bash
cd /path/to/project/backend
pm2 start ecosystem.production.config.js
cd /path/to/project/web  
pm2 start ecosystem.config.js --env production
```

## 四、注意事项

### 重要提醒
1. **迁移文件一致性**：确保新旧服务器使用相同的迁移文件
2. **环境变量检查**：仔细核对所有环境变量，特别是：
   - 数据库连接信息
   - Redis连接信息
   - API密钥
   - 域名配置
3. **文件权限**：确保上传目录、日志目录有正确的权限
4. **防火墙配置**：开放必要的端口（80, 443, 22等）
5. **SSL证书**：配置Let's Encrypt或其他SSL证书

### 测试清单
- [ ] 用户登录功能
- [ ] 文件上传功能
- [ ] WebSocket连接（如果有）
- [ ] 定时任务（Celery Beat）
- [ ] 邮件发送（如果有）
- [ ] 支付功能（如果有）
- [ ] 知识库功能
- [ ] AI对话功能

### 监控设置
```bash
# 设置监控脚本
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 100M
pm2 set pm2-logrotate:retain 7

# 设置告警（可选）
# 配置pm2-slack或其他告警工具
```

## 五、故障排查

### 常见问题
1. **数据库连接失败**
   - 检查PostgreSQL服务状态
   - 验证.env中的数据库配置
   - 检查pg_hba.conf认证配置

2. **静态文件404**
   - 运行 `python manage.py collectstatic`
   - 检查Nginx静态文件配置

3. **WebSocket连接失败**
   - 确保使用ASGI（Daphne）而非WSGI
   - 检查Nginx WebSocket配置

4. **Celery任务不执行**
   - 检查Redis连接
   - 验证Celery worker和beat是否运行
   - 查看Celery日志

### 日志位置
- Django日志：`/home/user/projects/X/backend/logs/`
- PM2日志：`~/.pm2/logs/`
- Nginx日志：`/var/log/nginx/`
- PostgreSQL日志：`/var/log/postgresql/`

## 完成标志
✅ 所有服务正常运行
✅ 网站可以正常访问
✅ 核心功能测试通过
✅ 监控和日志正常
✅ 备份策略已设置