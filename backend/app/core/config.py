"""
应用配置管理
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path


class Settings(BaseSettings):
    """应用全局配置"""
    
    # 基础配置
    APP_NAME: str = "LumiCreate"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./lumicreate.db"
    
    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS 配置
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # 存储配置
    STORAGE_PATH: Path = Path("./storage")
    IMAGES_PATH: Path = Path("./storage/images")
    AUDIO_PATH: Path = Path("./storage/audio")
    VIDEO_PATH: Path = Path("./storage/video")
    TEMP_PATH: Path = Path("./storage/temp")
    
    # DeepSeek API 配置
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    # ComfyUI 配置
    COMFYUI_API_URL: str = "http://localhost:8188"
    COMFYUI_OUTPUT_PATH: Path = Path("./comfyui_output")
    
    # TTS 配置（占位，后续支持 GPT-SoVITS）
    TTS_ENGINE: str = "free_tts"  # free_tts | gpt_sovits
    TTS_DEFAULT_VOICE: str = "male_1"
    TTS_SPEED: float = 1.0
    
    # GPT-SoVITS 配置（预埋）
    GPT_SOVITS_API_URL: Optional[str] = None
    
    # FFmpeg 配置
    FFMPEG_PATH: str = "ffmpeg"
    
    # 任务配置
    MAX_CONCURRENT_TASKS: int = 3
    TASK_TIMEOUT: int = 3600  # 1小时
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 确保存储目录存在
for path in [settings.STORAGE_PATH, settings.IMAGES_PATH, 
             settings.AUDIO_PATH, settings.VIDEO_PATH, settings.TEMP_PATH]:
    path.mkdir(parents=True, exist_ok=True)
