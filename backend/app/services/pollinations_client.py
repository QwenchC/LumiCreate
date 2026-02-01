"""
Pollinations.ai 图片生成客户端
https://pollinations.ai/

支持的模型:
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


async def translate_prompt_to_english(prompt: str) -> str:
    """
    将中文提示词翻译为英文
    使用 DeepSeek API 进行翻译
    """
    from app.services.deepseek_client import call_deepseek
    
    if not prompt:
        return ""
    
    # 检查是否已经是英文（简单检测）
    chinese_chars = sum(1 for c in prompt if '\u4e00' <= c <= '\u9fff')
    if chinese_chars == 0:
        return prompt
    
    try:
        translated = await call_deepseek(
            system_prompt="You are a translator. Translate the following Chinese text to English. Only output the translation, no explanations. Keep it concise and suitable for AI image generation prompts.",
            user_prompt=prompt,
            temperature=0.3,
            max_tokens=500
        )
        return translated.strip()
    except Exception as e:
        logger.warning(f"翻译失败，使用原始提示词: {e}")
        return prompt


def build_pollinations_url(
    prompt: str,
    model: str = "flux",
    width: int = 1024,
    height: int = 1024,
    seed: int = -1,
    nologo: bool = True,
    enhance: bool = False,
    safe: bool = True
) -> str:
    """
    构建 Pollinations 图片生成 URL
    
    Args:
        prompt: 图片描述（必须是英文）
        model: 模型名称
        width: 图片宽度
        height: 图片高度
        seed: 随机种子（-1 表示随机）
        nologo: 是否去除水印
        enhance: 是否增强提示词
        safe: 安全模式
    
    Returns:
        完整的 API URL
    """
    # URL 编码提示词
    encoded_prompt = quote(prompt, safe='')
    
    params = [
        f"model={model}",
        f"width={width}",
        f"height={height}",
        f"seed={seed}",
        f"nologo={'true' if nologo else 'false'}",
        f"enhance={'true' if enhance else 'false'}",
        f"safe={'true' if safe else 'false'}"
    ]
    
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?{'&'.join(params)}"
    return url


async def generate_image_pollinations(
    prompt: str,
    output_path: Path,
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
    model: Optional[str] = None,
    style_prefix: str = "",
    translate: bool = True
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
    
    # 生成种子
    if seed is None or seed < 0:
        seed = uuid.uuid4().int % (2**31)
    
    # 构建 URL
    url = build_pollinations_url(
        prompt=full_prompt,
        model=use_model,
        width=width,
        height=height,
        seed=seed,
        nologo=True,
        enhance=False,
        safe=True
    )
    
    logger.info(f"Pollinations 生成图片: {url[:200]}...")
    
    # 构建请求头
    headers = {
        "Accept": "image/*"
    }
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    
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
                        "model": use_model,
                        "width": width,
                        "height": height
                    }
                else:
                    error_msg = f"返回内容不是图片: {content_type}"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"Pollinations 请求失败: {error_msg}")
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
