"""
图片生成 Celery 任务
支持 ComfyUI 和 Pollinations.ai 两种生图方式
"""
import asyncio
import uuid
from pathlib import Path
from datetime import datetime

from app.celery_app import celery_app
from app.db.database import async_session
from app.models.job import Job, JobStatus
from app.models.segment import Segment, SegmentStatus
from app.models.asset import Asset, AssetType
from app.core.config import settings


@celery_app.task(bind=True, max_retries=3)
def generate_image_task(self, job_id: int):
    """
    图片生成任务
    
    Args:
        job_id: 任务ID
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_generate_image_async(self, job_id))


async def _generate_image_async(task, job_id: int):
    """异步执行图片生成"""
    async with async_session() as db:
        # 获取任务
        from sqlalchemy import select
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            return {"error": "任务不存在"}
        
        try:
            # 更新任务状态
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await db.commit()
            
            params = job.params
            segment_id = params["segment_id"]
            count = params.get("count", 1)
            
            # 获取段落
            seg_result = await db.execute(select(Segment).where(Segment.id == segment_id))
            segment = seg_result.scalar_one()
            
            # 准备输出目录
            output_dir = settings.IMAGES_PATH / str(job.project_id) / str(segment_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            generated_assets = []
            engine = params.get("engine", "pollinations")
            
            for i in range(count):
                # 更新进度
                job.progress = (i / count) * 100
                await db.commit()
                
                # 生成种子
                seed = params.get("seed") or uuid.uuid4().int % (2**32)
                
                if engine == "pollinations":
                    # 使用 Pollinations.ai 生成
                    from app.services.pollinations_client import generate_image_pollinations
                    
                    image_filename = f"{uuid.uuid4()}.png"
                    image_path = output_dir / image_filename
                    
                    result = await generate_image_pollinations(
                        prompt=params["prompt"],
                        output_path=image_path,
                        width=params.get("width", 1024),
                        height=params.get("height", 1024),
                        seed=seed,
                        model=params.get("pollinations_model", "zimage"),
                        translate=True  # 自动翻译中文
                    )
                    
                    if not result.get("success"):
                        raise Exception(result.get("error", "Pollinations 生成失败"))
                    
                    # 创建资产记录
                    asset = Asset(
                        project_id=job.project_id,
                        segment_id=segment_id,
                        asset_type=AssetType.IMAGE,
                        file_path=str(image_path),
                        file_name=image_filename,
                        metadata={
                            "engine": "pollinations",
                            "seed": result.get("seed", seed),
                            "prompt": result.get("prompt", params["prompt"]),
                            "model": result.get("model"),
                            "width": result.get("width"),
                            "height": result.get("height")
                        }
                    )
                else:
                    # 使用 ComfyUI 生成
                    workflow = _build_workflow(params, seed)
                    
                    # TODO: 实际调用 ComfyUI
                    # image_paths = await call_comfyui_api(workflow, output_dir)
                    
                    # 模拟生成
                    image_filename = f"{uuid.uuid4()}.png"
                    image_path = output_dir / image_filename
                    
                    # 创建资产记录
                    asset = Asset(
                        project_id=job.project_id,
                        segment_id=segment_id,
                        asset_type=AssetType.IMAGE,
                        file_path=str(image_path),
                        file_name=image_filename,
                        metadata={
                            "engine": "comfyui",
                            "seed": seed,
                            "prompt": params["prompt"],
                            "negative_prompt": params["negative_prompt"],
                            "steps": params["steps"],
                            "cfg_scale": params["cfg_scale"],
                            "sampler": params["sampler"],
                            "workflow_id": params.get("workflow_id")
                        }
                    )
                
                db.add(asset)
                generated_assets.append(asset)
            
            await db.commit()
            
            # 更新段落状态
            segment.status = SegmentStatus.IMAGES_READY
            
            # 如果是第一次生成，自动选择第一张
            if not segment.selected_image_asset_id and generated_assets:
                await db.refresh(generated_assets[0])
                segment.selected_image_asset_id = generated_assets[0].id
            
            # 更新任务状态
            job.status = JobStatus.SUCCEEDED
            job.progress = 100
            job.finished_at = datetime.utcnow()
            job.result = {
                "asset_ids": [a.id for a in generated_assets]
            }
            
            await db.commit()
            
            return {"status": "success", "asset_ids": [a.id for a in generated_assets]}
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            await db.commit()
            
            # 重试
            raise task.retry(exc=e, countdown=60)


def _build_workflow(params: dict, seed: int) -> dict:
    """构建 ComfyUI 工作流"""
    # 这是一个简化的工作流示例
    # 实际使用时需要根据 ComfyUI 的具体工作流格式构建
    
    # 解析分辨率
    resolution = params.get("resolution", "1024")
    aspect_ratio = params.get("aspect_ratio", "竖屏9:16")
    
    if aspect_ratio == "竖屏9:16":
        width = int(resolution)
        height = int(int(resolution) * 16 / 9)
    elif aspect_ratio == "横屏16:9":
        width = int(int(resolution) * 16 / 9)
        height = int(resolution)
    else:  # 正方形
        width = height = int(resolution)
    
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": params.get("steps", 20),
                "cfg": params.get("cfg_scale", 7.0),
                "sampler_name": params.get("sampler", "euler_ancestral"),
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "sd_xl_base_1.0.safetensors"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": params.get("prompt", ""),
                "clip": ["4", 1]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": params.get("negative_prompt", ""),
                "clip": ["4", 1]
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "lumicreate",
                "images": ["8", 0]
            }
        }
    }
    
    return workflow
