"""
AI 助填服务
使用 DeepSeek 根据用户描述生成配置建议
"""
import json
import logging
import re
from typing import Dict, Any, Optional

from app.schemas.config import ProjectConfig, AIFillResponse
from app.services.deepseek_client import call_deepseek

logger = logging.getLogger(__name__)


AI_FILL_SYSTEM_PROMPT = """你是一个专业的视频内容创作助手。用户会描述他们想要创作的视频风格和内容，你需要根据描述生成合适的配置参数。

你需要返回一个 JSON 格式的配置。重要：所有枚举值必须严格使用下列指定的中文值！

## 配置结构和可选值

### script_generation (文案生成配置)
- genre: "玄幻" | "武侠" | "都市" | "悬疑" | "历史" | "科幻" | "恐怖" | "轻松搞笑" | "言情" | "游戏" | null
- audience_taste: "下饭" | "爽文" | "推理烧脑" | "治愈" | "热血" | "虐心" | null
- narrative_perspective: "第一人称" | "第三人称" | "旁白式" | null
- writing_style: "口语" | "文艺" | "古风" | "网文" | "冷幽默" | "严肃纪实" | null
- pacing: "慢热" | "中速" | "快节奏" | null
- climax_position: "开头" | "中段" | "结尾" | null
- twist_frequency: "低" | "中" | "高" | null
- world_setting: 字符串，如"修真世界"、"末日废土" | null
- golden_finger: 字符串，如"系统"、"重生记忆" | null
- conflict_type: 字符串，如"复仇"、"夺宝" | null
- protagonist: 对象 {name, gender("男"|"女"|"未知"), age, personality, background} | null
- supporting_characters_count: 数字 0-10 | null
- target_word_count: 数字 500-50000 | null
- target_duration_minutes: 数字 1-60 | null
- segment_word_count: 数字 50-2000 | null
- no_violence: 布尔值，默认 true
- no_adult_content: 布尔值，默认 true
- no_sensitive_topics: 布尔值，默认 true
- require_visual_prompts: 布尔值，默认 true
- require_segment_titles: 布尔值，默认 true

### segmenter (切分配置)
- strategy: "按字数阈值" | "按语义" | "按镜头脚本"
- min_segment_length: 数字 20-500，默认 50
- max_segment_length: 数字 100-2000，默认 500
- require_narration: 布尔值，默认 true
- require_visual_prompt: 布尔值，默认 true
- require_mood: 布尔值，默认 false
- require_shot_type: 布尔值，默认 false

### comfyui (出图配置)
- style: "国风" | "赛博" | "写实" | "动漫" | "暗黑" | "油画" | "水彩" | "极简"
- resolution: "512" | "768" | "1024"（必须是字符串！）
- aspect_ratio: "横屏16:9" | "竖屏9:16" | "正方形1:1"
- steps: 数字 1-100，默认 20
- cfg_scale: 数字 1.0-20.0，默认 7.0
- sampler: "euler_ancestral" | "euler" | "dpmpp_2m" | "dpmpp_sde" | "ddim"
- negative_prompt: 字符串
- candidates_per_segment: 数字 1-10，默认 3
- parallel_generation: 布尔值，默认 false
- max_retries: 数字 0-10，默认 3

### tts (语音配置)
- engine: "free_tts" | "gpt_sovits"
- voice_type: "男-青年" | "男-中年" | "男-老年" | "女-青年" | "女-中年" | "女-老年"
- speed: 数字 0.5-2.0，默认 1.0（必须是数字！）
- volume: 数字 0.1-2.0，默认 1.0
- pitch: 数字 0.5-2.0，默认 1.0
- output_format: "mp3" | "wav"
- pause_between_sentences: 数字 0.0-2.0，默认 0.3

### video_composer (视频合成配置)
- frame_rate: "24" | "30" | "60"（必须是字符串！）
- resolution: "720p" | "1080p"
- is_portrait: 布尔值，默认 true（竖屏）
- transition_type: "淡入淡出" | "硬切" | "推拉" | "缩放"
- transition_duration: 数字 0.0-2.0，默认 0.3
- bgm_enabled: 布尔值，默认 false
- bgm_volume: 数字 0.0-1.0，默认 0.3
- bgm_ducking: 布尔值，默认 true
- subtitle_enabled: 布尔值，默认 true
- subtitle_format: "srt" | "ass"
- subtitle_font: 字符串，默认 "Microsoft YaHei"
- subtitle_font_size: 数字 12-120，默认 48
- subtitle_color: 字符串，如 "#FFFFFF"
- subtitle_outline: 布尔值，默认 true
- subtitle_position: "底部" | "顶部" | "居中"
- watermark_enabled: 布尔值，默认 false
- min_segment_duration: 数字 0.5-10.0，默认 1.5
- segment_padding: 数字 0.0-2.0，默认 0.3
- fallback_chars_per_second: 数字 1.0-10.0，默认 4.5

## 返回格式
```json
{
    "config": {
        "script_generation": {...},
        "segmenter": {...},
        "comfyui": {...},
        "tts": {...},
        "video_composer": {...}
    },
    "explanation": "简短解释为什么这样配置",
    "confidence": 0.0-1.0
}
```

重要提醒：
1. 所有枚举值必须严格使用上述列出的中文值
2. resolution 和 frame_rate 必须是字符串类型
3. speed、volume、pitch 等必须是数字类型
4. 只返回 JSON，不要有任何其他文字"""


# 值映射表，用于修正 AI 返回的不规范值
VALUE_MAPPINGS = {
    "segmenter.strategy": {
        "scene_based": "按镜头脚本",
        "by_scene": "按镜头脚本",
        "semantic": "按语义",
        "by_semantic": "按语义",
        "word_count": "按字数阈值",
        "by_word_count": "按字数阈值",
    },
    "comfyui.resolution": {
        "1920x1080": "1024",
        "1080x1920": "1024",
        "1280x720": "768",
        "720x1280": "768",
        "1024x1024": "1024",
        "512x512": "512",
        "768x768": "768",
    },
    "comfyui.style": {
        "chinese": "国风",
        "ink": "国风",
        "水墨": "国风",
        "水墨国风": "国风",
        "cyber": "赛博",
        "cyberpunk": "赛博",
        "realistic": "写实",
        "anime": "动漫",
        "dark": "暗黑",
        "oil": "油画",
        "oil_painting": "油画",
        "watercolor": "水彩",
        "minimal": "极简",
    },
    "video_composer.transition_type": {
        "fade": "淡入淡出",
        "cut": "硬切",
        "push": "推拉",
        "zoom": "缩放",
    },
    "video_composer.subtitle_position": {
        "bottom": "底部",
        "top": "顶部",
        "center": "居中",
    },
    "tts.engine": {
        "edge_tts": "free_tts",
        "edge-tts": "free_tts",
        "sovits": "gpt_sovits",
        "gpt-sovits": "gpt_sovits",
    },
}


def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """规范化配置值，修正 AI 返回的不规范值"""
    
    def normalize_value(path: str, value: Any) -> Any:
        # 检查是否需要映射
        if path in VALUE_MAPPINGS and isinstance(value, str):
            mapped = VALUE_MAPPINGS[path].get(value.lower(), value)
            if mapped != value:
                logger.info(f"值映射: {path}: {value} -> {mapped}")
            return mapped
        
        # 特殊处理：frame_rate 需要是字符串
        if path == "video_composer.frame_rate" and isinstance(value, int):
            return str(value)
        
        # 特殊处理：resolution 需要是字符串
        if path == "comfyui.resolution" and isinstance(value, int):
            return str(value)
        
        # 特殊处理：speed/volume/pitch 需要是数字
        if path in ["tts.speed", "tts.volume", "tts.pitch"]:
            if isinstance(value, str):
                mapping = {"slow": 0.8, "medium": 1.0, "fast": 1.2, "normal": 1.0}
                return mapping.get(value.lower(), 1.0)
        
        # 特殊处理：protagonist.age 需要是字符串
        if path == "script_generation.protagonist.age" and isinstance(value, (int, float)):
            return str(int(value)) + "岁"
        
        # 特殊处理：protagonist.name 需要是字符串
        if path == "script_generation.protagonist.name" and not isinstance(value, str):
            return str(value) if value else None
        
        return value
    
    def process_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        result = {}
        for key, value in d.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result[key] = process_dict(value, path)
            else:
                result[key] = normalize_value(path, value)
        return result
    
    return process_dict(config)


async def ai_fill_config(
    description: str,
    current_config: Optional[Dict[str, Any]] = None,
    only_fill_empty: bool = True
) -> AIFillResponse:
    """
    AI 助填配置
    
    Args:
        description: 用户对想要的视频/文案的描述
        current_config: 当前已有的配置
        only_fill_empty: 是否只填充空字段
    
    Returns:
        AIFillResponse: 建议的配置和解释
    """
    user_prompt = f"""用户描述：{description}

请根据这个描述生成合适的视频创作配置。返回格式：
{{
    "config": {{ ... 完整配置 ... }},
    "explanation": "简短解释为什么这样配置",
    "confidence": 0.0-1.0 的置信度
}}"""

    try:
        logger.info(f"开始 AI 助填，用户描述: {description[:100]}...")
        
        response = await call_deepseek(
            system_prompt=AI_FILL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.7
        )
        
        logger.info(f"DeepSeek 响应长度: {len(response)}")
        logger.debug(f"DeepSeek 原始响应: {response[:500]}...")
        
        # 尝试从响应中提取 JSON
        # 有时候 AI 会返回带 markdown 代码块的 JSON
        json_str = response
        if "```json" in response:
            match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if match:
                json_str = match.group(1)
        elif "```" in response:
            match = re.search(r'```\s*([\s\S]*?)\s*```', response)
            if match:
                json_str = match.group(1)
        
        # 解析响应
        result = json.loads(json_str)
        logger.info(f"JSON 解析成功，包含字段: {list(result.keys())}")
        
        # 规范化配置值
        raw_config = result.get("config", {})
        normalized_config = _normalize_config(raw_config)
        logger.info("配置值已规范化")
        
        suggested_config = ProjectConfig(**normalized_config)
        
        # 如果只填充空字段，需要合并配置
        if only_fill_empty and current_config:
            suggested_dict = suggested_config.model_dump()
            merged_config = _merge_configs(current_config, suggested_dict, only_fill_empty)
            suggested_config = ProjectConfig(**merged_config)
        
        return AIFillResponse(
            suggested_config=suggested_config,
            explanation=result.get("explanation", ""),
            confidence=result.get("confidence", 0.8)
        )
        
    except json.JSONDecodeError as e:
        # 如果解析失败，返回默认配置
        logger.error(f"JSON 解析失败: {e}")
        logger.error(f"原始响应: {response if 'response' in dir() else 'N/A'}")
        return AIFillResponse(
            suggested_config=ProjectConfig(),
            explanation=f"AI 解析失败（JSON格式错误）：{str(e)}",
            confidence=0.3
        )
    except Exception as e:
        logger.error(f"AI 助填发生异常: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return AIFillResponse(
            suggested_config=ProjectConfig(),
            explanation=f"发生错误：{type(e).__name__}: {str(e)}",
            confidence=0.0
        )


def _merge_configs(
    current: Dict[str, Any], 
    suggested: Dict[str, Any], 
    only_fill_empty: bool
) -> Dict[str, Any]:
    """合并配置，支持只填充空字段模式"""
    result = {}
    
    for key in set(list(current.keys()) + list(suggested.keys())):
        current_value = current.get(key)
        suggested_value = suggested.get(key)
        
        if isinstance(current_value, dict) and isinstance(suggested_value, dict):
            # 递归合并嵌套字典
            result[key] = _merge_configs(current_value, suggested_value, only_fill_empty)
        elif only_fill_empty:
            # 只填充空字段
            if current_value is None or current_value == "" or current_value == {}:
                result[key] = suggested_value
            else:
                result[key] = current_value
        else:
            # 完全覆盖
            result[key] = suggested_value if suggested_value is not None else current_value
    
    return result
