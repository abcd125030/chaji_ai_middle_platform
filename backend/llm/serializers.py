from rest_framework import serializers


class MessageSerializer(serializers.Serializer):
    role = serializers.CharField()
    content = serializers.CharField()


# 创建基类序列化器
class LLMInputSerializer(serializers.Serializer):
    session_id = serializers.CharField(default="", required=False)
    model = serializers.CharField()
    messages = MessageSerializer(many=True)
    stream = serializers.BooleanField(default=False, required=False)
    max_tokens = serializers.IntegerField(default=8096, required=False)
    temperature = serializers.FloatField(default=0.7, required=False)
    top_p = serializers.FloatField(default=0.7, required=False)
    frequency_penalty = serializers.FloatField(default=0.5, required=False)
    n = serializers.IntegerField(default=1, required=False)
