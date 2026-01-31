"""
段落数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.database import Base


class SegmentStatus(str, enum.Enum):
    """段落状态枚举"""
    NEEDS_SCRIPT = "needs_script"
    READY_SCRIPT = "ready_script"
    GENERATING_IMAGES = "generating_images"
    IMAGES_READY = "images_ready"
    GENERATING_AUDIO = "generating_audio"
    AUDIO_READY = "audio_ready"
    READY_TO_COMPOSE = "ready_to_compose"


class Segment(Base):
    """段落模型 - 视频的基本组成单元"""
    __tablename__ = "segments"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    
    # 排序
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # 段落内容
    segment_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    narration_text: Mapped[str] = mapped_column(Text, nullable=False)  # 旁白文本（给配音）
    visual_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 画面提示词（给ComfyUI）
    on_screen_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 屏幕字幕/金句
    
    # 氛围与镜头
    mood: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 紧张/温馨/热血...
    shot_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 远景/中景/特写...
    
    # 最终选用的资产
    selected_image_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assets.id"), 
        nullable=True
    )
    audio_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assets.id"), 
        nullable=True
    )
    
    # 展示时长（毫秒）
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # 状态
    status: Mapped[SegmentStatus] = mapped_column(
        SQLEnum(SegmentStatus), 
        default=SegmentStatus.NEEDS_SCRIPT
    )
    
    # 额外元数据
    segment_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # 关系
    project = relationship("Project", back_populates="segments")
    selected_image = relationship("Asset", foreign_keys=[selected_image_asset_id])
    audio = relationship("Asset", foreign_keys=[audio_asset_id])
    
    def __repr__(self):
        return f"<Segment(id={self.id}, order={self.order_index}, status='{self.status}')>"
