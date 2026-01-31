"""
文案/脚本数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Script(Base):
    """脚本模型 - 存储生成的文案"""
    __tablename__ = "scripts"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    
    # 脚本内容
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 开头钩子
    outline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 大纲
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 原始文本
    
    # 结构化内容（JSON）
    structured_content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 生成参数记录（用于复现）
    generation_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 版本控制
    version: Mapped[int] = mapped_column(Integer, default=1)
    
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
    project = relationship("Project", back_populates="scripts")
    
    def __repr__(self):
        return f"<Script(id={self.id}, title='{self.title}', version={self.version})>"
