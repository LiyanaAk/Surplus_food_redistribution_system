from django.contrib import admin
from .models import FoodCategory, FoodListing, StatusHistory

@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ('category_id', 'name')
    search_fields = ('name',)

@admin.register(FoodListing)
class FoodListingAdmin(admin.ModelAdmin):
    list_display = ('listing_id', 'food_type', 'category', 'donor', 'quantity', 'quantity_unit', 'priority', 'status', 'usable_until', 'created_at')
    list_filter = ('status', 'priority', 'category')
    search_fields = ('food_type', 'donor__name', 'pickup_address', 'description')
    ordering = ('-created_at',)

@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('history_id', 'listing', 'status', 'changed_by', 'changed_at', 'remarks')
    list_filter = ('status', 'changed_at')
    search_fields = ('listing__food_type', 'changed_by__name', 'remarks')
    ordering = ('-changed_at',)
