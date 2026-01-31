"""
图片生成服务
使用 ComfyUI 生成段落配图
"""
import json
import uuid
import httpx
from pathlib import Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project
from app.models.segment import Segment, SegmentStatus
from app.models.asset import Asset, AssetType
from app.models.job import Job, JobType, JobStatus
from app.core.config import settings


async def generate_segment_images(
    db: AsyncSession,
    segment: Segment,
    count: int = 1,
    override_prompt: Optional[str] = None,
    override_seed: Optional[int] = None
) -> Job:
    """
    为段落生成图片
    
    Args:
        db: 数据库会话
        segment: 段落对象
        count: 生成数量
        override_prompt: 覆盖的提示词
        override_seed: 覆盖的种子
    
    Returns:
        Job: 创建的任务对象
    """
    # 获取项目配置
    project_result = await db.execute(
        select(Project).where(Project.id == segment.project_id)
    )
    project = project_result.scalar_one()
    comfyui_config = project.project_config.get("comfyui", {})
    
    # 构建任务参数
    prompt = override_prompt or segment.visual_prompt or ""
    
    # 添加风格前缀
    style = comfyui_config.get("style", "国风")
    style_prefix_map = {
        "国风": "chinese style, traditional, ",
        "赛博": "cyberpunk, neon, futuristic, ",
        "写实": "realistic, photorealistic, ",
        "动漫": "anime style, illustration, ",
        "暗黑": "dark, gothic, moody, ",
        "油画": "oil painting, artistic, ",
        "水彩": "watercolor, soft, artistic, ",
        "极简": "minimalist, clean, simple, "
    }
    style_prefix = style_prefix_map.get(style, "")
    full_prompt = style_prefix + prompt
    
    # 添加氛围关键词
    if segment.mood:
        mood_map = {
            "紧张": "tense atmosphere, dramatic, ",
            "温馨": "warm, cozy, soft lighting, ",
            "热血": "dynamic, action, energetic, ",
            "恐怖": "horror, eerie, dark shadows, ",
            "轻松": "relaxed, peaceful, bright, ",
            "悲伤": "melancholic, sad, gloomy, ",
            "神秘": "mysterious, enigmatic, fog, "
        }
        mood_prefix = mood_map.get(segment.mood, "")
        full_prompt = mood_prefix + full_prompt
    
    job_params = {
        "segment_id": segment.id,
        "count": count,
        "prompt": full_prompt,
        "negative_prompt": comfyui_config.get("negative_prompt", "low quality, blurry"),
        "seed": override_seed,
        "steps": comfyui_config.get("steps", 20),
        "cfg_scale": comfyui_config.get("cfg_scale", 7.0),
        "sampler": comfyui_config.get("sampler", "euler_ancestral"),
        "resolution": comfyui_config.get("resolution", "1024"),
        "aspect_ratio": comfyui_config.get("aspect_ratio", "竖屏9:16"),
        "workflow_id": comfyui_config.get("workflow_id")
    }
    
    # 创建任务
    job = Job(
        project_id=segment.project_id,
        segment_id=segment.id,
        job_type=JobType.IMAGE_GEN,
        status=JobStatus.QUEUED,
        params=job_params
    )
    db.add(job)
    
    # 更新段落状态
    segment.status = SegmentStatus.GENERATING_IMAGES
    
    await db.commit()
    await db.refresh(job)
    
    # TODO: 提交到 Celery 队列
    # celery_task = image_gen_task.delay(job.id)
    # job.celery_task_id = celery_task.id
    # await db.commit()
    
    return job


async def generate_all_images(
    db: AsyncSession,
    project: Project,
    segment_ids: Optional[List[int]] = None
) -> List[Job]:
    """
    批量生成所有段落的图片
    
    Args:
        db: 数据库会话
        project: 项目对象
        segment_ids: 指定的段落ID列表（可选）
    
    Returns:
        List[Job]: 创建的任务列表
    """
    # 获取需要处理的段落
    query = select(Segment).where(Segment.project_id == project.id)
    if segment_ids:
        query = query.where(Segment.id.in_(segment_ids))
    query = query.order_by(Segment.order_index)
    
    result = await db.execute(query)
    segments = result.scalars().all()
    
    # 获取配置中的候选图数量
    comfyui_config = project.project_config.get("comfyui", {})
    count = comfyui_config.get("candidates_per_segment", 3)
    
    jobs = []
    for segment in segments:
        job = await generate_segment_images(db, segment, count=count)
        jobs.append(job)
    
    return jobs


async def call_comfyui_api(workflow: dict, output_dir: Path) -> List[str]:
    """
    调用 ComfyUI API 生成图片
    
    Args:
        workflow: ComfyUI 工作流配置
        output_dir: 输出目录
    
    Returns:
        List[str]: 生成的图片路径列表
    """
    # 提交工作流
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 获取队列状态
        response = await client.post(
            f"{settings.COMFYUI_API_URL}/prompt",
            json={"prompt": workflow}
        )
        response.raise_for_status()
        data = response.json()
        prompt_id = data["prompt_id"]
        
        # 轮询等待完成
        while True:
            history_response = await client.get(
                f"{settings.COMFYUI_API_URL}/history/{prompt_id}"
            )
            history = history_response.json()
            
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                # 提取图片路径
                image_paths = []
                for node_output in outputs.values():
                    if "images" in node_output:
                        for img in node_output["images"]:
                            image_paths.append(img["filename"])
                return image_paths
            
            import asyncio
            await asyncio.sleep(1)
