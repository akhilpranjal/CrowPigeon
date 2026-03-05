from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Max
from .models import Message, Room

@shared_task
def delete_old_messages():
    cutoff = timezone.now()-timedelta(days=7)
    Message.objects.filter(timestamp__lt=cutoff).delete()

@shared_task
def delete_inactive_rooms():
    cutoff = timezone.now()-timedelta(hours=48)
    Room.objects.annotate(last_message_at=Max('message__timestamp')).filter(Q(last_message_at__lt=cutoff) | Q(last_message_at__isnull=True)).delete()

