from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Public Pages
    path('', views.home_view, name='home'),
    path('about/', views.about_view, name='about'),
    path('how-it-works/', views.how_it_works_view, name='how_it_works'),
    path('contact/', views.contact_view, name='contact'),
    path('dashboard/', views.dashboard_router, name='dashboard_router'),

    # Admin Module Pages
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/users/', views.admin_user_management, name='admin_users'),
    path('admin-panel/users/<int:user_id>/toggle/', views.admin_toggle_user_active, name='admin_toggle_user'),
    path('admin-panel/verify/<int:user_id>/<str:action>/', views.admin_verify_user_action, name='admin_verify_user'),
    path('admin-panel/ngos/', views.admin_ngo_verification, name='admin_ngos'),
    path('admin-panel/institutions/', views.admin_institution_verification, name='admin_institutions'),
    path('admin-panel/listings/', views.admin_listings_management, name='admin_listings'),
    path('admin-panel/categories/', views.admin_categories_management, name='admin_categories'),
    path('admin-panel/categories/<int:category_id>/delete/', views.admin_delete_category, name='admin_delete_category'),
    path('admin-panel/configuration/', views.admin_system_configuration, name='admin_configuration'),
]
