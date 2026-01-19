from django.contrib import admin
from .models import Session, QA, AgenticLog


class QAInline(admin.TabularInline):
    model = QA
    fields = ('source_app', 'prompt_text', 'model', 'created_at')
    readonly_fields = ('source_app', 'prompt_text', 'model', 'created_at')
    extra = 0


class AgenticLogInline(admin.TabularInline):
    model = AgenticLog
    fields = ('step_order', 'log_type', 'created_at')
    readonly_fields = ('step_order', 'log_type', 'created_at')
    extra = 0
    ordering = ('step_order',)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'state', 'session_length', 'user', 'created_at')
    search_fields = ('session_id',)
    list_filter = ('state', 'created_at')
    inlines = [QAInline]


@admin.register(QA)
class QAAdmin(admin.ModelAdmin):
    list_display = ('source_app', 'source_type', 'user', 'session', 'prompt_text', 'prompt_images', 'prompt_files', 'model', 'prompt_params')
    search_fields = ('source_app', 'model')
    list_filter = ('source_type', 'created_at')
    inlines = [AgenticLogInline]


@admin.register(AgenticLog)
class AgenticLogAdmin(admin.ModelAdmin):
    list_display = ('task', 'qa_record', 'step_order', 'log_type', 'created_at')
    list_filter = ('log_type', 'created_at')
    search_fields = ('task__task_id',)
    readonly_fields = [field.name for field in AgenticLog._meta.fields]
