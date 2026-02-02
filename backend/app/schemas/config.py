"""
配置相关的 Pydantic Schema
定义丰富的配置系统：文案生成、切分、ComfyUI、语音、合成配置
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


# ============ 文案生成配置（DeepSeek）============

class GenreType(str, Enum):
    """题材/类型"""
    FANTASY = "玄幻"
    MARTIAL_ARTS = "武侠"
    URBAN = "都市"
    SUSPENSE = "悬疑"
    HISTORICAL = "历史"
    SCIFI = "科幻"
    HORROR = "恐怖"
    COMEDY = "轻松搞笑"
    ROMANCE = "言情"
    GAMING = "游戏"


class AudienceTaste(str, Enum):
    """受众口味"""
    CASUAL = "下饭"
    POWER_FANTASY = "爽文"
    MYSTERY = "推理烧脑"
    HEALING = "治愈"
    HOT_BLOODED = "热血"
    TEARJERKER = "虐心"


class NarrativePerspective(str, Enum):
    """叙事视角"""
    FIRST_PERSON = "第一人称"
    THIRD_PERSON = "第三人称"
    NARRATOR = "旁白式"


class WritingStyle(str, Enum):
    """文风"""
    COLLOQUIAL = "口语"
    LITERARY = "文艺"
    CLASSICAL = "古风"
    WEB_NOVEL = "网文"
    DRY_HUMOR = "冷幽默"
    SERIOUS = "严肃纪实"


class Pacing(str, Enum):
    """节奏"""
    SLOW = "慢热"
    MEDIUM = "中速"
    FAST = "快节奏"


class ClimaxPosition(str, Enum):
    """高潮位置"""
    BEGINNING = "开头"
    MIDDLE = "中段"
    END = "结尾"


class CharacterConfig(BaseModel):
    """角色设定"""
    name: Optional[str] = Field(None, description="角色姓名")
    gender: Optional[Literal["男", "女", "未知"]] = Field(None, description="性别")
    age: Optional[str] = Field(None, description="年龄/年龄段")
    personality: Optional[str] = Field(None, description="性格特点")
    background: Optional[str] = Field(None, description="背景故事")


class ScriptGenerationConfig(BaseModel):
    """文案生成配置（DeepSeek）"""
    # 基础设定
    genre: Optional[GenreType] = Field(None, description="题材/类型")
    audience_taste: Optional[AudienceTaste] = Field(None, description="受众口味")
    narrative_perspective: Optional[NarrativePerspective] = Field(None, description="叙事视角")
    writing_style: Optional[WritingStyle] = Field(None, description="文风")
    
    # 主线设定
    world_setting: Optional[str] = Field(None, description="世界观关键词")
    golden_finger: Optional[str] = Field(None, description="金手指/主角优势")
    conflict_type: Optional[str] = Field(None, description="矛盾冲突类型")
    
    # 角色设定
    protagonist: Optional[CharacterConfig] = Field(None, description="主角设定")
    supporting_characters_count: Optional[int] = Field(None, ge=0, le=10, description="配角数量")
    
    # 节奏设定
    pacing: Optional[Pacing] = Field(None, description="节奏")
    twist_frequency: Optional[Literal["低", "中", "高"]] = Field(None, description="反转频率")
    climax_position: Optional[ClimaxPosition] = Field(None, description="高潮位置")
    
    # 长度目标
    target_word_count: Optional[int] = Field(None, ge=500, le=50000, description="总字数目标")
    target_duration_minutes: Optional[int] = Field(None, ge=1, le=60, description="总时长目标（分钟）")
    segment_word_count: Optional[int] = Field(None, ge=50, le=2000, description="每段目标字数")
    
    # 合规设置
    no_violence: bool = Field(True, description="避免过度血腥暴力")
    no_adult_content: bool = Field(True, description="避免成人内容")
    no_sensitive_topics: bool = Field(True, description="避免现实敏感话题")
    
    # 高级设置
    system_prompt_template: Optional[str] = Field(None, description="系统提示词模板")
    require_visual_prompts: bool = Field(True, description="要求输出画面描述")
    require_segment_titles: bool = Field(True, description="要求输出段落标题")


# ============ 切分配置 ============

class SegmentStrategy(str, Enum):
    """切分策略"""
    BY_WORD_COUNT = "按字数阈值"
    BY_SEMANTIC = "按语义"
    BY_SHOT_SCRIPT = "按镜头脚本"


class SegmenterConfig(BaseModel):
    """切分配置"""
    strategy: SegmentStrategy = Field(
        SegmentStrategy.BY_SHOT_SCRIPT, 
        description="切分策略"
    )
    min_segment_length: int = Field(50, ge=20, le=500, description="最小段落字数")
    max_segment_length: int = Field(500, ge=100, le=2000, description="最大段落字数")
    
    # 多场景配置
    scenes_per_segment: int = Field(2, ge=1, le=5, description="每个段落的场景数（生成多少张图片）")
    
    # 必须包含的字段
    require_narration: bool = Field(True, description="必须包含旁白")
    require_visual_prompt: bool = Field(True, description="必须包含画面提示词")
    require_mood: bool = Field(False, description="必须包含氛围标签")
    require_shot_type: bool = Field(False, description="必须包含镜头类型")


# ============ ComfyUI 出图配置 ============

class ImageStyle(str, Enum):
    """画风"""
    CHINESE = "国风"
    CYBER = "赛博"
    REALISTIC = "写实"
    ANIME = "动漫"
    DARK = "暗黑"
    OIL_PAINTING = "油画"
    WATERCOLOR = "水彩"
    MINIMALIST = "极简"


class ImageResolution(str, Enum):
    """分辨率"""
    RES_512 = "512"
    RES_768 = "768"
    RES_1024 = "1024"


class AspectRatio(str, Enum):
    """画面比例"""
    LANDSCAPE = "横屏16:9"
    PORTRAIT = "竖屏9:16"
    SQUARE = "正方形1:1"


class ImageGenerationEngine(str, Enum):
    """图片生成引擎"""
    POLLINATIONS = "pollinations"
    COMFYUI = "comfyui"


class ComfyUIConfig(BaseModel):
    """出图配置（支持 Pollinations 和 ComfyUI）"""
    # 引擎选择
    engine: ImageGenerationEngine = Field(
        ImageGenerationEngine.POLLINATIONS, 
        description="生图引擎：pollinations 或 comfyui"
    )
    
    # Pollinations 特有参数
    pollinations_model: str = Field("zimage", description="Pollinations 模型")
    
    # 工作流
    workflow_id: Optional[str] = Field(None, description="工作流文件名（如 Multi-LoRA-SD1.json）")
    
    # 画风
    style: ImageStyle = Field(ImageStyle.CHINESE, description="画风")
    
    # 分辨率
    resolution: ImageResolution = Field(ImageResolution.RES_1024, description="分辨率")
    aspect_ratio: AspectRatio = Field(AspectRatio.PORTRAIT, description="画面比例")
    
    # 采样参数
    steps: int = Field(20, ge=1, le=100, description="采样步数")
    cfg_scale: float = Field(3.5, ge=1.0, le=20.0, description="CFG Scale")
    sampler: str = Field("euler_ancestral", description="采样器")
    seed: Optional[int] = Field(None, description="随机种子（空为随机）")
    
    # 负面提示词
    negative_prompt: str = Field(
        "low quality, blurry, watermark, text, logo, bad anatomy",
        description="负面提示词"
    )
    
    # 批量生成
    candidates_per_segment: int = Field(3, ge=1, le=10, description="每段候选图数量")
    parallel_generation: bool = Field(False, description="是否并行生成")
    
    # 失败重试
    max_retries: int = Field(3, ge=0, le=10, description="最大重试次数")
    fallback_workflow_id: Optional[str] = Field(None, description="失败时的备用工作流")
    
    # 主体一致性（预留）
    character_lora_id: Optional[str] = Field(None, description="角色LoRA ID（预留）")
    reference_image_id: Optional[str] = Field(None, description="参考图ID（预留）")


# ============ 语音配置 ============

class TTSEngine(str, Enum):
    """TTS 引擎"""
    FREE_TTS = "free_tts"
    GPT_SOVITS = "gpt_sovits"


class VoiceType(str, Enum):
    """音色类型"""
    MALE_YOUNG = "男-青年"
    MALE_MIDDLE = "男-中年"
    MALE_OLD = "男-老年"
    FEMALE_YOUNG = "女-青年"
    FEMALE_MIDDLE = "女-中年"
    FEMALE_OLD = "女-老年"


class AudioFormat(str, Enum):
    """音频格式"""
    WAV = "wav"
    MP3 = "mp3"


class TTSConfig(BaseModel):
    """语音配置"""
    # 引擎选择
    engine: TTSEngine = Field(TTSEngine.FREE_TTS, description="TTS引擎")
    
    # 音色
    voice_type: VoiceType = Field(VoiceType.MALE_YOUNG, description="音色类型")
    custom_voice_id: Optional[str] = Field(None, description="自定义音色ID（GPT-SoVITS）")
    
    # 参数
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    volume: float = Field(1.0, ge=0.1, le=2.0, description="音量")
    pitch: float = Field(1.0, ge=0.5, le=2.0, description="音调")
    
    # 输出格式
    output_format: AudioFormat = Field(AudioFormat.MP3, description="输出格式")
    
    # 断句策略
    pause_between_sentences: float = Field(0.3, ge=0.0, le=2.0, description="句间停顿（秒）")
    
    # 情绪（预留）
    emotion: Optional[str] = Field(None, description="情绪标签（预留）")


# ============ 合成配置 ============

class VideoFrameRate(str, Enum):
    """帧率"""
    FPS_24 = "24"
    FPS_30 = "30"
    FPS_60 = "60"


class VideoResolution(str, Enum):
    """视频分辨率"""
    RES_720P = "720p"
    RES_1080P = "1080p"


class TransitionType(str, Enum):
    """转场类型"""
    FADE = "淡入淡出"
    CUT = "硬切"
    PUSH = "推拉"
    ZOOM = "缩放"


class SubtitlePosition(str, Enum):
    """字幕位置"""
    BOTTOM = "底部"
    TOP = "顶部"
    CENTER = "居中"


class VideoComposerConfig(BaseModel):
    """视频合成配置"""
    # 基础参数
    frame_rate: VideoFrameRate = Field(VideoFrameRate.FPS_30, description="帧率")
    resolution: VideoResolution = Field(VideoResolution.RES_1080P, description="分辨率")
    is_portrait: bool = Field(True, description="是否竖屏（1080x1920）")
    
    # 转场
    transition_type: TransitionType = Field(TransitionType.FADE, description="转场类型")
    transition_duration: float = Field(0.3, ge=0.0, le=2.0, description="转场时长（秒）")
    
    # 图片动效（Ken Burns 效果）
    kenburns_enabled: bool = Field(True, description="是否启用图片动效（缓慢推拉缩放）")
    kenburns_intensity: float = Field(0.15, ge=0.05, le=0.3, description="动效强度（0.05-0.3）")
    
    # 背景音乐
    bgm_enabled: bool = Field(False, description="是否启用背景音乐")
    bgm_asset_id: Optional[int] = Field(None, description="背景音乐资产ID")
    bgm_volume: float = Field(0.3, ge=0.0, le=1.0, description="背景音乐音量")
    bgm_ducking: bool = Field(True, description="语音时降低BGM音量")
    
    # 字幕
    subtitle_enabled: bool = Field(True, description="是否启用字幕")
    subtitle_format: Literal["srt", "ass"] = Field("srt", description="字幕格式")
    subtitle_font: str = Field("Microsoft YaHei", description="字幕字体")
    subtitle_font_size: int = Field(48, ge=12, le=120, description="字幕字号")
    subtitle_color: str = Field("#FFFFFF", description="字幕颜色")
    subtitle_outline: bool = Field(True, description="字幕描边")
    subtitle_position: SubtitlePosition = Field(SubtitlePosition.BOTTOM, description="字幕位置")
    
    # 水印
    watermark_enabled: bool = Field(False, description="是否启用水印")
    watermark_text: Optional[str] = Field(None, description="水印文字")
    
    # 时长计算
    min_segment_duration: float = Field(1.5, ge=0.5, le=10.0, description="最小段落展示时长（秒）")
    segment_padding: float = Field(0.3, ge=0.0, le=2.0, description="段落时长补充（秒）")
    fallback_chars_per_second: float = Field(4.5, ge=1.0, le=10.0, description="无音频时的字数/秒估算")


# ============ 完整项目配置 ============

class ProjectConfig(BaseModel):
    """完整项目配置"""
    script_generation: ScriptGenerationConfig = Field(
        default_factory=ScriptGenerationConfig,
        description="文案生成配置"
    )
    segmenter: SegmenterConfig = Field(
        default_factory=SegmenterConfig,
        description="切分配置"
    )
    image_generation: ComfyUIConfig = Field(
        default_factory=ComfyUIConfig,
        description="出图配置（支持 Pollinations.ai 和 ComfyUI）"
    )
    # 保留 comfyui 字段别名以兼容旧数据
    comfyui: Optional[ComfyUIConfig] = Field(
        default=None,
        description="（已废弃，请使用 image_generation）ComfyUI出图配置"
    )
    tts: TTSConfig = Field(
        default_factory=TTSConfig,
        description="语音配置"
    )
    video_composer: VideoComposerConfig = Field(
        default_factory=VideoComposerConfig,
        description="视频合成配置"
    )


# ============ AI 助填相关 ============

class AIFillRequest(BaseModel):
    """AI 助填请求"""
    description: str = Field(
        ..., 
        min_length=10,
        max_length=2000,
        description="用户描述想要的文案/视频风格",
        json_schema_extra={
            "examples": [
                "我想做玄幻爽文风，下饭解说，男主从底层逆袭，20分钟左右，节奏快，画面偏国风暗黑。"
            ]
        }
    )
    only_fill_empty: bool = Field(True, description="只填充空字段")


class AIFillResponse(BaseModel):
    """AI 助填响应"""
    suggested_config: ProjectConfig = Field(..., description="建议的配置")
    explanation: Optional[str] = Field(None, description="AI 对配置的解释")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
