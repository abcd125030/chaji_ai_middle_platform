#!/bin/bash

# Redis 连接清理脚本

echo "========================================="
echo "Redis 连接清理脚本"
echo "========================================="

# 1. 停止所有 Celery 相关进程
echo "1. 停止所有 Celery Workers 和 Beat..."
pkill -f "celery.*worker" 2>/dev/null
pkill -f "celery.*beat" 2>/dev/null
sleep 2

# 2. 强制终止残留进程
echo "2. 强制终止残留 Celery 进程..."
pkill -9 -f "celery" 2>/dev/null
sleep 1

# 3. 停止 PM2 管理的 Django 进程（如果需要）
echo "3. 检查 PM2 进程..."
pm2 list

# 4. 清理 Redis 中的 Celery 队列（可选）
echo "4. 显示 Redis 客户端列表..."
redis-cli -a 'chagee332335!' CLIENT LIST

echo ""
echo "5. 清理 Celery 相关的 Redis 键..."
# 删除 Celery 相关的键（谨慎使用）
redis-cli -a 'chagee332335!' --scan --pattern "celery*" | xargs -L 1 redis-cli -a 'chagee332335!' DEL 2>/dev/null
redis-cli -a 'chagee332335!' --scan --pattern "_kombu*" | xargs -L 1 redis-cli -a 'chagee332335!' DEL 2>/dev/null
redis-cli -a 'chagee332335!' --scan --pattern "unacked*" | xargs -L 1 redis-cli -a 'chagee332335!' DEL 2>/dev/null

echo ""
echo "6. 检查剩余连接..."
redis-cli -a 'chagee332335!' INFO clients | grep connected_clients

echo ""
echo "========================================="
echo "清理完成！"
echo "========================================="
echo ""
echo "建议操作："
echo "1. 如果还有连接，可以重启 Redis："
echo "   systemctl restart redis"
echo ""
echo "2. 或者断开所有客户端连接（除了当前）："
echo "   redis-cli -a 'chagee332335!' CLIENT KILL TYPE normal"
echo ""
echo "3. 查看具体是哪些客户端："
echo "   redis-cli -a 'chagee332335!' CLIENT LIST"