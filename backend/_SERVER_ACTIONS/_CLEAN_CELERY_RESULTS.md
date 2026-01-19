# Celery 任务结果清理脚本使用说明

## 脚本名称
`_CLEAN_CELERY_RESULTS.py`

## 脚本功能
清理 Django Celery Results 在数据库中存储的任务执行结果数据，主要针对 `django_celery_results_taskresult` 表。

## 使用前提
- 需要在已配置好的 Django 环境中运行
- 需要有数据库访问权限
- 建议在执行清理前先备份数据

## 使用方法

### 1. 查看统计信息（默认模式）
```bash
cd /path/to/backend
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py
```
显示当前表的记录数、大小和任务类型分布，不执行任何清理操作。

### 2. 按时间清理
```bash
# 清理30天前的数据（默认）
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode age

# 清理7天前的数据
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode age --days 7

# 清理1天前的数据
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode age --days 1
```

### 3. 清理高频任务
```bash
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode high-freq
```
清理已配置 `ignore_result=True` 的高频任务：
- check_and_flush_callbacks
- cleanup_stuck_callbacks
- trigger_batch_send
- send_single_callback
- reload_worker_config

### 4. 清理特定任务
```bash
# 清理包含特定名称的任务
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode task --task-name image_editor

# 清理 Agent 相关任务
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode task --task-name run_graph_task
```

### 5. 清空所有数据（危险操作）
```bash
# 需要加 --confirm 参数确认
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode all --confirm
```

### 6. 优化表空间（PostgreSQL）
```bash
python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode vacuum
```
执行 VACUUM ANALYZE 优化表，回收已删除记录的空间。

## 脚本执行流程

1. **连接数据库**：使用 Django 配置的数据库连接
2. **显示当前统计**：展示表的当前状态
3. **执行清理操作**：根据指定模式清理数据
4. **显示清理后统计**：展示清理后的结果
5. **完成**：显示操作完成信息

## 预期结果

### 统计模式输出示例
```
============================================================
Celery 任务结果数据清理工具
============================================================

当前数据统计:
  总记录数: 125,432
  表大小: 256 MB

  任务类型统计 (Top 10):
    - customized.image_editor.tasks_batch.check_and_flush_callbacks: 100,234 条
    - customized.image_editor.tasks_batch.cleanup_stuck_callbacks: 20,198 条
    - agentic.tasks.run_graph_task: 5,000 条

------------------------------------------------------------

仅显示统计信息，未执行清理操作
```

### 清理操作输出示例
```
清理高频任务记录...
  删除任务 'check_and_flush_callbacks' 相关记录: 100,234 条
  删除任务 'cleanup_stuck_callbacks' 相关记录: 20,198 条
总共删除 120,432 条高频任务记录

------------------------------------------------------------

清理后数据统计:
  总记录数: 5,000
  表大小: 12 MB

============================================================
操作完成
```

## 注意事项

1. **生产环境谨慎操作**：清理操作不可逆，建议先在测试环境验证
2. **备份重要数据**：如果任务结果包含重要信息，先备份再清理
3. **避免高峰期操作**：大量删除操作可能影响数据库性能
4. **定期执行**：建议定期清理，避免数据积累过多
5. **配合配置优化**：脚本清理是临时方案，长期应通过配置 `ignore_result=True` 和 `CELERY_RESULT_EXPIRES` 减少数据产生

## 常见问题

**Q: 清理后表空间没有减少？**
A: PostgreSQL 删除数据后不会立即释放空间，需要执行 `--mode vacuum` 优化表。

**Q: 能否自动定期清理？**
A: 可以配合 cron 定时任务：
```bash
# 每天凌晨2点清理7天前的数据
0 2 * * * cd /path/to/backend && python _SERVER_ACTIONS/_CLEAN_CELERY_RESULTS.py --mode age --days 7
```

**Q: 清理会影响正在运行的任务吗？**
A: 不会。脚本只清理已完成的历史记录，不影响正在执行的任务。