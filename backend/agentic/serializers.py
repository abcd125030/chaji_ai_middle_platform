# -*- coding: utf-8 -*-
"""
此模块定义了用于 Agentic 应用中模型序列化的 Django REST Framework 序列化器。
它负责将复杂的模型实例转换为 Python 原生数据类型，以便于渲染为 JSON 或其他内容类型，
以及处理反序列化，将传入的验证过的数据转换回模型实例。
"""

from rest_framework import serializers
# 导入 Agentic 应用中定义的模型
from .models import Graph, Node, Edge, AgentTask

class GraphSerializer(serializers.ModelSerializer):
    """
    Graph 模型的序列化器。
    用于将 Graph 模型实例序列化/反序列化为 JSON 数据。
    """
    class Meta:
        # 指定此序列化器对应的模型为 Graph
        model = Graph
        # 指定序列化器应包含模型的所有字段
        fields = '__all__'

class NodeSerializer(serializers.ModelSerializer):
    """
    Node 模型的序列化器。
    用于将 Node 模型实例序列化/反序列化为 JSON 数据。
    """
    class Meta:
        # 指定此序列化器对应的模型为 Node
        model = Node
        # 指定序列化器应包含模型的所有字段
        fields = '__all__'

class EdgeSerializer(serializers.ModelSerializer):
    """
    Edge 模型的序列化器。
    用于将 Edge 模型实例序列化/反序列化为 JSON 数据。
    """
    class Meta:
        # 指定此序列化器对应的模型为 Edge
        model = Edge
        # 指定序列化器应包含模型的所有字段
        fields = '__all__'

class AgentTaskInputSerializer(serializers.Serializer):
    """
    用于处理 AgentTask 输入数据的序列化器。
    这是一个非模型序列化器，用于验证和解析 API 请求中的输入数据，
    例如用户提交的任务提示、文件和图名称。
    """
    session_id = serializers.CharField(max_length=255, required=True)
    messages = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True
    )
    graph_name = serializers.CharField(max_length=255, default='Super-Router Agent')
    usage = serializers.CharField(max_length=50, required=False, allow_blank=True)

class AgentTaskSerializer(serializers.ModelSerializer):
    """
    用于 AgentTask 模型的序列化器，提供详细的任务信息。
    它将 AgentTask 模型实例序列化为包含任务ID、状态、步骤、输入/输出数据和时间戳的 JSON 格式。
    """
    action_history = serializers.SerializerMethodField()

    class Meta:
        model = AgentTask
        fields = (
            'task_id',
            'status',
            'action_history',
            'input_data',
            'output_data',
            'created_at',
            'updated_at'
        )
        read_only_fields = fields

    def get_action_history(self, obj):
        """
        从 state_snapshot 中提取和格式化 action_history
        """
        if not obj.state_snapshot or 'action_history' not in obj.state_snapshot:
            return []
        
        action_history = obj.state_snapshot.get('action_history', [])
        # 在这里可以添加额外的格式化逻辑
        return action_history