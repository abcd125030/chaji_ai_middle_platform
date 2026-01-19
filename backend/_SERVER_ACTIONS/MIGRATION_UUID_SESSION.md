# ChatSession UUID 迁移指南

## 概述
本次迁移将 ChatSession 模型的主键从自增整数改为 UUID，以支持分布式部署和提高安全性。

## 迁移影响的组件

### 后端改动
1. **webapps.chat 应用**
   - `models.py`: ChatSession 模型添加 UUID 主键
   - `serializers.py`: 更新序列化器处理 UUID
   - `urls.py`: URL 路径参数从 `<int:session_id>` 改为 `<uuid:session_id>`
   - `views.py`: 视图函数自动兼容 UUID 参数
   - `services.py`: 移除 session_id 的类型提示，支持 UUID

2. **agentic 应用**
   - `models.py`: AgentTask.session_id 字段从 CharField 改为 UUIDField
   - `services.py`: session_id 处理已兼容（使用 str() 转换）

### 前端改动
- 无需修改：前端将 sessionId 作为字符串处理，UUID 会自动序列化为字符串

## 执行迁移步骤

### 1. 备份数据库（重要！）
```bash
# PostgreSQL 示例
pg_dump -U username -d database_name > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. 安装依赖
```bash
# 在虚拟环境中
source /data/data/com.termux/files/home/.venv_for_X/bin/activate
cd /storage/emulated/0/repos/X/backend
pip install -r requirements-termux.txt  # Termux 环境
# 或
pip install -r requirements-minimal.txt  # 标准环境
```

### 3. 执行数据库迁移
```bash
# 检查迁移脚本
python manage.py showmigrations

# 执行迁移
python manage.py migrate webapps.chat 0003_convert_session_id_to_uuid
python manage.py migrate agentic 0010_convert_session_id_to_uuid
```

### 4. 验证迁移结果
```bash
# Django shell 验证
python manage.py shell
```

```python
from webapps.chat.models import ChatSession
from agentic.models import AgentTask

# 检查 ChatSession
session = ChatSession.objects.first()
print(f"Session ID type: {type(session.id)}")  # 应该是 UUID
print(f"Session ID: {session.id}")

# 检查 AgentTask
task = AgentTask.objects.filter(session_id__isnull=False).first()
if task:
    print(f"Task session_id type: {type(task.session_id)}")  # 应该是 UUID
```

## 注意事项

### 数据迁移风险
1. **现有数据**: 迁移脚本会为现有的 ChatSession 记录生成新的 UUID
2. **外键关系**: ChatMessage 的外键关系会自动更新
3. **历史数据**: AgentTask 中的 session_id 需要手动更新（如果有历史数据）

### 回滚方案
如果迁移失败，可以通过以下步骤回滚：

```bash
# 回滚到迁移前的状态
python manage.py migrate webapps.chat 0002_rename_tables_to_standard
python manage.py migrate agentic 0009_actionsteps

# 恢复代码
git checkout -- backend/webapps/chat/models.py
git checkout -- backend/webapps/chat/serializers.py
git checkout -- backend/webapps/chat/urls.py
git checkout -- backend/webapps/chat/services.py
git checkout -- backend/agentic/models.py
```

## API 兼容性

### 变更前
- 创建会话返回: `{"id": 123, "sessionId": "123", ...}`
- API 路径: `/api/chat/sessions/123/messages/`

### 变更后
- 创建会话返回: `{"id": "550e8400-e29b-41d4-a716-446655440000", "sessionId": "550e8400-e29b-41d4-a716-446655440000", ...}`
- API 路径: `/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000/messages/`

### 前端兼容性
前端代码无需修改，因为：
1. sessionId 在前端一直作为字符串处理
2. localStorage 存储和读取不受影响
3. API 调用使用字符串插值，自动兼容

## 测试检查清单

- [ ] 创建新会话功能正常
- [ ] 会话列表加载正常
- [ ] 发送消息功能正常
- [ ] 会话历史记录加载正常
- [ ] AgentTask 能正确关联会话
- [ ] 前端页面刷新后能恢复会话

## 问题排查

### 常见问题

1. **迁移失败：外键约束错误**
   - 检查是否有孤立的 ChatMessage 记录
   - 清理无效数据后重试

2. **前端无法创建会话**
   - 检查 API 返回的 sessionId 格式
   - 确认前端 localStorage 中的 sessionId 格式

3. **历史会话无法加载**
   - 清理浏览器 localStorage 中的旧 sessionId
   - 重新创建会话

## 总结

此次迁移主要改动集中在后端数据库模型，前端代码基本不需要修改。迁移过程相对安全，但建议在生产环境执行前先在测试环境验证。