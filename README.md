# LumiCreate - 智能说书人视频生产系统

一个基于 AI 的长视频自动化生产线工具，专为"说书"类内容创作设计。

## 项目简介

LumiCreate 是一个端到端的视频生产系统，支持：

- 🎭 **AI 文案生成** - 使用 DeepSeek 生成高质量说书文案
- 🎨 **智能配图** - 集成 ComfyUI 进行 AI 图像生成
- 🎙️ **语音合成** - 支持 Edge TTS（免费）和 GPT-SoVITS（预留）
- 🎬 **视频合成** - 基于 FFmpeg 的专业视频合成
- ✨ **AI 助填** - 自然语言描述即可配置所有参数

## 技术栈

### 后端
- **FastAPI** - 高性能异步 Web 框架
- **SQLAlchemy 2.0** - 异步 ORM
- **Celery** - 分布式任务队列
- **Redis** - 消息队列和缓存
- **SQLite** - 轻量级数据库

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **TypeScript** - 类型安全
- **Pinia** - 状态管理
- **Element Plus** - UI 组件库
- **Vite** - 下一代前端构建工具

### AI 服务
- **DeepSeek API** - 文案生成
- **ComfyUI** - 图像生成
- **Edge TTS** - 语音合成

## 项目结构

```
LumiCreate/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── db/             # 数据库
│   │   ├── models/         # ORM 模型
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 业务服务
│   │   ├── tasks/          # Celery 任务
│   │   ├── celery_app.py   # Celery 配置
│   │   └── main.py         # FastAPI 入口
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # 前端代码
│   ├── src/
│   │   ├── api/            # API 客户端
│   │   ├── components/     # Vue 组件
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
- Redis
- FFmpeg
- ComfyUI (可选，用于图像生成)

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

# 编辑 .env 文件，配置必要的 API 密钥
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

```bash
# 1. 启动 Redis
redis-server

# 2. 启动后端 API
cd backend
uvicorn app.main:app --reload --port 8000

# 3. 启动 Celery Worker
cd backend
celery -A app.celery_app worker --loglevel=info

# 4. 启动前端
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

# Redis
REDIS_URL=redis://localhost:6379/0

# DeepSeek API
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ComfyUI
COMFYUI_HOST=http://localhost:8188

# FFmpeg
FFMPEG_PATH=ffmpeg

# 存储
STORAGE_PATH=./storage
```

## 使用流程

### 1. 创建项目
点击"创建项目"，输入项目名称。

### 2. 配置参数
在"配置"标签页：
- 使用 **AI 助填**：输入自然语言描述，如"三国演义主题，水墨风格，适合中老年观众"
- 或手动配置各项参数

### 3. 生成文案
在"脚本"标签页：
- 输入主题，点击"生成文案"
- 或直接粘贴已有文案
- 点击"解析并切分"分割段落

### 4. 生成配图
在"图片"标签页：
- 批量生成所有段落的配图
- 每个段落生成多张候选图
- 点击选择最满意的图片

### 5. 生成语音
在"语音"标签页：
- 批量生成所有段落的 TTS 语音
- 可试听和重新生成

### 6. 合成视频
在"合成导出"标签页：
- 检查所有段落的图片和音频状态
- 点击"开始合成视频"
- 下载或预览生成的视频

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
2. 在 `backend/app/tasks/` 下创建 Celery 任务
3. 在 `backend/app/api/` 下创建 API 路由

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
