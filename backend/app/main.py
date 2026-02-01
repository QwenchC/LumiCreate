"""
LumiCreate - 智能说书人视频自动化生产线
主应用入口
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.api import projects, scripts, segments, assets, jobs, config
from app.api import settings as settings_api
from app.core.config import settings
from app.db.database import init_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)
# 减少 aiosqlite 和 httpx 的日志输出
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理资源


app = FastAPI(
    title="LumiCreate API",
    description="智能说书人长视频自动化生产线 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(projects.router, prefix="/api/projects", tags=["项目管理"])
app.include_router(scripts.router, prefix="/api/scripts", tags=["文案管理"])
app.include_router(segments.router, prefix="/api/segments", tags=["段落管理"])
app.include_router(assets.router, prefix="/api/assets", tags=["资产管理"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["任务管理"])
app.include_router(config.router, prefix="/api/config", tags=["配置管理"])
app.include_router(settings_api.router, prefix="/api", tags=["系统设置"])

# 静态文件服务 - 提供图片、音频、视频访问
# 确保目录存在
settings.STORAGE_PATH.mkdir(parents=True, exist_ok=True)
settings.IMAGES_PATH.mkdir(parents=True, exist_ok=True)
settings.AUDIO_PATH.mkdir(parents=True, exist_ok=True)
settings.VIDEO_PATH.mkdir(parents=True, exist_ok=True)

# 挂载静态文件目录
app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_PATH)), name="storage")


@app.get("/", tags=["健康检查"])
async def root():
    return {
        "name": "LumiCreate API",
        "version": "0.1.0",
        "status": "running",
        "message": "智能说书人视频自动化生产线"
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "healthy"}
