# Image Editor 优化待办事项

## 优化任务列表（按优先级排序）

### 🔴 最高优先级

#### 1. 任务数据传递优化
**目标：** 减少Worker数据库查询，提升性能
**预计时间：** 2小时  
**状态：** ✅ 已完成

**改动文件：**
- `views.py` - 3处任务投递代码
- `tasks.py` - 任务接收逻辑
- `tasks_batch.py` - 批量任务处理（如有）

**核心改动：**
```python
# 当前实现
process_image_edit_task.delay(str(task.task_id))

# 优化后
task_data = {
    'task_id': str(task.task_id),
    'image_url': task.image_url,
    'prompt': task.prompt,
    'callback_url': task.callback_url,
    'user_id': task.user.id,
    'username': task.user.username
}
process_image_edit_task.delay(task_data)
```

**测试要点：**
- [x] 单任务提交正常
- [x] 批量任务提交正常
- [x] 消息体大小是否超限
- [x] 序列化/反序列化正确性

**完成时间：** 2025-08-14
**实施情况：** 
- ✅ views.py 中两处任务投递代码已优化（单任务和批量任务）
- ✅ tasks.py 已支持接收字典参数并保持向后兼容
- ✅ 新增 started_at 字段传递，优化处理时间计算

---

### 🟡 中等优先级

#### 2. Celery Result Backend配置
**目标：** 统一任务状态管理，简化代码
**预计时间：** 1.5小时
**状态：** ⏳ 待开始

**实施步骤：**
- [ ] 在settings.py添加Result Backend配置
- [ ] 测试与现有缓存的兼容性
- [ ] 评估是否需要调整状态查询逻辑
- [ ] 性能对比测试

**配置示例：**
```python
# backend/celery.py
app.conf.update(
    result_backend='redis://localhost:6379/2',  # 使用独立的DB
    result_expires=3600,  # 结果过期时间
    result_compression='zlib',  # 启用压缩
)
```

**注意事项：**
- 可能与现有TaskCacheManager冲突
- 需要评估是否值得改造

---

### 🟢 低优先级

#### 3. Redis主从复制配置
**目标：** 提升Redis可用性，实现基础容灾
**预计时间：** 2小时
**状态：** ⏳ 待开始

**实施步骤：**
- [ ] 备份当前Redis数据（`redis-cli BGSAVE`）
- [ ] 配置Redis从节点（修改redis.conf）
- [ ] 修改.env配置文件支持主从
- [ ] 测试主从同步是否正常
- [ ] 准备手动故障切换脚本
- [ ] 记录切换流程文档

**配置要点：**
```bash
# 从节点配置
replicaof <master-ip> 6379
replica-read-only yes
```

**验证命令：**
```bash
redis-cli info replication
```

---

#### 4. Celery Flower监控部署
**目标：** 可视化任务队列监控
**预计时间：** 1.5小时
**状态：** ⏳ 待开始

**实施步骤：**
- [ ] 安装flower（`pip install flower`）
- [ ] 配置认证参数
- [ ] 创建systemd服务或Docker容器
- [ ] 配置nginx反向代理（可选）
- [ ] 测试访问和权限

**启动命令：**
```bash
celery -A backend flower \
    --port=5555 \
    --basic_auth=admin:secure_password \
    --url_prefix=flower
```

---

#### 5. Prometheus基础监控
**目标：** 系统性能指标监控
**预计时间：** 3小时
**状态：** ⏳ 待开始

**实施步骤：**
- [ ] 安装django-prometheus
- [ ] 配置middleware和urls
- [ ] 部署Prometheus服务
- [ ] 配置采集规则
- [ ] 创建基础Grafana面板

**依赖安装：**
```bash
pip install django-prometheus
```

---

## 执行前准备工作

### 必须完成的准备
1. **代码备份**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/redis-optimizations
   ```

2. **数据备份**
   ```bash
   # Redis备份
   redis-cli BGSAVE
   redis-cli LASTSAVE  # 确认备份完成
   
   # PostgreSQL备份
   pg_dump -U postgres X > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

3. **记录当前基准指标**
   - [ ] 平均任务处理时间
   - [ ] 任务成功率
   - [ ] Redis内存使用量
   - [ ] 数据库连接数

### 回滚方案
每个优化都准备独立的回滚方案：
- **Redis主从：** 恢复单节点配置，重启服务
- **任务传递：** git revert相关commit
- **Result Backend：** 注释配置，重启Celery
- **Flower：** 停止服务即可
- **Prometheus：** 移除middleware配置

---

## 执行顺序建议

**第一批（核心优化）：**
1. 任务数据传递优化 - 2h

**第二批（可选优化）：**
2. Celery Result Backend - 1.5h

**第三批（监控增强）：**
3. Redis主从复制 - 2h
4. Celery Flower - 1.5h
5. Prometheus监控 - 3h

---

## 风险评估

| 任务 | 风险等级 | 影响范围 | 缓解措施 |
|------|----------|----------|----------|
| Redis主从 | 低 | Redis服务 | 充分测试，准备快速切换脚本 |
| 任务传递优化 | 中 | 所有任务处理 | 分批部署，保留回滚版本 |
| Result Backend | 低 | 状态查询 | 先在测试环境验证 |
| Flower | 极低 | 仅监控 | 独立服务，不影响业务 |
| Prometheus | 极低 | 仅监控 | 独立服务，可随时关闭 |

---

## 完成标准

- [ ] 所有高优先级任务完成
- [ ] 通过人工测试验证
- [ ] 性能指标达到预期
- [ ] 回滚方案验证通过
- [ ] 更新部署文档

---

*创建时间：2025-08-13*
*执行状态：等待开始信号*