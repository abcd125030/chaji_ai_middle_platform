# 迁移文件清理和重建指南 - 2025-09-11

## 背景

由于历史原因，部分backend应用的表迁移记录混乱，导致在新环境部署时可能出现问题。通过压缩迁移文件，可以解决这个问题。

## 已发现的问题

1. **authentication应用**：存在两个0005迁移文件
   - `0005_user_extended_fields`
   - `0005_emailverification_useraccount_oauthstate_provider_and_more`

2. **delivery_performance应用**：数据库有5条迁移记录，但应用目录已不存在

## 已生成的压缩迁移文件

以下应用已成功生成压缩迁移文件：

```
✅ agentic: 0001_initial_squashed_0012_add_todo_update_log_type.py
✅ knowledge: 0001_initial_squashed_0008_remove_mem0_fields.py  
✅ router: 0001_initial_squashed_0013_add_adapter_config.py
✅ image_editor: 0001_initial_squashed_0014_add_callback_tracking_fields.py
✅ pagtive: 0001_initial_squashed_0006_add_reference_files.py
✅ customization: 0001_initial_squashed_0006_customizedqa_is_final_customizedqa_task_id.py
✅ chat_sessions: 0001_initial_squashed_0003_rename_tables_to_standard_format.py
✅ chat: 0001_initial_squashed_0002_add_soft_delete_to_chatmessage.py
```

## 手动修复项

### 1. 修复的语法错误

以下压缩迁移文件中的RunPython操作已被注释，因为引用路径有语法错误：
- `agentic/migrations/0001_initial_squashed_0012_add_todo_update_log_type.py`
- `customized/image_editor/migrations/0001_initial_squashed_0014_add_callback_tracking_fields.py`

### 2. 清理delivery_performance记录

```sql
-- 在数据库中执行
DELETE FROM django_migrations WHERE app = 'delivery_performance';
```

### 3. 处理authentication的重复0005

数据库中有两条0005记录，但文件系统只有一个文件。这在现有环境不影响使用，但新环境部署时需要注意。

## 部署指南

### 现有环境（已应用所有原始迁移）

无需任何操作，压缩迁移文件会被自动忽略。

### 新环境部署

1. **使用压缩迁移**
   ```bash
   # 新环境会自动使用压缩迁移文件
   python manage.py migrate
   ```

2. **如果遇到问题**
   ```bash
   # 使用fake-initial跳过初始迁移
   python manage.py migrate --fake-initial
   ```

### 清理旧迁移文件（可选）

**注意**：只有在确认所有环境都已应用原始迁移后才能删除！

```bash
# 示例：删除agentic的旧迁移（保留压缩文件）
rm agentic/migrations/000[1-9]*.py
rm agentic/migrations/001[0-2]*.py
# 保留 0001_initial_squashed_0012_add_todo_update_log_type.py
```

## 验证步骤

1. **检查迁移状态**
   ```bash
   python manage.py showmigrations
   ```

2. **运行清理脚本**
   ```bash
   python scripts/clean_migrations.py
   ```

3. **测试迁移计划**
   ```bash
   python manage.py migrate --plan
   ```

## 注意事项

1. 压缩迁移文件必须提交到版本控制
2. 不要删除原始迁移文件，直到所有环境都更新
3. 压缩迁移包含`replaces`字段，Django会智能处理
4. 新环境会使用压缩版本，老环境继续使用原始版本

## 工具脚本

使用 `scripts/clean_migrations.py` 可以：
- 检查重复迁移
- 列出已压缩的迁移文件
- 生成待执行的压缩命令
- 提供清理建议

## 总结

通过压缩迁移，我们解决了：
1. ✅ 历史迁移混乱问题
2. ✅ 新环境部署效率问题
3. ✅ 迁移文件数量过多问题

新环境部署现在会更加顺畅和快速。