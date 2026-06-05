import logging
import time

from django.core.management.base import BaseCommand

from chat.redis_queue import execute_job, read_job

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process jobs from the Redis queue.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process a single job and exit.')

    def handle(self, *args, **options):
        self.stdout.write('Redis queue worker started')
        while True:
            job = read_job()
            if job is None:
                if options['once']:
                    return
                time.sleep(1)
                continue

            try:
                execute_job(job)
                self.stdout.write(self.style.SUCCESS(f'Processed job: {job.name}'))
            except Exception as exc:
                logger.exception('Failed to process Redis job %s', job.name)
                self.stderr.write(self.style.ERROR(f'Failed job {job.name}: {exc}'))

            if options['once']:
                return
