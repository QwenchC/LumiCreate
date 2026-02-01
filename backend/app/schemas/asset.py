"""
资产相关的 Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

from app.models.asset import AssetType


class AssetBase(BaseModel):
    """资产基础 Schema"""
    asset_type: AssetType
    description: Optional[str] = None


class AssetResponse(AssetBase):
    """资产响应 Schema"""
    id: int
    project_id: int
    segment_id: Optional[int]
    file_path: str
    file_name: str
    file_size: Optional[int]
    asset_metadata: Optional[dict] = None  # 与模型字段名保持一致
    duration_ms: Optional[int]
    version: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class AssetListResponse(BaseModel):
    """资产列表响应 Schema"""
    total: int
    items: List[AssetResponse]


class AssetUploadRequest(BaseModel):
    """资产上传请求"""
    asset_type: AssetType
    segment_id: Optional[int] = None
    description: Optional[str] = None
