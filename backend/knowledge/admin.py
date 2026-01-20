from django.contrib import admin
from django import forms
from .models import KnowledgeCollection, KnowledgeItem, KnowledgeInteraction, KnowledgeConfig
from router.models import LLMModel

class KnowledgeConfigForm(forms.ModelForm):
    """知识库配置表单，支持从路由器选择模型"""
    
    # 从路由器选择LLM模型
    llm_model_choice = forms.ModelChoiceField(
        queryset=LLMModel.objects.filter(model_type__in=['text', 'reasoning']),
        required=False,
        label='LLM 模型（从路由器选择）',
        help_text='选择一个已配置的LLM模型，将自动填充相关字段'
    )
    
    # 从路由器选择Embedder模型
    embedder_model_choice = forms.ModelChoiceField(
        queryset=LLMModel.objects.filter(model_type='embedding'),
        required=False,
        label='Embedder 模型（从路由器选择）',
        help_text='选择一个已配置的嵌入模型，将自动填充相关字段'
    )
    
    class Meta:
        model = KnowledgeConfig
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 如果是编辑现有配置，尝试匹配路由器中的模型
        if self.instance and self.instance.pk:
            # 尝试找到匹配的LLM模型
            llm_model = LLMModel.objects.filter(
                model_id=self.instance.llm_model_name
            ).first()
            if llm_model:
                self.fields['llm_model_choice'].initial = llm_model
            
            # 尝试找到匹配的Embedder模型
            embedder_model = LLMModel.objects.filter(
                model_id=self.instance.embedder_model_name,
                model_type='embedding'
            ).first()
            if embedder_model:
                self.fields['embedder_model_choice'].initial = embedder_model

"""
知识库配置管理后台
用于管理知识库的LLM、Embedder和向量存储配置
"""
@admin.register(KnowledgeConfig)
class KnowledgeConfigAdmin(admin.ModelAdmin):
    """知识库配置模型的后台管理类"""
    form = KnowledgeConfigForm
    list_display = ('name', 'is_active', 'get_llm_display', 'get_embedder_display', 'vector_store_provider', 'updated_at')
    list_filter = ('is_active', 'vector_store_provider')
    search_fields = ('name', 'llm_model_name', 'embedder_model_name')
    ordering = ('-is_active', '-updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'is_active')
        }),
        ('模型选择（推荐）', {
            'fields': ('llm_model_choice', 'embedder_model_choice'),
            'description': '从路由器中选择已配置的模型，将自动同步配置信息'
        }),
        ('LLM 配置（手动）', {
            'classes': ('collapse',),
            'fields': ('llm_model_name', 'llm_temperature'),
            'description': '如果选择了路由器模型，这些字段将自动更新'
        }),
        ('Embedder 配置（手动）', {
            'classes': ('collapse',),
            'fields': ('embedder_model_name', 'embedder_dimensions'),
            'description': '如果选择了路由器模型，这些字段将自动更新'
        }),
        ('向量存储配置', {
            'fields': ('vector_store_provider', 'qdrant_host', 'qdrant_port', 'qdrant_api_key')
        }),
    )
    
    def get_llm_display(self, obj):
        """显示LLM模型信息"""
        if obj.llm_model_name:
            # 尝试从路由器获取模型信息
            model = LLMModel.objects.filter(model_id=obj.llm_model_name).first()
            if model:
                return f"{model.name} ({obj.llm_model_name})"
            return obj.llm_model_name
        return '-'
    get_llm_display.short_description = 'LLM 模型'
    
    def get_embedder_display(self, obj):
        """显示Embedder模型信息"""
        if obj.embedder_model_name:
            # 尝试从路由器获取模型信息
            model = LLMModel.objects.filter(
                model_id=obj.embedder_model_name,
                model_type='embedding'
            ).first()
            if model:
                return f"{model.name} ({obj.embedder_model_name})"
            return obj.embedder_model_name
        return '-'
    get_embedder_display.short_description = 'Embedder 模型'
    
    def save_model(self, request, obj, form, change):
        """保存模型时，如果选择了路由器模型，则同步相关信息"""
        # 如果选择了LLM模型
        if form.cleaned_data.get('llm_model_choice'):
            llm_model = form.cleaned_data['llm_model_choice']
            obj.llm_model_name = llm_model.model_id
            # 这些字段现在从路由器获取，不再需要存储
            # obj.llm_provider = self._get_provider_from_model(llm_model)
            # obj.llm_api_key = self._get_api_key_from_model(llm_model)
            # obj.openai_base_url = llm_model.endpoint.endpoint if llm_model.endpoint else ''
        
        # 如果选择了Embedder模型
        if form.cleaned_data.get('embedder_model_choice'):
            embedder_model = form.cleaned_data['embedder_model_choice']
            obj.embedder_model_name = embedder_model.model_id
            # 这些字段现在从路由器获取，不再需要存储
            # obj.embedder_provider = self._get_provider_from_model(embedder_model)
            # obj.embedder_api_key = self._get_api_key_from_model(embedder_model)
            # obj.embedder_base_url = embedder_model.endpoint.endpoint if embedder_model.endpoint else ''
        
        super().save_model(request, obj, form, change)

"""
知识库集合管理后台
用于管理知识库集合(分类)信息
"""
@admin.register(KnowledgeCollection)
class KnowledgeCollectionAdmin(admin.ModelAdmin):
    """知识库集合模型的后台管理类"""
    list_display = ('name', 'description', 'created_by', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    # Ensure 'config' field is not in fieldsets or fields if it was previously.
    # Example: fields = ('name', 'description', 'mem0_collection_id', 'qdrant_collection_name', 'created_by')
    readonly_fields = ('created_at', 'updated_at')

"""
知识库条目管理后台
用于管理知识库中的具体知识条目
"""
@admin.register(KnowledgeItem)
class KnowledgeItemAdmin(admin.ModelAdmin):
    """知识条目模型的后台管理类"""
    list_display = ('id', 'collection', 'source_identifier', 'status', 'added_at', 'last_accessed_at')
    list_filter = ('status', 'collection')
    search_fields = ('source_identifier', 'content')
    readonly_fields = ('added_at',)

"""
知识库交互记录管理后台
用于记录用户与知识库的交互历史
"""
@admin.register(KnowledgeInteraction)
class KnowledgeInteractionAdmin(admin.ModelAdmin):
    """知识库交互记录模型的后台管理类"""
    list_display = ('id', 'user', 'collection', 'interaction_type', 'status_code', 'timestamp')
    list_filter = ('interaction_type', 'status_code', 'collection')
    search_fields = ('user__username', 'error_message') # Assuming user has a username
    readonly_fields = ('timestamp',)
