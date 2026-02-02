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
        # 获取该段落的选中场景图片配置
        segment_metadata = segment.segment_metadata or {}
        selected_scene_images = segment_metadata.get("selected_scene_images", {})
        
        # 获取该段落的所有图片
        all_images_result = await db.execute(
            select(Asset)
            .where(Asset.segment_id == segment.id)
            .where(Asset.asset_type == AssetType.IMAGE)
        )
        all_images = all_images_result.scalars().all()
        
        # 建立 asset_id -> asset 的映射
        asset_map = {asset.id: asset for asset in all_images}
        
        # 构建场景图片路径列表
        scene_image_paths = []
        
        if selected_scene_images:
            # 使用用户选择的场景图片
            for scene_idx_str, asset_id in sorted(selected_scene_images.items(), key=lambda x: int(x[0])):
                if asset_id in asset_map:
                    scene_image_paths.append({
                        "path": asset_map[asset_id].file_path,
                        "scene_index": int(scene_idx_str)
                    })
        else:
            # 没有选择记录时，回退到旧逻辑：使用每个场景的第一个候选
            scene_first_images = {}  # scene_index -> first asset
            for img in all_images:
                metadata = img.asset_metadata or {}
                scene_idx = metadata.get("scene_index")
                if scene_idx is not None:
                    # 选择每个场景 candidate_index 最小的
                    candidate_idx = metadata.get("candidate_index", 0)
                    if scene_idx not in scene_first_images:
                        scene_first_images[scene_idx] = (candidate_idx, img)
                    elif candidate_idx < scene_first_images[scene_idx][0]:
                        scene_first_images[scene_idx] = (candidate_idx, img)
            
            for scene_idx in sorted(scene_first_images.keys()):
                _, img = scene_first_images[scene_idx]
                scene_image_paths.append({
                    "path": img.file_path,
                    "scene_index": scene_idx
                })
        
        # 如果没有场景图片，回退到选定的单张图片
        if not scene_image_paths:
            if segment.selected_image_asset_id:
                asset_result = await db.execute(
                    select(Asset).where(Asset.id == segment.selected_image_asset_id)
                )
                image_asset = asset_result.scalar_one_or_none()
                if image_asset:
                    scene_image_paths = [{"path": image_asset.file_path, "scene_index": 0}]
        
        # 按 scene_index 排序
        scene_image_paths.sort(key=lambda x: x.get("scene_index", 0))
        image_paths = [x["path"] for x in scene_image_paths]
        
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
            "image_paths": image_paths,  # 多张场景图片路径列表
            "image_path": image_paths[0] if image_paths else None,  # 向后兼容
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
    """解析资产文件路径，处理 storage 前缀，返回绝对路径"""
    path = Path(relative_path)
    if str(path).startswith("storage"):
        # 路径已包含 storage 前缀，使用项目根目录的绝对路径
        return (Path(".") / relative_path).resolve()
    else:
        # 路径是相对于 STORAGE_PATH 的
        return (Path(settings.STORAGE_PATH) / relative_path).resolve()


import re


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


def _split_sentences(text: str) -> List[str]:
    """
    将文本按句子切分
    支持中文和英文标点符号
    """
    if not text:
        return []
    
    # 按中英文句子结束符切分，保留标点
    # 匹配：句号、问号、感叹号（中英文）、省略号
    pattern = r'([^。！？!?.…]+[。！？!?.…]+)'
    sentences = re.findall(pattern, text)
    
    # 如果没有匹配到任何句子（可能没有标点），返回整段
    if not sentences:
        return [text.strip()] if text.strip() else []
    
    # 清理空白
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences


def _wrap_text(text: str, max_chars_per_line: int = 20) -> str:
    """
    将长文本按指定字符数换行
    中文字符和英文字符都按1个字符计算
    """
    if not text:
        return ""
    
    lines = []
    current_line = ""
    
    for char in text:
        current_line += char
        # 简单按字符数换行
        if len(current_line) >= max_chars_per_line:
            lines.append(current_line)
            current_line = ""
    
    if current_line:
        lines.append(current_line)
    
    return "\n".join(lines)


def _format_ass_time_seconds(seconds: float) -> str:
    """将秒数格式化为 ASS 时间格式 (H:MM:SS.CC)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


def _generate_ass_subtitle(
    sentences: List[str],
    duration_seconds: float,
    width: int,
    height: int,
    font_size: int = 40,
    font_color: str = "FFFFFF",
    margin_bottom: int = 80,
    max_chars_per_line: int = 18
) -> str:
    """
    生成 ASS 格式字幕文件内容
    
    Args:
        sentences: 句子列表
        duration_seconds: 总时长（秒）
        width: 视频宽度
        height: 视频高度
        font_size: 字体大小
        font_color: 字体颜色（BGR格式，如 FFFFFF）
        margin_bottom: 底部边距
        max_chars_per_line: 每行最大字符数
    
    Returns:
        ASS 字幕文件内容
    """
    if not sentences:
        return ""
    
    # 计算每个句子的时长（按字数比例分配）
    total_chars = sum(len(s) for s in sentences)
    if total_chars == 0:
        return ""
    
    # ASS 文件头
    ass_content = f"""[Script Info]
Title: Auto Generated Subtitle
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,{font_size},&H00{font_color},&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,{margin_bottom},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    # 为每个句子分配时间并生成字幕条目
    current_time = 0.0
    for sentence in sentences:
        # 按字数比例分配时长
        sentence_duration = (len(sentence) / total_chars) * duration_seconds
        # 确保最短0.5秒
        sentence_duration = max(sentence_duration, 0.5)
        
        start_time = _format_ass_time_seconds(current_time)
        end_time = _format_ass_time_seconds(min(current_time + sentence_duration, duration_seconds))
        
        # 处理换行（如果句子太长）
        display_text = sentence
        if len(sentence) > max_chars_per_line:
            # 在中间位置换行
            lines = []
            current_line = ""
            for char in sentence:
                current_line += char
                if len(current_line) >= max_chars_per_line:
                    lines.append(current_line)
                    current_line = ""
            if current_line:
                lines.append(current_line)
            display_text = "\\N".join(lines)  # ASS 换行符
        
        ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{display_text}\n"
        current_time += sentence_duration
    
    return ass_content


async def _create_segment_video(
    segment: dict,
    config: dict,
    temp_dir: Path,
    index: int
) -> Optional[Path]:
    """创建单个段落的视频片段（支持多场景图片）"""
    image_paths = segment.get("image_paths", [])  # 多张场景图片
    image_path = segment.get("image_path")  # 向后兼容：单张图片
    audio_path = segment.get("audio_path")
    duration_ms = segment.get("duration_ms", 3000)
    duration_seconds = duration_ms / 1000
    narration_text = segment.get("narration_text", "")
    on_screen_text = segment.get("on_screen_text", "")
    
    # 确保有图片列表
    if not image_paths and image_path:
        image_paths = [image_path]
    
    if not image_paths:
        logger.warning(f"段落 {index} 没有图片")
        return None
    
    # 验证所有图片存在
    valid_image_paths = []
    for img_path in image_paths:
        full_path = _resolve_asset_path(img_path)
        if full_path.exists():
            valid_image_paths.append(full_path)
        else:
            logger.warning(f"图片文件不存在: {full_path}")
    
    if not valid_image_paths:
        logger.warning(f"段落 {index} 没有有效的图片文件")
        return None
    
    output_path = temp_dir / f"segment_{index:04d}.mp4"
    
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
    
    # 计算每张图片的显示时长
    num_images = len(valid_image_paths)
    per_image_duration = duration_seconds / num_images
    
    # 如果只有一张图片，使用简单逻辑
    if num_images == 1:
        return await _create_single_image_segment(
            image_path=valid_image_paths[0],
            audio_path=audio_path,
            duration_seconds=duration_seconds,
            narration_text=narration_text,
            on_screen_text=on_screen_text,
            config=config,
            temp_dir=temp_dir,
            output_path=output_path,
            index=index,
            width=width,
            height=height,
            frame_rate=frame_rate
        )
    
    # 多张图片：为每张图片创建子片段，然后合并
    sub_video_paths = []
    for img_idx, img_path in enumerate(valid_image_paths):
        sub_output = temp_dir / f"segment_{index:04d}_scene_{img_idx:02d}.mp4"
        scene_duration = per_image_duration
        
        # 子场景不添加字幕，字幕会在合并后添加（覆盖整个段落时长）
        sub_path = await _create_single_image_segment(
            image_path=img_path,
            audio_path=None,  # 音频稍后在合并时处理
            duration_seconds=scene_duration,
            narration_text="",  # 子场景不添加字幕
            on_screen_text="",  # 子场景不添加屏幕文字
            config=config,
            temp_dir=temp_dir,
            output_path=sub_output,
            index=f"{index}_{img_idx}",
            width=width,
            height=height,
            frame_rate=frame_rate,
            is_sub_segment=True
        )
        if sub_path:
            sub_video_paths.append(sub_path)
    
    if not sub_video_paths:
        logger.warning(f"段落 {index} 没有生成任何场景视频")
        return None
    
    # 合并所有场景视频
    if len(sub_video_paths) == 1:
        # 只有一个场景成功，直接使用
        shutil.copy(sub_video_paths[0], output_path)
    else:
        # 使用 concat 合并多个场景，并添加字幕
        await _concat_scene_videos(
            sub_video_paths, 
            output_path, 
            audio_path,
            duration_seconds,
            narration_text,
            on_screen_text,
            temp_dir, 
            config,
            index,
            width,
            height
        )
    
    return output_path


async def _create_single_image_segment(
    image_path: Path,
    audio_path: Optional[str],
    duration_seconds: float,
    narration_text: str,
    on_screen_text: str,
    config: dict,
    temp_dir: Path,
    output_path: Path,
    index: any,
    width: int,
    height: int,
    frame_rate: str,
    is_sub_segment: bool = False
) -> Optional[Path]:
    """创建单张图片的视频片段"""
    
    # 构建 FFmpeg 命令
    cmd = [settings.FFMPEG_PATH]
    
    # 输入图片（循环）
    cmd.extend(["-loop", "1", "-t", str(duration_seconds)])
    cmd.extend(["-i", str(image_path)])
    
    # 输入音频（如果有）
    has_audio = False
    if audio_path:
        full_audio_path = _resolve_asset_path(audio_path)
        if full_audio_path.exists():
            cmd.extend(["-i", str(full_audio_path)])
            has_audio = True
    
    # 无音频时添加静音输入源（必须在滤镜之前添加）
    if not has_audio:
        cmd.extend([
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100"
        ])
    
    is_portrait = config.get("is_portrait", True)
    
    # Ken Burns 效果配置
    kenburns_enabled = config.get("kenburns_enabled", True)
    kenburns_intensity = config.get("kenburns_intensity", 0.15)  # 0.05-0.3
    
    # 转场效果配置（淡入淡出）
    transition_type = config.get("transition_type", "淡入淡出")
    transition_duration = config.get("transition_duration", 0.3)
    
    # 视频滤镜
    vf_parts = []
    
    if kenburns_enabled:
        # 使用 zoompan 滤镜实现 Ken Burns 效果
        # 注意：使用基于 on (当前帧号) 的线性表达式，避免自引用导致的抖动
        fps = int(frame_rate)
        total_frames = int(duration_seconds * fps)
        
        # 随机选择不同的动效模式（基于 index 确保每个片段不同）
        import hashlib
        effect_seed = int(hashlib.md5(str(index).encode()).hexdigest()[:8], 16) % 4
        
        # 降低动效强度以减少抖动感（原来的 0.15 太强）
        intensity = min(kenburns_intensity, 0.08)
        zoom_start = 1.0
        zoom_end = 1.0 + intensity
        
        # 使用线性插值表达式，基于 on（当前帧号）计算，避免累积误差
        if effect_seed == 0:
            # 模式1: 缓慢放大 + 居中
            zoom_expr = f"{zoom_start}+{intensity}*on/{total_frames}"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif effect_seed == 1:
            # 模式2: 缓慢缩小 + 居中
            zoom_expr = f"{zoom_end}-{intensity}*on/{total_frames}"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif effect_seed == 2:
            # 模式3: 放大 + 轻微向右平移
            zoom_expr = f"{zoom_start}+{intensity}*on/{total_frames}"
            x_expr = f"iw/2-(iw/zoom/2)+{intensity}*iw/3*on/{total_frames}"
            y_expr = "ih/2-(ih/zoom/2)"
        else:
            # 模式4: 放大 + 轻微向左平移
            zoom_expr = f"{zoom_start}+{intensity}*on/{total_frames}"
            x_expr = f"iw/2-(iw/zoom/2)-{intensity}*iw/3*on/{total_frames}"
            y_expr = "ih/2-(ih/zoom/2)"
        
        # zoompan 滤镜 - 先缩放图片以适应输出尺寸
        vf_parts.append(f"scale=8000:-1")
        zoompan_filter = (
            f"zoompan=z='{zoom_expr}':"
            f"x='{x_expr}':"
            f"y='{y_expr}':"
            f"d={total_frames}:"
            f"s={width}x{height}:"
            f"fps={fps}"
        )
        vf_parts.append(zoompan_filter)
    else:
        # 无 Ken Burns，使用普通缩放填充
        vf_parts.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
    
    # 添加淡入淡出转场效果（在每个片段的开头和结尾）
    if transition_type == "淡入淡出" and transition_duration > 0:
        fade_frames = int(transition_duration * int(frame_rate))
        # 淡入（开头）和淡出（结尾）
        vf_parts.append(f"fade=t=in:st=0:d={transition_duration}")
        vf_parts.append(f"fade=t=out:st={duration_seconds - transition_duration}:d={transition_duration}")
    
    # 字幕配置
    subtitle_config = config.get("subtitle", {})
    # burn_subtitle: 是否将字幕烧录到视频中
    burn_subtitle = config.get("burn_subtitle", True)
    subtitle_enabled = subtitle_config.get("enabled", True) if subtitle_config else config.get("subtitle_enabled", True)
    
    # 根据视频宽度计算每行最大字符数（竖屏约20字，横屏约30字）
    max_chars_per_line = 18 if is_portrait else 28
    
    if subtitle_enabled and burn_subtitle:
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
        
        # 添加屏幕文字（顶部）- 使用 textfile 避免转义问题
        if on_screen_text and on_screen_text.strip():
            # 写入临时文件
            on_screen_file = temp_dir / f"onscreen_{index}.txt"
            with open(on_screen_file, "w", encoding="utf-8") as f:
                f.write(on_screen_text.strip())
            # 路径需要转义冒号
            on_screen_file_path = str(on_screen_file.resolve()).replace("\\", "/").replace(":", "\\:")
            # 顶部居中，带背景框
            vf_parts.append(
                f"drawtext=textfile='{on_screen_file_path}':"
                f"fontfile='{font_file}':"
                f"fontsize={on_screen_font_size}:"
                f"fontcolor={on_screen_font_color}:"
                f"x=(w-text_w)/2:"
                f"y={on_screen_margin}:"
                f"box=1:boxcolor={on_screen_bg_color}:boxborderw=10"
            )
        
        # 添加旁白字幕（底部）- 使用 ASS 字幕实现逐句显示
        if narration_text and narration_text.strip():
            # 将旁白按句子切分
            sentences = _split_sentences(narration_text.strip())
            
            if sentences:
                # 生成 ASS 字幕文件
                ass_content = _generate_ass_subtitle(
                    sentences=sentences,
                    duration_seconds=duration_seconds,
                    width=width,
                    height=height,
                    font_size=narration_font_size,
                    font_color="FFFFFF",  # 白色
                    margin_bottom=narration_margin,
                    max_chars_per_line=max_chars_per_line
                )
                
                # 写入 ASS 文件
                ass_file = temp_dir / f"subtitle_{index}.ass"
                with open(ass_file, "w", encoding="utf-8") as f:
                    f.write(ass_content)
                
                # 使用 ass 滤镜，路径需要转义冒号和反斜杠
                ass_file_path = str(ass_file.resolve()).replace("\\", "/").replace(":", "\\:")
                vf_parts.append(f"ass='{ass_file_path}'")
    
    # 合并所有滤镜
    vf = ",".join(vf_parts)
    
    cmd.extend([
        "-vf", vf,
        "-c:v", "libx264",
        "-profile:v", "main",  # 兼容更多播放器
        "-preset", "fast",
        "-crf", "23",
        "-r", frame_rate,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart"  # 支持流式播放和更好的兼容性
    ])
    
    # 音频编码
    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
    else:
        # 静音源已在输入阶段添加，这里只需指定时长和编码
        cmd.extend(["-t", str(duration_seconds), "-c:a", "aac", "-b:a", "128k"])
    
    cmd.extend(["-y", str(output_path)])
    
    logger.debug(f"FFmpeg 命令: {' '.join(cmd)}")
    
    # 执行 FFmpeg
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode != 0:
        logger.error(f"FFmpeg 错误: {process.stderr}")
        raise Exception(f"FFmpeg 错误 (段落 {index}): {process.stderr[:500]}")
    
    return output_path


async def _concat_scene_videos(
    video_paths: List[Path],
    output_path: Path,
    audio_path: Optional[str],
    total_duration: float,
    narration_text: str,
    on_screen_text: str,
    temp_dir: Path,
    config: dict,
    index: int,
    width: int,
    height: int
):
    """合并多个场景视频片段，添加音频和字幕"""
    if not video_paths:
        raise ValueError("没有可合并的场景视频片段")
    
    # 创建文件列表
    concat_file = temp_dir / f"scene_concat_{output_path.stem}.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            f.write(f"file '{vp.name}'\n")
    
    # 确保输出路径是绝对路径
    abs_output_path = output_path.resolve()
    abs_concat_file = concat_file.resolve()
    
    # 构建命令
    cmd = [settings.FFMPEG_PATH]
    
    # 输入：场景视频列表
    cmd.extend(["-f", "concat", "-safe", "0", "-i", str(abs_concat_file)])
    
    # 输入音频（如果有）
    has_audio = False
    if audio_path:
        full_audio_path = _resolve_asset_path(audio_path)
        logger.debug(f"场景合并音频路径: {audio_path} -> {full_audio_path}, 存在: {full_audio_path.exists()}")
        if full_audio_path.exists():
            cmd.extend(["-i", str(full_audio_path)])
            has_audio = True
        else:
            logger.warning(f"音频文件不存在，跳过音频: {full_audio_path}")
    
    # 构建视频滤镜（添加字幕）
    is_portrait = config.get("is_portrait", True)
    subtitle_config = config.get("subtitle", {})
    burn_subtitle = config.get("burn_subtitle", True)
    subtitle_enabled = subtitle_config.get("enabled", True) if subtitle_config else config.get("subtitle_enabled", True)
    
    vf_parts = []
    max_chars_per_line = 18 if is_portrait else 28
    
    if subtitle_enabled and burn_subtitle:
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
        narration_margin = narration_config.get("margin", 80)
        
        # 添加屏幕文字（顶部）
        if on_screen_text and on_screen_text.strip():
            on_screen_file = temp_dir / f"concat_onscreen_{index}.txt"
            with open(on_screen_file, "w", encoding="utf-8") as f:
                f.write(on_screen_text.strip())
            on_screen_file_path = str(on_screen_file.resolve()).replace("\\", "/").replace(":", "\\:")
            vf_parts.append(
                f"drawtext=textfile='{on_screen_file_path}':"
                f"fontfile='{font_file}':"
                f"fontsize={on_screen_font_size}:"
                f"fontcolor={on_screen_font_color}:"
                f"x=(w-text_w)/2:"
                f"y={on_screen_margin}:"
                f"box=1:boxcolor={on_screen_bg_color}:boxborderw=10"
            )
        
        # 添加旁白字幕（底部）- 使用 ASS 字幕
        if narration_text and narration_text.strip():
            sentences = _split_sentences(narration_text.strip())
            if sentences:
                ass_content = _generate_ass_subtitle(
                    sentences=sentences,
                    duration_seconds=total_duration,
                    width=width,
                    height=height,
                    font_size=narration_font_size,
                    font_color="FFFFFF",
                    margin_bottom=narration_margin,
                    max_chars_per_line=max_chars_per_line
                )
                ass_file = temp_dir / f"concat_subtitle_{index}.ass"
                with open(ass_file, "w", encoding="utf-8") as f:
                    f.write(ass_content)
                ass_file_path = str(ass_file.resolve()).replace("\\", "/").replace(":", "\\:")
                vf_parts.append(f"ass='{ass_file_path}'")
    
    # 构建输出命令
    if vf_parts:
        # 需要重新编码以添加字幕滤镜
        vf = ",".join(vf_parts)
        cmd.extend(["-vf", vf])
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
    else:
        # 无字幕，直接复制视频流
        cmd.extend(["-c:v", "copy"])
    
    if has_audio:
        cmd.extend([
            "-c:a", "aac", "-b:a", "128k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest"
        ])
    else:
        # 保留原有的静音音轨
        cmd.extend(["-c:a", "copy"])
    
    cmd.extend(["-y", str(abs_output_path)])
    
    logger.debug(f"FFmpeg scene concat 命令: {' '.join(cmd)}")
    
    # 在 temp_dir 中执行
    process = subprocess.run(cmd, capture_output=True, text=True, cwd=str(temp_dir))
    
    if process.returncode != 0:
        logger.error(f"FFmpeg scene concat 错误: {process.stderr}")
        raise Exception(f"FFmpeg scene concat 错误: {process.stderr[:500]}")
    
    logger.info(f"场景视频合并完成: {output_path}")


async def _concat_videos(
    video_paths: List[Path],
    output_path: Path,
    config: dict,
    temp_dir: Path
):
    """合并多个视频片段
    
    注意：为了性能考虑，使用简单的 concat 合并。
    转场效果通过在每个片段的开头/结尾添加淡入淡出来实现（在 _create_single_image_segment 中处理）
    """
    if not video_paths:
        raise ValueError("没有可合并的视频片段")
    
    # 确保输出路径是绝对路径
    abs_output_path = output_path.resolve()
    
    # 使用简单的 concat 合并（高性能）
    concat_file = temp_dir / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            f.write(f"file '{vp.name}'\n")
    
    abs_concat_file = concat_file.resolve()
    cmd = [
        settings.FFMPEG_PATH,
        "-f", "concat",
        "-safe", "0",
        "-i", str(abs_concat_file),
        "-c", "copy",
        "-movflags", "+faststart",  # 支持流式播放
        "-y", str(abs_output_path)
    ]
    
    logger.debug(f"FFmpeg concat 命令: {' '.join(cmd)}")
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
    """生成 SRT 格式字幕（使用旁白文本）"""
    lines = []
    current_time_ms = 0
    
    for i, seg in enumerate(segments):
        start_time = _format_srt_time(current_time_ms)
        end_time = _format_srt_time(current_time_ms + seg["duration_ms"])
        
        # 使用旁白文本作为字幕内容
        text = seg.get("narration_text", "")
        
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
        start_time = _format_ass_time_ms(current_time_ms)
        end_time = _format_ass_time_ms(current_time_ms + seg["duration_ms"])
        
        # 使用旁白文本作为字幕内容
        text = seg.get("narration_text", "")
        text = text.replace("\n", "\\N")
        
        events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")
        
        current_time_ms += seg["duration_ms"]
    
    return header + "\n".join(events)


def _format_ass_time_ms(ms: float) -> str:
    """格式化 ASS 时间（输入为毫秒）"""
    ms = int(ms)  # 确保是整数
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    centiseconds = (ms % 1000) // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
