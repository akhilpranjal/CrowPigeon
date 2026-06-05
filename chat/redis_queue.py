import json
import logging
import os
from dataclasses import dataclass

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
REDIS_QUEUE_NAME = os.getenv('REDIS_QUEUE_NAME', 'crowpigeon:jobs')

JOB_HANDLERS = {}


@dataclass(frozen=True)
class RedisJob:
    name: str
    payload: dict


def get_redis_connection():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def register_job(name):
    def decorator(func):
        JOB_HANDLERS[name] = func
        return func

    return decorator


def enqueue_job(name, payload=None):
    job = RedisJob(name=name, payload=payload or {})
    get_redis_connection().rpush(REDIS_QUEUE_NAME, json.dumps(job.__dict__))


def read_job(block_timeout=5):
    result = get_redis_connection().blpop(REDIS_QUEUE_NAME, timeout=block_timeout)
    if result is None:
        return None

    _, raw_job = result
    data = json.loads(raw_job)
    return RedisJob(name=data['name'], payload=data.get('payload') or {})


def execute_job(job):
    handler = JOB_HANDLERS.get(job.name)
    if handler is None:
        raise KeyError(f'No Redis job handler registered for {job.name!r}')

    return handler(**job.payload)
