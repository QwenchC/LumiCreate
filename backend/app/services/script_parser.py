"""
文案解析与切分服务
将原始文本或结构化内容转换为段落
"""
import json
import re
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.models.project import Project
from app.models.segment import Segment, SegmentStatus
from app.services.deepseek_client import call_deepseek_with_json_output


PARSE_SYSTEM_PROMPT = """你是一个专业的视频脚本分析师。你需要将用户提供的文本内容切分成适合视频制作的段落。

每个段落应该包含：
1. segment_title: 段落标题（简短概括）
2. narration_text: 旁白文本（用于配音，必须）
3. visual_prompt: 画面提示词（用于AI出图，必须，应该是详细的场景描述，适合作为Stable Diffusion prompt）
4. on_screen_text: 屏幕金句（可选，最能代表这段的一句话）
5. mood: 氛围标签（紧张/温馨/热血/恐怖/轻松/悲伤/神秘等）
6. shot_type: 镜头类型（远景/全景/中景/近景/特写）

切分原则：
- 每段旁白控制在 50-300 字左右
- 场景/情绪/节奏转换处应该分段
- 每个画面提示词要具体，包含主体、环境、氛围、光线

返回 JSON 数组格式：
{
    "segments": [
        {
            "segment_title": "...",
            "narration_text": "...",
            "visual_prompt": "...",
            "on_screen_text": "...",
            "mood": "...",
            "shot_type": "..."
        }
    ]
}"""


async def parse_script_to_segments(
    db: AsyncSession,
    project: Project,
    raw_text: str
) -> List[Segment]:
    """
    解析文本并创建段落
    
    Args:
        db: 数据库会话
        project: 项目对象
        raw_text: 原始文本
    
    Returns:
        List[Segment]: 创建的段落列表
    """
    # 获取切分配置
    segmenter_config = project.project_config.get("segmenter", {})
    
    min_length = segmenter_config.get("min_segment_length", 50)
    max_length = segmenter_config.get("max_segment_length", 500)
    
    user_prompt = f"""请将以下文本切分成视频段落。

切分要求：
- 每段旁白约 {min_length}-{max_length} 字
- 保持叙事连贯性
- 在情绪/场景转换处分段

原文内容：
{raw_text}"""

    # 调用 DeepSeek 进行智能切分
    response = await call_deepseek_with_json_output(
        system_prompt=PARSE_SYSTEM_PROMPT,
        user_prompt=user_prompt
    )
    
    # 解析响应
    try:
        result = json.loads(response)
        segments_data = result.get("segments", [])
    except json.JSONDecodeError:
        # 尝试提取 JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            segments_data = result.get("segments", [])
        else:
            # 回退到简单切分
            segments_data = _simple_split(raw_text, max_length)
    
    # 删除项目现有段落（可选，也可以追加）
    await db.execute(delete(Segment).where(Segment.project_id == project.id))
    
    # 创建段落
    segments = []
    for idx, seg_data in enumerate(segments_data):
        segment = Segment(
            project_id=project.id,
            order_index=idx,
            segment_title=seg_data.get("segment_title"),
            narration_text=seg_data.get("narration_text", ""),
            visual_prompt=seg_data.get("visual_prompt"),
            on_screen_text=seg_data.get("on_screen_text"),
            mood=seg_data.get("mood"),
            shot_type=seg_data.get("shot_type"),
            status=SegmentStatus.READY_SCRIPT
        )
        db.add(segment)
        segments.append(segment)
    
    await db.commit()
    for seg in segments:
        await db.refresh(seg)
    
    return segments


def _simple_split(text: str, max_length: int) -> List[dict]:
    """简单切分（按段落或长度）"""
    # 先按段落分
    paragraphs = re.split(r'\n\n+', text.strip())
    
    segments = []
    current_text = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_text) + len(para) <= max_length:
            current_text += ("\n\n" if current_text else "") + para
        else:
            if current_text:
                segments.append({
                    "narration_text": current_text,
                    "visual_prompt": f"场景描述：{current_text[:100]}..."
                })
            current_text = para
    
    if current_text:
        segments.append({
            "narration_text": current_text,
            "visual_prompt": f"场景描述：{current_text[:100]}..."
        })
    
    return segments
