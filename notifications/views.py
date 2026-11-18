from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Notification

@login_required
def notification_list(request):
    filter_type = request.GET.get('filter', 'all')
    notifications = Notification.objects.filter(user=request.user)

    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)

    notifications = notifications.order_by('-sent_at')

    context = {
        'title': 'My Notifications',
        'notifications': notifications,
        'filter_type': filter_type,
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
def mark_as_read(request, notification_id):
    notif = get_object_or_404(Notification, notification_id=notification_id, user=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})

    messages.info(request, "Notification marked as read.")
    return redirect('notifications:list')


@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('notifications:list')


@login_required
def unread_count_api(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'unread_count': count})
