from rest_framework import serializers


class PublicOpinionSerializer(serializers.Serializer):
    task_id = serializers.CharField(max_length=36)
    content = serializers.CharField(allow_blank=True)
    im_body = serializers.ListField(child=serializers.URLField(), allow_empty=True)
