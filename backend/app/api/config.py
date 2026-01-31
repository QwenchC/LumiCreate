"""
配置管理 API 路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.config import (
    ProjectConfig, ScriptGenerationConfig, SegmenterConfig,
    ComfyUIConfig, TTSConfig, VideoComposerConfig,
    GenreType, AudienceTaste, NarrativePerspective, WritingStyle,
    ImageStyle, VoiceType
)

router = APIRouter()


@router.get("/default")
async def get_default_config():
    """获取默认配置"""
    return ProjectConfig().model_dump()


@router.get("/options")
async def get_config_options():
    """获取所有配置选项（用于前端下拉框）"""
    return {
        "genre_types": [{"value": e.value, "label": e.value} for e in GenreType],
        "audience_tastes": [{"value": e.value, "label": e.value} for e in AudienceTaste],
        "narrative_perspectives": [{"value": e.value, "label": e.value} for e in NarrativePerspective],
        "writing_styles": [{"value": e.value, "label": e.value} for e in WritingStyle],
        "image_styles": [{"value": e.value, "label": e.value} for e in ImageStyle],
        "voice_types": [{"value": e.value, "label": e.value} for e in VoiceType],
    }


@router.get("/templates")
async def get_config_templates():
    """获取配置模板列表"""
    return {
        "templates": [
            {
                "id": "fantasy_power",
                "name": "玄幻爽文",
                "description": "男主逆袭流，节奏快，画面暗黑国风",
                "config": {
                    "script_generation": {
                        "genre": "玄幻",
                        "audience_taste": "爽文",
                        "pacing": "快节奏",
                        "writing_style": "网文"
                    },
                    "comfyui": {
                        "style": "暗黑"
                    }
                }
            },
            {
                "id": "urban_romance",
                "name": "都市言情",
                "description": "都市背景，治愈风格，画面写实",
                "config": {
                    "script_generation": {
                        "genre": "都市",
                        "audience_taste": "治愈",
                        "pacing": "中速",
                        "writing_style": "口语"
                    },
                    "comfyui": {
                        "style": "写实"
                    }
                }
            },
            {
                "id": "suspense_thriller",
                "name": "悬疑推理",
                "description": "烧脑剧情，反转频繁，画面暗黑",
                "config": {
                    "script_generation": {
                        "genre": "悬疑",
                        "audience_taste": "推理烧脑",
                        "pacing": "慢热",
                        "twist_frequency": "高"
                    },
                    "comfyui": {
                        "style": "暗黑"
                    }
                }
            },
            {
                "id": "martial_arts",
                "name": "武侠热血",
                "description": "江湖快意恩仇，画面国风",
                "config": {
                    "script_generation": {
                        "genre": "武侠",
                        "audience_taste": "热血",
                        "pacing": "快节奏",
                        "writing_style": "古风"
                    },
                    "comfyui": {
                        "style": "国风"
                    }
                }
            }
        ]
    }
