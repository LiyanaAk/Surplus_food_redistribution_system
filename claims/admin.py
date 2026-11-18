from django.contrib import admin
from .models import Claim

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_id', 'listing', 'claimer', 'institution', 'meals_delivered', 'is_active', 'claimed_at')
    list_filter = ('is_active', 'claimed_at')
    search_fields = ('listing__food_type', 'claimer__name', 'institution__user__name', 'recipient_note')
