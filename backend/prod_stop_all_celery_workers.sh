#!/bin/bash

# 定义配置变量（与启动脚本保持一致）
CELERY_APP="backend"
VENV_PATH="/www/wwwroot/repos/X/backend/.venv"
LOG_DIR="/www/wwwroot/repos/X/backend/celery_logs"
PID_DIR="/www/wwwroot/repos/X/backend/celery_pids"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Celery Workers 停止脚本${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# 统计信息
KILLED_COUNT=0
FAILED_COUNT=0

# 方法1: 使用 PID 文件优雅停止
echo -e "${GREEN}[步骤 1] 使用 PID 文件停止 workers...${NC}"
if [ -d "$PID_DIR" ]; then
    PID_FILES=("$PID_DIR"/*.pid)
    if [ -e "${PID_FILES[0]}" ]; then
        for pid_file in "${PID_FILES[@]}"; do
            if [ -f "$pid_file" ]; then
                PID=$(cat "$pid_file" 2>/dev/null)
                if [ ! -z "$PID" ]; then
                    # 检查进程是否存在
                    if kill -0 "$PID" 2>/dev/null; then
                        echo -n "  停止 worker PID $PID ($(basename $pid_file))..."
                        # 发送 TERM 信号优雅关闭
                        kill -TERM "$PID" 2>/dev/null
                        
                        # 等待进程结束（最多等待5秒）
                        for i in {1..5}; do
                            if ! kill -0 "$PID" 2>/dev/null; then
                                echo -e " ${GREEN}[成功]${NC}"
                                ((KILLED_COUNT++))
                                break
                            fi
                            sleep 1
                        done
                        
                        # 如果进程还在，强制杀掉
                        if kill -0 "$PID" 2>/dev/null; then
                            echo -n " 强制终止..."
                            kill -9 "$PID" 2>/dev/null
                            sleep 0.5
                            if ! kill -0 "$PID" 2>/dev/null; then
                                echo -e " ${YELLOW}[强制成功]${NC}"
                                ((KILLED_COUNT++))
                            else
                                echo -e " ${RED}[失败]${NC}"
                                ((FAILED_COUNT++))
                            fi
                        fi
                    else
                        echo "  PID $PID 已经不存在 ($(basename $pid_file))"
                    fi
                fi
                # 删除 PID 文件
                rm -f "$pid_file"
            fi
        done
    else
        echo "  没有找到 PID 文件"
    fi
else
    echo "  PID 目录不存在: $PID_DIR"
fi

echo ""
echo -e "${GREEN}[步骤 2] 查找并停止所有剩余的 Celery 进程...${NC}"

# 方法2: 使用 celery multi 停止（如果可用）
if [ -x "$VENV_PATH/bin/celery" ]; then
    echo "  尝试使用 celery multi stopwait..."
    # 获取所有 worker 名称（排除当前脚本）
    WORKER_NAMES=$(ps aux | grep -E "celery.*worker.*-n" | grep -v grep | grep -v "$0" | sed -n 's/.*-n \([^ ]*\).*/\1/p' | sort -u)
    if [ ! -z "$WORKER_NAMES" ]; then
        for worker in $WORKER_NAMES; do
            echo "    停止 worker: $worker"
            "$VENV_PATH/bin/celery" -A "$CELERY_APP" multi stopwait "$worker" --pidfile="$PID_DIR/%n.pid" 2>/dev/null
        done
    fi
fi

# 方法3: 使用 pkill 确保杀掉所有 celery 进程
echo ""
echo "  搜索剩余的 Celery 进程..."

# 获取当前脚本的 PID 和名称
SCRIPT_PID=$$
SCRIPT_NAME=$(basename "$0")

# 查找所有 celery worker 进程（排除当前脚本）
# 使用更精确的过滤：排除包含脚本名称的进程
CELERY_PIDS=$(ps aux | grep -E "celery.*worker" | grep -v grep | grep -v "$SCRIPT_NAME" | awk '{print $2}')

if [ ! -z "$CELERY_PIDS" ]; then
    echo "  发现 $(echo "$CELERY_PIDS" | wc -l) 个剩余进程"
    
    # 发送 TERM 信号
    echo "$CELERY_PIDS" | while read pid; do
        echo -n "    停止 PID $pid..."
        kill -TERM "$pid" 2>/dev/null
        echo -e " ${GREEN}[信号已发送]${NC}"
    done
    
    # 等待进程结束
    echo "  等待进程优雅关闭..."
    sleep 3
    
    # 检查是否还有进程存在（排除当前脚本）
    REMAINING_PIDS=$(ps aux | grep -E "celery.*worker" | grep -v grep | grep -v "$SCRIPT_NAME" | awk '{print $2}')
    if [ ! -z "$REMAINING_PIDS" ]; then
        echo -e "  ${YELLOW}仍有进程未停止，执行强制终止...${NC}"
        echo "$REMAINING_PIDS" | while read pid; do
            echo -n "    强制终止 PID $pid..."
            kill -9 "$pid" 2>/dev/null
            ((KILLED_COUNT++))
            echo -e " ${GREEN}[完成]${NC}"
        done
    fi
else
    echo "  没有发现运行中的 Celery 进程"
fi

# 方法4: 清理 celery beat 相关进程
echo ""
echo -e "${GREEN}[步骤 3] 停止 Celery Beat（如果存在）...${NC}"
# 排除脚本自身
BEAT_PIDS=$(ps aux | grep -E "celery.*beat" | grep -v grep | grep -v "$SCRIPT_NAME" | awk '{print $2}')
if [ ! -z "$BEAT_PIDS" ]; then
    echo "$BEAT_PIDS" | while read pid; do
        echo -n "  停止 Celery Beat PID $pid..."
        kill -TERM "$pid" 2>/dev/null
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        echo -e " ${GREEN}[完成]${NC}"
    done
else
    echo "  没有发现 Celery Beat 进程"
fi

# 清理文件
echo ""
echo -e "${GREEN}[步骤 4] 清理相关文件...${NC}"

# 清理 PID 文件
if [ -d "$PID_DIR" ]; then
    rm -f "$PID_DIR"/*.pid
    echo "  已清理 PID 文件"
fi

# 清理 celerybeat 相关文件
if [ -f "celerybeat.pid" ]; then
    rm -f celerybeat.pid
    echo "  已删除 celerybeat.pid"
fi

if [ -f "celerybeat-schedule" ]; then
    rm -f celerybeat-schedule
    echo "  已删除 celerybeat-schedule"
fi

# 最终验证
echo ""
echo -e "${GREEN}[步骤 5] 最终验证...${NC}"
# 使用更可靠的方法排除脚本自身
FINAL_CHECK=$(ps aux | grep -E "celery.*worker" | grep -v grep | grep -v "$SCRIPT_NAME" | awk '{print $2}')
if [ -z "$FINAL_CHECK" ]; then
    echo -e "  ${GREEN}✓ 所有 Celery workers 已成功停止${NC}"
else
    echo -e "  ${RED}✗ 警告：仍有 Celery 进程在运行：${NC}"
    # 排除 grep 本身和当前脚本
    ps aux | grep -E "celery.*worker" | grep -v grep | grep -v "$0"
fi

# 显示总结
echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}停止总结${NC}"
echo -e "${YELLOW}========================================${NC}"
echo -e "  成功停止: ${GREEN}$KILLED_COUNT${NC} 个进程"
if [ $FAILED_COUNT -gt 0 ]; then
    echo -e "  停止失败: ${RED}$FAILED_COUNT${NC} 个进程"
fi

# 显示日志信息
echo ""
echo "提示："
echo "  - 查看之前的运行日志: ls -la $LOG_DIR/"
echo "  - 检查进程状态: ps aux | grep celery | grep -v grep"
echo "  - 启动 workers: ./prod_start_all_celery_workers.sh"

echo ""
echo -e "${GREEN}Celery workers 停止脚本执行完成！${NC}"