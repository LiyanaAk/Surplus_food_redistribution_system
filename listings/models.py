from django.db import models
from django.conf import settings
from django.utils import timezone
import math

class FoodCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'food_categories'
        verbose_name = 'Food Category'
        verbose_name_plural = 'Food Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class FoodListing(models.Model):
    PRIORITY_NORMAL = 'NORMAL'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_URGENT = 'URGENT'

    PRIORITY_CHOICES = (
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High Priority (< 3 hrs left)'),
        (PRIORITY_URGENT, 'Urgent (< 1 hr left)'),
    )

    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_CLAIMED = 'CLAIMED'
    STATUS_COLLECTED = 'COLLECTED'
    STATUS_IN_TRANSIT = 'IN_TRANSIT'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = (
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_CLAIMED, 'Claimed'),
        (STATUS_COLLECTED, 'Collected'),
        (STATUS_IN_TRANSIT, 'In Transit'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    QUANTITY_UNITS = (
        ('kg', 'Kilograms (kg)'),
        ('meals', 'Meals / Servings'),
        ('packets', 'Packets / Boxes'),
        ('liters', 'Liters (L)'),
        ('items', 'Pieces / Items'),
    )

    listing_id = models.AutoField(primary_key=True)
    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='food_listings',
        db_column='donor_id'
    )
    category = models.ForeignKey(
        FoodCategory,
        on_delete=models.PROTECT,
        related_name='listings',
        db_column='category_id'
    )
    food_type = models.CharField(max_length=200, help_text="Specific food title (e.g., Rice, Dal & Sabzi, Mixed Sandwiches)")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Numerical amount")
    quantity_unit = models.CharField(max_length=50, choices=QUANTITY_UNITS, default='kg')
    prepared_at = models.DateTimeField(help_text="When food was prepared")
    usable_until = models.DateTimeField(help_text="Safe consumption deadline")
    pickup_address = models.TextField(help_text="Address where food must be collected")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)

    # Required validation / business fields
    description = models.TextField(blank=True, help_text="Allergens, storage instructions, or packaging notes")
    food_safety_accepted = models.BooleanField(
        default=False,
        help_text="Donor certification that food is hygienic, freshly cooked, and stored properly"
    )

    class Meta:
        db_table = 'food_listings'
        verbose_name = 'Food Listing'
        verbose_name_plural = 'Food Listings'
        ordering = ['usable_until', '-priority']

    def __str__(self):
        return f"#{self.listing_id} - {self.food_type} ({self.quantity} {self.quantity_unit}) [{self.status}]"

    @property
    def remaining_minutes(self):
        now = timezone.now()
        diff = (self.usable_until - now).total_seconds() / 60
        return int(diff)

    @property
    def remaining_time_display(self):
        mins = self.remaining_minutes
        if mins <= 0:
            return "Expired"
        hours = mins // 60
        remainder = mins % 60
        if hours > 24:
            days = hours // 24
            return f"{days}d {hours % 24}h remaining"
        elif hours > 0:
            return f"{hours}h {remainder}m remaining"
        else:
            return f"{mins}m remaining"

    def recalculate_priority_and_status(self, urgent_thresh=60, high_thresh=180, save=True, user=None):
        """
        Calculates priority and checks for expiration:
        - If remaining time <= 0 and status in (AVAILABLE, CLAIMED), mark EXPIRED.
        - Food already COLLECTED or IN_TRANSIT is not expired.
        - Priority: <= 60 mins -> URGENT, <= 180 mins -> HIGH, else NORMAL.
        """
        now = timezone.now()
        mins = (self.usable_until - now).total_seconds() / 60
        old_status = self.status
        old_priority = self.priority
        status_changed = False
        priority_changed = False

        if mins <= 0:
            if self.status in [self.STATUS_AVAILABLE, self.STATUS_CLAIMED]:
                self.status = self.STATUS_EXPIRED
                status_changed = True
        else:
            new_p = self.PRIORITY_NORMAL
            if mins <= urgent_thresh:
                new_p = self.PRIORITY_URGENT
            elif mins <= high_thresh:
                new_p = self.PRIORITY_HIGH
            
            if new_p != self.priority:
                self.priority = new_p
                priority_changed = True

        if save and (status_changed or priority_changed):
            self.save(update_fields=['status', 'priority'])
            if status_changed:
                StatusHistory.objects.create(
                    listing=self,
                    changed_by=user,
                    status=self.status,
                    remarks=f"Automatic expiry after safe usable period passed ({self.remaining_time_display})"
                )

        return status_changed, priority_changed

    @property
    def can_be_edited(self):
        return self.status == self.STATUS_AVAILABLE

    @property
    def can_be_cancelled(self):
        return self.status == self.STATUS_AVAILABLE

    @property
    def active_claim(self):
        return self.claims.filter(is_active=True).first()


class StatusHistory(models.Model):
    history_id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(
        FoodListing,
        on_delete=models.CASCADE,
        related_name='status_history',
        db_column='listing_id'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='status_changes',
        db_column='changed_by'
    )
    status = models.CharField(max_length=20)
    remarks = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'status_history'
        verbose_name = 'Status History'
        verbose_name_plural = 'Status Histories'
        ordering = ['changed_at']

    def __str__(self):
        return f"Listing #{self.listing_id} -> {self.status} at {self.changed_at.strftime('%Y-%m-%d %H:%M')}"
