# 服务器配置优化指南

## 概述
本目录包含用于优化服务器配置的脚本和配置文件，专门针对以下场景：
- **目标QPS**: 170 请求/秒
- **任务处理时间**: 20秒
- **并发任务数**: ~3400
- **服务器配置**: 500GB RAM, 64 CPU核心

## 文件说明

### 1. 配置文件
- `config_check.md` - 配置一致性检查文档
- `postgresql.conf` - PostgreSQL配置镜像
- `pgbouncer.ini` - PgBouncer连接池配置镜像
- `pgbouncer_optimized.ini` - 优化后的PgBouncer配置

### 2. 优化脚本
- `apply_optimizations.sh` - 一键应用所有优化配置
- `monitoring.sh` - 实时监控服务器状态
- `validate_config.py` - 验证配置是否正确应用

## 关键优化项

### PostgreSQL优化
```bash
# 原配置问题
work_mem = 256MB  # 1500连接 × 256MB = 375GB！

# 优化后
work_mem = 64MB   # 1500连接 × 64MB = 96GB
```

### Redis优化
```bash
# 添加内存限制防止OOM
maxmemory 50gb
maxmemory-policy allkeys-lru
```

### PgBouncer优化
```bash
# 原配置
default_pool_size = 800  # 过大

# 优化后
default_pool_size = 200  # transaction模式下足够
min_pool_size = 50       # 保持热连接
reserve_pool_size = 100  # 应对突发
```

## 使用方法

### 1. 应用优化配置
```bash
# 添加执行权限
chmod +x apply_optimizations.sh

# 运行优化脚本
sudo ./apply_optimizations.sh
```

### 2. 监控服务器状态
```bash
# 添加执行权限
chmod +x monitoring.sh

# 单次检查所有状态
./monitoring.sh

# 持续监控（每5秒刷新）
./monitoring.sh watch

# 只监控特定组件
./monitoring.sh postgresql  # 只看PostgreSQL
./monitoring.sh redis       # 只看Redis
./monitoring.sh summary     # 只看汇总
```

### 3. 验证配置
```bash
# 安装依赖
pip install psycopg2-binary redis

# 运行验证
python3 validate_config.py
```

## 监控命令速查

### PostgreSQL
```sql
-- 查看连接状态
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;

-- 查看慢查询
SELECT pid, now() - query_start AS duration, query 
FROM pg_stat_activity 
WHERE (now() - query_start) > interval '5 seconds';
```

### PgBouncer
```bash
# 查看连接池
psql -h localhost -p 6432 -U postgres pgbouncer -c "SHOW POOLS;"

# 查看统计
psql -h localhost -p 6432 -U postgres pgbouncer -c "SHOW STATS;"
```

### Redis
```bash
# 查看内存
redis-cli -a 'password' INFO memory

# 查看客户端
redis-cli -a 'password' INFO clients

# 查看队列
redis-cli -a 'password' LLEN "callback_queue:pending"
```

## 性能目标

| 指标 | 目标值 | 当前配置支持 |
|-----|--------|------------|
| QPS | 170 | ✅ 10,000 gevent并发 |
| 任务处理时间 | 20秒 | ✅ 3,400并发任务 |
| 数据库连接 | <1500 | ✅ PgBouncer池化 |
| 内存使用 | <400GB | ✅ 优化后~150GB |
| 带宽 | <200Mbps | ✅ 批量回调机制 |

## 故障排查

### 问题1: 数据库连接耗尽
```bash
# 检查连接数
psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# 解决方案
# 1. 减小PgBouncer的default_pool_size
# 2. 减少worker数量或gevent池大小
```

### 问题2: Redis内存过高
```bash
# 检查内存
redis-cli -a 'password' INFO memory

# 解决方案
# 1. 设置maxmemory限制
# 2. 调整淘汰策略
redis-cli CONFIG SET maxmemory 50gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### 问题3: 回调队列堆积
```bash
# 检查队列
redis-cli -a 'password' LLEN "callback_queue:pending"

# 解决方案
# 1. 增加批次大小
# 2. 减少延迟时间
# 3. 检查网络带宽
```

## 注意事项

1. **备份优先**: 应用任何配置前先备份
2. **逐步应用**: 建议先在测试环境验证
3. **监控跟进**: 应用后持续监控24小时
4. **回滚准备**: 保留原配置便于快速回滚

## 联系支持

如遇到问题，请提供以下信息：
1. `monitoring.sh` 输出
2. `validate_config.py` 报告
3. 错误日志（PostgreSQL、Redis、PgBouncer）