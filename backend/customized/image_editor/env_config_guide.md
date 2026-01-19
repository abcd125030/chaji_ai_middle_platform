# Image Editor 服务端测试配置指南

## 环境变量配置

### 1. 必须配置的环境变量

在服务器的 `.env` 文件中添加以下配置：

```bash
# Image Editor API 认证配置
IMAGE_EDITOR_APP_ID="your_app_id_here"        # 应用ID
IMAGE_EDITOR_APP_SECRET="your_app_secret_here" # 应用密钥

# API服务地址（可选，默认为localhost:8000）
API_BASE_URL="http://localhost:8000"          # 根据实际部署地址修改
```

### 2. 配置说明

#### IMAGE_EDITOR_APP_ID 和 IMAGE_EDITOR_APP_SECRET
- **用途**：用于API鉴权，获取JWT访问令牌
- **获取方式**：
  1. 登录Django Admin后台
  2. 进入 "Service_Api > External services" 
  3. 创建或查看已有的外部服务记录
  4. 记录对应的 `appid` 和 `appsecret`
- **注意**：这些凭证需要与数据库中 `ExternalService` 表的记录匹配

#### API_BASE_URL
- **用途**：指定API服务的基础地址
- **默认值**：`http://localhost:8000`
- **生产环境示例**：
  - `http://your-domain.com`
  - `https://api.your-domain.com`
  - `http://192.168.1.100:8000`

### 3. 在服务器上设置环境变量

#### 方法一：修改 .env 文件（推荐）

```bash
# 编辑项目根目录的 .env 文件
cd /www/wwwroot/repos/X/backend
vim .env

# 添加以下内容
IMAGE_EDITOR_APP_ID="your_actual_app_id"
IMAGE_EDITOR_APP_SECRET="your_actual_app_secret"
API_BASE_URL="http://localhost:8000"
```

#### 方法二：临时设置（仅用于测试）

```bash
# 在运行测试脚本前设置
export IMAGE_EDITOR_APP_ID="your_actual_app_id"
export IMAGE_EDITOR_APP_SECRET="your_actual_app_secret"
export API_BASE_URL="http://localhost:8000"

# 运行测试脚本
python test_submit_single_task.py
```

#### 方法三：在系统配置文件中设置（永久生效）

```bash
# 编辑用户的 bashrc 或 profile
vim ~/.bashrc

# 添加以下内容
export IMAGE_EDITOR_APP_ID="your_actual_app_id"
export IMAGE_EDITOR_APP_SECRET="your_actual_app_secret"
export API_BASE_URL="http://localhost:8000"

# 使配置生效
source ~/.bashrc
```

### 4. 验证配置

运行以下命令验证环境变量是否正确设置：

```bash
# 检查环境变量
echo $IMAGE_EDITOR_APP_ID
echo $IMAGE_EDITOR_APP_SECRET
echo $API_BASE_URL
```

### 5. 运行测试脚本

配置完成后，运行测试脚本：

```bash
# 进入脚本目录
cd /www/wwwroot/repos/X/backend/customized/image_editor/

# 运行测试
python test_submit_single_task.py
```

### 6. 创建测试用的 App ID 和 Secret

如果还没有创建外部服务凭证，可以通过以下方式创建：

#### 方法一：通过 Django Admin 创建

1. 访问 Django Admin：`http://your-server:8000/admin/`
2. 登录管理员账号
3. 进入 "Service_Api > External services"
4. 点击 "添加 External service"
5. 填写必要信息：
   - Name: `Image Editor Test`
   - Appid: 自动生成或手动输入
   - Appsecret: 自动生成或手动输入
   - User: 选择关联的用户
6. 保存记录

#### 方法二：通过 Django Shell 创建

```python
# 进入 Django shell
python manage.py shell

# 创建外部服务
from service_api.models import ExternalService
from authentication.models import User
import uuid

# 获取或创建测试用户
user = User.objects.get(username='your_username')  # 或使用 .first() 获取第一个用户

# 创建外部服务
service = ExternalService.objects.create(
    name="Image Editor Test Service",
    appid=str(uuid.uuid4()).replace('-', ''),
    appsecret=str(uuid.uuid4()).replace('-', ''),
    user=user
)

print(f"App ID: {service.appid}")
print(f"App Secret: {service.appsecret}")
```

### 7. 安全注意事项

1. **不要将凭证硬编码在代码中**
2. **不要将包含凭证的 .env 文件提交到版本控制系统**
3. **定期轮换 App Secret**
4. **在生产环境使用 HTTPS**
5. **限制 App ID 的权限范围**

### 8. 故障排查

如果测试失败，检查以下事项：

1. **环境变量是否正确设置**
   ```bash
   env | grep IMAGE_EDITOR
   ```

2. **API服务是否正常运行**
   ```bash
   curl http://localhost:8000/api/image-editor/
   ```

3. **数据库中是否存在对应的 ExternalService 记录**
   ```sql
   SELECT * FROM service_api_externalservice WHERE appid='your_app_id';
   ```

4. **查看服务器日志**
   ```bash
   tail -f /www/wwwroot/repos/X/backend/logs/django.log
   ```

5. **检查 Redis 和 Celery 是否正常运行**
   ```bash
   redis-cli ping
   celery -A backend inspect active
   ```