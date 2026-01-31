"""
段落相关的 Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.models.segment import SegmentStatus


class SegmentBase(BaseModel):
    """段落基础 Schema"""
    segment_title: Optional[str] = Field(None, max_length=500, description="段落标题")
    narration_text: str = Field(..., min_length=1, description="旁白文本")
    visual_prompt: Optional[str] = Field(None, description="画面提示词")
    on_screen_text: Optional[str] = Field(None, description="屏幕字幕/金句")
    mood: Optional[str] = Field(None, max_length=100, description="氛围")
    shot_type: Optional[str] = Field(None, max_length=100, description="镜头类型")


class SegmentCreate(SegmentBase):
    """创建段落 Schema"""
    order_index: int = Field(0, ge=0, description="排序索引")


class SegmentUpdate(BaseModel):
    """更新段落 Schema"""
    segment_title: Optional[str] = Field(None, max_length=500, description="段落标题")
    narration_text: Optional[str] = Field(None, min_length=1, description="旁白文本")
    visual_prompt: Optional[str] = Field(None, description="画面提示词")
    on_screen_text: Optional[str] = Field(None, description="屏幕字幕/金句")
    mood: Optional[str] = Field(None, max_length=100, description="氛围")
    shot_type: Optional[str] = Field(None, max_length=100, description="镜头类型")
    order_index: Optional[int] = Field(None, ge=0, description="排序索引")


class SegmentResponse(SegmentBase):
    """段落响应 Schema"""
    id: int
    project_id: int
    order_index: int
    status: SegmentStatus
    selected_image_asset_id: Optional[int]
    audio_asset_id: Optional[int]
    duration_ms: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SegmentListResponse(BaseModel):
    """段落列表响应 Schema"""
    total: int
    items: List[SegmentResponse]


class SegmentSplitRequest(BaseModel):
    """段落拆分请求"""
    split_at_position: int = Field(..., ge=1, description="拆分位置（字符位置）")


class SegmentMergeRequest(BaseModel):
    """段落合并请求"""
    merge_with_segment_id: int = Field(..., description="要合并的目标段落ID")


class SegmentReorderRequest(BaseModel):
    """段落重排序请求"""
    segment_ids: List[int] = Field(..., min_length=1, description="按新顺序排列的段落ID列表")


class ImageGenerateRequest(BaseModel):
    """图片生成请求"""
    count: int = Field(1, ge=1, le=10, description="生成数量")
    override_prompt: Optional[str] = Field(None, description="覆盖的提示词")
    override_seed: Optional[int] = Field(None, description="覆盖的种子")


class ImageSelectRequest(BaseModel):
    """选择最终图片请求"""
    asset_id: int = Field(..., description="选择的资产ID")


class AudioGenerateRequest(BaseModel):
    """音频生成请求"""
    override_text: Optional[str] = Field(None, description="覆盖的文本")
