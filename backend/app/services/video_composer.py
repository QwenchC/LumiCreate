"""
视频合成服务
使用 FFmpeg 合成最终视频
"""
import logging
import subprocess
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project, ProjectStatus
from app.models.segment import Segment
from app.models.asset import Asset, AssetType
from app.models.job import Job, JobType, JobStatus
from app.core.config import settings
from app.services.audio_generator import estimate_audio_duration

logger = logging.getLogger(__name__)


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


async def execute_video_composition(
    db: AsyncSession,
    job: Job,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    同步执行视频合成任务
    
    Args:
        db: 数据库会话
        job: 任务对象
        progress_callback: 进度回调函数
    
    Returns:
        Dict: 执行结果
    """
    temp_dir = None
    try:
        logger.info(f"开始执行视频合成任务: job_id={job.id}")
        
        # 更新任务状态为运行中
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.progress = 0
        await db.commit()
        
        params = job.params or {}
        segments = params.get("segments", [])
        config = params.get("config", {})
        output_filename = params.get("output_filename", f"output_{job.id}.mp4")
        
        if not segments:
            raise ValueError("没有可合成的段落")
        
        # 准备输出目录
        output_dir = Path(settings.STORAGE_PATH) / "video" / str(job.project_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename
        
        temp_dir = Path(settings.STORAGE_PATH) / "temp" / str(job.id)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 第一步：为每个段落创建视频片段
        segment_videos = []
        total_segments = len(segments)
        
        for i, seg in enumerate(segments):
            progress = int((i / total_segments) * 80)  # 留 20% 给最终合并
            job.progress = progress
            await db.commit()
            logger.info(f"处理段落 {i+1}/{total_segments}, 进度: {progress}%")
            
            segment_video = await _create_segment_video(
                seg, config, temp_dir, i
            )
            if segment_video:
                segment_videos.append(segment_video)
        
        if not segment_videos:
            raise ValueError("没有成功创建任何视频片段")
        
        # 第二步：合并所有片段
        job.progress = 85
        await db.commit()
        logger.info("开始合并视频片段...")
        
        await _concat_videos(segment_videos, output_path, config, temp_dir)
        
        # 第三步：生成字幕文件（可选）
        subtitle_asset = None
        if config.get("subtitle_enabled", True):
            logger.info("生成字幕文件...")
            subtitle_format = config.get("subtitle_format", "srt")
            subtitle_path = await generate_subtitle_file(
                segments, output_path, subtitle_format
            )
            
            # 创建字幕资产
            subtitle_asset = Asset(
                project_id=job.project_id,
                asset_type=AssetType.SUBTITLE,
                file_path=str(subtitle_path.relative_to(settings.STORAGE_PATH)),
                file_name=subtitle_path.name,
                file_size=subtitle_path.stat().st_size if subtitle_path.exists() else 0
            )
            db.add(subtitle_asset)
        
        # 创建视频资产
        video_asset = Asset(
            project_id=job.project_id,
            asset_type=AssetType.VIDEO,
            file_path=str(output_path.relative_to(settings.STORAGE_PATH)),
            file_name=output_filename,
            file_size=output_path.stat().st_size if output_path.exists() else 0,
            asset_metadata={
                "config": config,
                "segment_count": len(segments),
                "duration_ms": sum(seg.get("duration_ms", 0) for seg in segments)
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
        
        # 更新任务状态为成功
        job.status = JobStatus.SUCCEEDED
        job.progress = 100
        job.finished_at = datetime.utcnow()
        job.result = {
            "video_asset_id": video_asset.id,
            "output_path": str(output_path.relative_to(settings.STORAGE_PATH)),
            "subtitle_asset_id": subtitle_asset.id if subtitle_asset else None
        }
        await db.commit()
        
        # 清理临时文件
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        logger.info(f"视频合成成功: video_asset_id={video_asset.id}")
        return {
            "success": True,
            "video_asset_id": video_asset.id,
            "output_path": str(output_path)
        }
        
    except Exception as e:
        logger.error(f"视频合成失败: {str(e)}", exc_info=True)
        
        # 更新任务状态为失败
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.finished_at = datetime.utcnow()
        await db.commit()
        
        # 清理临时文件
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        return {
            "success": False,
            "error": str(e)
        }


def _resolve_asset_path(relative_path: str) -> Path:
    """解析资产文件路径，处理 storage 前缀"""
    path = Path(relative_path)
    if str(path).startswith("storage"):
        # 路径已包含 storage 前缀，直接使用相对于项目根目录的路径
        return Path(".") / relative_path
    else:
        # 路径是相对于 STORAGE_PATH 的
        return Path(settings.STORAGE_PATH) / relative_path


def _escape_ffmpeg_text(text: str) -> str:
    """转义 FFmpeg drawtext 滤镜中的特殊字符"""
    if not text:
        return ""
    # FFmpeg drawtext 需要转义的字符：' : \ 和换行符
    text = text.replace("\\", "\\\\")  # 反斜杠
    text = text.replace("'", "'\\''")  # 单引号
    text = text.replace(":", "\\:")    # 冒号
    text = text.replace("\n", "\\n")   # 换行符
    return text


async def _create_segment_video(
    segment: dict,
    config: dict,
    temp_dir: Path,
    index: int
) -> Optional[Path]:
    """创建单个段落的视频片段"""
    image_path = segment.get("image_path")
    audio_path = segment.get("audio_path")
    duration_ms = segment.get("duration_ms", 3000)
    duration_seconds = duration_ms / 1000
    narration_text = segment.get("narration_text", "")
    on_screen_text = segment.get("on_screen_text", "")
    
    # 构建完整路径（处理 storage 前缀）
    if image_path:
        full_image_path = _resolve_asset_path(image_path)
        if not full_image_path.exists():
            logger.warning(f"图片文件不存在: {full_image_path}")
            return None
    else:
        logger.warning(f"段落 {index} 没有图片")
        return None
    
    output_path = temp_dir / f"segment_{index:04d}.mp4"
    
    # 构建 FFmpeg 命令
    cmd = [settings.FFMPEG_PATH]
    
    # 输入图片（循环）
    cmd.extend(["-loop", "1", "-t", str(duration_seconds)])
    cmd.extend(["-i", str(full_image_path)])
    
    # 输入音频（如果有）
    has_audio = False
    if audio_path:
        full_audio_path = _resolve_asset_path(audio_path)
        if full_audio_path.exists():
            cmd.extend(["-i", str(full_audio_path)])
            has_audio = True
    
    # 视频编码参数
    frame_rate = str(config.get("frame_rate", 30))
    is_portrait = config.get("is_portrait", True)
    
    if is_portrait:
        width, height = 1080, 1920
    else:
        resolution = config.get("resolution", "1080p")
        if resolution == "1080p":
            width, height = 1920, 1080
        else:
            width, height = 1280, 720
    
    # 视频滤镜：缩放并填充（保持比例，黑边填充）
    vf_parts = [f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"]
    
    # 字幕配置
    subtitle_config = config.get("subtitle", {})
    subtitle_enabled = subtitle_config.get("enabled", True) if subtitle_config else config.get("subtitle_enabled", True)
    
    if subtitle_enabled:
        # 字体设置（使用系统中文字体）
        font_file = subtitle_config.get("font_file", "C\\\\:/Windows/Fonts/msyh.ttc") if subtitle_config else "C\\\\:/Windows/Fonts/msyh.ttc"
        
        # 屏幕文字配置（顶部）
        on_screen_config = subtitle_config.get("on_screen", {}) if subtitle_config else {}
        on_screen_font_size = on_screen_config.get("font_size", 48)
        on_screen_font_color = on_screen_config.get("font_color", "white")
        on_screen_bg_color = on_screen_config.get("bg_color", "black@0.6")
        on_screen_margin = on_screen_config.get("margin", 60)
        
        # 旁白字幕配置（底部）
        narration_config = subtitle_config.get("narration", {}) if subtitle_config else {}
        narration_font_size = narration_config.get("font_size", 40)
        narration_font_color = narration_config.get("font_color", "white")
        narration_bg_color = narration_config.get("bg_color", "black@0.5")
        narration_margin = narration_config.get("margin", 80)
        
        # 添加屏幕文字（顶部）
        if on_screen_text and on_screen_text.strip():
            escaped_on_screen = _escape_ffmpeg_text(on_screen_text.strip())
            # 顶部居中，带背景框
            vf_parts.append(
                f"drawtext=text='{escaped_on_screen}':"
                f"fontfile='{font_file}':"
                f"fontsize={on_screen_font_size}:"
                f"fontcolor={on_screen_font_color}:"
                f"x=(w-text_w)/2:"
                f"y={on_screen_margin}:"
                f"box=1:boxcolor={on_screen_bg_color}:boxborderw=10"
            )
        
        # 添加旁白字幕（底部）
        if narration_text and narration_text.strip():
            escaped_narration = _escape_ffmpeg_text(narration_text.strip())
            # 底部居中，带背景框
            vf_parts.append(
                f"drawtext=text='{escaped_narration}':"
                f"fontfile='{font_file}':"
                f"fontsize={narration_font_size}:"
                f"fontcolor={narration_font_color}:"
                f"x=(w-text_w)/2:"
                f"y=h-text_h-{narration_margin}:"
                f"box=1:boxcolor={narration_bg_color}:boxborderw=8"
            )
    
    # 合并所有滤镜
    vf = ",".join(vf_parts)
    
    cmd.extend([
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-r", frame_rate,
        "-pix_fmt", "yuv420p"
    ])
    
    # 音频编码
    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
    else:
        # 无音频时添加静音
        cmd.extend([
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration_seconds}",
            "-c:a", "aac", "-b:a", "128k"
        ])
    
    cmd.extend(["-y", str(output_path)])
    
    logger.debug(f"FFmpeg 命令: {' '.join(cmd)}")
    
    # 执行 FFmpeg
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode != 0:
        logger.error(f"FFmpeg 错误: {process.stderr}")
        raise Exception(f"FFmpeg 错误 (段落 {index}): {process.stderr[:500]}")
    
    return output_path


async def _concat_videos(
    video_paths: List[Path],
    output_path: Path,
    config: dict,
    temp_dir: Path
):
    """合并多个视频片段"""
    if not video_paths:
        raise ValueError("没有可合并的视频片段")
    
    # 创建文件列表
    concat_file = temp_dir / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            # 只使用文件名，因为 concat 列表文件和视频片段在同一目录
            # 这样避免路径拼接问题
            f.write(f"file '{vp.name}'\n")
    
    # 确保输出路径是绝对路径，因为我们要切换工作目录
    abs_output_path = output_path.resolve()
    abs_concat_file = concat_file.resolve()
    
    # 简单 concat
    cmd = [
        settings.FFMPEG_PATH,
        "-f", "concat",
        "-safe", "0",
        "-i", str(abs_concat_file),
        "-c", "copy",
        "-y", str(abs_output_path)
    ]
    
    logger.debug(f"FFmpeg concat 命令: {' '.join(cmd)}")
    
    # 在 temp_dir 中执行，这样 concat 列表中的相对路径才能正确解析
    process = subprocess.run(cmd, capture_output=True, text=True, cwd=str(temp_dir))
    
    if process.returncode != 0:
        logger.error(f"FFmpeg concat 错误: {process.stderr}")
        raise Exception(f"FFmpeg concat 错误: {process.stderr[:500]}")
    
    logger.info(f"视频合并完成: {output_path}")


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
