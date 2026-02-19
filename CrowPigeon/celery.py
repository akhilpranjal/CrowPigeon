import os
from celery import Celery

app = Celery('CrowPigeon')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()