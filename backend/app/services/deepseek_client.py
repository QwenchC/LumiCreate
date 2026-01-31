"""
DeepSeek API 客户端
"""
import httpx
from typing import Optional

from app.core.config import settings


async def call_deepseek(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 4096
) -> str:
    """
    调用 DeepSeek API
    
    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        temperature: 温度参数
        max_tokens: 最大生成 token 数
    
    Returns:
        str: 生成的文本
    """
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("未配置 DEEPSEEK_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.DEEPSEEK_API_BASE}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        
        return data["choices"][0]["message"]["content"]


async def call_deepseek_with_json_output(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 8192
) -> str:
    """
    调用 DeepSeek API 并期望 JSON 输出
    使用较低的温度以获得更稳定的结构化输出
    """
    # 强化 JSON 输出的提示
    enhanced_system = system_prompt + "\n\n重要：你必须只返回有效的 JSON，不要有任何其他文字、注释或 markdown 格式。"
    
    return await call_deepseek(
        system_prompt=enhanced_system,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens
    )


from typing import AsyncGenerator
import json as json_module


async def stream_deepseek(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 8192
) -> AsyncGenerator[str, None]:
    """
    流式调用 DeepSeek API
    
    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        temperature: 温度参数
        max_tokens: 最大生成 token 数
    
    Yields:
        str: 生成的文本片段
    """
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("未配置 DEEPSEEK_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True  # 启用流式输出
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            f"{settings.DEEPSEEK_API_BASE}/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]  # 移除 "data: " 前缀
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json_module.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json_module.JSONDecodeError:
                        continue


async def stream_deepseek_with_json_output(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 8192
) -> AsyncGenerator[str, None]:
    """
    流式调用 DeepSeek API 并期望 JSON 输出
    使用较低的温度以获得更稳定的结构化输出
    """
    # 强化 JSON 输出的提示
    enhanced_system = system_prompt + "\n\n重要：你必须只返回有效的 JSON，不要有任何其他文字、注释或 markdown 格式。"
    
    async for chunk in stream_deepseek(
        system_prompt=enhanced_system,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens
    ):
        yield chunk
