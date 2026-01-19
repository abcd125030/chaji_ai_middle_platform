from rest_framework import serializers
from .models import PDFParseTask, ParseResult


class ParseResultSerializer(serializers.ModelSerializer):
    """解析结果序列化器"""
    
    class Meta:
        model = ParseResult
        fields = [
            'markdown_path', 'json_path',
            'total_text_blocks', 'total_images', 
            'total_tables', 'total_formulas',
            'metadata', 'created_at'
        ]
        read_only_fields = fields


class PDFParseTaskSerializer(serializers.ModelSerializer):
    """PDF解析任务序列化器"""
    result = ParseResultSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    file_type_display = serializers.CharField(source='get_file_type_display', read_only=True)
    parse_method_display = serializers.CharField(source='get_parse_method_display', read_only=True)
    
    class Meta:
        model = PDFParseTask
        fields = [
            'task_id', 'user', 'original_filename', 'file_type', 'file_type_display',
            'file_size', 'file_path', 'parse_method', 'parse_method_display',
            'debug_enabled', 'status', 'status_display', 'output_dir',
            'page_count', 'processing_time', 'error_message', 'text_preview',
            'created_at', 'updated_at', 'completed_at', 'result'
        ]
        read_only_fields = [
            'task_id', 'user', 'file_path', 'status', 'output_dir',
            'page_count', 'processing_time', 'error_message', 'text_preview',
            'created_at', 'updated_at', 'completed_at', 'result'
        ]


class FileUploadSerializer(serializers.Serializer):
    """文件上传序列化器"""
    file = serializers.FileField(required=True)
    parse_method = serializers.ChoiceField(
        choices=['auto', 'ocr', 'txt'],
        default='auto',
        required=False
    )
    debug_enabled = serializers.BooleanField(default=False, required=False)
    
    def validate_file(self, value):
        """验证上传的文件"""
        # 文件大小验证
        max_size = 100 * 1024 * 1024  # 100MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"文件大小超过限制（最大 {max_size // (1024*1024)}MB）"
            )
        
        # 文件类型验证（基于扩展名）
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'ppt', 'pptx']
        ext = value.name.split('.')[-1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"不支持的文件类型。支持的类型: {', '.join(allowed_extensions)}"
            )
        
        return value


class TaskCreateSerializer(serializers.Serializer):
    """创建任务请求序列化器"""
    file_base64 = serializers.CharField(required=True, help_text="Base64编码的文件内容")
    filename = serializers.CharField(required=True, max_length=255)
    parse_method = serializers.ChoiceField(
        choices=['auto', 'ocr', 'txt'],
        default='auto',
        required=False
    )
    debug_enabled = serializers.BooleanField(default=False, required=False)


class TaskListSerializer(serializers.ModelSerializer):
    """任务列表序列化器（简化版）"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = PDFParseTask
        fields = [
            'task_id', 'original_filename', 'file_type', 'file_size',
            'status', 'status_display', 'created_at', 'processing_time'
        ]


class TaskStatusSerializer(serializers.Serializer):
    """任务状态查询响应"""
    task_id = serializers.UUIDField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    progress = serializers.IntegerField(default=0)
    message = serializers.CharField(allow_blank=True, default="")
    result = ParseResultSerializer(allow_null=True, required=False)