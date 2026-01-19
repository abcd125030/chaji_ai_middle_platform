"""
Xiaohongshu sentiment monitoring serializers
"""
from rest_framework import serializers
from .models import MonitorKeyword, XiaohongshuNote, NoteAnalysisResult


class MonitorKeywordSerializer(serializers.ModelSerializer):
    """Monitor keyword serializer"""

    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = MonitorKeyword
        fields = [
            'id',
            'keyword',
            'is_active',
            'priority',
            'match_type',
            'category',
            'description',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class NoteAnalysisResultSerializer(serializers.ModelSerializer):
    """Note analysis result serializer"""

    final_category = serializers.CharField(read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    sentiment_display = serializers.CharField(source='get_sentiment_display', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = NoteAnalysisResult
        fields = [
            'id',
            'category',
            'category_display',
            'final_category',
            'sentiment',
            'sentiment_display',
            'risk_score',
            'reason',
            'image_analysis',
            'llm_response',
            'model_used',
            'input_tokens',
            'output_tokens',
            'analyzed_at',
            'analysis_duration',
            'is_reviewed',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'review_notes',
            'manual_category',
        ]
        read_only_fields = [
            'id', 'category', 'sentiment', 'risk_score', 'reason',
            'image_analysis', 'llm_response', 'model_used',
            'input_tokens', 'output_tokens', 'analyzed_at', 'analysis_duration',
        ]


class XiaohongshuNoteSerializer(serializers.ModelSerializer):
    """Xiaohongshu note serializer"""

    analysis_result = NoteAnalysisResultSerializer(read_only=True)
    note_type_display = serializers.CharField(source='get_note_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    matched_keyword_names = serializers.SerializerMethodField()

    class Meta:
        model = XiaohongshuNote
        fields = [
            'id',
            'note_id',
            'author_name',
            'author_avatar',
            'description',
            'note_type',
            'note_type_display',
            'images',
            'tags',
            'likes_count',
            'collects_count',
            'comments_count',
            'publish_time',
            'location',
            'top_comments',
            'extracted_at',
            'card_index',
            'matched_keywords',
            'matched_keyword_names',
            'source',
            'status',
            'status_display',
            'created_at',
            'updated_at',
            'analysis_result',
        ]
        read_only_fields = [
            'id', 'note_id', 'author_name', 'author_avatar', 'description',
            'note_type', 'images', 'tags', 'likes_count', 'collects_count',
            'comments_count', 'publish_time', 'location', 'top_comments',
            'extracted_at', 'card_index', 'created_at', 'updated_at',
        ]

    def get_matched_keyword_names(self, obj):
        """Get list of matched keyword names"""
        return list(obj.matched_keywords.values_list('keyword', flat=True))


class NoteUploadSerializer(serializers.Serializer):
    """Serializer for note upload from crawler client"""

    # Required fields from crawled data
    note_id = serializers.CharField(max_length=64)
    author = serializers.CharField(max_length=100, required=False, allow_blank=True)
    author_avatar = serializers.URLField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    type = serializers.ChoiceField(choices=['image', 'video'], default='image')
    images = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=list
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    likes = serializers.CharField(required=False, default='0')
    collects = serializers.CharField(required=False, default='0')
    comments = serializers.CharField(required=False, default='0')
    publish_time = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    top_comments = serializers.ListField(required=False, default=list)
    extracted_at = serializers.CharField(required=False, allow_blank=True)
    card_index = serializers.IntegerField(required=False, default=0)

    def validate_likes(self, value):
        """Convert likes string to int"""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0

    def validate_collects(self, value):
        """Convert collects string to int"""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0

    def validate_comments(self, value):
        """Convert comments string to int"""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0


class BatchNoteUploadSerializer(serializers.Serializer):
    """Serializer for batch note upload"""

    notes = NoteUploadSerializer(many=True)
    source = serializers.CharField(max_length=50, required=False, default='')


class NoteListFilterSerializer(serializers.Serializer):
    """Serializer for note list filters"""

    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)
    status = serializers.ChoiceField(
        choices=['pending', 'analyzing', 'completed', 'failed', ''],
        required=False,
        allow_blank=True
    )
    note_type = serializers.ChoiceField(
        choices=['image', 'video', ''],
        required=False,
        allow_blank=True
    )
    keyword = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


class AnalysisReviewSerializer(serializers.Serializer):
    """Serializer for manual review update"""

    manual_category = serializers.ChoiceField(
        choices=['category_1', 'category_2', 'category_3', 'category_4', 'other'],
        required=False,
        allow_blank=True
    )
    review_notes = serializers.CharField(required=False, allow_blank=True)
