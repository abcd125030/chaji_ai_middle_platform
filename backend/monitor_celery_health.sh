#!/bin/bash

# Celery 健康监控脚本
# 可以加入 crontab 每分钟运行一次

BACKEND_DIR="/www/wwwroot/repos/X/backend"
PID_DIR="$BACKEND_DIR/celery_pids"
LOG_DIR="$BACKEND_DIR/celery_logs"
ALERT_LOG="$LOG_DIR/health_alerts.log"

# 检查并重启死掉的 workers
check_and_restart_workers() {
    for i in {1..10}; do
        PID_FILE="$PID_DIR/celery_worker_$i.pid"
        
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ! kill -0 "$PID" 2>/dev/null; then
                echo "[$(date)] Worker $i (PID: $PID) 已死亡，正在重启..." >> "$ALERT_LOG"
                
                # 重启单个 worker
                cd "$BACKEND_DIR"
                source .venv/bin/activate
                
                WORKER_NAME="gevent_worker_$i@$(hostname)"
                LOG_FILE="$LOG_DIR/celery_worker_$i.log"
                CPU_AFFINITY=$((i % 64))
                
                export C_FORCE_ROOT=1
                export GEVENT_SUPPORT=true
                
                taskset -c $CPU_AFFINITY nohup celery \
                    -A backend worker \
                    --pool=gevent \
                    --concurrency=400 \
                    --loglevel=info \
                    --max-memory-per-child=2000000 \
                    --max-tasks-per-child=1000 \
                    --prefetch-multiplier=4 \
                    --pidfile="$PID_FILE" \
                    -n "$WORKER_NAME" \
                    --time-limit=180 \
                    --soft-time-limit=120 \
                    --without-heartbeat \
                    --without-gossip \
                    --without-mingle \
                    -Q celery,image_normal_priority,image_high_priority,image_batch \
                    > "$LOG_FILE" 2>&1 &
                
                echo "[$(date)] Worker $i 已重启，新 PID: $!" >> "$ALERT_LOG"
            fi
        else
            echo "[$(date)] Worker $i PID 文件不存在" >> "$ALERT_LOG"
        fi
    done
}

# 检查队列积压
check_queue_backlog() {
    source "$BACKEND_DIR/.venv/bin/activate"
    cd "$BACKEND_DIR"
    
    # 获取队列长度
    QUEUE_LENGTH=$(celery -A backend inspect active | grep -c "task_id" || echo "0")
    
    if [ "$QUEUE_LENGTH" -gt 1000 ]; then
        echo "[$(date)] 警告：队列积压 $QUEUE_LENGTH 个任务" >> "$ALERT_LOG"
    fi
}

# 执行检查
check_and_restart_workers
check_queue_backlog

# 清理老日志（保留7天）
find "$LOG_DIR" -name "*.log" -mtime +7 -delete