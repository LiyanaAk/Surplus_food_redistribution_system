from django.db import models
from django.conf import settings
from listings.models import FoodListing

class Notification(models.Model):
    CHANNEL_IN_APP = 'IN_APP'
    CHANNEL_EMAIL = 'EMAIL'
    CHANNEL_SMS = 'SMS'
    CHANNEL_PUSH = 'PUSH'

    CHANNEL_CHOICES = (
        (CHANNEL_IN_APP, 'In-App'),
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_PUSH, 'Push Notification'),
    )

    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_column='user_id'
    )
    listing = models.ForeignKey(
        FoodListing,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        db_column='listing_id'
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_IN_APP)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-sent_at']

    def __str__(self):
        return f"[{self.channel}] To {self.user.name}: {self.message[:40]}"
