import logging

from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Max
from .models import Message, Room
from .redis_queue import enqueue_job, register_job

logger = logging.getLogger(__name__)

@register_job('delete_old_messages')
def delete_old_messages():
    cutoff = timezone.now()-timedelta(days=7)
    deleted_count, _ = Message.objects.filter(timestamp__lt=cutoff).delete()
    logger.info('Deleted %d old messages', deleted_count)
    return deleted_count

@register_job('delete_inactive_rooms')
def delete_inactive_rooms():
    cutoff = timezone.now()-timedelta(hours=48)
    deleted_count, _ = Room.objects.annotate(last_message_at=Max('message__timestamp')).filter(Q(last_message_at__lt=cutoff) | Q(last_message_at__isnull=True)).delete()
    logger.info('Deleted %d inactive rooms', deleted_count)
    return deleted_count


def queue_housekeeping_jobs():
    enqueue_job('delete_old_messages')
    enqueue_job('delete_inactive_rooms')

