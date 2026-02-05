# LumiCreate - 智能说书人视频生产系统

一个基于 AI 的长视频自动化生产线工具，专为"说书"类内容创作设计。

## 项目简介

LumiCreate 是一个端到端的视频生产系统，支持：

- 🎭 **AI 文案生成** - 使用 DeepSeek 生成高质量说书文案，支持流式输出和分阶段生成
- 🎨 **智能配图** - 集成 ComfyUI 和 Pollinations.ai 双引擎，支持人物一致性
- 🎙️ **语音合成** - 支持 Edge TTS（免费），可配置语速、音调等参数
- 🎬 **视频合成** - 基于 FFmpeg，支持 Ken Burns 效果、转场动画、字幕烧录
- ✨ **AI 助填** - 自然语言描述即可一键配置所有参数

## 功能特性

### 文案生成
- 基于 DeepSeek API 的智能文案生成
- 分阶段流式生成（大纲→章节→段落）
- 支持终止生成和清除文案
- 自动解析和智能切分段落

### 图片生成
- **双引擎支持**：
  - Pollinations.ai：免费云端生图，多种风格模型（zimage/flux/turbo/anime/3d等）
  - ComfyUI：本地部署，可自定义工作流
- **人物一致性**：配置主角描述后自动融合到场景提示词
- 自动翻译中文提示词为 Stable Diffusion 格式英文标签
- 批量生成、多候选图选择

### 语音合成
- 基于 Edge TTS 的免费语音合成
- 多种音色选择（男/女/青年/中年等）
- 可调节语速、音调、音量
- 批量生成、试听预览

### 视频合成
- **Ken Burns 效果**：缓慢推拉缩放，画面更有层次
- **转场效果**：淡入淡出、叠化等
- **字幕支持**：
  - 逐句显示旁白字幕（ASS格式）
  - 可选择烧录字幕或导出外挂字幕文件
  - 自动换行、样式可配置
- 背景音乐（可选）
- 多种视频分辨率

### 项目配置
- AI 助填：输入自然语言如"三国演义主题，水墨风格"自动配置
- 完整的配置面板覆盖所有参数
- 配置持久化保存

## 技术栈

### 后端
- **FastAPI** - 高性能异步 Web 框架
- **SQLAlchemy 2.0** - 异步 ORM
- **SQLite** - 轻量级数据库
- **Celery + Redis** - 分布式任务队列（可选，用于后台任务）

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **TypeScript** - 类型安全
- **Pinia** - 状态管理
- **Element Plus** - UI 组件库
- **Vite** - 下一代前端构建工具

### AI 服务
- **DeepSeek API** - 文案生成、提示词翻译、AI助填
- **Pollinations.ai** - 免费云端图像生成
- **ComfyUI** - 本地图像生成（可选）
- **Edge TTS** - 免费语音合成

### 工具
- **FFmpeg** - 音视频处理

## 项目结构

```
LumiCreate/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由（projects/scripts/segments/config/settings/jobs/assets）
│   │   ├── core/           # 核心配置
│   │   ├── db/             # 数据库初始化
│   │   ├── models/         # ORM 模型（Project/Script/Segment/Asset/Job）
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 业务服务
│   │   │   ├── ai_fill.py           # AI 助填服务
│   │   │   ├── script_generator.py  # 文案生成
│   │   │   ├── image_generator.py   # 图片生成（双引擎）
│   │   │   ├── audio_generator.py   # 语音生成
│   │   │   ├── video_composer.py    # 视频合成
│   │   │   ├── pollinations_client.py # Pollinations API
│   │   │   ├── comfyui_client.py    # ComfyUI API
│   │   │   ├── deepseek_client.py   # DeepSeek API
│   │   │   └── prompt_merger.py     # 人物一致性提示词合并
│   │   ├── tasks/          # Celery 任务（可选）
│   │   ├── celery_app.py   # Celery 配置
│   │   └── main.py         # FastAPI 入口
│   ├── workflows/          # ComfyUI 工作流
│   │   ├── simple.json
│   │   ├── z-image-turbo.json
│   │   └── Multi-LoRA-SD1.json
│   ├── storage/            # 存储目录（图片/音频/视频）
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # 前端代码
│   ├── src/
│   │   ├── api/            # API 客户端
│   │   ├── components/     # Vue 组件
│   │   │   ├── ConfigPanel.vue    # 配置面板（AI助填/图像/语音/视频/人物一致性）
│   │   │   ├── ScriptPanel.vue    # 文案面板（生成/解析/终止/清除）
│   │   │   ├── ImagesPanel.vue    # 图片面板（批量生成/选择）
│   │   │   ├── AudioPanel.vue     # 语音面板（批量生成/试听）
│   │   │   └── ComposePanel.vue   # 合成面板（视频合成/导出）
│   │   ├── layouts/        # 布局组件
│   │   ├── router/         # 路由配置
│   │   ├── stores/         # Pinia 状态
│   │   ├── styles/         # 全局样式
│   │   ├── types/          # TypeScript 类型
│   │   └── views/          # 页面视图
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg（必需，用于视频合成）
- Redis（可选，用于 Celery 任务队列）
- ComfyUI（可选，用于本地图像生成）

### 后端安装

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量配置
cp .env.example .env

# 编辑 .env 文件，配置 DeepSeek API 密钥
```

### 前端安装

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 启动服务

**基本模式（推荐）**：
```bash
# 1. 启动后端 API
cd backend
uvicorn app.main:app --reload --port 8000

# 2. 启动前端（新终端）
cd frontend
npm run dev
```

**完整模式（含 Celery）**：
```bash
# 1. 启动 Redis
redis-server

# 2. 启动后端 API
cd backend
uvicorn app.main:app --reload --port 8000

# 3. 启动 Celery Worker（新终端）
cd backend
celery -A app.celery_app worker --loglevel=info

# 4. 启动前端（新终端）
cd frontend
npm run dev
```

## 环境变量配置

创建 `backend/.env` 文件：

```env
# 应用配置
APP_NAME=LumiCreate
DEBUG=true

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./lumicreate.db

# Redis（可选，用于 Celery）
REDIS_URL=redis://localhost:6379/0

# DeepSeek API（必需）
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ComfyUI（可选）
COMFYUI_HOST=http://localhost:8188

# FFmpeg（如不在 PATH 中需配置）
FFMPEG_PATH=ffmpeg

# 存储路径
STORAGE_PATH=./storage
```

## 使用流程

### 1. 创建项目
点击"创建项目"，输入项目名称。

### 2. 配置参数
在"配置"标签页：
- 使用 **AI 助填**：输入自然语言描述，如"三国演义主题，水墨风格，适合中老年观众"
- 或手动配置各项参数
- 可配置人物一致性（主角描述）

### 3. 生成文案
在"脚本"标签页：
- 输入主题，点击"生成文案"
- 支持**终止生成**和**清除文案**
- 或直接粘贴已有文案
- 点击"解析并切分"分割段落

### 4. 生成配图
在"图片"标签页：
- 批量生成所有段落的配图
- 每个段落可生成多张候选图
- 点击选择最满意的图片

### 5. 生成语音
在"语音"标签页：
- 批量生成所有段落的 TTS 语音
- 可试听和重新生成

### 6. 合成视频
在"合成导出"标签页：
- 检查所有段落的图片和音频状态
- 配置 Ken Burns 效果、转场、字幕等
- 点击"开始合成视频"
- 下载或预览生成的视频

## 近期更新

- **人物一致性**：配置主角描述后，AI 会智能判断场景是否包含主角，避免错误融合
- **脚本终止/清除**：文案生成支持终止和清除功能
- **逐句旁白字幕（ASS）**：旁白字幕按句子逐句显示，避免整段字幕遮挡画面
- **嵌入字幕开关**：可控制是否将字幕烧录到视频中
- **Ken Burns 效果优化**：修复抖动问题，画面更流畅
- **转场效果**：支持淡入淡出等转场效果
- **新增工作流**：`z-image-turbo` ComfyUI 工作流，用于更快的图像生成

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发指南

### 添加新的配置选项

1. 在 `backend/app/schemas/config.py` 中添加字段
2. 在 `frontend/src/types/index.ts` 中更新类型
3. 在 `frontend/src/components/ConfigPanel.vue` 中添加表单项

### 添加新的服务

1. 在 `backend/app/services/` 下创建服务文件
2. 在 `backend/app/api/` 下创建 API 路由

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
