"""
任务管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional

from app.db.database import get_db
from app.models.job import Job, JobType, JobStatus
from app.models.project import Project
from app.schemas.job import JobResponse, JobListResponse, JobRetryRequest, JobCancelRequest, BatchJobRequest
from app.services.image_generator import generate_all_images
from app.services.audio_generator import generate_all_audio
from app.services.video_composer import compose_video

router = APIRouter()


@router.get("/projects/{project_id}", response_model=JobListResponse)
async def list_project_jobs(
    project_id: int,
    job_type: Optional[JobType] = None,
    status_filter: Optional[JobStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取项目的所有任务"""
    query = select(Job).where(Job.project_id == project_id)
    if job_type:
        query = query.where(Job.job_type == job_type)
    if status_filter:
        query = query.where(Job.status == status_filter)
    query = query.order_by(Job.created_at.desc())
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    return JobListResponse(total=len(jobs), items=jobs)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取任务详情"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """取消任务"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="只能取消排队中或运行中的任务")
    
    job.status = JobStatus.CANCELED
    await db.commit()
    
    # TODO: 如果是 Celery 任务，还需要取消 Celery 任务
    
    return {"status": "success", "message": "任务已取消"}


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """重试失败的任务"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if job.status != JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="只能重试失败的任务")
    
    # 重置任务状态
    job.status = JobStatus.QUEUED
    job.progress = 0.0
    job.error_message = None
    await db.commit()
    
    # TODO: 重新提交到 Celery 队列
    
    return {"status": "success", "message": "任务已重新排队"}


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除任务"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if job.status in [JobStatus.QUEUED, JobStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="不能删除排队中或运行中的任务，请先取消")
    
    await db.delete(job)
    await db.commit()
    
    return {"status": "success", "message": "任务已删除"}


@router.post("/projects/{project_id}/retry-failed")
async def retry_failed_jobs(
    project_id: int,
    request: JobRetryRequest,
    db: AsyncSession = Depends(get_db)
):
    """重试项目中所有失败的任务"""
    query = (
        update(Job)
        .where(Job.project_id == project_id)
        .where(Job.status == JobStatus.FAILED)
    )
    if request.job_ids:
        query = query.where(Job.id.in_(request.job_ids))
    query = query.values(status=JobStatus.QUEUED, progress=0.0, error_message=None)
    
    await db.execute(query)
    await db.commit()
    
    return {"status": "success", "message": "失败任务已重新排队"}


# ============ 批量任务 ============

@router.post("/projects/{project_id}/images/generate-all")
async def generate_all_project_images(
    project_id: int,
    request: BatchJobRequest,
    db: AsyncSession = Depends(get_db)
):
    """为项目所有段落生成图片"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    jobs = await generate_all_images(
        db=db,
        project=project,
        segment_ids=request.segment_ids
    )
    
    return {
        "status": "success",
        "message": f"已创建 {len(jobs)} 个图片生成任务",
        "job_ids": [job.id for job in jobs]
    }


@router.post("/projects/{project_id}/audio/generate-all")
async def generate_all_project_audio(
    project_id: int,
    request: BatchJobRequest,
    db: AsyncSession = Depends(get_db)
):
    """为项目所有段落生成音频"""
    from app.services.audio_generator import execute_audio_generation
    
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    jobs = await generate_all_audio(
        db=db,
        project=project,
        segment_ids=request.segment_ids
    )
    
    # 同步执行所有音频生成任务
    results = []
    for job in jobs:
        gen_result = await execute_audio_generation(db, job)
        results.append({
            "job_id": job.id,
            "segment_id": job.segment_id,
            "success": gen_result.get("success", False),
            "asset_id": gen_result.get("asset_id"),
            "duration_ms": gen_result.get("duration_ms"),
            "error": gen_result.get("error")
        })
    
    success_count = sum(1 for r in results if r["success"])
    
    return {
        "status": "success",
        "message": f"已完成 {success_count}/{len(jobs)} 个音频生成",
        "job_ids": [job.id for job in jobs],
        "results": results
    }


@router.post("/projects/{project_id}/video/compose")
async def compose_project_video(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """合成项目视频"""
    from app.services.video_composer import execute_video_composition
    
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查是否有正在进行的合成任务
    running_job_result = await db.execute(
        select(Job)
        .where(Job.project_id == project_id)
        .where(Job.job_type == JobType.VIDEO_COMPOSE)
        .where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
    )
    if running_job_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="已有正在进行的视频合成任务")
    
    job = await compose_video(db=db, project=project)
    
    # 同步执行视频合成
    gen_result = await execute_video_composition(db, job)
    
    if gen_result.get("success"):
        return {
            "status": "success",
            "message": "视频合成完成",
            "job_id": job.id,
            "video_asset_id": gen_result.get("video_asset_id"),
            "output_path": gen_result.get("output_path")
        }
    else:
        return {
            "status": "failed",
            "message": "视频合成失败",
            "job_id": job.id,
            "error": gen_result.get("error")
        }
