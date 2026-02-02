"""
段落管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.db.database import get_db
from app.models.project import Project
from app.models.segment import Segment, SegmentStatus
from app.models.asset import Asset, AssetType
from app.models.job import Job, JobType, JobStatus
from app.schemas.segment import (
    SegmentCreate, SegmentUpdate, SegmentResponse, SegmentListResponse,
    SegmentSplitRequest, SegmentMergeRequest, SegmentReorderRequest,
    ImageGenerateRequest, ImageSelectRequest, AudioGenerateRequest
)
from app.schemas.asset import AssetListResponse
from app.services.image_generator import generate_segment_images, execute_image_generation
from app.services.audio_generator import generate_segment_audio

router = APIRouter()


@router.get("/projects/{project_id}", response_model=SegmentListResponse)
async def list_project_segments(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取项目的所有段落"""
    result = await db.execute(
        select(Segment)
        .where(Segment.project_id == project_id)
        .order_by(Segment.order_index)
    )
    segments = result.scalars().all()
    return SegmentListResponse(total=len(segments), items=segments)


@router.post("/projects/{project_id}", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(
    project_id: int,
    segment_data: SegmentCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新段落"""
    # 验证项目存在
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在")
    
    segment = Segment(
        project_id=project_id,
        order_index=segment_data.order_index,
        segment_title=segment_data.segment_title,
        narration_text=segment_data.narration_text,
        visual_prompt=segment_data.visual_prompt,
        on_screen_text=segment_data.on_screen_text,
        mood=segment_data.mood,
        shot_type=segment_data.shot_type,
        status=SegmentStatus.READY_SCRIPT
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
    return segment


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取段落详情"""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    return segment


@router.patch("/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: int,
    segment_data: SegmentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新段落"""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    
    update_data = segment_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(segment, field, value)
    
    await db.commit()
    await db.refresh(segment)
    return segment


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除段落"""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    
    await db.delete(segment)
    await db.commit()


@router.post("/{segment_id}/split", response_model=SegmentListResponse)
async def split_segment(
    segment_id: int,
    request: SegmentSplitRequest,
    db: AsyncSession = Depends(get_db)
):
    """拆分段落"""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    
    text = segment.narration_text
    if request.split_at_position >= len(text):
        raise HTTPException(status_code=400, detail="拆分位置超出文本长度")
    
    # 创建两个新段落
    text1 = text[:request.split_at_position].strip()
    text2 = text[request.split_at_position:].strip()
    
    # 更新原段落
    segment.narration_text = text1
    
    # 创建新段落
    new_segment = Segment(
        project_id=segment.project_id,
        order_index=segment.order_index + 1,
        narration_text=text2,
        visual_prompt=segment.visual_prompt,  # 继承
        mood=segment.mood,
        shot_type=segment.shot_type,
        status=SegmentStatus.READY_SCRIPT
    )
    db.add(new_segment)
    
    # 更新后续段落的顺序
    await db.execute(
        update(Segment)
        .where(Segment.project_id == segment.project_id)
        .where(Segment.order_index > segment.order_index)
        .where(Segment.id != new_segment.id)
        .values(order_index=Segment.order_index + 1)
    )
    
    await db.commit()
    await db.refresh(segment)
    await db.refresh(new_segment)
    
    return SegmentListResponse(total=2, items=[segment, new_segment])


@router.post("/{segment_id}/merge", response_model=SegmentResponse)
async def merge_segments(
    segment_id: int,
    request: SegmentMergeRequest,
    db: AsyncSession = Depends(get_db)
):
    """合并段落"""
    result1 = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment1 = result1.scalar_one_or_none()
    if not segment1:
        raise HTTPException(status_code=404, detail="源段落不存在")
    
    result2 = await db.execute(select(Segment).where(Segment.id == request.merge_with_segment_id))
    segment2 = result2.scalar_one_or_none()
    if not segment2:
        raise HTTPException(status_code=404, detail="目标段落不存在")
    
    if segment1.project_id != segment2.project_id:
        raise HTTPException(status_code=400, detail="段落不属于同一项目")
    
    # 合并文本
    segment1.narration_text = f"{segment1.narration_text}\n\n{segment2.narration_text}"
    if segment2.visual_prompt and not segment1.visual_prompt:
        segment1.visual_prompt = segment2.visual_prompt
    
    # 删除第二个段落
    await db.delete(segment2)
    
    # 重新排序
    await db.execute(
        update(Segment)
        .where(Segment.project_id == segment1.project_id)
        .where(Segment.order_index > segment2.order_index)
        .values(order_index=Segment.order_index - 1)
    )
    
    await db.commit()
    await db.refresh(segment1)
    return segment1


@router.post("/projects/{project_id}/reorder")
async def reorder_segments(
    project_id: int,
    request: SegmentReorderRequest,
    db: AsyncSession = Depends(get_db)
):
    """重新排序段落"""
    for idx, segment_id in enumerate(request.segment_ids):
        await db.execute(
            update(Segment)
            .where(Segment.id == segment_id)
            .where(Segment.project_id == project_id)
            .values(order_index=idx)
        )
    await db.commit()
    return {"status": "success", "message": "段落顺序已更新"}


# ============ 图片生成相关 ============

@router.get("/{segment_id}/images", response_model=AssetListResponse)
async def list_segment_images(
    segment_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取段落的所有候选图片"""
    result = await db.execute(
        select(Asset)
        .where(Asset.segment_id == segment_id)
        .where(Asset.asset_type == AssetType.IMAGE)
        .order_by(Asset.created_at.desc())
    )
    assets = result.scalars().all()
    return AssetListResponse(total=len(assets), items=assets)


@router.post("/{segment_id}/images/generate")
async def generate_images(
    segment_id: int,
    request: ImageGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """为段落生成图片"""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    
    # 创建生成任务
    job = await generate_segment_images(
        db=db,
        segment=segment,
        count=request.count,
        override_prompt=request.override_prompt,
        override_seed=request.override_seed
    )
    
    # 直接执行图片生成（不通过 Celery）
    # 对于 Pollinations 等云端服务，这样可以立即返回结果
    gen_result = await execute_image_generation(db, job)
    
    if gen_result.get("success"):
        return {
            "job_id": job.id,
            "status": "completed",
            "message": f"图片生成完成，共 {len(gen_result.get('asset_ids', []))} 张",
            "asset_ids": gen_result.get("asset_ids", []),
            "assets": gen_result.get("assets", [])
        }
    else:
        return {
            "job_id": job.id,
            "status": "failed",
            "message": gen_result.get("error", "生成失败"),
            "error": gen_result.get("error")
        }


@router.post("/{segment_id}/images/{asset_id}/select", response_model=SegmentResponse)
async def select_image(
    segment_id: int,
    asset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """选择最终使用的图片"""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    
    # 验证资产存在且属于该段落
    asset_result = await db.execute(
        select(Asset)
        .where(Asset.id == asset_id)
        .where(Asset.segment_id == segment_id)
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="图片资产不存在或不属于该段落")
    
    segment.selected_image_asset_id = asset_id
    if segment.status == SegmentStatus.GENERATING_IMAGES:
        segment.status = SegmentStatus.IMAGES_READY
    
    await db.commit()
    await db.refresh(segment)
    return segment


@router.post("/{segment_id}/scenes/{scene_index}/select/{asset_id}", response_model=SegmentResponse)
async def select_scene_image(
    segment_id: int,
    scene_index: int,
    asset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """为特定场景选择图片"""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    
    # 验证资产存在且属于该段落和场景
    asset_result = await db.execute(
        select(Asset)
        .where(Asset.id == asset_id)
        .where(Asset.segment_id == segment_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="图片资产不存在或不属于该段落")
    
    # 验证资产属于指定场景
    asset_scene_index = asset.asset_metadata.get("scene_index") if asset.asset_metadata else None
    if asset_scene_index != scene_index:
        raise HTTPException(status_code=400, detail="该图片不属于指定场景")
    
    # 更新场景选择
    segment_metadata = dict(segment.segment_metadata or {})  # 创建副本
    selected_scene_images = dict(segment_metadata.get("selected_scene_images", {}))  # 创建副本
    selected_scene_images[str(scene_index)] = asset_id
    
    # 使用 flag_modified 确保 SQLAlchemy 检测到 JSON 字段变化
    from sqlalchemy.orm.attributes import flag_modified
    segment.segment_metadata = {
        **segment_metadata,
        "selected_scene_images": selected_scene_images
    }
    flag_modified(segment, "segment_metadata")
    
    if segment.status == SegmentStatus.GENERATING_IMAGES:
        segment.status = SegmentStatus.IMAGES_READY
    
    await db.commit()
    await db.refresh(segment)
    return segment


# ============ 音频生成相关 ============

@router.post("/{segment_id}/audio/generate")
async def generate_audio(
    segment_id: int,
    request: AudioGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """为段落生成音频"""
    from app.services.audio_generator import execute_audio_generation
    
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="段落不存在")
    
    # 创建生成任务
    job = await generate_segment_audio(
        db=db,
        segment=segment,
        override_text=request.override_text
    )
    
    # 同步执行音频生成
    gen_result = await execute_audio_generation(db, job)
    
    if gen_result.get("success"):
        # 刷新段落获取最新状态
        await db.refresh(segment)
        return {
            "job_id": job.id,
            "status": "completed",
            "asset_id": gen_result.get("asset_id"),
            "duration_ms": gen_result.get("duration_ms"),
            "message": "音频生成成功"
        }
    else:
        return {
            "job_id": job.id,
            "status": "failed",
            "error": gen_result.get("error"),
            "message": "音频生成失败"
        }
