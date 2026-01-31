"""
任务相关的 Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.models.job import JobType, JobStatus


class JobResponse(BaseModel):
    """任务响应 Schema"""
    id: int
    project_id: int
    segment_id: Optional[int]
    job_type: JobType
    status: JobStatus
    progress: float
    error_message: Optional[str]
    params: Optional[dict]
    result: Optional[dict]
    duration_seconds: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """任务列表响应 Schema"""
    total: int
    items: List[JobResponse]


class JobRetryRequest(BaseModel):
    """任务重试请求"""
    job_ids: Optional[List[int]] = Field(None, description="要重试的任务ID列表（空则重试所有失败任务）")


class JobCancelRequest(BaseModel):
    """任务取消请求"""
    job_ids: List[int] = Field(..., min_length=1, description="要取消的任务ID列表")


class BatchJobRequest(BaseModel):
    """批量任务请求"""
    segment_ids: Optional[List[int]] = Field(None, description="指定段落ID（空则处理所有段落）")
