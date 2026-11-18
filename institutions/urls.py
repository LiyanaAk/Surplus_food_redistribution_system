from django.urls import path
from . import views

app_name = 'institutions'

urlpatterns = [
    path('dashboard/', views.institution_dashboard, name='institution_dashboard'),
    path('received-history/', views.received_food_history, name='received_food_history'),
]
