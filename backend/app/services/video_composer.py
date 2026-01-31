"""
视频合成服务
使用 FFmpeg 合成最终视频
"""
import subprocess
import json
from pathlib import Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project, ProjectStatus
from app.models.segment import Segment
from app.models.asset import Asset, AssetType
from app.models.job import Job, JobType, JobStatus
from app.core.config import settings
from app.services.audio_generator import estimate_audio_duration


async def compose_video(
    db: AsyncSession,
    project: Project
) -> Job:
    """
    合成项目视频
    
    Args:
        db: 数据库会话
        project: 项目对象
    
    Returns:
        Job: 创建的任务对象
    """
    # 获取配置
    composer_config = project.project_config.get("video_composer", {})
    
    # 收集所有段落信息
    segments_result = await db.execute(
        select(Segment)
        .where(Segment.project_id == project.id)
        .order_by(Segment.order_index)
    )
    segments = segments_result.scalars().all()
    
    # 构建合成参数
    segment_data = []
    for segment in segments:
        # 获取选定的图片
        image_asset = None
        if segment.selected_image_asset_id:
            asset_result = await db.execute(
                select(Asset).where(Asset.id == segment.selected_image_asset_id)
            )
            image_asset = asset_result.scalar_one_or_none()
        
        # 获取音频
        audio_asset = None
        if segment.audio_asset_id:
            audio_result = await db.execute(
                select(Asset).where(Asset.id == segment.audio_asset_id)
            )
            audio_asset = audio_result.scalar_one_or_none()
        
        # 计算时长
        if audio_asset and audio_asset.duration_ms:
            duration_ms = audio_asset.duration_ms
        elif segment.duration_ms:
            duration_ms = segment.duration_ms
        else:
            # 估算时长
            fallback_cps = composer_config.get("fallback_chars_per_second", 4.5)
            duration_ms = estimate_audio_duration(segment.narration_text, fallback_cps)
        
        # 添加 padding
        padding_ms = int(composer_config.get("segment_padding", 0.3) * 1000)
        duration_ms += padding_ms
        
        # 确保最小时长
        min_duration_ms = int(composer_config.get("min_segment_duration", 1.5) * 1000)
        duration_ms = max(duration_ms, min_duration_ms)
        
        segment_data.append({
            "segment_id": segment.id,
            "order_index": segment.order_index,
            "image_path": image_asset.file_path if image_asset else None,
            "audio_path": audio_asset.file_path if audio_asset else None,
            "duration_ms": duration_ms,
            "narration_text": segment.narration_text,
            "on_screen_text": segment.on_screen_text
        })
    
    job_params = {
        "segments": segment_data,
        "config": composer_config,
        "output_filename": f"project_{project.id}_output.mp4"
    }
    
    # 创建任务
    job = Job(
        project_id=project.id,
        job_type=JobType.VIDEO_COMPOSE,
        status=JobStatus.QUEUED,
        params=job_params
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # TODO: 提交到 Celery 队列
    
    return job


def build_ffmpeg_command(
    segments: List[dict],
    config: dict,
    output_path: Path
) -> List[str]:
    """
    构建 FFmpeg 命令
    
    Args:
        segments: 段落数据列表
        config: 合成配置
        output_path: 输出路径
    
    Returns:
        List[str]: FFmpeg 命令参数
    """
    # 基础参数
    frame_rate = config.get("frame_rate", "30")
    is_portrait = config.get("is_portrait", True)
    
    if is_portrait:
        resolution = "1080x1920"
    else:
        resolution = "1920x1080" if config.get("resolution") == "1080p" else "1280x720"
    
    # 构建复杂滤镜
    # 这里给出一个简化的示例，实际需要更复杂的处理
    
    cmd = [settings.FFMPEG_PATH]
    
    # 添加输入
    filter_parts = []
    for i, seg in enumerate(segments):
        if seg.get("image_path"):
            cmd.extend(["-loop", "1", "-t", str(seg["duration_ms"] / 1000)])
            cmd.extend(["-i", seg["image_path"]])
        if seg.get("audio_path"):
            cmd.extend(["-i", seg["audio_path"]])
    
    # 输出参数
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-r", frame_rate,
        "-s", resolution,
        "-y",
        str(output_path)
    ])
    
    return cmd


async def generate_subtitle_file(
    segments: List[dict],
    output_path: Path,
    format: str = "srt"
) -> Path:
    """
    生成字幕文件
    
    Args:
        segments: 段落数据列表
        output_path: 输出路径
        format: 字幕格式（srt/ass）
    
    Returns:
        Path: 字幕文件路径
    """
    subtitle_path = output_path.with_suffix(f".{format}")
    
    if format == "srt":
        content = _generate_srt(segments)
    else:
        content = _generate_ass(segments)
    
    with open(subtitle_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return subtitle_path


def _generate_srt(segments: List[dict]) -> str:
    """生成 SRT 格式字幕"""
    lines = []
    current_time_ms = 0
    
    for i, seg in enumerate(segments):
        start_time = _format_srt_time(current_time_ms)
        end_time = _format_srt_time(current_time_ms + seg["duration_ms"])
        
        text = seg.get("on_screen_text") or seg.get("narration_text", "")
        
        lines.append(str(i + 1))
        lines.append(f"{start_time} --> {end_time}")
        lines.append(text)
        lines.append("")
        
        current_time_ms += seg["duration_ms"]
    
    return "\n".join(lines)


def _format_srt_time(ms: int) -> str:
    """格式化 SRT 时间"""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _generate_ass(segments: List[dict]) -> str:
    """生成 ASS 格式字幕"""
    header = """[Script Info]
Title: LumiCreate Generated Subtitle
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    events = []
    current_time_ms = 0
    
    for seg in segments:
        start_time = _format_ass_time(current_time_ms)
        end_time = _format_ass_time(current_time_ms + seg["duration_ms"])
        
        text = seg.get("on_screen_text") or seg.get("narration_text", "")
        text = text.replace("\n", "\\N")
        
        events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")
        
        current_time_ms += seg["duration_ms"]
    
    return header + "\n".join(events)


def _format_ass_time(ms: int) -> str:
    """格式化 ASS 时间"""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    centiseconds = (ms % 1000) // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
