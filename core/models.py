from django.db import models

class SystemSetting(models.Model):
    """
    Stores system-wide configurable parameters:
    - Priority thresholds (Urgent <= 60 mins, High <= 180 mins)
    - Default search radius for nearby listings (10 km)
    """
    urgent_threshold_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Listing priority becomes URGENT when remaining usable time is at or below this value (in minutes)"
    )
    high_threshold_minutes = models.PositiveIntegerField(
        default=180,
        help_text="Listing priority becomes HIGH when remaining usable time is at or below this value (in minutes)"
    )
    default_search_radius_km = models.PositiveIntegerField(
        default=10,
        help_text="Default radius in kilometers for finding nearby active food listings"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_settings'
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f"Settings: Urgent<={self.urgent_threshold_minutes}m, High<={self.high_threshold_minutes}m, Radius={self.default_search_radius_km}km"

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj
