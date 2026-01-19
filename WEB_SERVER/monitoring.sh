#!/bin/bash

# 监控脚本 - 实时检查服务器状态和性能指标

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 从 .env 文件读取配置
if [ -f "$SCRIPT_DIR/.env" ]; then
    # 读取 REDIS_PASSWORD
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    
    # 读取 DB_USER
    DB_USER=$(grep "^DB_USER=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    
    # 读取 DB_PASSWORD
    DB_PASSWORD=$(grep "^DB_PASSWORD=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    
    # 读取 DB_DATABASE (可选，有默认值)
    DB_DATABASE=$(grep "^DB_DATABASE=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    DB_DATABASE=${DB_DATABASE:-X}  # 默认值为 X
    
    if [ -z "$REDIS_PASSWORD" ]; then
        echo -e "${RED}错误：无法从 .env 文件读取 REDIS_PASSWORD${NC}"
        exit 1
    fi
    
    if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
        echo -e "${RED}错误：无法从 .env 文件读取 DB_USER 或 DB_PASSWORD${NC}"
        exit 1
    fi
else
    echo -e "${RED}错误：找不到 .env 文件${NC}"
    echo "请确保 .env 文件存在于: $SCRIPT_DIR/.env"
    exit 1
fi

# 分隔线
separator() {
    echo -e "${BLUE}================================================${NC}"
}

# PostgreSQL监控
monitor_postgresql() {
    echo -e "${GREEN}[PostgreSQL 状态]${NC}"
    
    # 连接数统计
    echo -e "${YELLOW}连接状态:${NC}"
    PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 5432 -U "$DB_USER" -d "$DB_DATABASE" -t -c "
        SELECT 
            state,
            count(*) as connections
        FROM pg_stat_activity 
        WHERE datname = '$DB_DATABASE'
        GROUP BY state
        ORDER BY connections DESC;
    " 2>/dev/null || echo "无法连接到PostgreSQL"
    
    # 慢查询（超过5秒）
    echo -e "${YELLOW}当前慢查询(>5秒):${NC}"
    PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 5432 -U "$DB_USER" -d "$DB_DATABASE" -t -c "
        SELECT 
            pid,
            now() - pg_stat_activity.query_start AS duration,
            substring(query, 1, 50) AS query_preview
        FROM pg_stat_activity
        WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
        AND state != 'idle'
        ORDER BY duration DESC
        LIMIT 5;
    " 2>/dev/null || echo "无慢查询"
    
    # 数据库大小
    echo -e "${YELLOW}数据库大小:${NC}"
    PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 5432 -U "$DB_USER" -d "$DB_DATABASE" -t -c "
        SELECT pg_size_pretty(pg_database_size('$DB_DATABASE')) as size;
    " 2>/dev/null || echo "无法获取"
    
    separator
}

# PgBouncer监控
monitor_pgbouncer() {
    echo -e "${GREEN}[PgBouncer 连接池]${NC}"
    
    # 连接池状态
    echo -e "${YELLOW}连接池状态:${NC}"
    PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 6432 -U "$DB_USER" pgbouncer -t -c "SHOW POOLS;" 2>/dev/null | head -10 || echo "无法连接到PgBouncer"
    
    # 连接统计
    echo -e "${YELLOW}连接统计:${NC}"
    PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 6432 -U "$DB_USER" pgbouncer -t -c "SHOW STATS;" 2>/dev/null | head -5 || echo "无统计信息"
    
    separator
}

# Redis监控
monitor_redis() {
    echo -e "${GREEN}[Redis 状态]${NC}"
    
    # 基本信息
    echo -e "${YELLOW}内存使用:${NC}"
    redis-cli -a "$REDIS_PASSWORD" INFO memory 2>/dev/null | grep -E "used_memory_human|used_memory_peak_human|maxmemory_human" || echo "无法连接Redis"
    
    echo -e "${YELLOW}客户端连接:${NC}"
    redis-cli -a "$REDIS_PASSWORD" INFO clients 2>/dev/null | grep -E "connected_clients|blocked_clients" || echo "无连接信息"
    
    echo -e "${YELLOW}命令统计:${NC}"
    redis-cli -a "$REDIS_PASSWORD" INFO stats 2>/dev/null | grep -E "instantaneous_ops_per_sec|total_commands_processed" | head -2 || echo "无统计信息"
    
    # 回调队列状态
    echo -e "${YELLOW}回调队列状态:${NC}"
    QUEUE_SIZE=$(redis-cli -a "$REDIS_PASSWORD" LLEN "callback_queue:pending" 2>/dev/null || echo "0")
    PROCESSING_SIZE=$(redis-cli -a "$REDIS_PASSWORD" LLEN "callback_queue:processing" 2>/dev/null || echo "0")
    echo "待处理: $QUEUE_SIZE | 处理中: $PROCESSING_SIZE"
    
    separator
}

# Celery监控
monitor_celery() {
    echo -e "${GREEN}[Celery Workers]${NC}"
    
    # Supervisorctl状态
    echo -e "${YELLOW}Worker进程状态:${NC}"
    supervisorctl status 2>/dev/null | grep celery || echo "无Celery进程信息"
    
    # 活跃任务数（从Redis获取）
    echo -e "${YELLOW}活跃任务:${NC}"
    ACTIVE_TASKS=$(redis-cli -a "$REDIS_PASSWORD" -n 0 LLEN "celery" 2>/dev/null || echo "0")
    echo "队列中的任务: $ACTIVE_TASKS"
    
    separator
}

# 系统资源监控
monitor_system() {
    echo -e "${GREEN}[系统资源]${NC}"
    
    # 内存使用
    echo -e "${YELLOW}内存使用:${NC}"
    free -h | grep -E "Mem:|Swap:"
    
    # CPU负载
    echo -e "${YELLOW}CPU负载:${NC}"
    uptime
    
    # 磁盘使用
    echo -e "${YELLOW}磁盘使用:${NC}"
    df -h | grep -E "/$|/www" | head -5
    
    # 网络连接
    echo -e "${YELLOW}网络连接统计:${NC}"
    ss -s | grep -E "TCP:|TIMEWAIT"
    
    # 端口使用情况
    echo -e "${YELLOW}可用端口范围:${NC}"
    sysctl net.ipv4.ip_local_port_range 2>/dev/null || echo "无法获取"
    
    separator
}

# 带宽监控（需要安装vnstat）
monitor_bandwidth() {
    echo -e "${GREEN}[网络带宽]${NC}"
    
    if command -v vnstat &> /dev/null; then
        echo -e "${YELLOW}实时带宽（最近5秒）:${NC}"
        vnstat -tr 5 2>/dev/null || echo "无法获取带宽信息"
    else
        echo -e "${YELLOW}安装vnstat以查看带宽: apt-get install vnstat${NC}"
        # 使用ifstat作为备选
        if command -v ifstat &> /dev/null; then
            ifstat 1 5 2>/dev/null || echo "无法获取带宽信息"
        fi
    fi
    
    separator
}

# 性能指标汇总
performance_summary() {
    echo -e "${GREEN}[性能指标汇总]${NC}"
    
    # PostgreSQL性能
    PG_CONNECTIONS=$(PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 5432 -U "$DB_USER" -d "$DB_DATABASE" -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '$DB_DATABASE';" 2>/dev/null || echo "0")
    echo -e "PostgreSQL连接数: ${YELLOW}$PG_CONNECTIONS${NC}"
    
    # Redis性能
    REDIS_OPS=$(redis-cli -a "$REDIS_PASSWORD" INFO stats 2>/dev/null | grep instantaneous_ops_per_sec | cut -d: -f2 | tr -d '\r' || echo "0")
    echo -e "Redis QPS: ${YELLOW}$REDIS_OPS${NC}"
    
    # 队列状态
    QUEUE_SIZE=$(redis-cli -a "$REDIS_PASSWORD" LLEN "callback_queue:pending" 2>/dev/null || echo "0")
    echo -e "回调队列大小: ${YELLOW}$QUEUE_SIZE${NC}"
    
    # 内存使用
    MEM_PERCENT=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
    echo -e "内存使用率: ${YELLOW}${MEM_PERCENT}%${NC}"
    
    # CPU使用
    CPU_LOAD=$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1)
    echo -e "CPU负载(1分钟): ${YELLOW}$CPU_LOAD${NC}"
    
    separator
}

# 主监控循环
main() {
    clear
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}    服务器实时监控 - $(date)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 根据参数选择监控内容
    case "${1:-all}" in
        pg|postgresql)
            monitor_postgresql
            ;;
        pgb|pgbouncer)
            monitor_pgbouncer
            ;;
        redis)
            monitor_redis
            ;;
        celery)
            monitor_celery
            ;;
        sys|system)
            monitor_system
            ;;
        net|network)
            monitor_bandwidth
            ;;
        summary)
            performance_summary
            ;;
        all|*)
            performance_summary
            monitor_postgresql
            monitor_pgbouncer
            monitor_redis
            monitor_celery
            monitor_system
            monitor_bandwidth
            ;;
    esac
    
    echo ""
    echo -e "${BLUE}监控时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
}

# 实时监控模式（默认模式）
if [ "$1" == "once" ]; then
    # 单次执行模式
    shift
    main "$@"
else
    # 默认为持续监控模式
    if [ "$1" == "watch" ]; then
        shift  # 兼容旧的watch参数
    fi
    
    echo -e "${BLUE}持续监控模式 - 按 Ctrl+C 退出${NC}"
    echo -e "${BLUE}提示: 使用 './monitoring.sh once' 仅运行一次${NC}"
    sleep 2
    
    while true; do
        clear
        main "$@"
        echo ""
        echo -e "${BLUE}刷新间隔: ${INTERVAL:-5}秒 | 按 Ctrl+C 退出${NC}"
        sleep "${INTERVAL:-5}"
    done
fi