# 配置一致性检查和优化建议

## 当前配置总览

### PostgreSQL (postgresql.conf)
- max_connections = 1500 ✅
- shared_buffers = 128GB ✅ (对于500GB内存合理)
- work_mem = 256MB ⚠️ (可能过大，1500连接 × 256MB = 375GB!)
- effective_cache_size = 384GB ✅

### PgBouncer (pgbouncer.ini)
- pool_mode = transaction ✅
- max_client_conn = 10000 ✅
- default_pool_size = 800 ⚠️ (过大)
- max_db_connections = 1200 ✅
- reserve_pool_size = 200 (需确认实际值)
- reserve_pool_timeout = 2

### Redis (redis.conf)
- maxclients = 10000 (默认值) ✅
- maxmemory = 未限制 ⚠️
- databases = 16 ✅
- timeout = 0 ✅
- tcp-keepalive = 300 ✅

### Django (settings.py)
- USE_PGBOUNCER = True
- CONN_MAX_AGE = 0 ✅
- Redis连接池: max_connections = 500 ✅

## 🔴 必须修复的问题

### 1. PostgreSQL work_mem 过大
```conf
# postgresql.conf
# 原值：work_mem = 256MB
# 建议改为：
work_mem = 64MB  # 1500连接 × 64MB = 96GB，更安全
```

### 2. PgBouncer default_pool_size 过大
```ini
# pgbouncer.ini
# 原值：default_pool_size = 800
# 建议改为：
default_pool_size = 200  # transaction模式下足够
min_pool_size = 50       # 保持最小连接
reserve_pool_size = 100  # 明确设置预留池
```

### 3. Redis 添加内存限制
```conf
# redis.conf
# 添加以下配置：
maxclients 10000
maxmemory 50gb
maxmemory-policy allkeys-lru
```

## 🎯 优化后的配置

### 场景：170 QPS，任务处理20秒

#### 需求计算：
- 并发任务数：170 × 20 = 3400个
- 数据库连接需求：约400-500个（事务池模式）
- Redis连接需求：约100个
- 内存需求：约50-80GB

#### 推荐配置：

**PostgreSQL:**
```conf
max_connections = 1500
shared_buffers = 128GB
work_mem = 64MB
effective_cache_size = 384GB
```

**PgBouncer:**
```ini
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 200
min_pool_size = 50
max_db_connections = 1200
reserve_pool_size = 100
reserve_pool_timeout = 2
```

**Redis:**
```conf
maxclients 10000
maxmemory 50gb
maxmemory-policy allkeys-lru
tcp-backlog 511
tcp-keepalive 60
```

**Django settings.py:**
```python
# 使用PgBouncer时
DATABASES['default']['CONN_MAX_AGE'] = 0
DATABASES['default']['OPTIONS'] = {
    'connect_timeout': 10,
}

# Redis连接池
CACHES['default']['OPTIONS']['CONNECTION_POOL_KWARGS'] = {
    'max_connections': 500,
    'retry_on_timeout': True,
}
```

## 监控命令

```bash
# PostgreSQL连接监控
psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# PgBouncer连接池监控
psql -h localhost -p 6432 -U postgres pgbouncer -c "SHOW POOLS;"
psql -h localhost -p 6432 -U postgres pgbouncer -c "SHOW STATS;"

# Redis连接监控
redis-cli -a 'chagee332335!' INFO clients
redis-cli -a 'chagee332335!' INFO memory

# 系统资源监控
free -h
ss -s
netstat -ant | grep -c TIME_WAIT
```

## 部署步骤

1. **备份当前配置**
```bash
cp /etc/postgresql/*/main/postgresql.conf /etc/postgresql/*/main/postgresql.conf.bak
cp /etc/pgbouncer/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini.bak
cp /www/server/redis/redis.conf /www/server/redis/redis.conf.bak
```

2. **应用PostgreSQL配置**
```bash
# 修改work_mem
sudo -u postgres psql -c "ALTER SYSTEM SET work_mem = '64MB';"
sudo systemctl reload postgresql
```

3. **应用PgBouncer配置**
```bash
# 编辑配置文件后
sudo systemctl reload pgbouncer
```

4. **应用Redis配置**
```bash
# 动态设置（不需要重启）
redis-cli -a 'chagee332335!' CONFIG SET maxmemory 50gb
redis-cli -a 'chagee332335!' CONFIG SET maxmemory-policy allkeys-lru
redis-cli -a 'chagee332335!' CONFIG REWRITE
```

5. **重启Celery Workers**
```bash
supervisorctl restart all
```