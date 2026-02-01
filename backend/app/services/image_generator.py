"""
图片生成服务
支持 ComfyUI 和 Pollinations.ai 两种生图方式
"""
import json
import uuid
import httpx
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project
from app.models.segment import Segment, SegmentStatus
from app.models.asset import Asset, AssetType
from app.models.job import Job, JobType, JobStatus
from app.core.config import settings


# 画风映射 - 通用英文前缀
STYLE_PREFIX_MAP = {
    "国风": "chinese style, traditional, ",
    "赛博": "cyberpunk, neon, futuristic, ",
    "写实": "realistic, photorealistic, ",
    "动漫": "anime style, illustration, ",
    "暗黑": "dark, gothic, moody, ",
    "油画": "oil painting, artistic, ",
    "水彩": "watercolor, soft, artistic, ",
    "极简": "minimalist, clean, simple, "
}

# 氛围映射
MOOD_PREFIX_MAP = {
    "紧张": "tense atmosphere, dramatic, ",
    "温馨": "warm, cozy, soft lighting, ",
    "热血": "dynamic, action, energetic, ",
    "恐怖": "horror, eerie, dark shadows, ",
    "轻松": "relaxed, peaceful, bright, ",
    "悲伤": "melancholic, sad, gloomy, ",
    "神秘": "mysterious, enigmatic, fog, "
}


def build_full_prompt(
    base_prompt: str,
    style: Optional[str] = None,
    mood: Optional[str] = None
) -> str:
    """
    构建完整的提示词
    
    Args:
        base_prompt: 基础提示词
        style: 画风
        mood: 氛围
    
    Returns:
        完整的提示词（英文前缀 + 基础提示词）
    """
    parts = []
    
    if mood and mood in MOOD_PREFIX_MAP:
        parts.append(MOOD_PREFIX_MAP[mood])
    
    if style and style in STYLE_PREFIX_MAP:
        parts.append(STYLE_PREFIX_MAP[style])
    
    parts.append(base_prompt)
    
    return "".join(parts)


def calculate_dimensions(resolution: str, aspect_ratio: str) -> tuple:
    """
    根据分辨率和画面比例计算实际尺寸
    
    Returns:
        (width, height)
    """
    base = int(resolution) if resolution else 1024
    
    if aspect_ratio == "竖屏9:16":
        # 竖屏：宽度为 base，高度按比例
        width = base
        height = int(base * 16 / 9)
    elif aspect_ratio == "横屏16:9":
        # 横屏：高度为 base，宽度按比例
        height = base
        width = int(base * 16 / 9)
    else:  # 正方形1:1
        width = height = base
    
    return width, height


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
    
    # 获取图片生成配置（统一配置）
    image_config = project.project_config.get("image_generation", {})
    # 向后兼容：如果没有 image_generation，尝试使用 comfyui
    if not image_config:
        image_config = project.project_config.get("comfyui", {})
    
    # 获取生图引擎：pollinations 或 comfyui
    engine = image_config.get("engine", "pollinations")
    
    # 构建任务参数
    prompt = override_prompt or segment.visual_prompt or ""
    style = image_config.get("style", "国风")
    
    # 构建完整提示词（包含风格和氛围前缀）
    full_prompt = build_full_prompt(
        base_prompt=prompt,
        style=style,
        mood=segment.mood
    )
    
    # 计算尺寸
    resolution = image_config.get("resolution", "1024")
    aspect_ratio = image_config.get("aspect_ratio", "竖屏9:16")
    width, height = calculate_dimensions(resolution, aspect_ratio)
    
    job_params = {
        "segment_id": segment.id,
        "count": count,
        "prompt": full_prompt,
        "engine": engine,
        "negative_prompt": image_config.get("negative_prompt", "low quality, blurry"),
        "seed": override_seed,
        "width": width,
        "height": height,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        # ComfyUI 特有参数
        "steps": image_config.get("steps", 20),
        "cfg_scale": image_config.get("cfg_scale", 7.0),
        "sampler": image_config.get("sampler", "euler_ancestral"),
        "workflow_id": image_config.get("workflow_id"),
        # Pollinations 特有参数
        "pollinations_model": image_config.get("pollinations_model", "flux")
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
    image_config = project.project_config.get("image_generation", {})
    if not image_config:
        image_config = project.project_config.get("comfyui", {})
    count = image_config.get("candidates_per_segment", 3)
    
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
