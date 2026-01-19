from django.contrib import admin
from .models import Dataset, DownloadTask, Notification, SystemConfig

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "created_at", "updated_at")
    fields = ("id", "url", "expected_md5", "file_size", "metadata", "status", "storage_path", "created_at", "updated_at")
    list_display = ("id", "url", "status", "file_size", "created_at", "updated_at")
    search_fields = ("url", "expected_md5", "storage_path")
    list_filter = ("status",)
    ordering = ("-created_at",)

    def id_star(self, obj):
        return obj.id
    id_star.short_description = "Id *"

@admin.register(DownloadTask)
class DownloadTaskAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "started_at", "last_heartbeat", "completed_at", "created_at", "updated_at")
    list_display = ("id", "dataset", "client_id", "status", "started_at", "last_heartbeat", "completed_at", "created_at", "updated_at")
    search_fields = ("client_id", "dataset__url")
    list_filter = ("status",)
    ordering = ("-created_at",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "created_at", "sent_at")
    list_display = ("id", "notification_type", "status", "created_at", "sent_at")
    list_filter = ("notification_type", "status")
    search_fields = ("subject", "recipients")
    ordering = ("-created_at",)

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "updated_at")
    list_display = ("id", "key", "updated_at")
    search_fields = ("key",)
    ordering = ("key",)
