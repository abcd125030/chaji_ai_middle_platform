#!/bin/bash

# 增强版监控脚本 - 实时监控服务器状态（持续更新）

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 从 .env 文件读取配置
if [ -f "$SCRIPT_DIR/.env" ]; then
    # 读取配置
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    DB_USER=$(grep "^DB_USER=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    DB_PASSWORD=$(grep "^DB_PASSWORD=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    DB_DATABASE=$(grep "^DB_DATABASE=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    DB_DATABASE=${DB_DATABASE:-X}
    CELERY_DB=$(grep "^CELERY_DB=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    CELERY_DB=${CELERY_DB:-0}
    CACHE_DB=$(grep "^CACHE_DB=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    CACHE_DB=${CACHE_DB:-1}
    
    if [ -z "$REDIS_PASSWORD" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
        echo -e "${RED}错误：无法从 .env 文件读取必要的配置${NC}"
        exit 1
    fi
else
    echo -e "${RED}错误：找不到 .env 文件${NC}"
    exit 1
fi

# 默认刷新间隔（秒）
REFRESH_INTERVAL=${1:-5}

# 清屏并移动光标到顶部
clear_and_reset() {
    clear
    printf '\033[0;0H'
}

# 格式化数字（添加千分位）
format_number() {
    printf "%'d" $1 2>/dev/null || echo $1
}

# 获取状态指示器
get_status_indicator() {
    local value=${1:-0}
    local warning=${2:-50}
    local critical=${3:-100}
    
    # 确保是数字
    value=$(echo "$value" | grep -o '[0-9]*' | head -1)
    value=${value:-0}
    
    if [ "$value" -ge "$critical" ]; then
        echo -e "${RED}●${NC}"
    elif [ "$value" -ge "$warning" ]; then
        echo -e "${YELLOW}●${NC}"
    else
        echo -e "${GREEN}●${NC}"
    fi
}

# Redis详细监控
monitor_redis_detailed() {
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║                           REDIS 监控                              ║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════════╝${NC}"
    
    # 基本信息
    echo -e "${YELLOW}▶ 基础指标:${NC}"
    
    # 内存使用
    MEMORY_INFO=$(redis-cli -a "$REDIS_PASSWORD" INFO memory 2>/dev/null)
    USED_MEMORY=$(echo "$MEMORY_INFO" | grep "^used_memory_human:" | cut -d: -f2 | tr -d '\r')
    PEAK_MEMORY=$(echo "$MEMORY_INFO" | grep "^used_memory_peak_human:" | cut -d: -f2 | tr -d '\r')
    MAX_MEMORY=$(echo "$MEMORY_INFO" | grep "^maxmemory_human:" | cut -d: -f2 | tr -d '\r')
    
    echo -e "  内存使用: ${GREEN}${USED_MEMORY}${NC} / ${CYAN}${MAX_MEMORY}${NC} (峰值: ${YELLOW}${PEAK_MEMORY}${NC})"
    echo -e "  ${MAGENTA}→ 说明: 当前使用/最大限制 (历史峰值)${NC}"
    
    # 客户端连接
    CLIENT_INFO=$(redis-cli -a "$REDIS_PASSWORD" INFO clients 2>/dev/null)
    CONNECTED=$(echo "$CLIENT_INFO" | grep "^connected_clients:" | cut -d: -f2 | tr -d '\r')
    BLOCKED=$(echo "$CLIENT_INFO" | grep "^blocked_clients:" | cut -d: -f2 | tr -d '\r')
    
    CLIENT_STATUS=$(get_status_indicator $CONNECTED 100 200)
    echo -e "  客户端: ${CLIENT_STATUS} 连接 ${GREEN}${CONNECTED}${NC} | 阻塞 ${YELLOW}${BLOCKED}${NC}"
    echo -e "  ${MAGENTA}→ 说明: 阻塞客户端通常是BLPOP等待队列数据${NC}"
    
    # 操作统计
    STATS_INFO=$(redis-cli -a "$REDIS_PASSWORD" INFO stats 2>/dev/null)
    OPS=$(echo "$STATS_INFO" | grep "^instantaneous_ops_per_sec:" | cut -d: -f2 | tr -d '\r')
    TOTAL_CMDS=$(echo "$STATS_INFO" | grep "^total_commands_processed:" | cut -d: -f2 | tr -d '\r')
    
    echo -e "  操作速率: ${GREEN}${OPS}${NC} ops/sec (总计: $(format_number $TOTAL_CMDS))"
    echo -e "  ${MAGENTA}→ 说明: 每秒操作数反映当前负载${NC}"
    
    echo ""
    echo -e "${YELLOW}▶ 业务队列监控:${NC}"
    
    # 回调队列（主要业务队列）
    CALLBACK_PENDING=$(redis-cli -a "$REDIS_PASSWORD" LLEN "callback_queue:pending" 2>/dev/null || echo "0")
    CALLBACK_PROCESSING=$(redis-cli -a "$REDIS_PASSWORD" LLEN "callback_queue:processing" 2>/dev/null || echo "0")
    CALLBACK_LOCK=$(redis-cli -a "$REDIS_PASSWORD" GET "callback_queue:lock" 2>/dev/null || echo "")
    
    PENDING_STATUS=$(get_status_indicator $CALLBACK_PENDING 100 500)
    echo -e "  ${BOLD}回调队列:${NC}"
    echo -e "    ${PENDING_STATUS} 待处理: ${GREEN}$(format_number $CALLBACK_PENDING)${NC} 个"
    echo -e "    ● 处理中: ${YELLOW}$(format_number $CALLBACK_PROCESSING)${NC} 个"
    if [ ! -z "$CALLBACK_LOCK" ]; then
        echo -e "    ${RED}● 锁状态: 已锁定${NC}"
    else
        echo -e "    ${GREEN}● 锁状态: 未锁定${NC}"
    fi
    echo -e "  ${MAGENTA}→ 说明: 批量回调系统，待处理>100需关注${NC}"
    
    # 回调统计
    CALLBACK_QUEUED=$(redis-cli -a "$REDIS_PASSWORD" GET "callback_queue:stats:queued" 2>/dev/null)
    CALLBACK_SENT=$(redis-cli -a "$REDIS_PASSWORD" GET "callback_queue:stats:sent" 2>/dev/null)
    CALLBACK_FAILED=$(redis-cli -a "$REDIS_PASSWORD" GET "callback_queue:stats:failed" 2>/dev/null)
    
    # 确保变量有默认值
    CALLBACK_QUEUED=${CALLBACK_QUEUED:-0}
    CALLBACK_SENT=${CALLBACK_SENT:-0}
    CALLBACK_FAILED=${CALLBACK_FAILED:-0}
    
    if [ "$CALLBACK_QUEUED" != "0" ]; then
        echo -e "  ${BOLD}回调统计:${NC}"
        echo -e "    总入队: $(format_number $CALLBACK_QUEUED) | 已发送: $(format_number $CALLBACK_SENT) | 失败: $(format_number $CALLBACK_FAILED)"
        
        # 计算成功率前检查是否有数据
        TOTAL_PROCESSED=$((CALLBACK_SENT + CALLBACK_FAILED))
        if [ "$TOTAL_PROCESSED" -gt 0 ]; then
            SUCCESS_RATE=$(echo "scale=2; $CALLBACK_SENT * 100 / $TOTAL_PROCESSED" | bc 2>/dev/null || echo "0")
            echo -e "    成功率: ${GREEN}${SUCCESS_RATE}%${NC}"
        fi
    fi
    
    # Celery队列（不同数据库）
    echo ""
    echo -e "  ${BOLD}Celery队列 (DB${CELERY_DB}):${NC}"
    
    # 获取所有Celery队列
    CELERY_QUEUES=$(redis-cli -a "$REDIS_PASSWORD" -n $CELERY_DB KEYS "_kombu.binding.*" 2>/dev/null | sed 's/_kombu.binding.//' | sort -u)
    
    if [ ! -z "$CELERY_QUEUES" ]; then
        for queue in $CELERY_QUEUES; do
            QUEUE_SIZE=$(redis-cli -a "$REDIS_PASSWORD" -n $CELERY_DB LLEN "$queue" 2>/dev/null || echo "0")
            if [ "$QUEUE_SIZE" != "0" ]; then
                QUEUE_STATUS=$(get_status_indicator $QUEUE_SIZE 50 200)
                echo -e "    ${QUEUE_STATUS} $queue: $(format_number $QUEUE_SIZE) 个任务"
            fi
        done
    else
        # 默认队列检查
        for queue in celery image_normal_priority image_high_priority image_batch; do
            QUEUE_SIZE=$(redis-cli -a "$REDIS_PASSWORD" -n $CELERY_DB LLEN "$queue" 2>/dev/null || echo "0")
            if [ "$QUEUE_SIZE" != "0" ] || [ "$queue" = "celery" ]; then
                QUEUE_STATUS=$(get_status_indicator $QUEUE_SIZE 50 200)
                echo -e "    ${QUEUE_STATUS} $queue: $(format_number $QUEUE_SIZE) 个任务"
            fi
        done
    fi
    echo -e "  ${MAGENTA}→ 说明: Celery任务队列，>50需检查Worker状态${NC}"
    
    echo ""
}

# 系统概览
system_overview() {
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║                          系统概览                                 ║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════════╝${NC}"
    
    # CPU和内存
    CPU_PERCENT=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}' 2>/dev/null)
    CPU_PERCENT=${CPU_PERCENT:-0}
    
    MEM_INFO=$(free -b | grep Mem)
    MEM_TOTAL=$(echo $MEM_INFO | awk '{print $2}')
    MEM_USED=$(echo $MEM_INFO | awk '{print $3}')
    
    if [ ! -z "$MEM_TOTAL" ] && [ "$MEM_TOTAL" -gt 0 ]; then
        MEM_PERCENT=$(echo "scale=1; $MEM_USED * 100 / $MEM_TOTAL" | bc 2>/dev/null || echo "0")
    else
        MEM_PERCENT="0"
    fi
    
    # 提取整数部分用于比较
    CPU_INT=$(echo "$CPU_PERCENT" | cut -d. -f1)
    MEM_INT=$(echo "$MEM_PERCENT" | cut -d. -f1)
    CPU_INT=${CPU_INT:-0}
    MEM_INT=${MEM_INT:-0}
    
    CPU_STATUS=$(get_status_indicator "$CPU_INT" 50 80)
    MEM_STATUS=$(get_status_indicator "$MEM_INT" 50 80)
    
    echo -e "  ${CPU_STATUS} CPU使用率: ${GREEN}${CPU_PERCENT}%${NC}"
    echo -e "  ${MEM_STATUS} 内存使用率: ${GREEN}${MEM_PERCENT}%${NC} ($(free -h | grep Mem | awk '{print $3}')/$(free -h | grep Mem | awk '{print $2}'))"
    
    # 负载
    LOAD=$(uptime | awk -F'load average:' '{print $2}')
    echo -e "  ● 系统负载: ${GREEN}${LOAD}${NC}"
    
    # PostgreSQL连接
    PG_CONNECTIONS=$(PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 5432 -U "$DB_USER" -d "$DB_DATABASE" -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '$DB_DATABASE';" 2>/dev/null)
    PG_ACTIVE=$(PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 5432 -U "$DB_USER" -d "$DB_DATABASE" -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '$DB_DATABASE' AND state = 'active';" 2>/dev/null)
    
    # 清理空格并设置默认值
    PG_CONNECTIONS=$(echo "$PG_CONNECTIONS" | tr -d ' ')
    PG_ACTIVE=$(echo "$PG_ACTIVE" | tr -d ' ')
    PG_CONNECTIONS=${PG_CONNECTIONS:-0}
    PG_ACTIVE=${PG_ACTIVE:-0}
    
    PG_STATUS=$(get_status_indicator "$PG_CONNECTIONS" 100 500)
    echo -e "  ${PG_STATUS} PostgreSQL: ${GREEN}${PG_CONNECTIONS}${NC} 连接 (活跃: ${YELLOW}${PG_ACTIVE}${NC})"
    
    echo ""
}

# 主监控循环
main_loop() {
    while true; do
        clear_and_reset
        
        # 标题栏
        echo -e "${BOLD}${BLUE}══════════════════════════════════════════════════════════════════════${NC}"
        echo -e "${BOLD}${BLUE}        服务器实时监控 - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
        echo -e "${BOLD}${BLUE}        刷新间隔: ${REFRESH_INTERVAL}秒 | 按 Ctrl+C 退出${NC}"
        echo -e "${BOLD}${BLUE}══════════════════════════════════════════════════════════════════════${NC}"
        echo ""
        
        # 系统概览
        system_overview
        
        # Redis详细监控
        monitor_redis_detailed
        
        # 底部信息
        echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════════════════${NC}"
        echo -e "${MAGENTA}提示: 使用 './monitoring_enhanced.sh 10' 可设置10秒刷新间隔${NC}"
        
        # 等待刷新
        sleep $REFRESH_INTERVAL
    done
}

# 捕获Ctrl+C优雅退出
trap 'echo -e "\n${GREEN}监控已停止${NC}"; exit 0' INT

# 启动监控
main_loop