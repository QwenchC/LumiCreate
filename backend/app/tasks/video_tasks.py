"""
视频合成 Celery 任务
"""
import asyncio
import subprocess
import uuid
import random
from pathlib import Path
from datetime import datetime
from typing import List

from app.celery_app import celery_app
from app.db.database import async_session
from app.models.job import Job, JobStatus
from app.models.project import Project, ProjectStatus
from app.models.asset import Asset, AssetType
from app.core.config import settings


# Ken Burns 动效类型
KENBURNS_EFFECTS = [
    "zoom_in",      # 从全景推进到中心
    "zoom_out",     # 从中心拉远到全景
    "pan_left",     # 从右到左平移
    "pan_right",    # 从左到右平移
    "pan_up",       # 从下到上平移
    "pan_down",     # 从上到下平移
]


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
    """创建单个段落的视频片段（支持 Ken Burns 效果）"""
    image_path = segment.get("image_path")
    audio_path = segment.get("audio_path")
    duration_ms = segment.get("duration_ms", 3000)
    duration_seconds = duration_ms / 1000
    
    if not image_path or not Path(image_path).exists():
        return None
    
    output_path = temp_dir / f"segment_{index:04d}.mp4"
    
    # 视频参数
    frame_rate = int(config.get("frame_rate", "30"))
    is_portrait = config.get("is_portrait", True)
    
    if is_portrait:
        width, height = 1080, 1920
    else:
        if config.get("resolution") == "1080p":
            width, height = 1920, 1080
        else:
            width, height = 1280, 720
    
    resolution = f"{width}x{height}"
    total_frames = int(duration_seconds * frame_rate)
    
    # Ken Burns 效果配置
    kenburns_enabled = config.get("kenburns_enabled", True)
    kenburns_intensity = config.get("kenburns_intensity", 0.15)  # 缩放幅度 0.1-0.3
    
    # 构建滤镜
    if kenburns_enabled and duration_seconds >= 2:
        # 选择随机效果或根据索引轮换
        effect = KENBURNS_EFFECTS[index % len(KENBURNS_EFFECTS)]
        vf = _build_kenburns_filter(effect, width, height, total_frames, kenburns_intensity)
    else:
        # 简单缩放填充
        vf = f"scale={resolution}:force_original_aspect_ratio=decrease,pad={resolution}:(ow-iw)/2:(oh-ih)/2:black"
    
    # 构建 FFmpeg 命令
    cmd = [settings.FFMPEG_PATH]
    
    # 输入图片（循环）
    cmd.extend(["-loop", "1", "-t", str(duration_seconds)])
    cmd.extend(["-i", image_path])
    
    # 输入音频（如果有）
    has_audio = audio_path and Path(audio_path).exists()
    if has_audio:
        cmd.extend(["-i", audio_path])
    
    # 视频滤镜
    cmd.extend([
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-r", str(frame_rate),
        "-pix_fmt", "yuv420p"
    ])
    
    # 音频编码
    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
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


def _build_kenburns_filter(effect: str, width: int, height: int, total_frames: int, intensity: float = 0.15) -> str:
    """
    构建 Ken Burns 效果的 FFmpeg 滤镜
    
    Args:
        effect: 效果类型 (zoom_in, zoom_out, pan_left, etc.)
        width: 输出宽度
        height: 输出高度
        total_frames: 总帧数
        intensity: 动效强度 (0.1-0.3)
    
    Returns:
        FFmpeg 滤镜字符串
    """
    # 基础缩放比例，确保图片能填充画面并有余量做动效
    base_scale = 1.0 + intensity * 2  # 如 intensity=0.15 则 base_scale=1.3
    
    # 计算放大后的尺寸
    scaled_w = int(width * base_scale)
    scaled_h = int(height * base_scale)
    
    # 每帧的变化量
    zoom_per_frame = intensity / total_frames
    pan_per_frame = (intensity * width) / total_frames
    
    if effect == "zoom_in":
        # 从 1.0 缩放到 1+intensity，中心点固定
        # zoompan: z从1变到1.15，x和y保持居中
        z_expr = f"1+{zoom_per_frame}*in"
        x_expr = f"(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)/2"
        
    elif effect == "zoom_out":
        # 从 1+intensity 缩放到 1.0
        z_expr = f"{1+intensity}-{zoom_per_frame}*in"
        x_expr = f"(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)/2"
        
    elif effect == "pan_left":
        # 从右向左平移
        z_expr = f"{base_scale}"
        x_expr = f"(iw-iw/zoom)*{1-intensity}+{pan_per_frame}*in"
        y_expr = f"(ih-ih/zoom)/2"
        
    elif effect == "pan_right":
        # 从左向右平移
        z_expr = f"{base_scale}"
        x_expr = f"(iw-iw/zoom)*{intensity}-{pan_per_frame}*in+iw*{intensity}"
        y_expr = f"(ih-ih/zoom)/2"
        
    elif effect == "pan_up":
        # 从下向上平移
        z_expr = f"{base_scale}"
        x_expr = f"(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)*{1-intensity}+{pan_per_frame}*in"
        
    elif effect == "pan_down":
        # 从上向下平移
        z_expr = f"{base_scale}"
        x_expr = f"(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)*{intensity}-{pan_per_frame}*in+ih*{intensity}"
        
    else:
        # 默认 zoom_in
        z_expr = f"1+{zoom_per_frame}*in"
        x_expr = f"(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)/2"
    
    # zoompan 滤镜: d=总帧数, s=输出尺寸, fps=帧率
    # 先缩放图片到足够大，然后用 zoompan 做动效
    vf = (
        f"scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase,"
        f"crop={scaled_w}:{scaled_h},"
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={width}x{height}:fps=30"
    )
    
    return vf


async def _concat_videos(
    video_paths: List[Path], 
    output_path: Path, 
    config: dict
):
    """合并多个视频片段（支持转场效果）"""
    if not video_paths:
        raise ValueError("没有可合并的视频片段")
    
    # 转场配置
    transition_type = config.get("transition_type", "淡入淡出")
    transition_duration = float(config.get("transition_duration", 0.3))
    
    # 转场类型映射到 FFmpeg xfade 效果
    transition_map = {
        "淡入淡出": "fade",
        "硬切": None,  # 无转场
        "推拉": "slideleft",
        "缩放": "circleopen",
    }
    
    xfade_effect = transition_map.get(transition_type)
    
    # 如果是硬切或只有一个视频，直接 concat
    if xfade_effect is None or len(video_paths) == 1:
        await _simple_concat(video_paths, output_path)
        return
    
    # 使用 xfade 实现转场效果
    await _xfade_concat(video_paths, output_path, xfade_effect, transition_duration)


async def _simple_concat(video_paths: List[Path], output_path: Path):
    """简单拼接视频（无转场）"""
    concat_file = output_path.parent / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            # 使用绝对路径并转换反斜杠
            abs_path = str(vp.absolute()).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")
    
    cmd = [
        settings.FFMPEG_PATH,
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-y", str(output_path)
    ]
    
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode != 0:
        raise Exception(f"FFmpeg concat 错误: {process.stderr}")
    
    concat_file.unlink(missing_ok=True)


async def _xfade_concat(
    video_paths: List[Path], 
    output_path: Path, 
    effect: str, 
    duration: float
):
    """
    使用 xfade 滤镜实现转场效果
    
    对于多个视频，需要链式应用 xfade：
    v0 xfade v1 -> tmp1
    tmp1 xfade v2 -> tmp2
    ...
    """
    if len(video_paths) == 1:
        # 只有一个视频，直接复制
        import shutil
        shutil.copy(video_paths[0], output_path)
        return
    
    # 获取每个视频的时长
    durations = []
    for vp in video_paths:
        dur = await _get_video_duration(vp)
        durations.append(dur)
    
    # 构建复杂滤镜
    # 输入: [0:v][0:a][1:v][1:a]...
    # 输出: 链式 xfade
    
    inputs = []
    for i, vp in enumerate(video_paths):
        inputs.extend(["-i", str(vp)])
    
    # 构建滤镜图
    n = len(video_paths)
    filter_parts = []
    
    # 第一次 xfade: [0:v][1:v]xfade -> [v1]
    # 计算第一个视频结束时开始转场的时间点
    offset = durations[0] - duration
    if offset < 0:
        offset = 0
    
    filter_parts.append(f"[0:v][1:v]xfade=transition={effect}:duration={duration}:offset={offset}[v1]")
    filter_parts.append(f"[0:a][1:a]acrossfade=d={duration}[a1]")
    
    # 后续的 xfade
    cumulative_duration = durations[0] + durations[1] - duration  # 减去转场重叠时间
    
    for i in range(2, n):
        offset = cumulative_duration - duration
        if offset < 0:
            offset = 0
        
        prev_v = f"v{i-1}"
        prev_a = f"a{i-1}"
        curr_v = f"v{i}"
        curr_a = f"a{i}"
        
        filter_parts.append(f"[{prev_v}][{i}:v]xfade=transition={effect}:duration={duration}:offset={offset}[{curr_v}]")
        filter_parts.append(f"[{prev_a}][{i}:a]acrossfade=d={duration}[{curr_a}]")
        
        cumulative_duration += durations[i] - duration
    
    # 最终输出标签
    final_v = f"v{n-1}"
    final_a = f"a{n-1}"
    
    filter_complex = ";".join(filter_parts)
    
    cmd = [settings.FFMPEG_PATH]
    cmd.extend(inputs)
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", f"[{final_v}]",
        "-map", f"[{final_a}]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-y", str(output_path)
    ])
    
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode != 0:
        # 如果 xfade 失败，回退到简单拼接
        import logging
        logging.warning(f"xfade 转场失败，回退到简单拼接: {process.stderr}")
        await _simple_concat(video_paths, output_path)


async def _get_video_duration(video_path: Path) -> float:
    """获取视频时长（秒）"""
    ffprobe_path = settings.FFMPEG_PATH.replace("ffmpeg", "ffprobe")
    
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode == 0 and process.stdout.strip():
        return float(process.stdout.strip())
    
    return 3.0  # 默认 3 秒
