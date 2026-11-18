from core.models import SystemSetting
from notifications.models import Notification

def global_context(request):
    """
    Context processor to supply global variables to all templates:
    - unread_notifications_count for logged-in users
    - system_settings for priority thresholds & radius
    """
    context = {
        'site_name': 'Surplus Food Redistribution System',
    }
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        context['unread_notifications_count'] = unread_count
        context['recent_notifications'] = Notification.objects.filter(user=request.user).order_by('-sent_at')[:5]
    else:
        context['unread_notifications_count'] = 0
        context['recent_notifications'] = []

    try:
        context['system_settings'] = SystemSetting.get_settings()
    except Exception:
        context['system_settings'] = None

    return context
