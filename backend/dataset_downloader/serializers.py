from rest_framework import serializers
from .models import Dataset, DownloadTask

class DatasetItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ['url', 'expected_md5', 'file_size', 'metadata']
        extra_kwargs = {'url': {'validators': []}}

    def validate_expected_md5(self, value):
        if len(value) != 32:
            raise serializers.ValidationError('expected_md5必须是32字符')
        return value

class DatasetBatchSerializer(serializers.Serializer):
    datasets = DatasetItemSerializer(many=True)

    def validate_datasets(self, value):
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError('datasets字段必须是非空数组')
        return value

class TaskRequestSerializer(serializers.Serializer):
    client_id = serializers.CharField(max_length=100)

class TaskResponseDatasetSerializer(serializers.Serializer):
    id = serializers.CharField()
    url = serializers.CharField()
    expected_md5 = serializers.CharField()
    file_size = serializers.IntegerField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)

class TaskResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    dataset = TaskResponseDatasetSerializer()
    heartbeat_interval_seconds = serializers.IntegerField()
    heartbeat_timeout_seconds = serializers.IntegerField()

class HeartbeatSerializer(serializers.Serializer):
    client_id = serializers.CharField(max_length=100)

class TaskCompleteSerializer(serializers.Serializer):
    client_id = serializers.CharField(max_length=100)
    actual_md5 = serializers.CharField(max_length=32)
    storage_path = serializers.CharField(max_length=1024, required=False, allow_blank=True)

    def validate_actual_md5(self, value):
        if len(value) != 32:
            raise serializers.ValidationError('actual_md5必须是32字符')
        return value

class TaskCompleteResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    dataset_id = serializers.CharField()
    task_status = serializers.CharField()
    dataset_status = serializers.CharField()
    storage_path = serializers.CharField(required=False, allow_blank=True, allow_null=True)

class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ['id', 'url', 'expected_md5', 'file_size', 'metadata', 'status', 'storage_path', 'created_at', 'updated_at']

class DatasetListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ['id', 'url', 'status', 'file_size', 'storage_path', 'created_at']

class TaskDetailSerializer(serializers.ModelSerializer):
    dataset_id = serializers.CharField(read_only=True)
    class Meta:
        model = DownloadTask
        fields = ['id', 'dataset_id', 'client_id', 'status', 'started_at', 'last_heartbeat', 'completed_at', 'actual_md5', 'error_message']