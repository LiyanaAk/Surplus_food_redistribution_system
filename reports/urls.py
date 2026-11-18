from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_dashboard, name='reports_dashboard'),
    path('export/csv/', views.export_report_csv, name='export_report_csv'),
]
