"""
文案/脚本相关的 Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ScriptSegmentOutput(BaseModel):
    """脚本段落输出结构"""
    segment_title: Optional[str] = Field(None, description="段落标题")
    narration_text: str = Field(..., description="旁白文本")
    visual_prompt: Optional[str] = Field(None, description="画面提示词")
    on_screen_text: Optional[str] = Field(None, description="屏幕字幕/金句")
    mood: Optional[str] = Field(None, description="氛围")
    shot_type: Optional[str] = Field(None, description="镜头类型")


class ScriptStructuredOutput(BaseModel):
    """脚本结构化输出"""
    title: str = Field(..., description="标题")
    hook: Optional[str] = Field(None, description="开头钩子")
    outline: Optional[str] = Field(None, description="大纲")
    segments: List[ScriptSegmentOutput] = Field(..., description="段落列表")


class ScriptGenerateRequest(BaseModel):
    """文案生成请求"""
    topic: Optional[str] = Field(None, description="主题/话题（可选，会结合配置）")
    additional_instructions: Optional[str] = Field(None, description="额外指令")


class ScriptParseRequest(BaseModel):
    """文案解析请求（将原始文本转为结构化）"""
    raw_text: str = Field(..., min_length=10, description="原始文本")


class ScriptResponse(BaseModel):
    """文案响应 Schema"""
    id: int
    project_id: int
    title: Optional[str]
    hook: Optional[str]
    outline: Optional[str]
    raw_text: Optional[str]
    structured_content: Optional[dict]
    version: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ScriptUpdateRequest(BaseModel):
    """更新文案请求"""
    title: Optional[str] = Field(None, description="标题")
    hook: Optional[str] = Field(None, description="开头钩子")
    outline: Optional[str] = Field(None, description="大纲")
    raw_text: Optional[str] = Field(None, description="原始文本")
