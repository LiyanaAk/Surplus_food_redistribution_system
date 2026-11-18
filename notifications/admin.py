from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('notification_id', 'user', 'listing', 'channel', 'message_snippet', 'is_read', 'sent_at')
    list_filter = ('channel', 'is_read', 'sent_at')
    search_fields = ('user__name', 'user__email', 'message')

    def message_snippet(self, obj):
        return obj.message[:50]
    message_snippet.short_description = "Message"
