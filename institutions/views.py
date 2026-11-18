from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from .models import Institution
from claims.models import Claim
from listings.models import FoodListing

@login_required
def institution_dashboard(request):
    if not (request.user.is_institution or request.user.is_admin_user):
        messages.error(request, "Access restricted to Beneficiary Institution accounts.")
        return redirect('core:home')

    institution = getattr(request.user, 'institution_profile', None)
    if not institution:
        # Create default profile if missing
        institution = Institution.objects.create(user=request.user, institution_type='shelter_home', capacity=50)

    received_claims = Claim.objects.filter(
        institution=institution,
        listing__status=FoodListing.STATUS_DELIVERED
    ).select_related('listing', 'claimer', 'listing__donor')

    total_deliveries = received_claims.count()
    total_meals = received_claims.aggregate(m=Sum('meals_delivered'))['m'] or 0

    recent_deliveries = received_claims.order_by('-claimed_at')[:6]

    context = {
        'title': 'Beneficiary Institution Dashboard',
        'institution': institution,
        'is_approved': request.user.is_approved,
        'total_deliveries': total_deliveries,
        'total_meals': total_meals,
        'recent_deliveries': recent_deliveries,
    }
    return render(request, 'institutions/institution_dashboard.html', context)


@login_required
def received_food_history(request):
    if not (request.user.is_institution or request.user.is_admin_user):
        messages.error(request, "Access restricted to Beneficiary Institution accounts.")
        return redirect('core:home')

    institution = getattr(request.user, 'institution_profile', None)
    if not institution:
        return redirect('institutions:institution_dashboard')

    deliveries = Claim.objects.filter(
        institution=institution,
        listing__status=FoodListing.STATUS_DELIVERED
    ).select_related('listing', 'claimer', 'listing__donor').order_by('-claimed_at')

    total_meals = deliveries.aggregate(m=Sum('meals_delivered'))['m'] or 0

    context = {
        'title': 'Received Food History',
        'institution': institution,
        'deliveries': deliveries,
        'total_meals': total_meals,
    }
    return render(request, 'institutions/received_food_history.html', context)
