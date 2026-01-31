"""
音频生成 Celery 任务
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
def generate_audio_task(self, job_id: int):
    """
    音频生成任务
    
    Args:
        job_id: 任务ID
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_generate_audio_async(self, job_id))


async def _generate_audio_async(task, job_id: int):
    """异步执行音频生成"""
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
            segment_id = params["segment_id"]
            text = params["text"]
            engine = params.get("engine", "free_tts")
            
            # 获取段落
            seg_result = await db.execute(select(Segment).where(Segment.id == segment_id))
            segment = seg_result.scalar_one()
            
            # 准备输出目录
            output_dir = settings.AUDIO_PATH / str(job.project_id) / str(segment_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成音频
            output_format = params.get("output_format", "mp3")
            audio_filename = f"{uuid.uuid4()}.{output_format}"
            audio_path = output_dir / audio_filename
            
            # 根据引擎选择生成方法
            if engine == "gpt_sovits":
                audio_data = await _generate_with_gpt_sovits(text, params)
            else:
                audio_data = await _generate_with_free_tts(text, params)
            
            # 保存音频文件
            if audio_data:
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
                file_size = len(audio_data)
            else:
                file_size = 0
            
            # 获取音频时长
            duration_ms = await _get_audio_duration(audio_path)
            if not duration_ms:
                # 估算时长
                from app.services.audio_generator import estimate_audio_duration
                duration_ms = estimate_audio_duration(text)
            
            # 创建资产记录
            asset = Asset(
                project_id=job.project_id,
                segment_id=segment_id,
                asset_type=AssetType.AUDIO,
                file_path=str(audio_path),
                file_name=audio_filename,
                file_size=file_size,
                duration_ms=duration_ms,
                metadata={
                    "engine": engine,
                    "voice_type": params.get("voice_type"),
                    "speed": params.get("speed"),
                    "volume": params.get("volume"),
                    "pitch": params.get("pitch")
                }
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)
            
            # 更新段落
            segment.audio_asset_id = asset.id
            segment.duration_ms = duration_ms
            segment.status = SegmentStatus.AUDIO_READY
            
            # 更新任务状态
            job.status = JobStatus.SUCCEEDED
            job.progress = 100
            job.finished_at = datetime.utcnow()
            job.result = {
                "asset_id": asset.id,
                "duration_ms": duration_ms
            }
            
            await db.commit()
            
            return {"status": "success", "asset_id": asset.id, "duration_ms": duration_ms}
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            await db.commit()
            
            raise task.retry(exc=e, countdown=60)


async def _generate_with_free_tts(text: str, params: dict) -> bytes:
    """使用免费 TTS 生成音频"""
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
        
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        return audio_data
        
    except ImportError:
        # edge-tts 未安装，返回空
        return b""
    except Exception:
        return b""


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
        result = subprocess.run(
            [
                settings.FFMPEG_PATH.replace("ffmpeg", "ffprobe"),
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ],
            capture_output=True,
            text=True
        )
        duration_seconds = float(result.stdout.strip())
        return int(duration_seconds * 1000)
    except Exception:
        return 0
