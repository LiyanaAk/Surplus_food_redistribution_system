from django.contrib import admin
from .models import Institution

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('institution_id', 'user', 'institution_type', 'capacity')
    list_filter = ('institution_type',)
    search_fields = ('user__name', 'user__email', 'institution_type')
