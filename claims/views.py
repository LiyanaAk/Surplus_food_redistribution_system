from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from listings.models import FoodListing, FoodCategory, StatusHistory
from institutions.models import Institution
from accounts.models import User
from .models import Claim
from .forms import ClaimListingForm, DeliveryStatusUpdateForm
from notifications.models import Notification
from core.utils import update_all_priorities_and_expiries, haversine_distance, suggest_nearest_institutions
from core.models import SystemSetting

@login_required
def ngo_dashboard(request):
    if not (request.user.is_ngo or request.user.is_admin_user):
        messages.error(request, "Access restricted to NGO / Volunteer accounts.")
        return redirect('core:home')

    update_all_priorities_and_expiries()

    # Verification warning if pending
    is_approved = request.user.is_approved
    
    available_count = FoodListing.objects.filter(status=FoodListing.STATUS_AVAILABLE).count()
    my_claims_qs = Claim.objects.filter(claimer=request.user, is_active=True).select_related('listing', 'institution')

    pending_collection_count = my_claims_qs.filter(listing__status=FoodListing.STATUS_CLAIMED).count()
    in_transit_count = my_claims_qs.filter(listing__status=FoodListing.STATUS_IN_TRANSIT).count()
    collected_count = my_claims_qs.filter(listing__status=FoodListing.STATUS_COLLECTED).count()

    completed_claims = Claim.objects.filter(claimer=request.user, listing__status=FoodListing.STATUS_DELIVERED)
    completed_count = completed_claims.count()
    total_meals_delivered = completed_claims.aggregate(m=Sum('meals_delivered'))['m'] or 0

    recent_claims = Claim.objects.filter(claimer=request.user).select_related('listing', 'institution__user').order_by('-claimed_at')[:5]

    context = {
        'title': 'NGO / Volunteer Dashboard',
        'is_approved': is_approved,
        'available_count': available_count,
        'pending_collection_count': pending_collection_count,
        'collected_count': collected_count,
        'in_transit_count': in_transit_count,
        'completed_count': completed_count,
        'total_meals_delivered': total_meals_delivered,
        'recent_claims': recent_claims,
    }
    return render(request, 'claims/ngo_dashboard.html', context)


@login_required
def available_listings(request):
    if not (request.user.is_ngo or request.user.is_admin_user):
        messages.error(request, "Access restricted to NGO / Volunteer accounts.")
        return redirect('core:home')

    update_all_priorities_and_expiries()

    settings = SystemSetting.get_settings()
    default_radius = settings.default_search_radius_km

    # Query params
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    priority_filter = request.GET.get('priority', '')
    min_qty = request.GET.get('min_qty', '')
    radius_km = request.GET.get('radius', '')
    use_location = request.GET.get('use_location', '')

    try:
        radius_km = float(radius_km) if radius_km else default_radius
    except ValueError:
        radius_km = default_radius

    listings_qs = FoodListing.objects.filter(
        status=FoodListing.STATUS_AVAILABLE
    ).select_related('donor', 'category')

    if search_query:
        listings_qs = listings_qs.filter(
            Q(food_type__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(pickup_address__icontains=search_query)
        )

    if category_id:
        listings_qs = listings_qs.filter(category_id=category_id)

    if priority_filter:
        listings_qs = listings_qs.filter(priority=priority_filter)

    if min_qty:
        try:
            listings_qs = listings_qs.filter(quantity__gte=float(min_qty))
        except ValueError:
            pass

    # Sort primarily by usable_until (nearest expiry first per Section 5)
    listings_qs = listings_qs.order_by('usable_until', '-priority')

    # Location filtering using Haversine formula
    volunteer_lat = request.user.latitude
    volunteer_lng = request.user.longitude
    filtered_listings = []

    for item in listings_qs:
        dist = None
        if volunteer_lat and volunteer_lng and item.latitude and item.longitude:
            dist = haversine_distance(volunteer_lat, volunteer_lng, item.latitude, item.longitude)
        
        item.distance_from_volunteer = dist

        # Apply radius filter if volunteer has location
        if dist is not None and use_location == '1' and dist > radius_km:
            continue

        filtered_listings.append(item)

    categories = FoodCategory.objects.all()

    context = {
        'title': 'Available Surplus Food Listings',
        'listings': filtered_listings,
        'categories': categories,
        'search_query': search_query,
        'category_id': category_id,
        'priority_filter': priority_filter,
        'min_qty': min_qty,
        'radius_km': radius_km,
        'use_location': use_location,
        'volunteer_has_coords': bool(volunteer_lat and volunteer_lng),
    }
    return render(request, 'claims/available_listings.html', context)


@login_required
def claim_listing(request, listing_id):
    if not (request.user.is_ngo or request.user.is_admin_user):
        messages.error(request, "Only registered NGO / volunteers can claim food.")
        return redirect('core:home')

    # Account must be approved by the administrator before claiming food
    if not request.user.is_approved:
        messages.error(
            request,
            "Your NGO account is pending administrative approval. You cannot claim food until your verification is approved."
        )
        return redirect('claims:ngo_dashboard')

    if request.method == 'POST':
        # Concurrency safety: atomic transaction with row-level lock
        with transaction.atomic():
            try:
                listing = FoodListing.objects.select_for_update().get(listing_id=listing_id)
            except FoodListing.DoesNotExist:
                messages.error(request, "Food listing not found.")
                return redirect('claims:available_listings')

            # Only AVAILABLE listings can be claimed
            if listing.status != FoodListing.STATUS_AVAILABLE:
                messages.warning(
                    request,
                    f"Sorry! This listing is no longer available (Current Status: {listing.get_status_display()})."
                )
                return redirect('claims:available_listings')

            # Check if usable time has expired
            now = timezone.now()
            if listing.usable_until <= now:
                listing.status = FoodListing.STATUS_EXPIRED
                listing.save(update_fields=['status'])
                StatusHistory.objects.create(
                    listing=listing,
                    status=FoodListing.STATUS_EXPIRED,
                    remarks="Listing expired before claim could be executed."
                )
                messages.error(request, "This listing has expired and can no longer be claimed.")
                return redirect('claims:available_listings')

            # Update listing status to CLAIMED
            listing.status = FoodListing.STATUS_CLAIMED
            listing.save(update_fields=['status'])

            institution_id = request.POST.get('institution')
            inst_obj = None
            if institution_id:
                inst_obj = Institution.objects.filter(
                    institution_id=institution_id,
                    user__verification_status=User.STATUS_APPROVED
                ).first()

            note = request.POST.get('recipient_note', '').strip()

            claim = Claim.objects.create(
                listing=listing,
                claimer=request.user,
                institution=inst_obj,
                recipient_note=note,
                is_active=True
            )

            # Record Status History
            StatusHistory.objects.create(
                listing=listing,
                changed_by=request.user,
                status=FoodListing.STATUS_CLAIMED,
                remarks=f"Food reserved and claimed by {request.user.name}."
            )

            # Notify Donor
            Notification.objects.create(
                user=listing.donor,
                listing=listing,
                channel=Notification.CHANNEL_IN_APP,
                message=f"Good news! Your food listing '{listing.food_type}' has been claimed by {request.user.name}. Pickup coordination initiated."
            )

        messages.success(
            request,
            f"Listing #{listing.listing_id} claimed successfully! Please coordinate pickup at {listing.pickup_address}."
        )
        return redirect('claims:my_claims')

    # GET request: Show confirmation and suggested institutions
    listing = get_object_or_404(FoodListing.objects.select_related('donor', 'category'), listing_id=listing_id)
    if listing.status != FoodListing.STATUS_AVAILABLE:
        messages.error(request, "This listing is not available for claiming.")
        return redirect('claims:available_listings')

    suggested_institutions = suggest_nearest_institutions(listing)
    all_approved_institutions = Institution.objects.filter(
        user__verification_status=User.STATUS_APPROVED,
        user__is_active=True
    ).select_related('user')

    context = {
        'title': f"Claim Food: {listing.food_type}",
        'listing': listing,
        'suggested_institutions': suggested_institutions,
        'all_institutions': all_approved_institutions,
    }
    return render(request, 'claims/claim_confirm.html', context)


@login_required
def release_claim(request, claim_id):
    """
    Allow a claimant to release a claim before collection,
    returning the listing to AVAILABLE status.
    """
    claim = get_object_or_404(Claim.objects.select_related('listing'), claim_id=claim_id, claimer=request.user)

    if not claim.is_active:
        messages.info(request, "This claim is already inactive or released.")
        return redirect('claims:my_claims')

    # A claim can only be released before collection (i.e. status == CLAIMED)
    if claim.listing.status != FoodListing.STATUS_CLAIMED:
        messages.error(request, f"Cannot release claim after food has reached '{claim.listing.get_status_display()}' status.")
        return redirect('claims:my_claims')

    if request.method == 'POST':
        with transaction.atomic():
            listing = claim.listing
            listing.status = FoodListing.STATUS_AVAILABLE
            listing.save(update_fields=['status'])

            claim.is_active = False
            claim.released_at = timezone.now()
            release_reason = request.POST.get('reason', 'Released by volunteer before collection.')
            claim.recipient_note = (claim.recipient_note or '') + f" [Released: {release_reason}]"
            claim.save(update_fields=['is_active', 'released_at', 'recipient_note'])

            # Record Status History
            StatusHistory.objects.create(
                listing=listing,
                changed_by=request.user,
                status=FoodListing.STATUS_AVAILABLE,
                remarks=f"Claim released by {request.user.name}. Reason: {release_reason}"
            )

            # Notify Donor
            Notification.objects.create(
                user=listing.donor,
                listing=listing,
                channel=Notification.CHANNEL_IN_APP,
                message=f"The claim on '{listing.food_type}' was released and returned to Available status for other volunteers."
            )

        messages.info(request, f"Claim on #{listing.listing_id} has been released. The listing is now available again.")
        return redirect('claims:my_claims')

    return render(request, 'claims/release_claim_confirm.html', {'claim': claim, 'title': 'Confirm Claim Release'})


@login_required
def manage_delivery(request, claim_id):
    """
    Volunteer updates delivery status:
    1. COLLECTED
    2. IN_TRANSIT
    3. DELIVERED
    At delivery, volunteer selects registered beneficiary institution or logs manual details for homeless individuals.
    """
    claim = get_object_or_404(
        Claim.objects.select_related('listing', 'institution__user', 'listing__donor'),
        claim_id=claim_id,
        claimer=request.user
    )

    if not claim.is_active:
        messages.error(request, "This claim has already been concluded or released.")
        return redirect('claims:my_claims')

    listing = claim.listing

    if request.method == 'POST':
        form = DeliveryStatusUpdateForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            rtype = form.cleaned_data['recipient_type']
            institution = form.cleaned_data['institution']
            recipient_note = form.cleaned_data['recipient_note']
            meals_delivered = form.cleaned_data['meals_delivered']
            remarks = form.cleaned_data['remarks']

            # Validate valid unidirectional status transition
            valid = False
            if listing.status == FoodListing.STATUS_CLAIMED and new_status == FoodListing.STATUS_COLLECTED:
                valid = True
            elif listing.status == FoodListing.STATUS_COLLECTED and new_status == FoodListing.STATUS_IN_TRANSIT:
                valid = True
            elif listing.status in [FoodListing.STATUS_COLLECTED, FoodListing.STATUS_IN_TRANSIT] and new_status == FoodListing.STATUS_DELIVERED:
                valid = True

            if not valid:
                messages.error(
                    request,
                    f"Invalid status transition from '{listing.get_status_display()}' to '{new_status}'."
                )
                return redirect('claims:manage_delivery', claim_id=claim.claim_id)

            with transaction.atomic():
                listing.status = new_status
                listing.save(update_fields=['status'])

                if new_status == FoodListing.STATUS_DELIVERED:
                    if rtype == 'institution' and institution:
                        claim.institution = institution
                    else:
                        claim.institution = None

                    claim.recipient_note = recipient_note
                    claim.meals_delivered = meals_delivered
                    claim.save(update_fields=['institution', 'recipient_note', 'meals_delivered'])

                    # Notify donor
                    Notification.objects.create(
                        user=listing.donor,
                        listing=listing,
                        channel=Notification.CHANNEL_IN_APP,
                        message=f"Food successfully delivered! '{listing.food_type}' served {meals_delivered} meals to beneficiaries."
                    )

                    # Notify institution if applicable
                    if claim.institution:
                        Notification.objects.create(
                            user=claim.institution.user,
                            listing=listing,
                            channel=Notification.CHANNEL_IN_APP,
                            message=f"Food delivery received! '{listing.food_type}' ({meals_delivered} meals) delivered by {request.user.name}."
                        )
                else:
                    # For COLLECTED or IN_TRANSIT
                    # Notify donor of milestone
                    Notification.objects.create(
                        user=listing.donor,
                        listing=listing,
                        channel=Notification.CHANNEL_IN_APP,
                        message=f"Update for '{listing.food_type}': Status changed to {listing.get_status_display()}."
                    )

                # Record Status History
                status_remarks = remarks or f"Status updated to {listing.get_status_display()} by {request.user.name}."
                if new_status == FoodListing.STATUS_DELIVERED and claim.institution:
                    status_remarks += f" Handed over to {claim.institution.user.name}."
                elif new_status == FoodListing.STATUS_DELIVERED:
                    status_remarks += f" Distributed directly: {recipient_note}"

                StatusHistory.objects.create(
                    listing=listing,
                    changed_by=request.user,
                    status=new_status,
                    remarks=status_remarks
                )

            messages.success(request, f"Status updated to '{listing.get_status_display()}' successfully!")
            if new_status == FoodListing.STATUS_DELIVERED:
                return redirect('claims:delivery_history')
            return redirect('claims:manage_delivery', claim_id=claim.claim_id)
    else:
        # Initial form state based on current listing status
        next_status = FoodListing.STATUS_COLLECTED
        if listing.status == FoodListing.STATUS_COLLECTED:
            next_status = FoodListing.STATUS_IN_TRANSIT
        elif listing.status == FoodListing.STATUS_IN_TRANSIT:
            next_status = FoodListing.STATUS_DELIVERED

        initial_data = {
            'status': next_status,
            'institution': claim.institution,
            'recipient_note': claim.recipient_note,
            'meals_delivered': claim.meals_delivered,
            'recipient_type': 'institution' if claim.institution else 'homeless',
        }
        form = DeliveryStatusUpdateForm(initial=initial_data)

    suggested_institutions = suggest_nearest_institutions(listing)
    history_records = listing.status_history.order_by('changed_at')

    context = {
        'title': f"Delivery Tracking: Listing #{listing.listing_id}",
        'claim': claim,
        'listing': listing,
        'form': form,
        'suggested_institutions': suggested_institutions,
        'history_records': history_records,
    }
    return render(request, 'claims/manage_delivery.html', context)


@login_required
def my_claims(request):
    if not (request.user.is_ngo or request.user.is_admin_user):
        messages.error(request, "Access restricted to NGO / Volunteer accounts.")
        return redirect('core:home')

    update_all_priorities_and_expiries()

    active_claims = Claim.objects.filter(
        claimer=request.user,
        is_active=True,
        listing__status__in=[
            FoodListing.STATUS_CLAIMED,
            FoodListing.STATUS_COLLECTED,
            FoodListing.STATUS_IN_TRANSIT
        ]
    ).select_related('listing', 'institution__user', 'listing__donor').order_by('-claimed_at')

    context = {
        'title': 'My Active Claims & Deliveries',
        'active_claims': active_claims,
    }
    return render(request, 'claims/my_claims.html', context)


@login_required
def delivery_history(request):
    if not (request.user.is_ngo or request.user.is_admin_user):
        messages.error(request, "Access restricted to NGO / Volunteer accounts.")
        return redirect('core:home')

    completed_claims = Claim.objects.filter(
        claimer=request.user,
        listing__status=FoodListing.STATUS_DELIVERED
    ).select_related('listing', 'institution__user', 'listing__donor').order_by('-claimed_at')

    total_deliveries = completed_claims.count()
    total_meals = completed_claims.aggregate(m=Sum('meals_delivered'))['m'] or 0

    context = {
        'title': 'Delivery History & Impact Record',
        'completed_claims': completed_claims,
        'total_deliveries': total_deliveries,
        'total_meals': total_meals,
    }
    return render(request, 'claims/delivery_history.html', context)
