"""Background housekeeping tasks for automatic data cleanup.

These jobs are registered with the Redis queue and executed by the
`redis_queue_worker` management command.
"""

import logging
from datetime import timedelta

from django.db.models import Q, Max
from django.utils import timezone

from .models import Message, Room
from .redis_queue import enqueue_job, register_job

logger = logging.getLogger(__name__)


@register_job('delete_old_messages')
def delete_old_messages():
    """Delete chat messages older than 7 days."""
    cutoff = timezone.now() - timedelta(days=7)
    deleted_count, _ = Message.objects.filter(timestamp__lt=cutoff).delete()
    logger.info('Deleted %d old messages', deleted_count)
    return deleted_count


@register_job('delete_inactive_rooms')
def delete_inactive_rooms():
    """Delete rooms with no message activity in the last 48 hours."""
    cutoff = timezone.now() - timedelta(hours=48)
    deleted_count, _ = (
        Room.objects
        .annotate(last_message_at=Max('message__timestamp'))
        .filter(Q(last_message_at__lt=cutoff) | Q(last_message_at__isnull=True))
        .delete()
    )
    logger.info('Deleted %d inactive rooms', deleted_count)
    return deleted_count


def queue_housekeeping_jobs():
    """Enqueue all housekeeping jobs onto the Redis queue."""
    enqueue_job('delete_old_messages')
    enqueue_job('delete_inactive_rooms')
