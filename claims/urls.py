from django.urls import path
from . import views

app_name = 'claims'

urlpatterns = [
    path('dashboard/', views.ngo_dashboard, name='ngo_dashboard'),
    path('available/', views.available_listings, name='available_listings'),
    path('claim/<int:listing_id>/', views.claim_listing, name='claim_listing'),
    path('release/<int:claim_id>/', views.release_claim, name='release_claim'),
    path('manage/<int:claim_id>/', views.manage_delivery, name='manage_delivery'),
    path('my-claims/', views.my_claims, name='my_claims'),
    path('history/', views.delivery_history, name='delivery_history'),
]
