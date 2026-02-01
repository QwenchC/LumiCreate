"""
图片生成服务
支持 ComfyUI 和 Pollinations.ai 两种生图方式
"""
import json
import uuid
import httpx
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project
from app.models.segment import Segment, SegmentStatus
from app.models.asset import Asset, AssetType
from app.models.job import Job, JobType, JobStatus
from app.core.config import settings

logger = logging.getLogger(__name__)


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
    确保尺寸是 64 的倍数（大多数图像生成 API 的要求）
    
    Returns:
        (width, height)
    """
    base = int(resolution) if resolution else 1024
    
    # 确保 base 是 64 的倍数
    base = (base // 64) * 64
    if base < 512:
        base = 512
    
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
    
    # 确保 width 和 height 都是 64 的倍数
    width = (width // 64) * 64
    height = (height // 64) * 64
    
    return width, height


async def generate_segment_images(
    db: AsyncSession,
    segment: Segment,
    count: Optional[int] = None,
    override_prompt: Optional[str] = None,
    override_seed: Optional[int] = None
) -> Job:
    """
    为段落生成图片
    
    Args:
        db: 数据库会话
        segment: 段落对象
        count: 生成数量（如果为 None，从项目配置读取）
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
    
    # 如果没有指定 count，从项目配置读取
    if count is None:
        count = image_config.get("candidates_per_segment", 3)
    
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
        "pollinations_model": image_config.get("pollinations_model", "zimage")
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


async def execute_image_generation(
    db: AsyncSession,
    job: Job
) -> Dict[str, Any]:
    """
    直接执行图片生成（不通过 Celery）
    适用于 Pollinations 等快速云端生图
    
    Args:
        db: 数据库会话
        job: 任务对象
    
    Returns:
        生成结果
    """
    import uuid
    from datetime import datetime
    from app.models.asset import Asset, AssetType
    from app.services.pollinations_client import generate_image_pollinations
    
    params = job.params
    segment_id = params["segment_id"]
    count = params.get("count", 1)
    engine = params.get("engine", "pollinations")
    
    # 获取段落
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        job.status = JobStatus.FAILED
        job.error_message = "段落不存在"
        await db.commit()
        return {"success": False, "error": "段落不存在"}
    
    # 更新任务状态
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    await db.commit()
    
    # 准备输出目录
    output_dir = settings.IMAGES_PATH / str(job.project_id) / str(segment_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_assets = []
    failed_count = 0
    
    try:
        for i in range(count):
            # 更新进度
            job.progress = (i / count) * 100
            await db.commit()
            
            # 生成种子 (Pollinations API 限制种子范围为 0-999999999)
            seed = params.get("seed") or uuid.uuid4().int % 1000000000
            
            try:
                if engine == "pollinations":
                    # 使用 Pollinations.ai 生成
                    image_filename = f"{uuid.uuid4()}.png"
                    image_path = output_dir / image_filename
                    
                    gen_result = await generate_image_pollinations(
                        prompt=params["prompt"],
                        output_path=image_path,
                        width=params.get("width", 1024),
                        height=params.get("height", 1024),
                        seed=seed,
                        model=params.get("pollinations_model", "zimage"),
                        translate=True
                    )
                    
                    if not gen_result.get("success"):
                        logger.warning(f"第 {i+1} 张图片生成失败: {gen_result.get('error')}")
                        failed_count += 1
                        continue
                    
                    # 创建资产记录
                    asset = Asset(
                        project_id=job.project_id,
                        segment_id=segment_id,
                        asset_type=AssetType.IMAGE,
                        file_path=str(image_path),
                        file_name=image_filename,
                        asset_metadata={
                            "engine": "pollinations",
                            "seed": gen_result.get("seed", seed),
                            "prompt": gen_result.get("prompt", params["prompt"]),
                            "model": gen_result.get("model"),
                            "width": gen_result.get("width"),
                            "height": gen_result.get("height")
                        }
                    )
                else:
                    # 使用 ComfyUI 生成
                    from app.services.comfyui_client import generate_image_comfyui
                    
                    image_filename = f"{uuid.uuid4()}.png"
                    image_path = output_dir / image_filename
                    
                    gen_result = await generate_image_comfyui(
                        prompt=params["prompt"],
                        output_path=image_path,
                        negative_prompt=params.get("negative_prompt"),
                        seed=seed,
                        width=params.get("width", 1024),
                        height=params.get("height", 1024),
                        steps=params.get("steps", 20),
                        cfg_scale=params.get("cfg_scale", 3.5),
                        workflow_path=params.get("workflow_id")  # 可指定工作流
                    )
                    
                    if not gen_result.get("success"):
                        logger.warning(f"第 {i+1} 张图片生成失败 (ComfyUI): {gen_result.get('error')}")
                        failed_count += 1
                        continue
                    
                    asset = Asset(
                        project_id=job.project_id,
                        segment_id=segment_id,
                        asset_type=AssetType.IMAGE,
                        file_path=str(image_path),
                        file_name=image_filename,
                        asset_metadata={
                            "engine": "comfyui",
                            "seed": gen_result.get("seed", seed),
                            "prompt": gen_result.get("prompt", params["prompt"]),
                            "width": gen_result.get("width"),
                            "height": gen_result.get("height"),
                            "prompt_id": gen_result.get("prompt_id"),
                            "comfyui_filename": gen_result.get("comfyui_filename")
                        }
                    )
                
                db.add(asset)
                await db.flush()  # 获取 asset.id
                generated_assets.append(asset)
                
            except Exception as img_error:
                logger.warning(f"第 {i+1} 张图片生成失败: {img_error}")
                failed_count += 1
                continue
        
        await db.commit()
        
        # 更新段落状态（只要有成功生成的图片就算成功）
        if generated_assets:
            segment.status = SegmentStatus.IMAGES_READY
            
            # 如果是第一次生成，自动选择第一张
            if not segment.selected_image_asset_id:
                segment.selected_image_asset_id = generated_assets[0].id
        
        # 更新任务状态
        if failed_count == 0:
            job.status = JobStatus.SUCCEEDED
        elif generated_assets:
            job.status = JobStatus.SUCCEEDED  # 部分成功也算成功
            job.error_message = f"部分图片生成失败 ({failed_count}/{count})"
        else:
            job.status = JobStatus.FAILED
            job.error_message = "所有图片生成失败"
            segment.status = SegmentStatus.READY_SCRIPT
            
        job.progress = 100
        job.finished_at = datetime.utcnow()
        job.result = {
            "asset_ids": [a.id for a in generated_assets],
            "failed_count": failed_count
        }
        
        await db.commit()
        
        return {
            "success": len(generated_assets) > 0,
            "asset_ids": [a.id for a in generated_assets],
            "failed_count": failed_count,
            "assets": [
                {
                    "id": a.id,
                    "file_name": a.file_name,
                    "file_path": a.file_path
                } for a in generated_assets
            ]
        }
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.finished_at = datetime.utcnow()
        segment.status = SegmentStatus.READY_SCRIPT  # 回退到脑本就绪状态
        await db.commit()
        
        return {"success": False, "error": str(e)}


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
