"""
文案生成服务 V2
采用分阶段生成策略：先生成大纲，再逐段生成内容
解决长文本生成中断问题
"""
import json
import re
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any
from dataclasses import dataclass, field, asdict

from app.services.deepseek_client import stream_deepseek, call_deepseek

logger = logging.getLogger(__name__)


# ==================== 提示词模板 ====================

OUTLINE_SYSTEM_PROMPT = """你是一个专业的短视频脚本策划者。
你需要根据用户需求，生成一个结构化的脚本大纲。

输出要求（JSON格式）：
{
    "title": "吸引人的标题",
    "hook": "开头钩子文案（3-5秒抓住观众，50字以内）",
    "total_segments": 段落总数（整数），
    "chapters": [
        {
            "chapter_id": 1,
            "chapter_title": "章节标题",
            "summary": "本章节简要内容描述（50字以内）",
            "segment_count": 本章节包含的段落数,
            "mood": "整体氛围"
        }
    ]
}

注意：
- 根据目标时长/字数合理规划章节数（每章约2-5个段落）
- 每个段落约100-200字旁白
- 返回纯JSON，不要有其他文字"""


SEGMENT_SYSTEM_PROMPT = """你是一个专业的短视频脚本创作者，擅长创作"说书"风格的叙事内容。

你正在按章节创作脚本，需要根据大纲生成该章节的详细段落内容。

每个段落必须包含：
1. segment_title: 段落小标题
2. narration_text: 旁白文本（用于配音，100-200字）
3. visual_prompt: 画面提示词（详细的场景描述，用于AI生图，必须包含人物、环境、光线、氛围）
4. on_screen_text: 屏幕金句（可选，10-20字精炼语句）
5. mood: 氛围标签（紧张/温馨/热血/恐怖/轻松/史诗等）
6. shot_type: 镜头类型（远景/中景/近景/特写）

输出格式（JSON数组）：
[
    {
        "segment_title": "...",
        "narration_text": "...",
        "visual_prompt": "...",
        "on_screen_text": "...",
        "mood": "...",
        "shot_type": "..."
    }
]

重要：
- 确保内容与前文衔接自然
- 旁白要适合口语朗读，节奏感强
- visual_prompt 要足够详细，能直接作为 AI 绘图 prompt
- 返回纯JSON数组，不要有其他文字"""


CONTINUATION_SYSTEM_PROMPT = """你需要继续完成一段被截断的内容。

前文内容如下（已生成部分）：
{previous_content}

请直接继续写下去，确保：
1. 内容自然衔接，不要重复前文
2. 保持相同的格式和风格
3. 完成当前正在生成的段落/章节

直接输出续写内容，不要有任何解释。"""


@dataclass
class GenerationProgress:
    """生成进度追踪"""
    phase: str = "init"  # init, outline, segments, complete, error
    current_chapter: int = 0
    total_chapters: int = 0
    current_segment: int = 0
    total_segments: int = 0
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass  
class ScriptOutline:
    """脚本大纲"""
    title: str = ""
    hook: str = ""
    total_segments: int = 0
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptOutline":
        return cls(
            title=data.get("title", ""),
            hook=data.get("hook", ""),
            total_segments=data.get("total_segments", 0),
            chapters=data.get("chapters", [])
        )


def _build_outline_prompt(config: Dict[str, Any], topic: str, additional_instructions: str = "") -> str:
    """构建大纲生成提示词"""
    parts = []
    
    # 基础配置
    if config.get("genre"):
        parts.append(f"题材类型：{config['genre']}")
    if config.get("audience_taste"):
        parts.append(f"受众口味：{config['audience_taste']}")
    if config.get("narrative_perspective"):
        parts.append(f"叙事视角：{config['narrative_perspective']}")
    if config.get("writing_style"):
        parts.append(f"文风：{config['writing_style']}")
    
    # 主线设定
    if config.get("world_setting"):
        parts.append(f"世界观设定：{config['world_setting']}")
    if config.get("golden_finger"):
        parts.append(f"主角金手指：{config['golden_finger']}")
    if config.get("conflict_type"):
        parts.append(f"核心冲突：{config['conflict_type']}")
    
    # 角色
    protagonist = config.get("protagonist", {})
    if protagonist:
        char_info = []
        if protagonist.get("name"):
            char_info.append(f"姓名:{protagonist['name']}")
        if protagonist.get("gender"):
            char_info.append(f"性别:{protagonist['gender']}")
        if protagonist.get("age"):
            char_info.append(f"年龄:{protagonist['age']}")
        if protagonist.get("personality"):
            char_info.append(f"性格:{protagonist['personality']}")
        if char_info:
            parts.append(f"主角设定：{', '.join(char_info)}")
    
    # 节奏
    if config.get("pacing"):
        parts.append(f"叙事节奏：{config['pacing']}")
    if config.get("twist_frequency"):
        parts.append(f"反转频率：{config['twist_frequency']}")
    if config.get("climax_position"):
        parts.append(f"高潮位置：{config['climax_position']}")
    
    # 长度目标 - 这很重要
    target_words = config.get("target_word_count", 0)
    if not target_words and config.get("target_duration_minutes"):
        target_words = config["target_duration_minutes"] * 180
    
    if target_words:
        # 估算章节数：每章约500-800字
        estimated_chapters = max(3, target_words // 600)
        parts.append(f"目标总字数：约{target_words}字")
        parts.append(f"建议章节数：{estimated_chapters}章左右")
    else:
        parts.append("目标：中等长度，约5-8个章节")
    
    # 合规
    compliance = []
    if config.get("no_violence"):
        compliance.append("避免血腥暴力")
    if config.get("no_adult_content"):
        compliance.append("避免成人内容")
    if config.get("no_sensitive_topics"):
        compliance.append("避免敏感话题")
    if compliance:
        parts.append(f"内容规范：{', '.join(compliance)}")
    
    # 主题
    parts.append(f"\n【创作主题】\n{topic}")
    
    if additional_instructions:
        parts.append(f"\n【额外要求】\n{additional_instructions}")
    
    return "\n".join(parts)


def _build_segment_prompt(
    outline: ScriptOutline,
    chapter: Dict[str, Any],
    chapter_index: int,
    previous_segments: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> str:
    """构建段落生成提示词"""
    parts = []
    
    parts.append(f"【脚本标题】{outline.title}")
    parts.append(f"【开头钩子】{outline.hook}")
    
    # 大纲概述
    parts.append("\n【完整大纲】")
    for idx, ch in enumerate(outline.chapters):
        marker = "→" if idx == chapter_index else "  "
        parts.append(f"{marker} 第{ch['chapter_id']}章: {ch['chapter_title']} - {ch['summary']}")
    
    # 当前章节信息
    parts.append(f"\n【当前任务】生成第{chapter['chapter_id']}章：{chapter['chapter_title']}")
    parts.append(f"章节概述：{chapter['summary']}")
    parts.append(f"氛围：{chapter.get('mood', '叙事')}")
    parts.append(f"需要生成的段落数：{chapter['segment_count']}个")
    
    # 前文摘要（如果有）
    if previous_segments:
        parts.append("\n【前文回顾】（最近3个段落）")
        for seg in previous_segments[-3:]:
            parts.append(f"- {seg.get('segment_title', '无标题')}: {seg.get('narration_text', '')[:80]}...")
    
    # 风格要求
    if config.get("writing_style"):
        parts.append(f"\n【文风要求】{config['writing_style']}")
    
    return "\n".join(parts)


def _extract_json(text: str, expect_array: bool = False) -> Any:
    """从文本中提取JSON"""
    text = text.strip()
    
    # 移除 markdown 代码块
    if "```" in text:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1).strip()
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 JSON 对象或数组
    if expect_array:
        match = re.search(r'\[[\s\S]*\]', text)
    else:
        match = re.search(r'\{[\s\S]*\}', text)
    
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    return None


async def _generate_with_retry(
    system_prompt: str,
    user_prompt: str,
    expect_array: bool = False,
    max_retries: int = 2
) -> Any:
    """带重试的生成"""
    for attempt in range(max_retries + 1):
        try:
            response = await call_deepseek(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7 if attempt == 0 else 0.5,
                max_tokens=4096
            )
            
            result = _extract_json(response, expect_array=expect_array)
            if result is not None:
                return result
            
            logger.warning(f"JSON解析失败，尝试 {attempt + 1}/{max_retries + 1}")
            
        except Exception as e:
            logger.error(f"生成失败: {e}")
            if attempt == max_retries:
                raise
    
    return None


async def generate_script_phased(
    config: Dict[str, Any],
    topic: str,
    additional_instructions: str = ""
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    分阶段生成脚本（主入口）
    
    Yields:
        Dict包含：
        - type: "progress" | "outline" | "chapter" | "segments" | "complete" | "error"
        - data: 对应的数据
    """
    all_segments = []
    
    try:
        # ========== 阶段1：生成大纲 ==========
        yield {
            "type": "progress",
            "data": GenerationProgress(
                phase="outline",
                message="正在生成脚本大纲..."
            ).to_dict()
        }
        
        outline_prompt = _build_outline_prompt(config, topic, additional_instructions)
        outline_data = await _generate_with_retry(
            system_prompt=OUTLINE_SYSTEM_PROMPT,
            user_prompt=outline_prompt,
            expect_array=False
        )
        
        if not outline_data:
            yield {
                "type": "error",
                "data": {"message": "大纲生成失败，请重试"}
            }
            return
        
        outline = ScriptOutline.from_dict(outline_data)
        
        yield {
            "type": "outline",
            "data": {
                "title": outline.title,
                "hook": outline.hook,
                "total_segments": outline.total_segments,
                "chapters": outline.chapters
            }
        }
        
        # ========== 阶段2：逐章节生成 ==========
        total_chapters = len(outline.chapters)
        
        for chapter_idx, chapter in enumerate(outline.chapters):
            yield {
                "type": "progress",
                "data": GenerationProgress(
                    phase="segments",
                    current_chapter=chapter_idx + 1,
                    total_chapters=total_chapters,
                    current_segment=len(all_segments),
                    total_segments=outline.total_segments,
                    message=f"正在生成第 {chapter_idx + 1}/{total_chapters} 章：{chapter['chapter_title']}"
                ).to_dict()
            }
            
            segment_prompt = _build_segment_prompt(
                outline=outline,
                chapter=chapter,
                chapter_index=chapter_idx,
                previous_segments=all_segments,
                config=config
            )
            
            chapter_segments = await _generate_with_retry(
                system_prompt=SEGMENT_SYSTEM_PROMPT,
                user_prompt=segment_prompt,
                expect_array=True
            )
            
            if not chapter_segments:
                logger.warning(f"第{chapter_idx + 1}章生成失败，尝试简化生成")
                # 简化重试：生成更少的段落
                chapter_segments = [{
                    "segment_title": chapter["chapter_title"],
                    "narration_text": f"（第{chapter['chapter_id']}章内容待补充）",
                    "visual_prompt": "场景待描述",
                    "mood": chapter.get("mood", "叙事"),
                    "shot_type": "中景"
                }]
            
            # 添加章节信息
            for seg in chapter_segments:
                seg["chapter_id"] = chapter["chapter_id"]
                seg["chapter_title"] = chapter["chapter_title"]
            
            all_segments.extend(chapter_segments)
            
            # 发送本章节完成的段落
            yield {
                "type": "chapter",
                "data": {
                    "chapter_index": chapter_idx,
                    "chapter_id": chapter["chapter_id"],
                    "chapter_title": chapter["chapter_title"],
                    "segments": chapter_segments
                }
            }
        
        # ========== 完成 ==========
        yield {
            "type": "complete",
            "data": {
                "title": outline.title,
                "hook": outline.hook,
                "outline": json.dumps(outline.chapters, ensure_ascii=False),
                "segments": all_segments,
                "total_segments": len(all_segments)
            }
        }
        
    except Exception as e:
        logger.exception("脚本生成失败")
        yield {
            "type": "error",
            "data": {"message": str(e)}
        }


async def generate_script_phased_stream(
    config: Dict[str, Any],
    topic: str,
    additional_instructions: str = ""
) -> AsyncGenerator[str, None]:
    """
    分阶段流式生成（SSE格式输出）
    
    Yields:
        SSE格式的JSON字符串
    """
    async for event in generate_script_phased(config, topic, additional_instructions):
        yield json.dumps(event, ensure_ascii=False)


# ==================== 续写功能 ====================

async def continue_incomplete_content(
    incomplete_content: str,
    context: str = "",
    max_tokens: int = 2048
) -> str:
    """
    续写不完整的内容
    
    Args:
        incomplete_content: 被截断的内容
        context: 上下文信息
        max_tokens: 续写的最大token数
    
    Returns:
        续写的内容（不含原文）
    """
    prompt = f"""以下内容在生成过程中被截断，请继续完成：

{incomplete_content[-2000:]}  # 只取最后2000字符作为上下文

请直接续写，不要重复上面的内容，确保格式一致。"""
    
    response = await call_deepseek(
        system_prompt="你是一个续写助手。直接续写给定的内容，保持格式和风格一致。",
        user_prompt=prompt,
        temperature=0.5,
        max_tokens=max_tokens
    )
    
    return response


async def repair_incomplete_json(
    incomplete_json: str,
    expected_structure: str = "object"
) -> Optional[Dict[str, Any]]:
    """
    修复不完整的JSON
    
    Args:
        incomplete_json: 不完整的JSON字符串
        expected_structure: 期望的结构类型 "object" 或 "array"
    
    Returns:
        修复后的JSON对象
    """
    # 尝试补全常见的截断情况
    repairs = [
        ('"}]', '"}]}'),
        ('"}', '"}]'),
        ('"', '"}]'),
        (',', '}]'),
        ('"]', '"}]'),
    ]
    
    for suffix, replacement in repairs:
        if incomplete_json.rstrip().endswith(suffix.rstrip()):
            try:
                fixed = incomplete_json.rstrip()[:-len(suffix)] + replacement
                return json.loads(fixed)
            except:
                continue
    
    # 尝试找到最后一个完整的元素
    if expected_structure == "array":
        # 找最后一个 },
        last_complete = incomplete_json.rfind('},')
        if last_complete > 0:
            try:
                return json.loads(incomplete_json[:last_complete + 1] + ']')
            except:
                pass
    
    return None
