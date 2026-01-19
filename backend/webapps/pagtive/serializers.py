from rest_framework import serializers
from .models import Project, ProjectDetail, ProjectLLMLog


class ProjectDetailSerializer(serializers.ModelSerializer):
    """项目详情序列化器"""
    
    class Meta:
        model = ProjectDetail
        fields = [
            'id', 'page_id', 'html', 'styles', 'script',
            'images', 'mermaid_content', 'version_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProjectSerializer(serializers.ModelSerializer):
    """项目序列化器"""
    
    details = ProjectDetailSerializer(many=True, read_only=True)
    page_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'project_name', 'project_description', 'project_style',
            'global_style_code', 'pages', 'is_public', 'is_published',
            'is_featured', 'style_tags', 'reference_files', 'created_at', 'updated_at',
            'page_count', 'details'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'reference_files']
    
    def get_page_count(self, obj):
        """获取页面数量"""
        if obj.pages:
            return len(obj.pages)
        return 0


class CreateProjectSerializer(serializers.ModelSerializer):
    """创建项目序列化器"""
    
    class Meta:
        model = Project
        fields = [
            'id', 'project_name', 'project_description', 'project_style',
            'global_style_code', 'is_public'
        ]
        read_only_fields = ['id']
    
    def create(self, validated_data):
        """创建项目"""
        validated_data['user'] = self.context['request'].user
        validated_data['pages'] = []  # 初始化空页面列表
        return super().create(validated_data)


class PageSerializer(serializers.Serializer):
    """页面序列化器（页面存储在项目的pages字段中）"""
    
    # ID可以是字符串形式的数字，也可以是UUID
    id = serializers.CharField(required=False, allow_blank=False)
    title = serializers.CharField(max_length=255)
    order = serializers.IntegerField(required=False, default=0)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ImageInfoSerializer(serializers.Serializer):
    """图片信息序列化器"""
    uuid = serializers.CharField(required=True)
    alias = serializers.CharField(required=True)
    type = serializers.ChoiceField(choices=['upload', 'external'], default='upload')
    url = serializers.CharField(required=False, allow_blank=True)
    isReference = serializers.BooleanField(default=False)


class ReferenceContentSerializer(serializers.Serializer):
    """参考页面内容序列化器"""
    pageId = serializers.CharField(required=True)
    pageName = serializers.CharField(required=True)
    includeHtml = serializers.BooleanField(default=True)
    includeCss = serializers.BooleanField(default=True)
    includeJs = serializers.BooleanField(default=True)


class CurrentContentSerializer(serializers.Serializer):
    """当前页面内容序列化器（用于编辑模式）"""
    html = serializers.CharField(allow_blank=True, default='')
    styles = serializers.CharField(allow_blank=True, default='')  # 注意: 使用styles而不是css
    script = serializers.CharField(allow_blank=True, default='')  # 注意: 使用script而不是js
    mermaid = serializers.CharField(allow_blank=True, default='', required=False)


class GenerateRequestSerializer(serializers.Serializer):
    """AI生成请求序列化器 - 与旧项目保持一致的字段"""
    
    projectId = serializers.CharField(required=True)
    pageId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    prompt = serializers.CharField(required=True)
    scenario = serializers.ChoiceField(
        choices=['generatePageCode', 'editPageCode'],
        required=False,
        allow_blank=True,
        allow_null=True
    )
    template = serializers.ChoiceField(
        choices=['generatePageCode', 'editPageCode'],
        default='generatePageCode'
    )
    images = ImageInfoSerializer(many=True, required=False, default=list)
    references = ReferenceContentSerializer(many=True, required=False, default=list)
    current = CurrentContentSerializer(required=False, allow_null=True)
    tempPageId = serializers.CharField(required=False, allow_blank=True)
    insertAfterId = serializers.CharField(required=False, allow_blank=True, default='end')
    
    def validate(self, attrs):
        """验证请求数据"""
        template = attrs.get('template')
        
        # 编辑模式必须有pageId和current
        if template == 'editPageCode':
            if not attrs.get('pageId'):
                raise serializers.ValidationError('编辑模式必须提供pageId')
            if not attrs.get('current'):
                raise serializers.ValidationError('编辑模式必须提供当前页面内容')
        
        # 创建模式不应该有pageId
        if template == 'generatePageCode' and attrs.get('pageId'):
            attrs.pop('pageId')  # 移除pageId，避免混淆
            
        return attrs


class LLMLogSerializer(serializers.ModelSerializer):
    """LLM日志序列化器"""
    
    class Meta:
        model = ProjectLLMLog
        fields = '__all__'
        read_only_fields = ['id', 'request_timestamp']


class FileUploadSerializer(serializers.Serializer):
    """文件上传序列化器"""
    
    file = serializers.FileField(required=True)
    project_id = serializers.UUIDField(required=False)
    
    def validate_file(self, value):
        """验证文件"""
        # 检查文件大小（100MB限制）
        if value.size > 100 * 1024 * 1024:
            raise serializers.ValidationError("文件大小不能超过100MB")
        
        # 可以在这里添加更多的文件类型检查
        return value