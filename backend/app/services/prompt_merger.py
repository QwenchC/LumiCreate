"""
提示词融合服务

简化版：直接将主角描述与场景描述拼接。
真正的智能融合在翻译成英文时由 AI 处理。
"""
import logging

logger = logging.getLogger(__name__)


def merge_character_with_scene(
    scene_prompt: str,
    character_description: str
) -> str:
    """
    将主角描述与场景描述简单拼接
    
    真正的融合处理在 translate_prompt_to_english 中进行，
    翻译 AI 会智能判断如何处理主角描述和场景人物。
    
    Args:
        scene_prompt: 原始场景提示词
        character_description: 主角外观描述
    
    Returns:
        拼接后的提示词
    """
    if not character_description or not character_description.strip():
        return scene_prompt
    
    if not scene_prompt or not scene_prompt.strip():
        return character_description
    
    # 简单拼接：主角描述 + 分隔符 + 场景描述
    # 翻译 AI 会智能处理融合逻辑
    return f"【主角】{character_description}【场景】{scene_prompt}"


def batch_merge_prompts(
    scene_prompts: list[str],
    character_description: str
) -> list[str]:
    """
    批量融合多个场景的提示词
    """
    return [
        merge_character_with_scene(scene, character_description)
        for scene in scene_prompts
    ]
