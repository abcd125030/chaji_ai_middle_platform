from rest_framework import serializers
from .models import ChatSession, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    """聊天消息序列化器"""
    
    task_steps = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'session_id', 'role', 'content', 
            'files_info', 'task_id', 'task_steps',
            'final_web_search_results', 'is_complete', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_task_steps(self, obj):
        """获取任务步骤，自动处理压缩数据"""
        steps = obj.get_task_steps()
        
        # 验证数据完整性
        if steps and isinstance(steps, list):
            # 确保每个步骤都有必要的字段
            validated_steps = []
            for step in steps:
                if isinstance(step, dict) and 'type' in step:
                    validated_steps.append(step)
            return validated_steps if validated_steps else None
        
        return steps
    
    session_id = serializers.UUIDField(
        source='session.id',
        read_only=True
    )


class ChatSessionSerializer(serializers.ModelSerializer):
    """聊天会话序列化器"""
    
    messages = ChatMessageSerializer(many=True, read_only=True)
    user_ai_id = serializers.CharField(source='user.id', read_only=True)
    sessionId = serializers.UUIDField(source='id', read_only=True)  # 为前端兼容性添加，返回 UUID 字符串
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'sessionId', 'user_ai_id', 'ai_conversation_id', 'title',
            'last_message_preview', 'last_interacted_at',
            'is_pinned', 'is_archived', 'tags',
            'created_at', 'updated_at', 'messages'
        ]
        read_only_fields = ['id', 'sessionId', 'created_at', 'updated_at', 'user_ai_id']


class SessionListSerializer(serializers.ModelSerializer):
    """会话列表序列化器（简化版）"""
    
    message_count = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()
    has_active_tasks = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'ai_conversation_id', 'title',
            'last_message_preview', 'last_interacted_at',
            'is_pinned', 'is_archived', 'tags',
            'created_at', 'updated_at',
            'message_count', 'file_count', 'has_active_tasks'
        ]
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_file_count(self, obj):
        count = 0
        for message in obj.messages.filter(files_info__isnull=False):
            if message.files_info:
                if isinstance(message.files_info, list):
                    count += len(message.files_info)
                elif isinstance(message.files_info, dict):
                    count += 1
        return count
    
    def get_has_active_tasks(self, obj):
        # 检查最后一条消息是否有未完成的任务
        last_message = obj.messages.last()
        if not last_message or not last_message.task_id:
            return False
        
        if not last_message.task_steps:
            return False
        
        # 检查任务步骤中的最后一步
        if isinstance(last_message.task_steps, list) and last_message.task_steps:
            last_step = last_message.task_steps[-1]
            if isinstance(last_step, dict):
                return last_step.get('type') != 'final_answer'
        
        return not last_message.is_complete