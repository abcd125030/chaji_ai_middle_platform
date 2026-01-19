from django.contrib import admin
from .models import UserLoginAuth


# Register your models here.
@admin.register(UserLoginAuth)
class UserLoginAuthAdmin(admin.ModelAdmin):
    list_display = ('user', 'address', 'reason', 'task', 'service_api', 'result', 'get_llm_models')
    search_fields = ('user__username', 'address', 'reason', 'task', 'result')
    list_filter = ('user',)
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'address', 'reason', 'task', 'service_api', 'result')
        }),
        ('模型配置', {
            'fields': ('llm_models',),
            'description': '选择此服务可以使用的大语言模型'
        }),
    )

    filter_horizontal = ('llm_models',)
    autocomplete_fields = ['llm_models']

    def get_llm_models(self, obj):
        """获取关联的大语言模型名称列表，以逗号分隔"""
        return ", ".join([model.name for model in obj.llm_models.all()]) if obj.llm_models.exists() else None
