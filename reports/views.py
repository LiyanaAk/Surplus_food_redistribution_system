from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime, timedelta
import csv
from listings.models import FoodListing, FoodCategory, StatusHistory
from claims.models import Claim
from accounts.models import User
from institutions.models import Institution

@login_required
def reports_dashboard(request):
    """
    Generate reports on food listed, collected, distributed,
    and expired over a selected period.
    """
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to Administrators.")
        return redirect('core:home')

    # Date filtering
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    now = timezone.now()
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = (now - timedelta(days=30)).date()
    else:
        start_date = (now - timedelta(days=30)).date()

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = now.date()
    else:
        end_date = now.date()

    # Query listings within date range
    listings = FoodListing.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )

    total_listed = listings.count()
    total_available = listings.filter(status=FoodListing.STATUS_AVAILABLE).count()
    total_claimed = listings.filter(status=FoodListing.STATUS_CLAIMED).count()
    total_collected = listings.filter(status__in=[FoodListing.STATUS_COLLECTED, FoodListing.STATUS_IN_TRANSIT, FoodListing.STATUS_DELIVERED]).count()
    total_delivered = listings.filter(status=FoodListing.STATUS_DELIVERED).count()
    total_expired = listings.filter(status=FoodListing.STATUS_EXPIRED).count()

    total_quantity_listed = listings.aggregate(q=Sum('quantity'))['q'] or 0
    total_quantity_delivered = listings.filter(status=FoodListing.STATUS_DELIVERED).aggregate(q=Sum('quantity'))['q'] or 0

    total_meals_delivered = Claim.objects.filter(
        listing__status=FoodListing.STATUS_DELIVERED,
        listing__created_at__date__gte=start_date,
        listing__created_at__date__lte=end_date
    ).aggregate(m=Sum('meals_delivered'))['m'] or 0

    # Category breakdown
    category_data = FoodCategory.objects.annotate(
        cat_count=Count('listings', filter=Q(listings__created_at__date__gte=start_date, listings__created_at__date__lte=end_date)),
        delivered_count=Count('listings', filter=Q(listings__status=FoodListing.STATUS_DELIVERED, listings__created_at__date__gte=start_date, listings__created_at__date__lte=end_date))
    ).filter(cat_count__gt=0).order_by('-cat_count')

    # Donor Leaderboard
    top_donors = User.objects.filter(
        role=User.ROLE_DONOR,
        food_listings__created_at__date__gte=start_date,
        food_listings__created_at__date__lte=end_date
    ).annotate(
        donation_count=Count('food_listings'),
        delivered_count=Count('food_listings', filter=Q(food_listings__status=FoodListing.STATUS_DELIVERED))
    ).order_by('-donation_count')[:5]

    # Volunteer Leaderboard
    top_volunteers = User.objects.filter(
        role=User.ROLE_NGO,
        claims__claimed_at__date__gte=start_date,
        claims__claimed_at__date__lte=end_date
    ).annotate(
        claims_count=Count('claims'),
        delivered_count=Count('claims', filter=Q(claims__listing__status=FoodListing.STATUS_DELIVERED)),
        total_meals=Sum('claims__meals_delivered')
    ).order_by('-delivered_count')[:5]

    context = {
        'title': 'System Reports & Redistribution Analytics',
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'total_listed': total_listed,
        'total_available': total_available,
        'total_claimed': total_claimed,
        'total_collected': total_collected,
        'total_delivered': total_delivered,
        'total_expired': total_expired,
        'total_quantity_listed': total_quantity_listed,
        'total_quantity_delivered': total_quantity_delivered,
        'total_meals_delivered': total_meals_delivered,
        'category_data': category_data,
        'top_donors': top_donors,
        'top_volunteers': top_volunteers,
    }
    return render(request, 'reports/reports_dashboard.html', context)


@login_required
def export_report_csv(request):
    if not request.user.is_admin_user:
        return redirect('core:home')

    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    now = timezone.now()
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else (now - timedelta(days=30)).date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else now.date()
    except ValueError:
        start_date = (now - timedelta(days=30)).date()
        end_date = now.date()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="food_redistribution_report_{start_date}_to_{end_date}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Listing ID', 'Food Title', 'Category', 'Quantity', 'Unit', 'Donor',
        'Status', 'Priority', 'Prepared At', 'Usable Until', 'Claimer NGO',
        'Recipient Type/Name', 'Meals Delivered', 'Created At'
    ])

    listings = FoodListing.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).select_related('donor', 'category').prefetch_related('claims__institution__user', 'claims__claimer')

    for l in listings:
        active_claim = l.claims.filter(is_active=True).first() or l.claims.first()
        claimer_name = active_claim.claimer.name if active_claim else "N/A"
        recipient = "N/A"
        meals = ""
        if active_claim:
            if active_claim.institution:
                recipient = f"Institution: {active_claim.institution.user.name}"
            elif active_claim.recipient_note:
                recipient = f"Direct/Homeless: {active_claim.recipient_note[:40]}"
            meals = active_claim.meals_delivered or ""

        writer.writerow([
            l.listing_id,
            l.food_type,
            l.category.name,
            l.quantity,
            l.quantity_unit,
            l.donor.name,
            l.status,
            l.priority,
            l.prepared_at.strftime('%Y-%m-%d %H:%M'),
            l.usable_until.strftime('%Y-%m-%d %H:%M'),
            claimer_name,
            recipient,
            meals,
            l.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response
