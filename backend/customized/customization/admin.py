from django.contrib import admin

from customized.customization.models import CustomizedQA


# Register your models here.
@admin.register(CustomizedQA)
class CustomizedQAAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'source_type', 'user', 'input', 'prompt_text', 'prompt_images', 'prompt_files', 'model', 'output', "is_final", 'input_session_length', 'output_session_length')
    search_fields = ('task_id', 'model')
    list_filter = ('source_type', 'created_at')