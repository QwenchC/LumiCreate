"""
Pollinations.ai 图片生成客户端
https://pollinations.ai/

API 格式: https://gen.pollinations.ai/image/{prompt}?model={model}&width=X&height=Y&seed=N

支持的模型:
- zimage: 推荐模型，快速高质量
- flux: 默认模型，质量和速度平衡
- turbo: 快速生成
- flux-realism: 写实风格
- flux-anime: 动漫风格  
- flux-3d: 3D风格
- any-dark: 暗黑风格
- flux-pro: 高质量专业版
"""
import uuid
import httpx
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote

from app.api.settings import get_pollinations_config

logger = logging.getLogger(__name__)


async def translate_prompt_to_english(
    prompt: str,
    character_description: str = ""
) -> str:
    """
    将中文提示词转换为 Stable Diffusion 风格的英文标签格式
    同时智能处理主角描述的融合
    
    Args:
        prompt: 场景描述（可能包含【主角】【场景】标记）
        character_description: 可选的主角描述（如果 prompt 中已包含则忽略）
    """
    from app.services.deepseek_client import call_deepseek
    
    if not prompt:
        return ""
    
    # 检查是否已经是英文（简单检测）
    chinese_chars = sum(1 for c in prompt if '\u4e00' <= c <= '\u9fff')
    if chinese_chars == 0:
        return prompt
    
    # 检查是否包含主角标记
    has_character_tag = "【主角】" in prompt and "【场景】" in prompt
    
    if has_character_tag:
        # 使用融合模式的系统提示词
        system_prompt = """You are an expert at converting Chinese scene descriptions into Stable Diffusion image prompts, with careful handling for protagonist consistency.

The input contains two parts:
- 【主角】: The protagonist's appearance description (ONLY use when scene actually contains the protagonist)
- 【场景】: The scene description

**Critical Rules - MUST FOLLOW**:

1. **Check if Protagonist is in Scene First**:
   - Look for protagonist indicators in scene: 他/她/主角/少年/少女/男子/女子 or other references to the main character
   - If scene is about objects, landscapes, buildings, animals without the protagonist → DO NOT include protagonist description
   - If scene describes other characters only (敌人/对手/路人/其他人) → DO NOT include protagonist description
   
2. **Gender Must Match** (only when protagonist IS in scene):
   - If protagonist is male (男/他/少年/男子), only apply to male character references
   - If protagonist is female (女/她/少女/女子), only apply to female character references
   - For love interests/other characters of different gender: keep their original description
   
3. **Multiple Characters**:
   - Only apply protagonist desc to the actual protagonist
   - Keep original descriptions for: enemies (敌人), opponents (对手), companions (同伴), love interests (恋人/情人)

4. **No Protagonist = No Protagonist Description**:
   - Scenery only → just translate the scene
   - Objects/items only → just translate the scene
   - Other people only → just translate their descriptions

Convert to English SD prompt format:
- Use comma-separated tags/phrases
- Include: masterpiece, best quality, highly detailed
- For protagonist (ONLY when confirmed present): describe with gender, hair, eyes, clothing from 【主角】
- For environment: location, lighting, atmosphere
- Use weight syntax like (important:1.3) for emphasis

Only output the prompt tags, no explanations."""
    else:
        # 普通翻译模式
        system_prompt = """You are an expert at converting Chinese scene descriptions into Stable Diffusion image prompts.

Convert the Chinese text into English tags/phrases in the standard SD prompt format:
- Use comma-separated English words and short phrases
- Include quality tags like: masterpiece, best quality, highly detailed, 8k
- Include style tags based on the scene mood
- Describe characters with: gender, hair, eyes, clothing, pose, expression
- Describe environment with: location, lighting, atmosphere
- Use weight syntax like (important:1.3) for emphasis
- Use BREAK to separate different sections if needed

Example output format:
masterpiece, best quality, highly detailed, 
1boy, black hair, determined expression, traditional chinese clothing,
standing in ancient forest, misty atmosphere, dramatic lighting,
detailed background, fantasy scene

Only output the prompt tags, no explanations or translations of the original text."""

    try:
        translated = await call_deepseek(
            system_prompt=system_prompt,
            user_prompt=f"将以下中文场景描述转换为 Stable Diffusion 提示词格式：\n\n{prompt}",
            temperature=0.5,
            max_tokens=800
        )
        return translated.strip()
    except Exception as e:
        logger.warning(f"提示词转换失败，使用原始提示词: {e}")
        return prompt


def build_pollinations_url(
    prompt: str,
    model: str = "zimage",
    width: int = 1024,
    height: int = 1024,
    seed: int = 0
) -> str:
    """
    构建 Pollinations 图片生成 URL
    
    API 格式: https://gen.pollinations.ai/image/{prompt}?model={model}&width=X&height=Y&seed=N
    
    Args:
        prompt: 图片描述（必须是英文）
        model: 模型名称 (zimage, flux, turbo...)
        width: 图片宽度
        height: 图片高度
        seed: 随机种子
    
    Returns:
        完整的 API URL
    """
    # URL 编码提示词
    encoded_prompt = quote(prompt, safe='')
    
    params = [
        f"model={model}",
        f"width={width}",
        f"height={height}",
        f"seed={seed}"
    ]
    
    url = f"https://gen.pollinations.ai/image/{encoded_prompt}?{'&'.join(params)}"
    return url


# 模型回退列表（按优先级排序）
FALLBACK_MODELS = ["flux", "turbo", "flux-realism"]


async def generate_image_pollinations(
    prompt: str,
    output_path: Path,
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
    model: Optional[str] = None,
    style_prefix: str = "",
    translate: bool = True,
    retry_with_fallback: bool = True
) -> Dict[str, Any]:
    """
    使用 Pollinations.ai 生成图片
    
    Args:
        prompt: 图片描述
        output_path: 输出路径
        width: 图片宽度
        height: 图片高度
        seed: 随机种子
        model: 模型名称（可选，默认从配置读取）
        style_prefix: 风格前缀
        translate: 是否翻译中文为英文
        retry_with_fallback: 是否在模型不可用时自动尝试备用模型
    
    Returns:
        生成结果字典
    """
    config = get_pollinations_config()
    
    # 使用配置的模型或默认模型
    use_model = model or config.model or "flux"
    
    # 组合完整提示词
    full_prompt = f"{style_prefix}{prompt}".strip()
    
    # 翻译为英文
    if translate:
        full_prompt = await translate_prompt_to_english(full_prompt)
    
    # 生成种子 (确保在合理范围内 0-999999999)
    if seed is None or seed < 0:
        seed = uuid.uuid4().int % 1000000000
    
    # 尝试的模型列表
    models_to_try = [use_model]
    if retry_with_fallback:
        # 添加备用模型（排除已在列表中的）
        for fallback in FALLBACK_MODELS:
            if fallback not in models_to_try:
                models_to_try.append(fallback)
    
    last_error = None
    
    for try_model in models_to_try:
        # 构建 URL
        url = build_pollinations_url(
            prompt=full_prompt,
            model=try_model,
            width=width,
            height=height,
            seed=seed
        )
        
        if try_model != use_model:
            logger.info(f"尝试备用模型 {try_model}...")
        logger.info(f"Pollinations 生成图片: {url[:200]}...")
        
        # 构建请求头
        headers = {
            "Accept": "image/*"
        }
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        
        try:
            result = await _do_pollinations_request(
                url=url,
                headers=headers,
                output_path=output_path,
                full_prompt=full_prompt,
                seed=seed,
                model=try_model,
                width=width,
                height=height
            )
            
            if result.get("success"):
                return result
            
            # 检查是否是服务器不可用错误（可以尝试其他模型）
            error_msg = result.get("error", "")
            if "No active" in error_msg and "servers available" in error_msg:
                logger.warning(f"模型 {try_model} 服务器不可用，尝试备用模型...")
                last_error = error_msg
                continue
            elif "500" in error_msg or "503" in error_msg:
                logger.warning(f"模型 {try_model} 服务器错误，尝试备用模型...")
                last_error = error_msg
                continue
            else:
                # 其他错误直接返回
                return result
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"模型 {try_model} 请求失败: {e}")
            continue
    
    # 所有模型都失败
    return {"success": False, "error": f"所有模型都不可用: {last_error}"}


async def _do_pollinations_request(
    url: str,
    headers: dict,
    output_path: Path,
    full_prompt: str,
    seed: int,
    model: str,
    width: int,
    height: int
) -> Dict[str, Any]:
    """执行实际的 Pollinations API 请求"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("image"):
                    # 确保输出目录存在
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 保存图片
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    
                    logger.info(f"图片已保存: {output_path}")
                    
                    return {
                        "success": True,
                        "path": str(output_path),
                        "prompt": full_prompt,
                        "seed": seed,
                        "model": model,
                        "width": width,
                        "height": height
                    }
                else:
                    error_msg = f"返回内容不是图片: {content_type}"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
            else:
                # 记录完整错误信息以便调试
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                logger.error(f"Pollinations 请求失败: {error_msg}")
                # 记录请求参数以便调试
                logger.error(f"请求参数: model={model}, width={width}, height={height}, seed={seed}")
                return {"success": False, "error": error_msg}
                
    except httpx.TimeoutException:
        error_msg = "请求超时"
        logger.error(f"Pollinations 请求超时")
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Pollinations 生成失败: {e}")
        return {"success": False, "error": error_msg}


async def generate_batch_pollinations(
    prompts: list,
    output_dir: Path,
    width: int = 1024,
    height: int = 1024,
    model: Optional[str] = None,
    style_prefix: str = ""
) -> list:
    """
    批量生成图片
    
    Args:
        prompts: 提示词列表
        output_dir: 输出目录
        width: 图片宽度
        height: 图片高度
        model: 模型名称
        style_prefix: 风格前缀
    
    Returns:
        生成结果列表
    """
    results = []
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for i, prompt in enumerate(prompts):
        filename = f"{uuid.uuid4()}.png"
        output_path = output_dir / filename
        
        result = await generate_image_pollinations(
            prompt=prompt,
            output_path=output_path,
            width=width,
            height=height,
            model=model,
            style_prefix=style_prefix
        )
        
        result["index"] = i
        results.append(result)
    
    return results
