"""
系统设置 API
"""
import json
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/settings", tags=["settings"])

# 设置文件路径
SETTINGS_FILE = Path(__file__).parent.parent.parent / "settings.json"


class DeepSeekSettings(BaseModel):
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"


class ComfyUISettings(BaseModel):
    api_url: str = "http://localhost:8188"
    default_workflow: str = ""


class PollinationsSettings(BaseModel):
    api_key: str = ""
    model: str = "zimage"  # 推荐模型: zimage, flux, turbo, flux-realism, flux-anime, flux-3d, any-dark, flux-pro


class TTSSettings(BaseModel):
    engine: str = "edge-tts"
    sovits_url: str = "http://localhost:9880"


class FFmpegSettings(BaseModel):
    path: str = "ffmpeg"


class StorageSettings(BaseModel):
    path: str = "./storage"


class SystemSettings(BaseModel):
    deepseek: DeepSeekSettings = DeepSeekSettings()
    comfyui: ComfyUISettings = ComfyUISettings()
    pollinations: PollinationsSettings = PollinationsSettings()
    tts: TTSSettings = TTSSettings()
    ffmpeg: FFmpegSettings = FFmpegSettings()
    storage: StorageSettings = StorageSettings()


def load_settings() -> SystemSettings:
    """加载设置"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SystemSettings(**data)
        except Exception:
            pass
    return SystemSettings()


def save_settings(settings: SystemSettings):
    """保存设置"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=2, ensure_ascii=False)


@router.get("", response_model=SystemSettings)
async def get_settings():
    """获取系统设置"""
    return load_settings()


@router.post("", response_model=SystemSettings)
async def update_settings(settings: SystemSettings):
    """更新系统设置"""
    save_settings(settings)
    return settings


class DeepSeekTestRequest(BaseModel):
    api_key: str
    api_base: str
    model: str


@router.post("/test/deepseek")
async def test_deepseek(request: DeepSeekTestRequest):
    """测试 DeepSeek 连接"""
    if not request.api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{request.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": request.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5
                }
            )
            if response.status_code == 200:
                return {"status": "success", "message": "连接成功"}
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"API 返回错误: {response.status_code}"
                )
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")


class ComfyUITestRequest(BaseModel):
    api_url: str


@router.post("/test/comfyui")
async def test_comfyui(request: ComfyUITestRequest):
    """测试 ComfyUI 连接"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{request.api_url}/system_stats")
            if response.status_code == 200:
                return {"status": "success", "message": "连接成功"}
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"ComfyUI 返回错误: {response.status_code}"
                )
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")


class FFmpegTestRequest(BaseModel):
    path: str


@router.post("/test/ffmpeg")
async def test_ffmpeg(request: FFmpegTestRequest):
    """测试 FFmpeg"""
    try:
        result = subprocess.run(
            [request.path, "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # 提取版本信息
            version_line = result.stdout.split("\n")[0]
            return {"status": "success", "version": version_line}
        else:
            raise HTTPException(status_code=400, detail="FFmpeg 执行失败")
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="FFmpeg 未找到")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=400, detail="FFmpeg 执行超时")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"检测失败: {str(e)}")


# 辅助函数：获取当前设置中的 API 配置
def get_deepseek_config() -> DeepSeekSettings:
    """获取 DeepSeek 配置"""
    settings = load_settings()
    return settings.deepseek


def get_comfyui_config() -> ComfyUISettings:
    """获取 ComfyUI 配置"""
    settings = load_settings()
    return settings.comfyui


def get_pollinations_config() -> PollinationsSettings:
    """获取 Pollinations 配置"""
    settings = load_settings()
    return settings.pollinations


class PollinationsTestRequest(BaseModel):
    api_key: str
    model: str = "zimage"


@router.post("/test/pollinations")
async def test_pollinations(request: PollinationsTestRequest):
    """测试 Pollinations 连接"""
    try:
        # 生成一个小测试图片
        url = f"https://gen.pollinations.ai/image/test?model={request.model}&width=128&height=128&seed=42"
        headers = {
            "Accept": "*/*"
        }
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            if response.status_code == 200 and response.headers.get("content-type", "").startswith("image"):
                return {"status": "success", "message": "Pollinations 连接成功"}
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pollinations 返回错误: {response.status_code}"
                )
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")
