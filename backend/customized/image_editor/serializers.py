from rest_framework import serializers


class SubmitTaskSerializer(serializers.Serializer):
    """提交单个任务的序列化器"""
    prompt = serializers.CharField(required=True, help_text="风格描述提示词")
    image = serializers.URLField(required=True, help_text="需要编辑的图片URL")
    callback_url = serializers.URLField(required=False, allow_blank=True, help_text="任务完成后的回调地址")


class QueryTaskSerializer(serializers.Serializer):
    """查询任务的序列化器"""
    task_id = serializers.UUIDField(required=True, help_text="任务ID")


class BatchSubmitSerializer(serializers.Serializer):
    """批量提交任务的序列化器"""
    tasks = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        min_length=1,
        max_length=100,
        help_text="任务数组，每个元素包含 prompt 和 image"
    )
    callback_url = serializers.URLField(required=False, allow_blank=True, help_text="批量任务完成后的回调地址")
    
    def validate_tasks(self, value):
        """验证每个任务的格式"""
        for i, task in enumerate(value):
            if 'prompt' not in task:
                raise serializers.ValidationError(f"任务 {i} 缺少 prompt 字段")
            if 'image' not in task:
                raise serializers.ValidationError(f"任务 {i} 缺少 image 字段")
            
            # 验证 URL 格式
            url_validator = serializers.URLField()
            try:
                url_validator.run_validation(task['image'])
            except serializers.ValidationError:
                raise serializers.ValidationError(f"任务 {i} 的 image URL 格式无效")
        
        return value


class BatchQuerySerializer(serializers.Serializer):
    """批量查询任务的序列化器"""
    task_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
        help_text="任务ID数组"
    )