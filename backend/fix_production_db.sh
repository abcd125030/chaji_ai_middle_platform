#!/bin/bash

echo "=========================================="
echo "生产环境数据库修复脚本"
echo "=========================================="

# 激活虚拟环境
source .venv/bin/activate || source venv/bin/activate || echo "无法激活虚拟环境，继续执行..."

echo ""
echo "1. 检查当前迁移状态..."
echo "----------------------------------------"
python manage.py showmigrations chat

echo ""
echo "2. 生成迁移文件（如果需要）..."
echo "----------------------------------------"
python manage.py makemigrations chat --dry-run

echo ""
echo "3. 应用迁移..."
echo "----------------------------------------"
read -p "是否应用迁移到数据库? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py migrate chat
    echo "迁移已应用"
else
    echo "跳过迁移"
fi

echo ""
echo "4. 检查数据库表结构..."
echo "----------------------------------------"
python manage.py dbshell << EOF
\d chat_chatmessage
EOF

echo ""
echo "5. 验证API..."
echo "----------------------------------------"
python manage.py shell << EOF
from django.contrib.auth import get_user_model
from webapps.chat.models import ChatMessage, ChatSession
from django.utils import timezone
from datetime import timedelta

User = get_user_model()
print("用户数量:", User.objects.count())
print("会话数量:", ChatSession.objects.count())
print("消息数量:", ChatMessage.objects.count())

# 测试查询
try:
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    incomplete_messages = ChatMessage.objects.filter(
        is_complete=False,
        task_id__isnull=False,
        created_at__gte=twenty_four_hours_ago
    )
    print("未完成任务数量:", incomplete_messages.count())
    print("✓ 查询成功")
except Exception as e:
    print("✗ 查询失败:", str(e))
EOF

echo ""
echo "=========================================="
echo "检查完成"
echo "=========================================="