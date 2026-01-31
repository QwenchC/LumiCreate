"""
视频合成 Celery 任务
"""
import asyncio
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
from typing import List

from app.celery_app import celery_app
from app.db.database import async_session
from app.models.job import Job, JobStatus
from app.models.project import Project, ProjectStatus
from app.models.asset import Asset, AssetType
from app.core.config import settings


@celery_app.task(bind=True, max_retries=2)
def compose_video_task(self, job_id: int):
    """
    视频合成任务
    
    Args:
        job_id: 任务ID
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_compose_video_async(self, job_id))


async def _compose_video_async(task, job_id: int):
    """异步执行视频合成"""
    async with async_session() as db:
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
            segments = params["segments"]
            config = params["config"]
            output_filename = params.get("output_filename", f"output_{job_id}.mp4")
            
            # 准备输出目录
            output_dir = settings.VIDEO_PATH / str(job.project_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / output_filename
            
            temp_dir = settings.TEMP_PATH / str(job_id)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 第一步：为每个段落创建视频片段
            segment_videos = []
            total_segments = len(segments)
            
            for i, seg in enumerate(segments):
                job.progress = (i / total_segments) * 80  # 留 20% 给最终合并
                await db.commit()
                
                segment_video = await _create_segment_video(
                    seg, config, temp_dir, i
                )
                if segment_video:
                    segment_videos.append(segment_video)
            
            # 第二步：合并所有片段
            job.progress = 85
            await db.commit()
            
            await _concat_videos(segment_videos, output_path, config)
            
            # 第三步：生成字幕文件（可选）
            if config.get("subtitle_enabled", True):
                from app.services.video_composer import generate_subtitle_file
                subtitle_format = config.get("subtitle_format", "srt")
                subtitle_path = await generate_subtitle_file(
                    segments, output_path, subtitle_format
                )
                
                # 创建字幕资产
                subtitle_asset = Asset(
                    project_id=job.project_id,
                    asset_type=AssetType.SUBTITLE,
                    file_path=str(subtitle_path),
                    file_name=subtitle_path.name,
                )
                db.add(subtitle_asset)
            
            # 创建视频资产
            video_asset = Asset(
                project_id=job.project_id,
                asset_type=AssetType.VIDEO,
                file_path=str(output_path),
                file_name=output_filename,
                file_size=output_path.stat().st_size if output_path.exists() else 0,
                metadata={
                    "config": config,
                    "segment_count": len(segments)
                }
            )
            db.add(video_asset)
            await db.commit()
            await db.refresh(video_asset)
            
            # 更新项目状态
            project_result = await db.execute(
                select(Project).where(Project.id == job.project_id)
            )
            project = project_result.scalar_one()
            project.status = ProjectStatus.EXPORTED
            
            # 更新任务状态
            job.status = JobStatus.SUCCEEDED
            job.progress = 100
            job.finished_at = datetime.utcnow()
            job.result = {
                "video_asset_id": video_asset.id,
                "output_path": str(output_path)
            }
            
            await db.commit()
            
            # 清理临时文件
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return {"status": "success", "video_asset_id": video_asset.id}
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            await db.commit()
            
            raise task.retry(exc=e, countdown=120)


async def _create_segment_video(
    segment: dict, 
    config: dict, 
    temp_dir: Path, 
    index: int
) -> Path:
    """创建单个段落的视频片段"""
    image_path = segment.get("image_path")
    audio_path = segment.get("audio_path")
    duration_ms = segment.get("duration_ms", 3000)
    duration_seconds = duration_ms / 1000
    
    if not image_path or not Path(image_path).exists():
        return None
    
    output_path = temp_dir / f"segment_{index:04d}.mp4"
    
    # 构建 FFmpeg 命令
    cmd = [settings.FFMPEG_PATH]
    
    # 输入图片（循环）
    cmd.extend(["-loop", "1", "-t", str(duration_seconds)])
    cmd.extend(["-i", image_path])
    
    # 输入音频（如果有）
    if audio_path and Path(audio_path).exists():
        cmd.extend(["-i", audio_path])
        # 使用音频时长
        cmd.extend(["-shortest"])
    
    # 视频编码参数
    frame_rate = config.get("frame_rate", "30")
    is_portrait = config.get("is_portrait", True)
    
    if is_portrait:
        resolution = "1080x1920"
    else:
        resolution = "1920x1080" if config.get("resolution") == "1080p" else "1280x720"
    
    # 视频滤镜：缩放并填充
    vf = f"scale={resolution}:force_original_aspect_ratio=decrease,pad={resolution}:(ow-iw)/2:(oh-ih)/2:black"
    
    cmd.extend([
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-r", frame_rate,
        "-pix_fmt", "yuv420p"
    ])
    
    # 音频编码
    if audio_path and Path(audio_path).exists():
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
    else:
        # 无音频时添加静音
        cmd.extend(["-f", "lavfi", "-t", str(duration_seconds)])
        cmd.extend(["-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
    
    cmd.extend(["-y", str(output_path)])
    
    # 执行 FFmpeg
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode != 0:
        raise Exception(f"FFmpeg 错误: {process.stderr}")
    
    return output_path


async def _concat_videos(
    video_paths: List[Path], 
    output_path: Path, 
    config: dict
):
    """合并多个视频片段"""
    if not video_paths:
        raise ValueError("没有可合并的视频片段")
    
    # 创建文件列表
    concat_file = output_path.parent / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")
    
    # 转场处理
    transition_type = config.get("transition_type", "淡入淡出")
    transition_duration = config.get("transition_duration", 0.3)
    
    # 简单 concat（不带转场）
    cmd = [
        settings.FFMPEG_PATH,
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-y", str(output_path)
    ]
    
    # TODO: 如果需要转场效果，需要更复杂的滤镜链
    # 这里先用简单的 concat
    
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode != 0:
        raise Exception(f"FFmpeg concat 错误: {process.stderr}")
    
    # 清理临时文件
    concat_file.unlink(missing_ok=True)
