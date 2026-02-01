"""
资产管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import aiofiles
import uuid

from app.db.database import get_db
from app.models.asset import Asset, AssetType
from app.models.project import Project
from app.schemas.asset import AssetResponse, AssetListResponse
from app.core.config import settings

router = APIRouter()


@router.get("/projects/{project_id}", response_model=AssetListResponse)
async def list_project_assets(
    project_id: int,
    asset_type: AssetType = None,
    db: AsyncSession = Depends(get_db)
):
    """获取项目的所有资产"""
    query = select(Asset).where(Asset.project_id == project_id)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    query = query.order_by(Asset.created_at.desc())
    
    result = await db.execute(query)
    assets = result.scalars().all()
    return AssetListResponse(total=len(assets), items=assets)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取资产详情"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """下载资产文件"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    
    # 构建完整路径
    # 检查 file_path 是否已经包含 storage 前缀
    asset_file_path = Path(asset.file_path)
    if str(asset_file_path).startswith("storage"):
        # file_path 已经包含 storage 前缀，直接使用相对于项目根目录的路径
        file_path = Path(".") / asset.file_path
    else:
        # file_path 是相对于 STORAGE_PATH 的路径
        file_path = Path(settings.STORAGE_PATH) / asset.file_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    
    # 根据资产类型设置正确的 MIME 类型
    media_type = "application/octet-stream"
    if asset.asset_type == AssetType.AUDIO:
        media_type = "audio/mpeg"
    elif asset.asset_type == AssetType.IMAGE:
        if asset.file_name and asset.file_name.endswith(".png"):
            media_type = "image/png"
        else:
            media_type = "image/jpeg"
    elif asset.asset_type == AssetType.VIDEO:
        media_type = "video/mp4"
    
    return FileResponse(
        path=file_path,
        filename=asset.file_name,
        media_type=media_type
    )


@router.post("/projects/{project_id}/upload", response_model=AssetResponse)
async def upload_asset(
    project_id: int,
    file: UploadFile = File(...),
    asset_type: AssetType = Form(...),
    segment_id: int = Form(None),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """上传资产文件"""
    # 验证项目存在
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 确定存储目录
    if asset_type == AssetType.IMAGE:
        base_path = settings.IMAGES_PATH
    elif asset_type == AssetType.AUDIO:
        base_path = settings.AUDIO_PATH
    elif asset_type == AssetType.VIDEO:
        base_path = settings.VIDEO_PATH
    else:
        base_path = settings.STORAGE_PATH
    
    # 生成唯一文件名
    ext = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = base_path / str(project_id) / unique_filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # 创建资产记录
    asset = Asset(
        project_id=project_id,
        segment_id=segment_id,
        asset_type=asset_type,
        file_path=str(file_path),
        file_name=file.filename,
        file_size=len(content),
        description=description
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    
    return asset


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除资产"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    
    # 删除文件
    file_path = Path(asset.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # 删除记录
    await db.delete(asset)
    await db.commit()
    
    return {"status": "success", "message": "资产已删除"}
