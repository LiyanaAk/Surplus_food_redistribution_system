from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_select_view, name='register_select'),
    path('register/donor/', views.register_donor_view, name='register_donor'),
    path('register/ngo/', views.register_ngo_view, name='register_ngo'),
    path('register/institution/', views.register_institution_view, name='register_institution'),
    path('profile/', views.profile_view, name='profile'),
]
