from django.core.management.base import BaseCommand

from chat.tasks import queue_housekeeping_jobs


class Command(BaseCommand):
    help = 'Enqueue housekeeping jobs on the Redis queue.'

    def handle(self, *args, **options):
        queue_housekeeping_jobs()
        self.stdout.write(self.style.SUCCESS('Housekeeping jobs enqueued'))