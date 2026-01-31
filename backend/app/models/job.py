"""
任务数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, Integer, Enum as SQLEnum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.database import Base


class JobType(str, enum.Enum):
    """任务类型枚举"""
    DEEPSEEK = "deepseek"  # 文案生成
    SCRIPT_PARSE = "script_parse"  # 脚本解析/切分
    IMAGE_GEN = "image_gen"  # 图片生成
    TTS = "tts"  # 语音合成
    VIDEO_COMPOSE = "video_compose"  # 视频合成
    AI_FILL = "ai_fill"  # AI助填配置


class JobStatus(str, enum.Enum):
    """任务状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class Job(Base):
    """任务模型 - 追踪所有异步任务"""
    __tablename__ = "jobs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    segment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("segments.id"), 
        nullable=True  # 全局任务可为空
    )
    
    # 任务类型
    job_type: Mapped[JobType] = mapped_column(SQLEnum(JobType), nullable=False)
    
    # 任务状态
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus), 
        default=JobStatus.QUEUED
    )
    
    # 进度 (0-100)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 任务参数
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 任务结果
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 日志文件路径
    logs_uri: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Celery 任务 ID
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # 耗时（秒）
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 关系
    project = relationship("Project", back_populates="jobs")
    
    def __repr__(self):
        return f"<Job(id={self.id}, type='{self.job_type}', status='{self.status}')>"
