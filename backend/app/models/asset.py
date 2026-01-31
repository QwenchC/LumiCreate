"""
资产数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.database import Base


class AssetType(str, enum.Enum):
    """资产类型枚举"""
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    SUBTITLE = "subtitle"
    JSON = "json"
    BGM = "bgm"


class Asset(Base):
    """资产模型 - 存储所有生成的文件"""
    __tablename__ = "assets"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    segment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("segments.id"), 
        nullable=True  # 全局资产（如BGM）可为空
    )
    
    # 资产类型
    asset_type: Mapped[AssetType] = mapped_column(SQLEnum(AssetType), nullable=False)
    
    # 文件路径
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 字节
    
    # 资产描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 元数据（用于复现：seed、workflow、prompt、tts params 等）
    asset_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 音频专用：时长（毫秒）
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # 版本（同一段落可能有多个候选图）
    version: Mapped[int] = mapped_column(Integer, default=1)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    
    # 关系
    project = relationship("Project", back_populates="assets")
    
    def __repr__(self):
        return f"<Asset(id={self.id}, type='{self.asset_type}', file='{self.file_name}')>"
