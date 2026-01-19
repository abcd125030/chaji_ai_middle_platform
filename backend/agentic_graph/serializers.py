"""
agentic_graph 序列化器
用于数据验证和序列化
"""
from rest_framework import serializers
from .models import GraphDefinition, NodeDefinition, EdgeDefinition, TaskExecution, StepRecord


class NodeDefinitionSerializer(serializers.ModelSerializer):
    """节点定义序列化器"""
    
    class Meta:
        model = NodeDefinition
        fields = [
            'id', 'node_id', 'node_type', 'node_name',
            'tool_name', 'config', 'position', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class EdgeDefinitionSerializer(serializers.ModelSerializer):
    """边定义序列化器"""
    
    class Meta:
        model = EdgeDefinition
        fields = [
            'id', 'edge_id', 'source_node_id', 'target_node_id',
            'condition', 'priority', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class GraphDefinitionSerializer(serializers.ModelSerializer):
    """图定义序列化器"""
    nodes = NodeDefinitionSerializer(many=True, read_only=True)
    edges = EdgeDefinitionSerializer(many=True, read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    
    class Meta:
        model = GraphDefinition
        fields = [
            'id', 'name', 'version', 'description',
            'creator', 'creator_name', 'created_at', 'updated_at',
            'is_active', 'is_default', 'config',
            'nodes', 'edges'
        ]
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at']


class TaskInputSerializer(serializers.Serializer):
    """
    任务输入验证序列化器
    用于验证创建任务的输入参数
    """
    session_id = serializers.CharField(
        max_length=255,
        required=True,
        help_text="会话ID"
    )
    messages = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        help_text="消息列表（JSON字符串格式）"
    )
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
        help_text="上传的文件列表"
    )
    graph_name = serializers.CharField(
        max_length=255,
        default='Super-Router Agent',
        help_text="要使用的图名称"
    )
    usage = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        help_text="任务用途标签"
    )
    
    def validate_messages(self, value):
        """验证并转换消息格式"""
        import json
        
        validated_messages = []
        for msg_str in value:
            try:
                # 尝试解析 JSON 字符串
                msg = json.loads(msg_str)
                if not isinstance(msg, dict):
                    raise serializers.ValidationError("每条消息必须是一个对象")
                if 'content' not in msg:
                    raise serializers.ValidationError("消息必须包含 content 字段")
                validated_messages.append(msg)
            except json.JSONDecodeError:
                # 如果不是 JSON，作为纯文本处理
                validated_messages.append({
                    'role': 'user',
                    'content': msg_str
                })
        
        return validated_messages
    
    def validate_files(self, value):
        """验证文件"""
        MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
        MAX_FILES = 6
        ALLOWED_EXTENSIONS = [
            '.docx', '.pdf', '.xlsx', '.xls',
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp',
            '.txt', '.md', '.json', '.csv'
        ]
        
        if len(value) > MAX_FILES:
            raise serializers.ValidationError(f"最多允许上传 {MAX_FILES} 个文件")
        
        total_size = 0
        for file_obj in value:
            # 检查文件大小
            file_size = file_obj.size
            total_size += file_size
            
            # 检查文件扩展名
            import os
            file_ext = os.path.splitext(file_obj.name)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                raise serializers.ValidationError(
                    f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
                )
        
        if total_size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f"文件总大小超过限制: {total_size / 1024 / 1024:.2f}MB / {MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        return value


class StepRecordSerializer(serializers.ModelSerializer):
    """步骤记录序列化器"""
    
    class Meta:
        model = StepRecord
        fields = [
            'id', 'step_number', 'node_id', 'node_type', 'node_name',
            'input_data', 'output_data', 'result', 'error_message',
            'prompt_tokens', 'completion_tokens', 'total_tokens',
            'duration_ms', 'started_at', 'completed_at', 'metadata'
        ]
        read_only_fields = fields


class TaskExecutionSerializer(serializers.ModelSerializer):
    """
    任务执行序列化器
    提供任务详细信息
    """
    graph_name = serializers.CharField(source='graph.name', read_only=True)
    graph_version = serializers.CharField(source='graph.version', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    steps = StepRecordSerializer(many=True, read_only=True)
    
    # 从 runtime_state 中提取的字段
    action_history = serializers.SerializerMethodField()
    current_prompt = serializers.SerializerMethodField()
    usage_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskExecution
        fields = [
            'id', 'graph', 'graph_name', 'graph_version',
            'user', 'user_name', 'session_id', 'turn_id',
            'status', 'current_node',
            'runtime_state', 'result', 'error_message',
            'total_tokens', 'total_cost',
            'created_at', 'started_at', 'updated_at', 'completed_at',
            'metadata', 'steps',
            # 派生字段
            'action_history', 'current_prompt', 'usage_stats'
        ]
        read_only_fields = [
            'id', 'created_at', 'started_at', 'updated_at', 'completed_at'
        ]
    
    def get_action_history(self, obj):
        """从 runtime_state 提取 action_history"""
        if not obj.runtime_state:
            return []
        
        action_history = obj.runtime_state.get('action_history', [[]])
        # 返回最新一轮的历史
        if action_history and len(action_history) > 0:
            return action_history[-1]
        return []
    
    def get_current_prompt(self, obj):
        """获取当前提示词"""
        if not obj.runtime_state:
            return ''
        
        prompts = obj.runtime_state.get('prompts', [])
        if prompts:
            return prompts[-1]
        return ''
    
    def get_usage_stats(self, obj):
        """获取使用统计"""
        if not obj.runtime_state:
            return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        
        usage_list = obj.runtime_state.get('usage', [])
        if not usage_list:
            return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        
        # 计算总和
        total_prompt = sum(u.get('prompt_tokens', 0) for u in usage_list)
        total_completion = sum(u.get('completion_tokens', 0) for u in usage_list)
        total_tokens = sum(u.get('total_tokens', 0) for u in usage_list)
        
        return {
            'prompt_tokens': total_prompt,
            'completion_tokens': total_completion,
            'total_tokens': total_tokens,
            'rounds': len(usage_list)
        }


class TaskStatusSerializer(serializers.Serializer):
    """
    任务状态序列化器
    用于轻量级的状态查询
    """
    task_id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    current_node = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True)
    error_message = serializers.CharField(read_only=True)
    is_completed = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    def get_is_completed(self, obj):
        """判断任务是否完成"""
        return obj.get('status') in ['completed', 'failed', 'cancelled']
    
    def get_progress_percentage(self, obj):
        """估算进度百分比"""
        status = obj.get('status', 'pending')
        if status == 'pending':
            return 0
        elif status == 'running':
            # 可以根据 current_node 来估算进度
            return 50
        elif status in ['completed', 'failed', 'cancelled']:
            return 100
        return 0


class GraphCloneSerializer(serializers.Serializer):
    """图克隆序列化器"""
    new_version = serializers.CharField(
        max_length=50,
        required=False,
        help_text="新版本号，不提供则自动生成"
    )
    activate = serializers.BooleanField(
        default=False,
        help_text="是否激活新版本"
    )