"""
文案管理 API 路由
"""
import json
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.project import Project
from app.models.script import Script
from app.models.segment import Segment, SegmentStatus
from app.schemas.script import (
    ScriptGenerateRequest, ScriptParseRequest, 
    ScriptResponse, ScriptUpdateRequest
)
from app.schemas.segment import SegmentResponse, SegmentListResponse
from app.services.script_generator import generate_script, stream_generate_script, save_generated_script
from app.services.script_parser import parse_script_to_segments

router = APIRouter()


@router.post("/projects/{project_id}/generate", response_model=ScriptResponse)
async def generate_project_script(
    project_id: int,
    request: ScriptGenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """生成文案（使用 DeepSeek）"""
    # 验证项目存在
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 调用文案生成服务
    script = await generate_script(
        db=db,
        project=project,
        topic=request.topic,
        additional_instructions=request.additional_instructions
    )
    
    return script


@router.post("/projects/{project_id}/generate/stream")
async def stream_generate_project_script(
    project_id: int,
    request: ScriptGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """流式生成文案（SSE）"""
    # 验证项目存在
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 保存请求参数供后续使用
    topic = request.topic
    additional_instructions = request.additional_instructions
    project_id_local = project.id
    project_config = project.project_config
    
    async def event_stream():
        """SSE 事件流生成器"""
        full_response = ""
        
        try:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'message': '开始生成文案...'})}\n\n"
            
            # 流式生成
            async for chunk in stream_generate_script(
                project=project,
                topic=topic,
                additional_instructions=additional_instructions
            ):
                full_response += chunk
                # 发送内容块
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # 生成完成后保存到数据库
            from app.db.database import async_session_factory
            async with async_session_factory() as save_db:
                # 重新获取项目（新的数据库会话）
                result = await save_db.execute(select(Project).where(Project.id == project_id_local))
                fresh_project = result.scalar_one_or_none()
                
                if fresh_project:
                    script = await save_generated_script(
                        db=save_db,
                        project=fresh_project,
                        full_response=full_response,
                        topic=topic,
                        additional_instructions=additional_instructions
                    )
                    
                    # 发送完成事件，包含脚本信息
                    yield f"data: {json.dumps({'type': 'done', 'script_id': script.id, 'message': '文案生成完成'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': '项目不存在'})}\n\n"
        
        except Exception as e:
            import traceback
            error_detail = str(e)
            print(f"流式生成错误: {error_detail}")
            print(traceback.format_exc())
            yield f"data: {json.dumps({'type': 'error', 'message': f'生成失败: {error_detail}'})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )


@router.post("/projects/{project_id}/generate/phased")
async def phased_generate_project_script(
    project_id: int,
    request: ScriptGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    分阶段生成文案（SSE）- 推荐用于长文本
    
    生成流程：
    1. 先生成大纲（标题、钩子、章节列表）
    2. 逐章节生成详细段落内容
    
    SSE事件类型：
    - progress: 进度更新
    - outline: 大纲生成完成
    - chapter: 单个章节生成完成
    - complete: 全部生成完成
    - error: 错误信息
    """
    from app.services.script_generator_v2 import generate_script_phased
    from app.models.project import ProjectStatus
    
    # 验证项目存在
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 获取配置 - 传入完整的 project_config，以便脚本生成器可以访问 segmenter 等其他配置
    config = project.project_config or {}
    topic = request.topic or ""
    additional_instructions = request.additional_instructions or ""
    project_id_local = project.id
    
    async def event_stream():
        """SSE 事件流生成器"""
        final_data = None
        
        try:
            async for event in generate_script_phased(
                config=config,
                topic=topic,
                additional_instructions=additional_instructions
            ):
                event_type = event.get("type")
                
                # 记录完成数据
                if event_type == "complete":
                    final_data = event.get("data")
                
                # 发送SSE事件
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            # 生成完成后保存到数据库
            if final_data:
                from app.db.database import async_session_factory
                async with async_session_factory() as save_db:
                    result = await save_db.execute(select(Project).where(Project.id == project_id_local))
                    fresh_project = result.scalar_one_or_none()
                    
                    if fresh_project:
                        from sqlalchemy import select as sql_select, func
                        version_result = await save_db.execute(
                            sql_select(func.max(Script.version)).where(Script.project_id == project_id_local)
                        )
                        current_max_version = version_result.scalar() or 0
                        
                        # 创建脚本记录
                        script = Script(
                            project_id=project_id_local,
                            title=final_data.get("title", ""),
                            hook=final_data.get("hook", ""),
                            outline=final_data.get("outline", ""),
                            raw_text=json.dumps(final_data, ensure_ascii=False),
                            structured_content={
                                "title": final_data.get("title"),
                                "hook": final_data.get("hook"),
                                "segments": final_data.get("segments", [])
                            },
                            generation_params={
                                "topic": topic,
                                "additional_instructions": additional_instructions,
                                "config": config,
                                "generation_mode": "phased"
                            },
                            version=current_max_version + 1
                        )
                        
                        save_db.add(script)
                        fresh_project.status = ProjectStatus.SCRIPT_READY
                        await save_db.commit()
                        await save_db.refresh(script)
                        
                        yield f"data: {json.dumps({'type': 'saved', 'script_id': script.id}, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            import traceback
            error_detail = str(e)
            print(f"分阶段生成错误: {error_detail}")
            print(traceback.format_exc())
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': f'生成失败: {error_detail}'}}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/projects/{project_id}/parse", response_model=SegmentListResponse)
async def parse_project_script(
    project_id: int,
    request: ScriptParseRequest,
    db: AsyncSession = Depends(get_db)
):
    """解析文案并切分为段落"""
    # 验证项目存在
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 调用切分服务
    segments = await parse_script_to_segments(
        db=db,
        project=project,
        raw_text=request.raw_text
    )
    
    return SegmentListResponse(total=len(segments), items=segments)


@router.get("/projects/{project_id}", response_model=ScriptResponse)
async def get_project_script(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取项目文案"""
    result = await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="文案不存在")
    return script


@router.patch("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: int,
    request: ScriptUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新文案"""
    result = await db.execute(select(Script).where(Script.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="文案不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(script, field, value)
    
    await db.commit()
    await db.refresh(script)
    return script


@router.post("/{script_id}/segments/auto-split", response_model=SegmentListResponse)
async def auto_split_script(
    script_id: int,
    db: AsyncSession = Depends(get_db)
):
    """自动切分文案为段落"""
    result = await db.execute(select(Script).where(Script.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="文案不存在")
    
    # 获取项目
    project_result = await db.execute(select(Project).where(Project.id == script.project_id))
    project = project_result.scalar_one_or_none()
    
    # 使用结构化内容或原始文本进行切分
    text_to_parse = script.raw_text or ""
    if script.structured_content:
        # 如果已有结构化内容，直接使用
        segments_data = script.structured_content.get("segments", [])
        segments = []
        for idx, seg_data in enumerate(segments_data):
            # 处理多场景 visual_prompts（数组）
            visual_prompts = seg_data.get("visual_prompts", [])
            visual_prompt = seg_data.get("visual_prompt")
            
            # 兼容处理：如果有 visual_prompts 数组，使用第一个作为主 visual_prompt
            if visual_prompts and isinstance(visual_prompts, list):
                visual_prompt = visual_prompts[0] if visual_prompts else visual_prompt
            elif visual_prompt and not visual_prompts:
                # 兼容旧格式：单个 visual_prompt 转为数组
                visual_prompts = [visual_prompt]
            
            segment = Segment(
                project_id=script.project_id,
                order_index=idx,
                segment_title=seg_data.get("segment_title"),
                narration_text=seg_data.get("narration_text", ""),
                visual_prompt=visual_prompt,
                on_screen_text=seg_data.get("on_screen_text"),
                mood=seg_data.get("mood"),
                shot_type=seg_data.get("shot_type"),
                status=SegmentStatus.READY_SCRIPT,
                segment_metadata={
                    "visual_prompts": visual_prompts,  # 存储完整的场景列表
                    "chapter_id": seg_data.get("chapter_id"),
                    "chapter_title": seg_data.get("chapter_title")
                }
            )
            db.add(segment)
            segments.append(segment)
        await db.commit()
        for seg in segments:
            await db.refresh(seg)
        return SegmentListResponse(total=len(segments), items=segments)
    else:
        # 否则调用解析服务
        segments = await parse_script_to_segments(
            db=db,
            project=project,
            raw_text=text_to_parse
        )
        return SegmentListResponse(total=len(segments), items=segments)
