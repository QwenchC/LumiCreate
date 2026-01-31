"""
项目相关的 Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.models.project import ProjectStatus
from app.schemas.config import ProjectConfig


class ProjectBase(BaseModel):
    """项目基础 Schema"""
    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")


class ProjectCreate(ProjectBase):
    """创建项目 Schema"""
    project_config: Optional[ProjectConfig] = Field(None, description="项目配置")


class ProjectUpdate(BaseModel):
    """更新项目 Schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    status: Optional[ProjectStatus] = Field(None, description="项目状态")


class ProjectConfigUpdate(BaseModel):
    """更新项目配置 Schema"""
    project_config: ProjectConfig = Field(..., description="项目配置")


class ProjectResponse(ProjectBase):
    """项目响应 Schema"""
    id: int
    status: ProjectStatus
    project_config: dict
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """项目列表响应 Schema"""
    total: int
    items: List[ProjectResponse]


class ProjectSummary(BaseModel):
    """项目概要 Schema（用于列表展示）"""
    id: int
    name: str
    status: ProjectStatus
    segments_count: int = 0
    images_count: int = 0
    audio_ready: bool = False
    created_at: datetime
    updated_at: datetime
