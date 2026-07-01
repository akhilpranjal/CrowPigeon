"""Lightweight Redis-backed job queue.

How it works:
    1. Register handlers with @register_job('job_name').
    2. Enqueue work with enqueue_job('job_name', payload).
    3. The redis_queue_worker management command polls the queue,
       deserialises each job, and calls the matching handler.
"""

import json
import logging
import os
from dataclasses import dataclass

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
if REDIS_URL.startswith('rediss://') and 'ssl_cert_reqs' not in REDIS_URL:
    separator = '&' if '?' in REDIS_URL else '?'
    REDIS_URL = f"{REDIS_URL}{separator}ssl_cert_reqs=none"
REDIS_QUEUE_NAME = os.getenv('REDIS_QUEUE_NAME', 'crowpigeon:jobs')

# Maps job names → handler functions (populated by @register_job).
JOB_HANDLERS = {}


@dataclass(frozen=True)
class RedisJob:
    """Immutable representation of a queued job."""
    name: str
    payload: dict


def get_redis_connection():
    """Return a Redis client connected to REDIS_URL."""
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def register_job(name):
    """Decorator that registers a function as a handler for the given job name."""
    def decorator(func):
        JOB_HANDLERS[name] = func
        return func
    return decorator


def enqueue_job(name, payload=None):
    """Push a job onto the Redis queue for later processing."""
    job = RedisJob(name=name, payload=payload or {})
    get_redis_connection().rpush(REDIS_QUEUE_NAME, json.dumps(job.__dict__))


def read_job(block_timeout=5):
    """Pop the next job from the queue, blocking up to *block_timeout* seconds.

    Returns a RedisJob or None if the queue is empty after the timeout.
    """
    result = get_redis_connection().blpop(REDIS_QUEUE_NAME, timeout=block_timeout)
    if result is None:
        return None

    _, raw_job = result
    data = json.loads(raw_job)
    return RedisJob(name=data['name'], payload=data.get('payload') or {})


def execute_job(job):
    """Look up and call the registered handler for *job*."""
    handler = JOB_HANDLERS.get(job.name)
    if handler is None:
        raise KeyError(f'No Redis job handler registered for {job.name!r}')
    return handler(**job.payload)
