"""
项目管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.db.database import get_db
from app.models.project import Project, ProjectStatus
from app.models.segment import Segment
from app.models.asset import Asset, AssetType
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, 
    ProjectListResponse, ProjectConfigUpdate, ProjectSummary
)
from app.schemas.config import AIFillRequest, AIFillResponse
from app.services.ai_fill import ai_fill_config

router = APIRouter()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新项目"""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        project_config=project_data.project_config.model_dump() if project_data.project_config else {}
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[ProjectStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取项目列表"""
    query = select(Project)
    if status_filter:
        query = query.where(Project.status == status_filter)
    query = query.order_by(Project.updated_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    # 获取总数
    count_query = select(func.count(Project.id))
    if status_filter:
        count_query = count_query.where(Project.status == status_filter)
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return ProjectListResponse(total=total, items=projects)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取项目详情"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.get("/{project_id}/summary", response_model=ProjectSummary)
async def get_project_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取项目概要"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 统计段落数量
    segments_count = await db.execute(
        select(func.count(Segment.id)).where(Segment.project_id == project_id)
    )
    
    # 统计图片数量
    images_count = await db.execute(
        select(func.count(Asset.id)).where(
            Asset.project_id == project_id,
            Asset.asset_type == AssetType.IMAGE
        )
    )
    
    # 检查音频状态
    audio_count = await db.execute(
        select(func.count(Asset.id)).where(
            Asset.project_id == project_id,
            Asset.asset_type == AssetType.AUDIO
        )
    )
    
    return ProjectSummary(
        id=project.id,
        name=project.name,
        status=project.status,
        segments_count=segments_count.scalar() or 0,
        images_count=images_count.scalar() or 0,
        audio_ready=(audio_count.scalar() or 0) > 0,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新项目基本信息"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    await db.commit()
    await db.refresh(project)
    return project


@router.patch("/{project_id}/config", response_model=ProjectResponse)
async def update_project_config(
    project_id: int,
    config_data: ProjectConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新项目配置"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project.project_config = config_data.project_config.model_dump()
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/config/ai-fill", response_model=AIFillResponse)
async def ai_fill_project_config(
    project_id: int,
    request: AIFillRequest,
    db: AsyncSession = Depends(get_db)
):
    """AI 助填配置"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 调用 AI 助填服务
    suggested_config = await ai_fill_config(
        description=request.description,
        current_config=project.project_config,
        only_fill_empty=request.only_fill_empty
    )
    
    return suggested_config


@router.post("/{project_id}/config/ai-fill/apply", response_model=ProjectResponse)
async def apply_ai_fill_config(
    project_id: int,
    config_data: ProjectConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """应用 AI 助填的配置"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project.project_config = config_data.project_config.model_dump()
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    await db.delete(project)
    await db.commit()
