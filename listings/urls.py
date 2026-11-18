from django.urls import path
from . import views

app_name = 'listings'

urlpatterns = [
    path('dashboard/', views.donor_dashboard, name='donor_dashboard'),
    path('create/', views.create_listing, name='create_listing'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('<int:listing_id>/', views.listing_detail, name='listing_detail'),
    path('<int:listing_id>/edit/', views.edit_listing, name='edit_listing'),
    path('<int:listing_id>/cancel/', views.cancel_listing, name='cancel_listing'),
    path('history/', views.donation_history, name='donation_history'),
]
