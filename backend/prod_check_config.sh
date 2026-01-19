#!/bin/bash

# ================================================
# 生产环境配置检查脚本
# 功能：
# 1. 检查系统环境是否满足高并发需求
# 2. 检查PostgreSQL、PgBouncer、Redis配置
# 3. 输出检查报告和优化建议
# ================================================

set -euo pipefail  # 更严格的错误处理

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置标志
ALL_CHECKS_PASSED=true
ERRORS=()
NEED_PG_RESTART=false

# 基础路径（检查路径是否存在）
BACKEND_DIR="/www/wwwroot/repos/X/backend"
PGSQL_DIR="/www/server/pgsql"
REDIS_DIR="/www/server/redis"

# 安全检查：确保路径存在
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}错误: Backend目录不存在: $BACKEND_DIR${NC}"
    exit 1
fi

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then 
   echo -e "${YELLOW}警告: 建议使用root权限运行此脚本${NC}"
   echo -n "是否继续? (y/n): "
   read -r response
   if [[ ! "$response" =~ ^[Yy]$ ]]; then
       exit 1
   fi
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}     生产环境配置检查脚本${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# ========== 1. 系统环境检查 ==========
echo -e "${YELLOW}[1/5] 检查系统环境...${NC}"

# 根据模式设置不同的资源要求
SINGLE_MODE=false
if [[ "${1:-}" == "--single" ]] || [[ "${SINGLE_WORKER:-false}" == "true" ]]; then
    SINGLE_MODE=true
    REQUIRED_CPU=2      # 单线程模式只需要2核
    REQUIRED_MEM=8      # 单线程模式只需要8GB内存
    echo -e "${BLUE}  运行模式: 单线程测试模式（降低资源要求）${NC}"
else
    REQUIRED_CPU=32     # 生产模式需要32核
    REQUIRED_MEM=400    # 生产模式需要400GB内存
    echo -e "${BLUE}  运行模式: 生产模式（完整资源要求）${NC}"
fi

# 检查CPU核心数
CPU_CORES=$(nproc)
echo -n "  CPU核心数: $CPU_CORES "
if [ $CPU_CORES -ge $REQUIRED_CPU ]; then
    echo -e "${GREEN}✓${NC}"
else
    if [ "$SINGLE_MODE" = true ]; then
        echo -e "${YELLOW}⚠ (建议至少${REQUIRED_CPU}核，但单线程模式可以运行)${NC}"
    else
        echo -e "${RED}✗ (需要至少${REQUIRED_CPU}核)${NC}"
        ERRORS+=("CPU核心不足: $CPU_CORES < $REQUIRED_CPU")
        ALL_CHECKS_PASSED=false
    fi
fi

# 检查内存
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
echo -n "  总内存: ${TOTAL_MEM_GB}GB "
if [ $TOTAL_MEM_GB -ge $REQUIRED_MEM ]; then
    echo -e "${GREEN}✓${NC}"
else
    if [ "$SINGLE_MODE" = true ]; then
        echo -e "${YELLOW}⚠ (建议至少${REQUIRED_MEM}GB，但单线程模式可以运行)${NC}"
    else
        echo -e "${RED}✗ (需要至少${REQUIRED_MEM}GB)${NC}"
        ERRORS+=("内存不足: ${TOTAL_MEM_GB}GB < ${REQUIRED_MEM}GB")
        ALL_CHECKS_PASSED=false
    fi
fi

# 检查端口范围
PORT_RANGE=$(sysctl net.ipv4.ip_local_port_range 2>/dev/null | awk '{print $3"-"$4}')
PORT_COUNT=$(sysctl net.ipv4.ip_local_port_range 2>/dev/null | awk '{print $4-$3}')
echo -n "  可用端口数: $PORT_COUNT "
if [ $PORT_COUNT -ge 20000 ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ (建议至少20000个端口)${NC}"
fi

# 检查文件句柄限制
FILE_MAX=$(sysctl fs.file-max 2>/dev/null | awk '{print $3}')
echo -n "  文件句柄限制: $FILE_MAX "
if [ $FILE_MAX -ge 1000000 ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ (建议至少1000000)${NC}"
fi

# ========== 2. PostgreSQL配置检查 ==========
echo ""
echo -e "${YELLOW}[2/5] 检查PostgreSQL配置...${NC}"

# 检查PostgreSQL是否运行
if pgrep -f "postgres" > /dev/null; then
    echo -e "  PostgreSQL状态: ${GREEN}运行中✓${NC}"
    
    # 检查关键配置（添加错误处理）
    PG_WORK_MEM=$($PGSQL_DIR/bin/psql -U postgres -t -c "SHOW work_mem;" 2>/dev/null | tr -d ' ' || echo "ERROR")
    PG_MAX_CONN=$($PGSQL_DIR/bin/psql -U postgres -t -c "SHOW max_connections;" 2>/dev/null | tr -d ' ' || echo "ERROR")
    PG_SHARED_BUF=$($PGSQL_DIR/bin/psql -U postgres -t -c "SHOW shared_buffers;" 2>/dev/null | tr -d ' ' || echo "ERROR")
    
    # 检查是否成功获取配置
    if [[ "$PG_WORK_MEM" == "ERROR" ]] || [[ "$PG_MAX_CONN" == "ERROR" ]]; then
        echo -e "${RED}  无法连接到PostgreSQL或获取配置${NC}"
        ERRORS+=("无法获取PostgreSQL配置")
        ALL_CHECKS_PASSED=false
    else
    
    # 检查work_mem（应该是64MB）
    echo -n "  work_mem: $PG_WORK_MEM "
    if [[ "$PG_WORK_MEM" == "64MB" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗ (应该是64MB)${NC}"
        echo -e "${YELLOW}  尝试自动修正...${NC}"
        $PGSQL_DIR/bin/psql -U postgres -c "ALTER SYSTEM SET work_mem = '64MB';" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ 已修正work_mem为64MB，需要重启PostgreSQL生效${NC}"
            NEED_PG_RESTART=true
        else
            echo -e "${RED}  ✗ 自动修正失败，请手动修复${NC}"
            ERRORS+=("PostgreSQL work_mem错误: $PG_WORK_MEM != 64MB")
            ALL_CHECKS_PASSED=false
        fi
    fi
    
    # 检查max_connections（根据模式设置不同要求）
    if [ "$SINGLE_MODE" = true ]; then
        REQUIRED_CONN=100   # 单线程模式只需要100个连接
    else
        REQUIRED_CONN=1500  # 生产模式需要1500个连接
    fi
    
    echo -n "  max_connections: $PG_MAX_CONN "
    PG_MAX_CONN_NUM=$(echo $PG_MAX_CONN | tr -d ' ')
    if [[ "$PG_MAX_CONN_NUM" -ge "$REQUIRED_CONN" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        if [ "$SINGLE_MODE" = true ]; then
            echo -e "${YELLOW}⚠ (建议至少${REQUIRED_CONN}，但单线程模式可以运行)${NC}"
        else
            echo -e "${RED}✗ (应该是${REQUIRED_CONN})${NC}"
            echo -e "${YELLOW}  尝试自动修正...${NC}"
            $PGSQL_DIR/bin/psql -U postgres -c "ALTER SYSTEM SET max_connections = '${REQUIRED_CONN}';" 2>/dev/null
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}  ✓ 已修正max_connections为${REQUIRED_CONN}，需要重启PostgreSQL生效${NC}"
                NEED_PG_RESTART=true
            else
                echo -e "${RED}  ✗ 自动修正失败，请手动修复${NC}"
                ERRORS+=("PostgreSQL max_connections错误: $PG_MAX_CONN != ${REQUIRED_CONN}")
                ALL_CHECKS_PASSED=false
            fi
        fi
    fi
    
    # 检查shared_buffers（根据模式设置不同要求）
    if [ "$SINGLE_MODE" = true ]; then
        REQUIRED_SHARED_BUF=10   # 单线程模式只需要10GB
    else
        REQUIRED_SHARED_BUF=100  # 生产模式需要100GB
    fi
    
    echo -n "  shared_buffers: $PG_SHARED_BUF "
    if [[ "$PG_SHARED_BUF" == *"GB" ]] && [[ "${PG_SHARED_BUF%GB}" -ge "$REQUIRED_SHARED_BUF" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        if [ "$SINGLE_MODE" = true ]; then
            echo -e "${YELLOW}⚠ (建议至少${REQUIRED_SHARED_BUF}GB，但单线程模式可以运行)${NC}"
        else
            echo -e "${YELLOW}⚠ (建议至少${REQUIRED_SHARED_BUF}GB)${NC}"
            # 计算合理的shared_buffers（不超过总内存的25%）
            TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
            TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
            SUGGESTED_SHARED_BUF=$((TOTAL_MEM_GB / 4))
            if [ $SUGGESTED_SHARED_BUF -gt $REQUIRED_SHARED_BUF ]; then
                SUGGESTED_SHARED_BUF=$REQUIRED_SHARED_BUF
            fi
            echo -e "${YELLOW}  尝试自动修正为${SUGGESTED_SHARED_BUF}GB...${NC}"
            $PGSQL_DIR/bin/psql -U postgres -c "ALTER SYSTEM SET shared_buffers = '${SUGGESTED_SHARED_BUF}GB';" 2>/dev/null
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}  ✓ 已修正shared_buffers为${SUGGESTED_SHARED_BUF}GB，需要重启PostgreSQL生效${NC}"
                NEED_PG_RESTART=true
            else
                echo -e "${YELLOW}  ⚠ 自动修正失败，但不影响运行${NC}"
            fi
        fi
    fi
    fi  # 关闭错误检查的if
else
    echo -e "  PostgreSQL状态: ${RED}未运行✗${NC}"
    ERRORS+=("PostgreSQL未运行")
    ALL_CHECKS_PASSED=false
fi

# 如果需要重启PostgreSQL
if [ "$NEED_PG_RESTART" = true ]; then
    echo ""
    echo -e "${YELLOW}PostgreSQL配置已修改，需要重启服务...${NC}"
    # 尝试重启PostgreSQL
    if command -v systemctl &> /dev/null; then
        systemctl restart postgresql 2>/dev/null || systemctl restart postgresql-14 2>/dev/null || {
            echo -e "${RED}自动重启PostgreSQL失败，请手动执行：systemctl restart postgresql${NC}"
            ERRORS+=("需要手动重启PostgreSQL")
            ALL_CHECKS_PASSED=false
        }
    elif [ -f /etc/init.d/pgsql ]; then
        /etc/init.d/pgsql restart || {
            echo -e "${RED}自动重启PostgreSQL失败，请手动执行：/etc/init.d/pgsql restart${NC}"
            ERRORS+=("需要手动重启PostgreSQL")
            ALL_CHECKS_PASSED=false
        }
    else
        echo -e "${RED}无法自动重启PostgreSQL，请手动重启后再运行此脚本${NC}"
        ERRORS+=("需要手动重启PostgreSQL")
        ALL_CHECKS_PASSED=false
    fi
    
    if [ "$ALL_CHECKS_PASSED" = true ]; then
        echo -e "${GREEN}✓ PostgreSQL已重启${NC}"
        sleep 3
        # 重新检查配置是否生效
        echo -e "${YELLOW}重新验证PostgreSQL配置...${NC}"
        PG_WORK_MEM=$($PGSQL_DIR/bin/psql -U postgres -t -c "SHOW work_mem;" 2>/dev/null | tr -d ' ' || echo "ERROR")
        PG_MAX_CONN=$($PGSQL_DIR/bin/psql -U postgres -t -c "SHOW max_connections;" 2>/dev/null | tr -d ' ' || echo "ERROR")
        PG_SHARED_BUF=$($PGSQL_DIR/bin/psql -U postgres -t -c "SHOW shared_buffers;" 2>/dev/null | tr -d ' ' || echo "ERROR")
        
        echo "  work_mem: $PG_WORK_MEM"
        echo "  max_connections: $PG_MAX_CONN"
        echo "  shared_buffers: $PG_SHARED_BUF"
        
        PG_MAX_CONN_NUM=$(echo $PG_MAX_CONN | tr -d ' ')
        if [[ "$PG_WORK_MEM" != "64MB" ]] || [[ "$PG_MAX_CONN_NUM" -lt "$REQUIRED_CONN" ]]; then
            if [ "$SINGLE_MODE" = true ] && [[ "$PG_WORK_MEM" == "64MB" ]] && [[ "$PG_MAX_CONN_NUM" -ge "$REQUIRED_CONN" ]]; then
                echo -e "${GREEN}✓ PostgreSQL配置满足单线程模式要求${NC}"
            else
                echo -e "${RED}PostgreSQL配置修正后仍未生效，请检查${NC}"
                ALL_CHECKS_PASSED=false
            fi
        else
            echo -e "${GREEN}✓ PostgreSQL配置已成功更新${NC}"
        fi
    fi
fi

# ========== 3. PgBouncer配置检查 ==========
echo ""
echo -e "${YELLOW}[3/5] 检查PgBouncer配置...${NC}"

PGBOUNCER_CONFIG="/etc/pgbouncer/pgbouncer.ini"
if [ -f "$PGBOUNCER_CONFIG" ]; then
    # 检查关键配置
    POOL_SIZE=$(grep "^default_pool_size" $PGBOUNCER_CONFIG 2>/dev/null | awk -F'=' '{print $2}' | tr -d ' ')
    MIN_POOL=$(grep "^min_pool_size" $PGBOUNCER_CONFIG 2>/dev/null | awk -F'=' '{print $2}' | tr -d ' ')
    RESERVE_POOL=$(grep "^reserve_pool_size" $PGBOUNCER_CONFIG 2>/dev/null | awk -F'=' '{print $2}' | tr -d ' ')
    MAX_CLIENT=$(grep "^max_client_conn" $PGBOUNCER_CONFIG 2>/dev/null | awk -F'=' '{print $2}' | tr -d ' ')
    MAX_DB_CONN=$(grep "^max_db_connections" $PGBOUNCER_CONFIG 2>/dev/null | awk -F'=' '{print $2}' | tr -d ' ')
    
    # 检查default_pool_size（根据模式设置不同要求）
    if [ "$SINGLE_MODE" = true ]; then
        REQUIRED_POOL_SIZE=20   # 单线程模式只需要20个连接池
    else
        REQUIRED_POOL_SIZE=200  # 生产模式需要200个连接池
    fi
    
    echo -n "  default_pool_size: $POOL_SIZE "
    POOL_SIZE_NUM=$(echo $POOL_SIZE | tr -d ' ')
    if [[ "$POOL_SIZE_NUM" -ge "$REQUIRED_POOL_SIZE" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        if [ "$SINGLE_MODE" = true ]; then
            echo -e "${YELLOW}⚠ (建议至少${REQUIRED_POOL_SIZE}，但单线程模式可以运行)${NC}"
        else
            echo -e "${RED}✗ (应该是${REQUIRED_POOL_SIZE})${NC}"
            echo -e "${YELLOW}  PgBouncer配置需要手动修改 /etc/pgbouncer/pgbouncer.ini${NC}"
            ERRORS+=("PgBouncer default_pool_size错误: $POOL_SIZE != ${REQUIRED_POOL_SIZE} (需手动修改配置文件)")
            ALL_CHECKS_PASSED=false
        fi
    fi
    
    # 检查min_pool_size（应该是50）
    echo -n "  min_pool_size: $MIN_POOL "
    if [[ "$MIN_POOL" == "50" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ (建议50)${NC}"
    fi
    
    # 检查reserve_pool_size（应该是100）
    echo -n "  reserve_pool_size: $RESERVE_POOL "
    if [[ "$RESERVE_POOL" == "100" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ (建议100)${NC}"
    fi
    
    # 检查max_client_conn（应该是10000）
    echo -n "  max_client_conn: $MAX_CLIENT "
    if [[ "$MAX_CLIENT" == "10000" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ (建议10000)${NC}"
    fi
    
    # 检查PgBouncer是否运行
    if pgrep -f "pgbouncer" > /dev/null; then
        echo -e "  PgBouncer状态: ${GREEN}运行中✓${NC}"
    else
        echo -e "  PgBouncer状态: ${RED}未运行✗${NC}"
        ERRORS+=("PgBouncer未运行")
        ALL_CHECKS_PASSED=false
    fi
else
    echo -e "${RED}  PgBouncer配置文件不存在${NC}"
    ERRORS+=("PgBouncer配置文件不存在")
    ALL_CHECKS_PASSED=false
fi

# ========== 4. Redis配置检查 ==========
echo ""
echo -e "${YELLOW}[4/5] 检查Redis配置...${NC}"

# 检查Redis是否运行
if pgrep -f "redis-server" > /dev/null; then
    echo -e "  Redis状态: ${GREEN}运行中✓${NC}"
    
    # 检查Redis配置（从环境变量读取密码，避免明文）
    REDIS_PASSWORD="${REDIS_PASSWORD:-chagee332335!}"
    REDIS_MAXMEM=$($REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG GET maxmemory 2>/dev/null | tail -1)
    REDIS_POLICY=$($REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG GET maxmemory-policy 2>/dev/null | tail -1)
    REDIS_MAXCLIENTS=$($REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG GET maxclients 2>/dev/null | tail -1)
    
    # 检查maxmemory（应该设置了限制）
    echo -n "  maxmemory: "
    if [[ "$REDIS_MAXMEM" != "0" ]] && [[ ! -z "$REDIS_MAXMEM" ]]; then
        REDIS_MAXMEM_GB=$((REDIS_MAXMEM / 1024 / 1024 / 1024))
        echo -e "${REDIS_MAXMEM_GB}GB ${GREEN}✓${NC}"
    else
        echo -e "${RED}未设置✗${NC}"
        echo -e "${YELLOW}  尝试自动修正...${NC}"
        $REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxmemory 50gb 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ 已设置maxmemory为50GB${NC}"
            # Redis配置立即生效，无需重启
            $REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG REWRITE 2>/dev/null
        else
            echo -e "${RED}  ✗ 自动修正失败，请手动修复${NC}"
            ERRORS+=("Redis未设置内存限制")
            ALL_CHECKS_PASSED=false
        fi
    fi
    
    # 检查maxmemory-policy
    echo -n "  maxmemory-policy: $REDIS_POLICY "
    if [[ "$REDIS_POLICY" == "allkeys-lru" ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ (建议allkeys-lru)${NC}"
        echo -e "${YELLOW}  尝试自动修正...${NC}"
        $REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxmemory-policy allkeys-lru 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ 已设置maxmemory-policy为allkeys-lru${NC}"
            $REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG REWRITE 2>/dev/null
        else
            echo -e "${YELLOW}  ⚠ 自动修正失败，但不影响运行${NC}"
        fi
    fi
    
    # 检查maxclients
    echo -n "  maxclients: $REDIS_MAXCLIENTS "
    if [[ "$REDIS_MAXCLIENTS" -ge 10000 ]]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ (建议10000)${NC}"
        echo -e "${YELLOW}  尝试自动修正...${NC}"
        $REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxclients 10000 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ 已设置maxclients为10000${NC}"
            $REDIS_DIR/src/redis-cli -a "$REDIS_PASSWORD" CONFIG REWRITE 2>/dev/null
        else
            echo -e "${YELLOW}  ⚠ 自动修正失败，但不影响运行${NC}"
        fi
    fi
else
    echo -e "  Redis状态: ${RED}未运行✗${NC}"
    ERRORS+=("Redis未运行")
    ALL_CHECKS_PASSED=false
fi

# ========== 5. 检查结果汇总 ==========
echo ""
echo -e "${YELLOW}[5/5] 检查结果汇总...${NC}"

if [ "$ALL_CHECKS_PASSED" = true ]; then
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}✓ 所有检查通过！系统配置满足生产环境要求${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo -e "${BLUE}启动服务命令：${NC}"
    echo "  使用PM2管理所有服务（Django + Celery）："
    echo ""
    echo "  1. 本地开发环境："
    echo "     ${GREEN}pm2 start ecosystem.local.config.js${NC}"
    echo ""
    echo "  2. 测试环境（16核 123GB）："
    echo "     ${GREEN}pm2 start ecosystem.test.config.js${NC}"
    echo ""
    echo "  3. 生产环境（高性能服务器）："
    echo "     ${GREEN}pm2 start ecosystem.production.config.js${NC}"
    echo ""
    echo -e "${BLUE}监控命令：${NC}"
    echo "  1. PM2进程状态: pm2 status"
    echo "  2. Celery队列: celery -A backend inspect active"
    echo "  3. 数据库连接: psql -h localhost -p 6432 pgbouncer -c 'SHOW POOLS;'"
    echo "  4. Redis状态: redis-cli -a '\$REDIS_PASSWORD' INFO clients"
    echo ""
    echo -e "${BLUE}日志查看：${NC}"
    echo "  Django日志: tail -f $BACKEND_DIR/logs/pm2/pm2-django-*.log"
    echo "  Workers日志: tail -f $BACKEND_DIR/logs/celery/pm2_celery_worker_*.log"
    echo "  Beat日志: tail -f $BACKEND_DIR/logs/celery/pm2_celery_beat_*.log"
    echo ""
else
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}✗ 配置检查失败！${NC}"
    echo -e "${RED}================================================${NC}"
    echo ""
    echo -e "${RED}发现以下问题：${NC}"
    for error in "${ERRORS[@]}"; do
        echo -e "  ${RED}• $error${NC}"
    done
    echo ""
    echo -e "${YELLOW}修复建议：${NC}"
    echo "  1. PostgreSQL work_mem: ALTER SYSTEM SET work_mem = '64MB';"
    echo "  2. PostgreSQL max_connections: ALTER SYSTEM SET max_connections = '1500';"
    echo "  3. PgBouncer配置: 编辑 /etc/pgbouncer/pgbouncer.ini"
    echo "     - default_pool_size = 200"
    echo "     - min_pool_size = 50"
    echo "     - reserve_pool_size = 100"
    echo "     - max_client_conn = 10000"
    echo "  4. Redis配置:"
    echo "     - redis-cli CONFIG SET maxmemory 50gb"
    echo "     - redis-cli CONFIG SET maxmemory-policy allkeys-lru"
    echo "     - redis-cli CONFIG SET maxclients 10000"
    echo ""
    echo -e "${YELLOW}请修复以上问题后再次运行此脚本进行验证${NC}"
    exit 1
fi