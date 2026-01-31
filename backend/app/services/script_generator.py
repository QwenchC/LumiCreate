"""
文案生成服务
使用 DeepSeek 生成结构化文案
"""
import json
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectStatus
from app.models.script import Script
from app.services.deepseek_client import call_deepseek_with_json_output, stream_deepseek_with_json_output


SCRIPT_GENERATION_SYSTEM_PROMPT = """你是一个专业的短视频脚本创作者，擅长创作适合"说书"风格的叙事内容。

你需要根据用户的配置生成一个结构化的脚本，包含：
1. title: 吸引人的标题
2. hook: 开头钩子（3-5秒内抓住观众）
3. outline: 简要大纲（可选）
4. segments: 分段内容列表，每段包含：
   - segment_title: 段落标题（可选）
   - narration_text: 旁白文本（用于配音，必须）
   - visual_prompt: 画面提示词（用于AI出图，必须，应该是详细的场景描述）
   - on_screen_text: 屏幕金句（可选，用于字幕高亮）
   - mood: 氛围标签（紧张/温馨/热血/恐怖/轻松等）
   - shot_type: 镜头类型（远景/中景/近景/特写等）

视觉提示词要求：
- 必须是完整的场景描述，包含人物、环境、光线、氛围
- 适合作为 AI 绘图的 prompt
- 与旁白内容相匹配但不是简单复述

返回纯 JSON 格式，不要有其他文字。"""


def _build_generation_prompt(project: Project, topic: Optional[str], additional_instructions: Optional[str]) -> str:
    """构建生成提示词"""
    config = project.project_config.get("script_generation", {})
    
    prompt_parts = []
    
    # 基础配置
    if config.get("genre"):
        prompt_parts.append(f"题材类型：{config['genre']}")
    if config.get("audience_taste"):
        prompt_parts.append(f"受众口味：{config['audience_taste']}")
    if config.get("narrative_perspective"):
        prompt_parts.append(f"叙事视角：{config['narrative_perspective']}")
    if config.get("writing_style"):
        prompt_parts.append(f"文风：{config['writing_style']}")
    
    # 主线设定
    if config.get("world_setting"):
        prompt_parts.append(f"世界观：{config['world_setting']}")
    if config.get("golden_finger"):
        prompt_parts.append(f"主角优势：{config['golden_finger']}")
    if config.get("conflict_type"):
        prompt_parts.append(f"冲突类型：{config['conflict_type']}")
    
    # 角色设定
    protagonist = config.get("protagonist", {})
    if protagonist:
        char_desc = []
        if protagonist.get("name"):
            char_desc.append(f"姓名：{protagonist['name']}")
        if protagonist.get("gender"):
            char_desc.append(f"性别：{protagonist['gender']}")
        if protagonist.get("personality"):
            char_desc.append(f"性格：{protagonist['personality']}")
        if char_desc:
            prompt_parts.append(f"主角设定：{', '.join(char_desc)}")
    
    # 节奏设定
    if config.get("pacing"):
        prompt_parts.append(f"节奏：{config['pacing']}")
    if config.get("twist_frequency"):
        prompt_parts.append(f"反转频率：{config['twist_frequency']}")
    if config.get("climax_position"):
        prompt_parts.append(f"高潮位置：{config['climax_position']}")
    
    # 长度目标
    if config.get("target_word_count"):
        prompt_parts.append(f"目标字数：约{config['target_word_count']}字")
    elif config.get("target_duration_minutes"):
        # 按每分钟约 180 字估算
        estimated_words = config['target_duration_minutes'] * 180
        prompt_parts.append(f"目标字数：约{estimated_words}字（{config['target_duration_minutes']}分钟视频）")
    
    if config.get("segment_word_count"):
        prompt_parts.append(f"每段约{config['segment_word_count']}字")
    
    # 合规设置
    compliance = []
    if config.get("no_violence"):
        compliance.append("避免过度血腥暴力")
    if config.get("no_adult_content"):
        compliance.append("避免成人内容")
    if config.get("no_sensitive_topics"):
        compliance.append("避免敏感话题")
    if compliance:
        prompt_parts.append(f"内容规范：{', '.join(compliance)}")
    
    # 主题
    if topic:
        prompt_parts.append(f"\n创作主题：{topic}")
    
    # 额外指令
    if additional_instructions:
        prompt_parts.append(f"\n额外要求：{additional_instructions}")
    
    # 自定义系统提示词
    if config.get("system_prompt_template"):
        prompt_parts.append(f"\n特别说明：{config['system_prompt_template']}")
    
    return "\n".join(prompt_parts)


async def generate_script(
    db: AsyncSession,
    project: Project,
    topic: Optional[str] = None,
    additional_instructions: Optional[str] = None
) -> Script:
    """
    生成文案
    
    Args:
        db: 数据库会话
        project: 项目对象
        topic: 创作主题
        additional_instructions: 额外指令
    
    Returns:
        Script: 生成的脚本对象
    """
    # 构建提示词
    user_prompt = _build_generation_prompt(project, topic, additional_instructions)
    
    # 调用 DeepSeek
    response = await call_deepseek_with_json_output(
        system_prompt=SCRIPT_GENERATION_SYSTEM_PROMPT,
        user_prompt=user_prompt
    )
    
    # 解析响应
    try:
        structured_content = json.loads(response)
    except json.JSONDecodeError:
        # 尝试提取 JSON 部分
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            structured_content = json.loads(json_match.group())
        else:
            structured_content = {"segments": [], "error": "解析失败"}
    
    # 获取当前版本号
    from sqlalchemy import select, func
    version_result = await db.execute(
        select(func.max(Script.version)).where(Script.project_id == project.id)
    )
    current_max_version = version_result.scalar() or 0
    
    # 创建脚本记录
    script = Script(
        project_id=project.id,
        title=structured_content.get("title", ""),
        hook=structured_content.get("hook", ""),
        outline=structured_content.get("outline", ""),
        raw_text=response,
        structured_content=structured_content,
        generation_params={
            "topic": topic,
            "additional_instructions": additional_instructions,
            "config": project.project_config.get("script_generation", {})
        },
        version=current_max_version + 1
    )
    
    db.add(script)
    
    # 更新项目状态
    project.status = ProjectStatus.SCRIPT_READY
    
    await db.commit()
    await db.refresh(script)
    
    return script


async def stream_generate_script(
    project: Project,
    topic: Optional[str] = None,
    additional_instructions: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    流式生成文案
    
    Args:
        project: 项目对象
        topic: 创作主题
        additional_instructions: 额外指令
    
    Yields:
        str: 生成的文本片段
    """
    # 构建提示词
    user_prompt = _build_generation_prompt(project, topic, additional_instructions)
    
    # 流式调用 DeepSeek
    async for chunk in stream_deepseek_with_json_output(
        system_prompt=SCRIPT_GENERATION_SYSTEM_PROMPT,
        user_prompt=user_prompt
    ):
        yield chunk


async def save_generated_script(
    db: AsyncSession,
    project: Project,
    full_response: str,
    topic: Optional[str] = None,
    additional_instructions: Optional[str] = None
) -> Script:
    """
    保存流式生成完成后的文案
    
    Args:
        db: 数据库会话
        project: 项目对象
        full_response: 完整的生成响应
        topic: 创作主题
        additional_instructions: 额外指令
    
    Returns:
        Script: 生成的脚本对象
    """
    # 解析响应
    try:
        structured_content = json.loads(full_response)
    except json.JSONDecodeError:
        # 尝试提取 JSON 部分
        import re
        json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
        if json_match:
            try:
                structured_content = json.loads(json_match.group())
            except json.JSONDecodeError:
                structured_content = {"segments": [], "error": "解析失败", "raw": full_response}
        else:
            structured_content = {"segments": [], "error": "解析失败", "raw": full_response}
    
    # 获取当前版本号
    from sqlalchemy import select, func
    version_result = await db.execute(
        select(func.max(Script.version)).where(Script.project_id == project.id)
    )
    current_max_version = version_result.scalar() or 0
    
    # 创建脚本记录
    script = Script(
        project_id=project.id,
        title=structured_content.get("title", ""),
        hook=structured_content.get("hook", ""),
        outline=structured_content.get("outline", ""),
        raw_text=full_response,
        structured_content=structured_content,
        generation_params={
            "topic": topic,
            "additional_instructions": additional_instructions,
            "config": project.project_config.get("script_generation", {})
        },
        version=current_max_version + 1
    )
    
    db.add(script)
    
    # 更新项目状态
    project.status = ProjectStatus.SCRIPT_READY
    
    await db.commit()
    await db.refresh(script)
    
    return script
