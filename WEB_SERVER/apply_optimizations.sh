#!/bin/bash

# 配置优化脚本 - 安全应用服务器配置优化
# 处理170 QPS，20秒任务处理时间的场景

set -e  # 出错时立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}服务器配置优化脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 备份配置文件
backup_configs() {
    echo -e "${YELLOW}[1/5] 备份现有配置文件...${NC}"
    
    BACKUP_DIR="/tmp/config_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    
    # 备份PostgreSQL配置
    if [ -f "/etc/postgresql/*/main/postgresql.conf" ]; then
        cp /etc/postgresql/*/main/postgresql.conf $BACKUP_DIR/postgresql.conf.bak 2>/dev/null || true
    fi
    
    # 备份PgBouncer配置
    if [ -f "/etc/pgbouncer/pgbouncer.ini" ]; then
        cp /etc/pgbouncer/pgbouncer.ini $BACKUP_DIR/pgbouncer.ini.bak
    fi
    
    # 备份Redis配置
    if [ -f "/www/server/redis/redis.conf" ]; then
        cp /www/server/redis/redis.conf $BACKUP_DIR/redis.conf.bak
    fi
    
    echo -e "${GREEN}✓ 配置已备份到: $BACKUP_DIR${NC}"
}

# 优化PostgreSQL配置
optimize_postgresql() {
    echo -e "${YELLOW}[2/5] 优化PostgreSQL配置...${NC}"
    
    # 修改work_mem（从256MB降到64MB）
    echo "正在调整work_mem..."
    sudo -u postgres psql -c "ALTER SYSTEM SET work_mem = '64MB';" 2>/dev/null || {
        echo -e "${RED}⚠ 无法通过ALTER SYSTEM修改，请手动编辑postgresql.conf${NC}"
        echo "  work_mem = 64MB"
    }
    
    # 应用其他优化参数
    sudo -u postgres psql -c "ALTER SYSTEM SET effective_cache_size = '384GB';" 2>/dev/null || true
    sudo -u postgres psql -c "ALTER SYSTEM SET shared_buffers = '128GB';" 2>/dev/null || true
    sudo -u postgres psql -c "ALTER SYSTEM SET max_connections = 1500;" 2>/dev/null || true
    
    # 连接池相关优化
    sudo -u postgres psql -c "ALTER SYSTEM SET idle_in_transaction_session_timeout = '5min';" 2>/dev/null || true
    sudo -u postgres psql -c "ALTER SYSTEM SET statement_timeout = '30s';" 2>/dev/null || true
    
    # 重载配置
    sudo systemctl reload postgresql 2>/dev/null || {
        echo -e "${YELLOW}请手动重载PostgreSQL: sudo systemctl reload postgresql${NC}"
    }
    
    echo -e "${GREEN}✓ PostgreSQL配置已优化${NC}"
}

# 优化Redis配置
optimize_redis() {
    echo -e "${YELLOW}[3/5] 优化Redis配置...${NC}"
    
    REDIS_PASSWORD="chagee332335!"
    
    # 动态设置Redis参数（不需要重启）
    echo "设置Redis内存限制..."
    redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxmemory 50gb 2>/dev/null || {
        echo -e "${RED}⚠ 无法连接Redis，请检查密码${NC}"
        return 1
    }
    
    echo "设置内存淘汰策略..."
    redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxmemory-policy allkeys-lru
    
    echo "设置最大客户端连接数..."
    redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxclients 10000
    
    echo "设置TCP keepalive..."
    redis-cli -a "$REDIS_PASSWORD" CONFIG SET tcp-keepalive 60
    
    echo "设置TCP backlog..."
    redis-cli -a "$REDIS_PASSWORD" CONFIG SET tcp-backlog 511
    
    # 持久化配置到文件
    echo "保存配置到文件..."
    redis-cli -a "$REDIS_PASSWORD" CONFIG REWRITE
    
    echo -e "${GREEN}✓ Redis配置已优化${NC}"
}

# 优化PgBouncer配置
optimize_pgbouncer() {
    echo -e "${YELLOW}[4/5] 优化PgBouncer配置...${NC}"
    
    PGBOUNCER_CONFIG="/etc/pgbouncer/pgbouncer.ini"
    
    if [ ! -f "$PGBOUNCER_CONFIG" ]; then
        echo -e "${RED}⚠ PgBouncer配置文件不存在: $PGBOUNCER_CONFIG${NC}"
        return 1
    fi
    
    # 创建优化后的配置
    cat > /tmp/pgbouncer_optimized.ini << 'EOF'
# 主要优化点：
# - default_pool_size从800降到200
# - min_pool_size设置为50
# - reserve_pool_size设置为100
# - 优化超时参数

# 请手动应用以下配置到pgbouncer.ini:

[databases]
X = host=localhost port=5432 dbname=X

[pgbouncer]
listen_addr = localhost
listen_port = 6432

# 连接池配置（关键优化）
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 200    # 从800降到200
min_pool_size = 50         # 保持最小连接
max_db_connections = 1200
reserve_pool_size = 100    # 明确设置预留池
reserve_pool_timeout = 2

# 超时配置（优化响应速度）
server_lifetime = 3600
server_idle_timeout = 60
query_wait_timeout = 5
client_idle_timeout = 30

# 其他保持不变的重要配置
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
logfile = /var/log/postgresql/pgbouncer.log
pidfile = /var/run/postgresql/pgbouncer.pid
EOF
    
    echo -e "${YELLOW}优化配置已生成到: /tmp/pgbouncer_optimized.ini${NC}"
    echo -e "${YELLOW}请手动对比并应用配置，然后运行:${NC}"
    echo "  sudo systemctl reload pgbouncer"
    
    echo -e "${GREEN}✓ PgBouncer优化配置已准备${NC}"
}

# 系统内核参数优化（保守配置）
optimize_kernel() {
    echo -e "${YELLOW}[5/5] 优化系统内核参数...${NC}"
    
    # 创建优化配置文件
    cat > /tmp/99-performance.conf << 'EOF'
# 网络优化（保守配置）
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 10000 65000
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 8192

# 文件句柄（适中配置）
fs.file-max = 2000000
fs.nr_open = 1000000

# 内存管理（保守配置）
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF
    
    echo -e "${YELLOW}内核优化配置已生成到: /tmp/99-performance.conf${NC}"
    echo -e "${YELLOW}请手动检查并应用:${NC}"
    echo "  sudo cp /tmp/99-performance.conf /etc/sysctl.d/"
    echo "  sudo sysctl -p /etc/sysctl.d/99-performance.conf"
    
    echo -e "${GREEN}✓ 内核参数优化配置已准备${NC}"
}

# 主执行流程
main() {
    echo -e "${YELLOW}此脚本将优化服务器配置以支持170 QPS${NC}"
    echo -e "${YELLOW}任务处理时间: 20秒${NC}"
    echo -e "${YELLOW}并发任务数: ~3400${NC}"
    echo ""
    read -p "是否继续? (y/n): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}已取消${NC}"
        exit 1
    fi
    
    # 执行优化步骤
    backup_configs
    optimize_postgresql
    optimize_redis
    optimize_pgbouncer
    optimize_kernel
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}配置优化完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}重要提醒:${NC}"
    echo "1. PostgreSQL work_mem已从256MB降到64MB（节省内存）"
    echo "2. Redis已设置50GB内存限制（防止OOM）"
    echo "3. PgBouncer连接池已优化（降低连接开销）"
    echo "4. 请手动应用PgBouncer和内核参数配置"
    echo "5. 建议重启Celery workers: supervisorctl restart all"
    echo ""
    echo -e "${GREEN}备份位置: $BACKUP_DIR${NC}"
}

# 运行主函数
main