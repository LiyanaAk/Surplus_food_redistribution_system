from django.contrib import admin
from .models import SystemSetting

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('id', 'urgent_threshold_minutes', 'high_threshold_minutes', 'default_search_radius_km', 'updated_at')
