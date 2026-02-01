"""
音频生成服务
支持免费 TTS 和 GPT-SoVITS（预留）
"""
import logging
from datetime import datetime
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


async def generate_segment_audio(
    db: AsyncSession,
    segment: Segment,
    override_text: Optional[str] = None
) -> Job:
    """
    为段落生成音频
    
    Args:
        db: 数据库会话
        segment: 段落对象
        override_text: 覆盖的文本
    
    Returns:
        Job: 创建的任务对象
    """
    # 获取项目配置
    project_result = await db.execute(
        select(Project).where(Project.id == segment.project_id)
    )
    project = project_result.scalar_one()
    tts_config = project.project_config.get("tts", {})
    
    # 构建任务参数
    text = override_text or segment.narration_text
    
    job_params = {
        "segment_id": segment.id,
        "text": text,
        "engine": tts_config.get("engine", "free_tts"),
        "voice_type": tts_config.get("voice_type", "男-青年"),
        "custom_voice_id": tts_config.get("custom_voice_id"),
        "speed": tts_config.get("speed", 1.0),
        "volume": tts_config.get("volume", 1.0),
        "pitch": tts_config.get("pitch", 1.0),
        "output_format": tts_config.get("output_format", "mp3"),
        "pause_between_sentences": tts_config.get("pause_between_sentences", 0.3)
    }
    
    # 创建任务
    job = Job(
        project_id=segment.project_id,
        segment_id=segment.id,
        job_type=JobType.TTS,
        status=JobStatus.QUEUED,
        params=job_params
    )
    db.add(job)
    
    # 更新段落状态
    segment.status = SegmentStatus.GENERATING_AUDIO
    
    await db.commit()
    await db.refresh(job)
    
    # TODO: 提交到 Celery 队列
    
    return job


async def execute_audio_generation(
    db: AsyncSession,
    job: Job
) -> Dict[str, Any]:
    """
    同步执行音频生成任务
    
    Args:
        db: 数据库会话
        job: 任务对象
    
    Returns:
        Dict: 执行结果
    """
    try:
        logger.info(f"开始执行音频生成任务: job_id={job.id}")
        
        # 更新任务状态为运行中
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        await db.commit()
        
        params = job.params or {}
        text = params.get("text", "")
        engine = params.get("engine", "free_tts")
        
        if not text:
            raise ValueError("音频文本为空")
        
        # 获取段落
        segment_result = await db.execute(
            select(Segment).where(Segment.id == job.segment_id)
        )
        segment = segment_result.scalar_one_or_none()
        if not segment:
            raise ValueError(f"段落不存在: {job.segment_id}")
        
        # 根据引擎生成音频
        logger.info(f"使用 {engine} 引擎生成音频")
        if engine == "free_tts":
            audio_data = await _generate_with_edge_tts(text, params)
        elif engine == "gpt_sovits":
            audio_data = await _generate_with_gpt_sovits(text, params)
        else:
            raise ValueError(f"不支持的 TTS 引擎: {engine}")
        
        if not audio_data:
            raise ValueError("生成的音频数据为空")
        
        # 保存音频文件
        output_format = params.get("output_format", "mp3")
        audio_dir = Path(settings.STORAGE_PATH) / "audio" / str(job.project_id) / str(segment.id)
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / f"audio.{output_format}"
        audio_path.write_bytes(audio_data)
        logger.info(f"音频文件已保存: {audio_path}")
        
        # 获取音频时长
        duration_ms = await _get_audio_duration(audio_path)
        if duration_ms == 0:
            # 如果无法获取真实时长，估算一个
            duration_ms = estimate_audio_duration(text)
        
        # 创建资产记录
        asset = Asset(
            project_id=job.project_id,
            segment_id=segment.id,
            asset_type=AssetType.AUDIO,
            file_path=str(audio_path.relative_to(settings.STORAGE_PATH)),
            file_name=f"audio.{output_format}",
            file_size=len(audio_data),
            asset_metadata={
                "duration_ms": duration_ms,
                "format": output_format,
                "engine": engine,
                "voice_type": params.get("voice_type")
            }
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        
        # 更新段落
        segment.audio_asset_id = asset.id
        segment.duration_ms = duration_ms
        segment.status = SegmentStatus.AUDIO_READY
        
        # 更新任务状态为成功
        job.status = JobStatus.SUCCEEDED
        job.progress = 100
        job.finished_at = datetime.utcnow()
        job.result = {
            "asset_id": asset.id,
            "duration_ms": duration_ms
        }
        await db.commit()
        
        logger.info(f"音频生成成功: asset_id={asset.id}, duration={duration_ms}ms")
        return {
            "success": True,
            "asset_id": asset.id,
            "duration_ms": duration_ms,
            "file_path": str(audio_path)
        }
        
    except Exception as e:
        logger.error(f"音频生成失败: {str(e)}", exc_info=True)
        
        # 更新任务状态为失败
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.finished_at = datetime.utcnow()
        await db.commit()
        
        return {
            "success": False,
            "error": str(e)
        }


async def _generate_with_edge_tts(text: str, params: dict) -> bytes:
    """使用 edge-tts 生成音频"""
    try:
        import edge_tts
        
        # 根据音色类型选择语音
        voice_map = {
            "男-青年": "zh-CN-YunxiNeural",
            "男-中年": "zh-CN-YunjianNeural",
            "男-老年": "zh-CN-YunyeNeural",
            "女-青年": "zh-CN-XiaoxiaoNeural",
            "女-中年": "zh-CN-XiaoyiNeural",
            "女-老年": "zh-CN-XiaoshuangNeural"
        }
        voice = voice_map.get(params.get("voice_type", "男-青年"), "zh-CN-YunxiNeural")
        
        # 调整语速
        rate = params.get("speed", 1.0)
        rate_str = f"+{int((rate-1)*100)}%" if rate >= 1 else f"{int((rate-1)*100)}%"
        
        logger.info(f"edge-tts: voice={voice}, rate={rate_str}, text_len={len(text)}")
        
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        logger.info(f"edge-tts 生成完成: {len(audio_data)} bytes")
        return audio_data
        
    except ImportError as e:
        logger.error("edge-tts 未安装")
        raise ValueError("edge-tts 未安装，请运行: pip install edge-tts")
    except Exception as e:
        logger.error(f"edge-tts 生成失败: {str(e)}")
        raise


async def _generate_with_gpt_sovits(text: str, params: dict) -> bytes:
    """使用 GPT-SoVITS 生成音频"""
    import httpx
    
    if not settings.GPT_SOVITS_API_URL:
        raise ValueError("未配置 GPT_SOVITS_API_URL")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.GPT_SOVITS_API_URL}/tts",
            json={
                "text": text,
                "voice_id": params.get("custom_voice_id"),
                "speed": params.get("speed", 1.0)
            }
        )
        response.raise_for_status()
        return response.content


async def _get_audio_duration(audio_path: Path) -> int:
    """获取音频时长（毫秒）"""
    try:
        import subprocess
        
        ffprobe_path = settings.FFMPEG_PATH.replace("ffmpeg", "ffprobe")
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            duration_seconds = float(result.stdout.strip())
            return int(duration_seconds * 1000)
    except Exception as e:
        logger.warning(f"获取音频时长失败: {str(e)}")
    return 0


async def generate_all_audio(
    db: AsyncSession,
    project: Project,
    segment_ids: Optional[List[int]] = None
) -> List[Job]:
    """
    批量生成所有段落的音频
    
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
    
    jobs = []
    for segment in segments:
        job = await generate_segment_audio(db, segment)
        jobs.append(job)
    
    return jobs


def estimate_audio_duration(text: str, chars_per_second: float = 4.5) -> int:
    """
    估算音频时长（毫秒）
    
    Args:
        text: 文本内容
        chars_per_second: 每秒字数（默认 4.5）
    
    Returns:
        int: 估算的时长（毫秒）
    """
    # 移除空白字符
    clean_text = text.replace(" ", "").replace("\n", "")
    char_count = len(clean_text)
    
    duration_seconds = char_count / chars_per_second
    return int(duration_seconds * 1000)
