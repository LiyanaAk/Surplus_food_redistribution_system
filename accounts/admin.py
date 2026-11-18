from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('user_id', 'email', 'name', 'role', 'verification_status', 'phone', 'is_active', 'created_at')
    list_filter = ('role', 'verification_status', 'is_active')
    search_fields = ('email', 'name', 'phone', 'address')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile Information', {'fields': ('name', 'phone', 'address', 'latitude', 'longitude')}),
        ('Role & Verification', {'fields': ('role', 'verification_status')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'created_at')}),
    )
    readonly_fields = ('created_at', 'last_login')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password1', 'password2'),
        }),
    )

    actions = ['approve_selected_users', 'reject_selected_users']

    def approve_selected_users(self, request, queryset):
        count = queryset.update(verification_status=User.STATUS_APPROVED)
        self.message_user(request, f"{count} user(s) approved successfully.")
    approve_selected_users.short_description = "Approve verification for selected accounts"

    def reject_selected_users(self, request, queryset):
        count = queryset.update(verification_status=User.STATUS_REJECTED)
        self.message_user(request, f"{count} user(s) rejected.")
    reject_selected_users.short_description = "Reject verification for selected accounts"
