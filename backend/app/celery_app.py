"""
Celery 应用配置
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lumicreate",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.image_tasks", "app.tasks.audio_tasks", "app.tasks.video_tasks"]
)

# Celery 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    worker_prefetch_multiplier=1,  # 每次只取一个任务
    task_acks_late=True,  # 任务完成后再确认
    task_reject_on_worker_lost=True,  # worker 丢失时重新入队
)

# 任务路由
celery_app.conf.task_routes = {
    "app.tasks.image_tasks.*": {"queue": "image_queue"},
    "app.tasks.audio_tasks.*": {"queue": "audio_queue"},
    "app.tasks.video_tasks.*": {"queue": "video_queue"},
}
