from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import FoodListing, FoodCategory, StatusHistory
from .forms import FoodListingForm
from core.utils import update_all_priorities_and_expiries, notify_nearby_ngos, suggest_nearest_institutions
from core.models import SystemSetting
from claims.models import Claim

@login_required
def donor_dashboard(request):
    if not (request.user.is_donor or request.user.is_admin_user):
        messages.error(request, "Access restricted to Donor accounts.")
        return redirect('core:home')

    # Run quick priority recalculation on demand
    update_all_priorities_and_expiries()

    listings_qs = FoodListing.objects.filter(donor=request.user)

    total_listings = listings_qs.count()
    active_count = listings_qs.filter(status=FoodListing.STATUS_AVAILABLE).count()
    claimed_count = listings_qs.filter(status=FoodListing.STATUS_CLAIMED).count()
    in_transit_count = listings_qs.filter(status=FoodListing.STATUS_IN_TRANSIT).count()
    delivered_count = listings_qs.filter(status=FoodListing.STATUS_DELIVERED).count()
    expired_count = listings_qs.filter(status=FoodListing.STATUS_EXPIRED).count()

    total_meals_delivered = Claim.objects.filter(
        listing__donor=request.user,
        listing__status=FoodListing.STATUS_DELIVERED
    ).aggregate(total=Sum('meals_delivered'))['total'] or 0

    recent_listings = listings_qs.select_related('category').order_by('-created_at')[:6]

    context = {
        'title': 'Donor Dashboard',
        'total_listings': total_listings,
        'active_count': active_count,
        'claimed_count': claimed_count,
        'in_transit_count': in_transit_count,
        'delivered_count': delivered_count,
        'expired_count': expired_count,
        'total_meals_delivered': total_meals_delivered,
        'recent_listings': recent_listings,
    }
    return render(request, 'listings/donor_dashboard.html', context)


@login_required
def create_listing(request):
    if not (request.user.is_donor or request.user.is_admin_user):
        messages.error(request, "Only registered donors can post surplus food listings.")
        return redirect('core:home')

    if request.method == 'POST':
        form = FoodListingForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                listing = form.save(commit=False)
                listing.donor = request.user
                listing.status = FoodListing.STATUS_AVAILABLE

                # Autofill coordinates from user profile if not entered in form
                if not listing.latitude and request.user.latitude:
                    listing.latitude = request.user.latitude
                if not listing.longitude and request.user.longitude:
                    listing.longitude = request.user.longitude
                if not listing.pickup_address and request.user.address:
                    listing.pickup_address = request.user.address

                listing.save()

                # Calculate initial priority
                settings = SystemSetting.get_settings()
                listing.recalculate_priority_and_status(
                    urgent_thresh=settings.urgent_threshold_minutes,
                    high_thresh=settings.high_threshold_minutes,
                    save=True,
                    user=request.user
                )

                # Record status history
                StatusHistory.objects.create(
                    listing=listing,
                    changed_by=request.user,
                    status=FoodListing.STATUS_AVAILABLE,
                    remarks="Food listing posted and verified available for pickup."
                )

                # Notify nearby NGOs
                notify_nearby_ngos(listing, is_urgent=(listing.priority == FoodListing.PRIORITY_URGENT))

            messages.success(request, f"Food listing '{listing.food_type}' created successfully! Nearby NGOs have been alerted.")
            return redirect('listings:my_listings')
    else:
        # Prepopulate pickup address from user profile
        initial_data = {
            'pickup_address': request.user.address,
            'latitude': request.user.latitude,
            'longitude': request.user.longitude,
            'prepared_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'usable_until': (timezone.now() + timezone.timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M'),
        }
        form = FoodListingForm(initial=initial_data)

    categories = FoodCategory.objects.all()
    return render(request, 'listings/create_listing.html', {'form': form, 'categories': categories, 'title': 'Create Food Listing'})


@login_required
def my_listings(request):
    if not (request.user.is_donor or request.user.is_admin_user):
        messages.error(request, "Access restricted to Donor accounts.")
        return redirect('core:home')

    update_all_priorities_and_expiries()

    status_filter = request.GET.get('status', 'all')
    listings_qs = FoodListing.objects.filter(donor=request.user).select_related('category').prefetch_related('claims')

    if status_filter != 'all':
        listings_qs = listings_qs.filter(status=status_filter.upper())

    listings_qs = listings_qs.order_by('-created_at')

    context = {
        'title': 'My Food Listings',
        'listings': listings_qs,
        'current_status': status_filter,
    }
    return render(request, 'listings/my_listings.html', context)


@login_required
def edit_listing(request, listing_id):
    listing = get_object_or_404(FoodListing, listing_id=listing_id, donor=request.user)

    # Donor can only edit listings that have not yet been claimed
    if not listing.can_be_edited:
        messages.error(request, f"Listing cannot be edited because it is in '{listing.get_status_display()}' status.")
        return redirect('listings:my_listings')

    if request.method == 'POST':
        form = FoodListingForm(request.POST, instance=listing)
        if form.is_valid():
            with transaction.atomic():
                saved_listing = form.save()
                settings = SystemSetting.get_settings()
                saved_listing.recalculate_priority_and_status(
                    urgent_thresh=settings.urgent_threshold_minutes,
                    high_thresh=settings.high_threshold_minutes,
                    save=True,
                    user=request.user
                )
                StatusHistory.objects.create(
                    listing=saved_listing,
                    changed_by=request.user,
                    status=saved_listing.status,
                    remarks="Listing details updated by donor."
                )
            messages.success(request, "Food listing updated successfully.")
            return redirect('listings:my_listings')
    else:
        form = FoodListingForm(instance=listing)

    return render(request, 'listings/edit_listing.html', {'form': form, 'listing': listing, 'title': 'Edit Food Listing'})


@login_required
def cancel_listing(request, listing_id):
    listing = get_object_or_404(FoodListing, listing_id=listing_id, donor=request.user)

    # Donor can only cancel listings that have not been claimed
    if not listing.can_be_cancelled:
        messages.error(request, f"Cannot cancel listing in '{listing.get_status_display()}' status.")
        return redirect('listings:my_listings')

    if request.method == 'POST':
        with transaction.atomic():
            listing.status = FoodListing.STATUS_CANCELLED
            listing.save(update_fields=['status'])
            StatusHistory.objects.create(
                listing=listing,
                changed_by=request.user,
                status=FoodListing.STATUS_CANCELLED,
                remarks=request.POST.get('reason', 'Cancelled by donor.')
            )
        messages.success(request, "Listing has been successfully cancelled.")
        return redirect('listings:my_listings')

    return render(request, 'listings/cancel_listing_confirm.html', {'listing': listing, 'title': 'Confirm Cancellation'})


@login_required
def donation_history(request):
    if not (request.user.is_donor or request.user.is_admin_user):
        messages.error(request, "Access restricted to Donor accounts.")
        return redirect('core:home')

    listings = FoodListing.objects.filter(donor=request.user).select_related('category').prefetch_related('claims__institution__user').order_by('-created_at')

    total_donations = listings.count()
    completed_deliveries = listings.filter(status=FoodListing.STATUS_DELIVERED).count()
    total_meals = Claim.objects.filter(
        listing__donor=request.user,
        listing__status=FoodListing.STATUS_DELIVERED
    ).aggregate(m=Sum('meals_delivered'))['m'] or 0

    context = {
        'title': 'Donation History & Impact',
        'listings': listings,
        'total_donations': total_donations,
        'completed_deliveries': completed_deliveries,
        'total_meals': total_meals,
    }
    return render(request, 'listings/donation_history.html', context)


@login_required
def listing_detail(request, listing_id):
    update_all_priorities_and_expiries()
    listing = get_object_or_404(FoodListing.objects.select_related('donor', 'category'), listing_id=listing_id)

    # If listing is claimed or completed, sensitive pickup details
    # are visible to the donor, claimant, and admin.
    is_claimant = False
    active_claim = listing.claims.filter(is_active=True).first()
    if request.user.is_authenticated and active_claim and active_claim.claimer == request.user:
        is_claimant = True

    history_records = listing.status_history.select_related('changed_by').order_by('changed_at')
    suggested_institutions = suggest_nearest_institutions(listing, limit=4)

    context = {
        'title': f"Listing #{listing.listing_id} - {listing.food_type}",
        'listing': listing,
        'active_claim': active_claim,
        'is_claimant': is_claimant,
        'history_records': history_records,
        'suggested_institutions': suggested_institutions,
    }
    return render(request, 'listings/listing_detail.html', context)
