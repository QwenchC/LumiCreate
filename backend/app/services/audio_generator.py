"""
音频生成服务
支持免费 TTS 和 GPT-SoVITS（预留）
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project
from app.models.segment import Segment, SegmentStatus
from app.models.asset import Asset, AssetType
from app.models.job import Job, JobType, JobStatus
from app.core.config import settings


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


# ============ TTS 引擎实现（占位）============

async def free_tts_generate(text: str, params: dict) -> bytes:
    """
    免费 TTS 生成（占位实现）
    
    后续可以接入：
    - edge-tts（免费）
    - pyttsx3（本地）
    - 云服务免费额度
    """
    # TODO: 实现实际的 TTS 调用
    # 这里返回空字节作为占位
    return b""


async def gpt_sovits_generate(text: str, params: dict) -> bytes:
    """
    GPT-SoVITS 生成（预留）
    
    需要：
    - GPT-SoVITS 服务运行
    - 训练好的音色模型
    """
    if not settings.GPT_SOVITS_API_URL:
        raise ValueError("未配置 GPT_SOVITS_API_URL")
    
    # TODO: 实现 GPT-SoVITS API 调用
    return b""
