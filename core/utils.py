import math
from django.utils import timezone
from listings.models import FoodListing, StatusHistory
from core.models import SystemSetting
from notifications.models import Notification

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on the earth (in km).
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (ValueError, TypeError):
        return None

    R = 6371.0 # Earth's radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def update_all_priorities_and_expiries(user=None):
    """
    Background priority & expiry calculation engine.
    1. Fetches listings with AVAILABLE or CLAIMED status.
    2. Recalculates remaining usable time vs now.
    3. If time expired (<= 0), transitions to EXPIRED, writes StatusHistory, and notifies donor/claimant.
    4. Otherwise assigns NORMAL, HIGH, or URGENT based on SystemSetting thresholds.
    5. If a listing newly transitions to URGENT, notifies nearby approved NGOs.
    """
    settings = SystemSetting.get_settings()
    urgent_thresh = settings.urgent_threshold_minutes
    high_thresh = settings.high_threshold_minutes

    active_listings = FoodListing.objects.filter(
        status__in=[FoodListing.STATUS_AVAILABLE, FoodListing.STATUS_CLAIMED]
    )

    expired_count = 0
    priority_changed_count = 0

    for listing in active_listings:
        old_status = listing.status
        old_priority = listing.priority

        status_changed, priority_changed = listing.recalculate_priority_and_status(
            urgent_thresh=urgent_thresh,
            high_thresh=high_thresh,
            save=True,
            user=user
        )

        if status_changed and listing.status == FoodListing.STATUS_EXPIRED:
            expired_count += 1
            # Notify donor
            Notification.objects.create(
                user=listing.donor,
                listing=listing,
                channel=Notification.CHANNEL_IN_APP,
                message=f"Your food listing '{listing.food_type}' has expired because the safe usable period elapsed."
            )
            # If it was claimed, notify the claimer as well
            active_claim = listing.claims.filter(is_active=True).first()
            if active_claim:
                active_claim.is_active = False
                active_claim.released_at = timezone.now()
                active_claim.recipient_note = (active_claim.recipient_note or '') + " [Expired before collection]"
                active_claim.save(update_fields=['is_active', 'released_at', 'recipient_note'])

                Notification.objects.create(
                    user=active_claim.claimer,
                    listing=listing,
                    channel=Notification.CHANNEL_IN_APP,
                    message=f"Claim on '{listing.food_type}' was automatically cancelled because the food reached expiry."
                )

        if priority_changed:
            priority_changed_count += 1
            # If newly urgent, alert nearby NGOs
            if listing.priority == FoodListing.PRIORITY_URGENT and old_priority != FoodListing.PRIORITY_URGENT:
                notify_nearby_ngos(listing, is_urgent=True)

    return expired_count, priority_changed_count


def notify_nearby_ngos(listing, is_urgent=False):
    """
    Notifies approved NGOs within the configured search radius.
    """
    from accounts.models import User
    from core.models import SystemSetting

    settings = SystemSetting.get_settings()
    radius_km = settings.default_search_radius_km

    approved_ngos = User.objects.filter(
        role=User.ROLE_NGO,
        verification_status=User.STATUS_APPROVED,
        is_active=True
    )

    for ngo in approved_ngos:
        # Check distance if coordinates exist
        if listing.latitude and listing.longitude and ngo.latitude and ngo.longitude:
            dist = haversine_distance(listing.latitude, listing.longitude, ngo.latitude, ngo.longitude)
            if dist is not None and dist > radius_km:
                continue

        urgency_prefix = "URGENT ALERT: " if is_urgent else "New Donation Available: "
        message = (
            f"{urgency_prefix}'{listing.food_type}' ({listing.quantity} {listing.quantity_unit}) "
            f"available for pickup at {listing.pickup_address}. Remaining: {listing.remaining_time_display}."
        )

        Notification.objects.create(
            user=ngo,
            listing=listing,
            channel=Notification.CHANNEL_IN_APP,
            message=message
        )


def suggest_nearest_institutions(listing, limit=5):
    """
    Suggests the nearest registered, approved beneficiary institutions for a given food listing.
    """
    from institutions.models import Institution
    from accounts.models import User

    approved_institutions = Institution.objects.filter(
        user__verification_status=User.STATUS_APPROVED,
        user__is_active=True
    ).select_related('user')

    results = []
    for inst in approved_institutions:
        dist = None
        if listing.latitude and listing.longitude and inst.user.latitude and inst.user.longitude:
            dist = haversine_distance(listing.latitude, listing.longitude, inst.user.latitude, inst.user.longitude)

        results.append({
            'institution': inst,
            'distance_km': dist if dist is not None else 999999.0,
            'has_distance': dist is not None,
        })

    # Sort by distance (if known), then capacity descending
    results.sort(key=lambda x: (0 if x['has_distance'] else 1, x['distance_km'], -x['institution'].capacity))
    return [item['institution'] for item in results[:limit]]
