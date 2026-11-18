from django.db import models
from django.conf import settings
from listings.models import FoodListing
from institutions.models import Institution

class Claim(models.Model):
    claim_id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(
        FoodListing,
        on_delete=models.CASCADE,
        related_name='claims',
        db_column='listing_id'
    )
    claimer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='claims',
        db_column='claimer_id'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_claims',
        db_column='institution_id',
        help_text="Registered beneficiary institution recipient (if applicable)"
    )
    recipient_note = models.TextField(
        blank=True,
        null=True,
        help_text="Manual recipient logging for homeless individuals, location of distribution, or notes"
    )
    meals_delivered = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Approximate or actual count of meals served"
    )
    claimed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this claim is currently active (False if released)"
    )
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'claims'
        verbose_name = 'Claim'
        verbose_name_plural = 'Claims'
        ordering = ['-claimed_at']

    def __str__(self):
        inst_label = self.institution.user.name if self.institution else "Homeless / Direct"
        return f"Claim #{self.claim_id} for Listing #{self.listing_id} by {self.claimer.name} -> {inst_label}"
