from celery import Celery
from celery.schedules import crontab
from bot.config import settings

celery_app = Celery(
    'hh_jobs_bot',
    broker=f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0',
    backend=f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0',
    include=['tasks.vacancy_checker']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    'check-new-vacancies': {
        'task': 'tasks.vacancy_checker.check_new_vacancies',
        'schedule': crontab(minute='*/15'),
    },
}
