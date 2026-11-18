from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from accounts.models import User
from institutions.models import Institution
from listings.models import FoodListing, FoodCategory, StatusHistory
from claims.models import Claim
from notifications.models import Notification
from .models import SystemSetting
from .forms import SystemSettingForm, ContactForm
from .utils import update_all_priorities_and_expiries
from listings.forms import FoodCategoryForm

def home_view(request):
    # Recalculate priorities so visitor sees fresh state
    update_all_priorities_and_expiries()

    # Public impact metrics
    total_listings = FoodListing.objects.count()
    delivered_listings = FoodListing.objects.filter(status=FoodListing.STATUS_DELIVERED).count()
    total_meals = Claim.objects.filter(listing__status=FoodListing.STATUS_DELIVERED).aggregate(m=Sum('meals_delivered'))['m'] or 0
    active_available = FoodListing.objects.filter(status=FoodListing.STATUS_AVAILABLE).count()

    total_donors = User.objects.filter(role=User.ROLE_DONOR).count()
    total_ngos = User.objects.filter(role=User.ROLE_NGO, verification_status=User.STATUS_APPROVED).count()
    total_institutions = Institution.objects.filter(user__verification_status=User.STATUS_APPROVED).count()

    # Recent available preview
    sample_available = FoodListing.objects.filter(
        status=FoodListing.STATUS_AVAILABLE
    ).select_related('category', 'donor').order_by('usable_until')[:4]

    context = {
        'title': 'Surplus Food Redistribution System - Bridge the Food Gap',
        'total_listings': total_listings,
        'delivered_listings': delivered_listings,
        'total_meals': total_meals,
        'active_available': active_available,
        'total_donors': total_donors,
        'total_ngos': total_ngos,
        'total_institutions': total_institutions,
        'sample_available': sample_available,
    }
    return render(request, 'core/home.html', context)


def about_view(request):
    return render(request, 'core/about.html', {'title': 'About Our Mission'})


def how_it_works_view(request):
    return render(request, 'core/how_it_works.html', {'title': 'How It Works'})


def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message_text = form.cleaned_data['message']

            # Notify administrators
            admins = User.objects.filter(role=User.ROLE_ADMIN)
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    channel=Notification.CHANNEL_IN_APP,
                    message=f"Contact Inquiry from {name} ({email}): {subject} - {message_text[:60]}"
                )

            messages.success(request, "Thank you! Your message has been received. Our team will get back to you shortly.")
            return redirect('core:contact')
    else:
        form = ContactForm()

    return render(request, 'core/contact.html', {'form': form, 'title': 'Contact & Support'})


def dashboard_router(request):
    """Routes logged-in users to their respective role dashboard"""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    if request.user.is_admin_user:
        return redirect('core:admin_dashboard')
    elif request.user.is_ngo:
        return redirect('claims:ngo_dashboard')
    elif request.user.is_institution:
        return redirect('institutions:institution_dashboard')
    else:
        return redirect('listings:donor_dashboard')


# ==========================================
# ADMINISTRATOR VIEWS
# ==========================================

@login_required
def admin_dashboard(request):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    update_all_priorities_and_expiries()

    # User counts
    total_users = User.objects.count()
    total_donors = User.objects.filter(role=User.ROLE_DONOR).count()
    total_ngos = User.objects.filter(role=User.ROLE_NGO).count()
    total_institutions = User.objects.filter(role=User.ROLE_INSTITUTION).count()
    pending_verifications = User.objects.filter(verification_status=User.STATUS_PENDING).count()

    # Listings breakdown
    total_listings = FoodListing.objects.count()
    available_listings = FoodListing.objects.filter(status=FoodListing.STATUS_AVAILABLE).count()
    claimed_listings = FoodListing.objects.filter(status=FoodListing.STATUS_CLAIMED).count()
    collected_listings = FoodListing.objects.filter(status=FoodListing.STATUS_COLLECTED).count()
    in_transit_listings = FoodListing.objects.filter(status=FoodListing.STATUS_IN_TRANSIT).count()
    delivered_listings = FoodListing.objects.filter(status=FoodListing.STATUS_DELIVERED).count()
    expired_listings = FoodListing.objects.filter(status=FoodListing.STATUS_EXPIRED).count()

    total_meals = Claim.objects.filter(listing__status=FoodListing.STATUS_DELIVERED).aggregate(m=Sum('meals_delivered'))['m'] or 0

    # Recent activities (Status History)
    recent_activities = StatusHistory.objects.select_related('listing', 'changed_by').order_by('-changed_at')[:8]
    pending_users = User.objects.filter(verification_status=User.STATUS_PENDING).order_by('-created_at')[:5]

    context = {
        'title': 'Administrator Dashboard',
        'total_users': total_users,
        'total_donors': total_donors,
        'total_ngos': total_ngos,
        'total_institutions': total_institutions,
        'pending_verifications': pending_verifications,
        'total_listings': total_listings,
        'available_listings': available_listings,
        'claimed_listings': claimed_listings,
        'collected_listings': collected_listings,
        'in_transit_listings': in_transit_listings,
        'delivered_listings': delivered_listings,
        'expired_listings': expired_listings,
        'total_meals': total_meals,
        'recent_activities': recent_activities,
        'pending_users': pending_users,
    }
    return render(request, 'core/admin_dashboard.html', context)


@login_required
def admin_user_management(request):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('q', '').strip()

    users = User.objects.all().order_by('-created_at')

    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter:
        users = users.filter(verification_status=status_filter)
    if search_query:
        users = users.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    context = {
        'title': 'User Management',
        'users': users,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'core/admin_user_management.html', context)


@login_required
def admin_toggle_user_active(request, user_id):
    if not request.user.is_admin_user:
        return redirect('core:home')

    target_user = get_object_or_404(User, user_id=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own administrative account.")
        return redirect('core:admin_users')

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])
    status_str = "activated" if target_user.is_active else "deactivated"
    messages.success(request, f"User {target_user.name} ({target_user.email}) has been {status_str}.")
    return redirect('core:admin_users')


@login_required
def admin_ngo_verification(request):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    status_filter = request.GET.get('status', 'pending')
    ngos = User.objects.filter(role=User.ROLE_NGO)
    if status_filter != 'all':
        ngos = ngos.filter(verification_status=status_filter)
    ngos = ngos.order_by('-created_at')

    context = {
        'title': 'NGO & Volunteer Verification',
        'ngos': ngos,
        'status_filter': status_filter,
    }
    return render(request, 'core/admin_ngo_verification.html', context)


@login_required
def admin_institution_verification(request):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    status_filter = request.GET.get('status', 'pending')
    institutions = Institution.objects.select_related('user')
    if status_filter != 'all':
        institutions = institutions.filter(user__verification_status=status_filter)
    institutions = institutions.order_by('-user__created_at')

    context = {
        'title': 'Beneficiary Institution Verification',
        'institutions': institutions,
        'status_filter': status_filter,
    }
    return render(request, 'core/admin_institution_verification.html', context)


@login_required
def admin_verify_user_action(request, user_id, action):
    """
    Allow an admin to verify and approve NGO and institution registrations.
    """
    if not request.user.is_admin_user:
        return redirect('core:home')

    target_user = get_object_or_404(User, user_id=user_id)
    if action == 'approve':
        target_user.verification_status = User.STATUS_APPROVED
        target_user.save(update_fields=['verification_status'])
        Notification.objects.create(
            user=target_user,
            channel=Notification.CHANNEL_IN_APP,
            message="Congratulations! Your account registration has been reviewed and APPROVED by the Administrator. You have full access."
        )
        messages.success(request, f"Approved registration for {target_user.name}.")
    elif action == 'reject':
        target_user.verification_status = User.STATUS_REJECTED
        target_user.save(update_fields=['verification_status'])
        Notification.objects.create(
            user=target_user,
            channel=Notification.CHANNEL_IN_APP,
            message="Your registration application has been REJECTED by the Administrator. Please contact support."
        )
        messages.warning(request, f"Rejected registration for {target_user.name}.")

    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    if target_user.role == User.ROLE_NGO:
        return redirect('core:admin_ngos')
    elif target_user.role == User.ROLE_INSTITUTION:
        return redirect('core:admin_institutions')
    return redirect('core:admin_users')


@login_required
def admin_listings_management(request):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    update_all_priorities_and_expiries()

    status_filter = request.GET.get('status', '')
    category_id = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()

    listings = FoodListing.objects.select_related('donor', 'category').prefetch_related('claims')

    if status_filter:
        listings = listings.filter(status=status_filter)
    if category_id:
        listings = listings.filter(category_id=category_id)
    if search_query:
        listings = listings.filter(
            Q(food_type__icontains=search_query) |
            Q(donor__name__icontains=search_query) |
            Q(pickup_address__icontains=search_query)
        )

    listings = listings.order_by('-created_at')
    categories = FoodCategory.objects.all()

    context = {
        'title': 'Food Listings Management',
        'listings': listings,
        'categories': categories,
        'status_filter': status_filter,
        'category_id': category_id,
        'search_query': search_query,
    }
    return render(request, 'core/admin_listings_management.html', context)


@login_required
def admin_categories_management(request):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    if request.method == 'POST':
        form = FoodCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' added successfully.")
            return redirect('core:admin_categories')
    else:
        form = FoodCategoryForm()

    categories = FoodCategory.objects.annotate(listing_count=Count('listings')).order_by('name')

    context = {
        'title': 'Food Category Management',
        'categories': categories,
        'form': form,
    }
    return render(request, 'core/admin_categories_management.html', context)


@login_required
def admin_delete_category(request, category_id):
    if not request.user.is_admin_user:
        return redirect('core:home')

    category = get_object_or_404(FoodCategory, category_id=category_id)
    if category.listings.exists():
        messages.error(request, f"Cannot delete '{category.name}' because existing food listings belong to it.")
    else:
        category.delete()
        messages.success(request, f"Category '{category.name}' deleted successfully.")

    return redirect('core:admin_categories')


@login_required
def admin_system_configuration(request):
    """
    Manage priority thresholds and default search radius.
    """
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    settings_obj = SystemSetting.get_settings()

    if request.method == 'POST':
        form = SystemSettingForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            # Immediately trigger recalculation with newly configured thresholds
            update_all_priorities_and_expiries()
            messages.success(request, "System priority thresholds and search radius updated successfully!")
            return redirect('core:admin_configuration')
    else:
        form = SystemSettingForm(instance=settings_obj)

    context = {
        'title': 'System Configuration & Thresholds',
        'form': form,
        'settings_obj': settings_obj,
    }
    return render(request, 'core/admin_system_configuration.html', context)
