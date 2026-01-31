// 项目状态
export type ProjectStatus = 
  | 'draft' 
  | 'script_ready' 
  | 'images_ready' 
  | 'audio_ready' 
  | 'composable' 
  | 'exported'

// 段落状态
export type SegmentStatus = 
  | 'pending' 
  | 'image_ready' 
  | 'audio_ready' 
  | 'complete'

// 资产类型
export type AssetType = 
  | 'image' 
  | 'audio' 
  | 'video' 
  | 'subtitle' 
  | 'other'

// 任务类型
export type JobType = 
  | 'deepseek' 
  | 'script_parse' 
  | 'image_gen' 
  | 'tts' 
  | 'video_compose' 
  | 'ai_fill'

// 任务状态
export type JobStatus = 
  | 'queued' 
  | 'running' 
  | 'succeeded' 
  | 'failed' 
  | 'canceled'

// 项目配置
export interface ProjectConfig {
  script_generation: ScriptGenerationConfig
  segmenter: SegmenterConfig
  comfyui: ComfyUIConfig
  tts: TTSConfig
  video_composer: VideoComposerConfig
}

export interface ScriptGenerationConfig {
  genre: string
  audience: string
  pacing: string
  language_style: string
  target_duration_minutes: number
  compliance_level: 'strict' | 'moderate' | 'loose'
  forbidden_topics?: string[]
  custom_instructions?: string
}

export interface SegmenterConfig {
  strategy: 'sentence' | 'paragraph' | 'custom'
  min_segment_chars: number
  max_segment_chars: number
  prefer_natural_breaks: boolean
}

export interface ComfyUIConfig {
  workflow_template: string
  style: string
  resolution: string
  steps: number
  cfg_scale: number
  sampler: string
  scheduler: string
  seed?: number
  batch_count: number
  negative_prompt: string
  style_keywords?: string[]
}

export interface TTSConfig {
  engine: 'edge-tts' | 'gpt-sovits'
  voice: string
  speed: number
  pitch?: number
  volume?: number
  output_format: string
  sovits_model?: string
  sovits_ref_audio?: string
}

export interface VideoComposerConfig {
  frame_rate: number
  resolution: string
  transition: string
  transition_duration_ms: number
  subtitle_enabled: boolean
  subtitle_style?: SubtitleStyle
  bgm_enabled: boolean
  bgm_path?: string
  bgm_volume: number
  ken_burns_enabled: boolean
  output_format: string
  output_quality: string
}

export interface SubtitleStyle {
  font_family: string
  font_size: number
  font_color: string
  outline_color: string
  outline_width: number
  position: 'bottom' | 'top' | 'center'
  margin_bottom: number
}

// 项目
export interface Project {
  id: number
  name: string
  description?: string
  status: ProjectStatus
  project_config: ProjectConfig
  created_at: string
  updated_at: string
}

// 脚本
export interface Script {
  id: number
  project_id: number
  raw_text: string
  structured_data?: any
  word_count: number
  estimated_duration_seconds?: number
  version: number
  created_at: string
  updated_at: string
}

// 段落
export interface Segment {
  id: number
  project_id: number
  script_id?: number
  order_index: number
  segment_title?: string
  narration_text: string
  visual_prompt?: string
  on_screen_text?: string
  mood?: string
  shot_type?: string
  status: SegmentStatus
  selected_image_asset_id?: number
  audio_asset_id?: number
  duration_ms?: number
  created_at: string
  updated_at: string
}

// 资产
export interface Asset {
  id: number
  project_id: number
  segment_id?: number
  asset_type: AssetType
  file_path: string
  file_name: string
  file_size?: number
  mime_type?: string
  metadata?: Record<string, any>
  duration_ms?: number
  version: number
  is_selected: boolean
  created_at: string
}

// 任务
export interface Job {
  id: number
  project_id: number
  segment_id?: number
  job_type: JobType
  status: JobStatus
  progress: number
  error_message?: string
  params?: Record<string, any>
  result?: Record<string, any>
  celery_task_id?: string
  created_at: string
  started_at?: string
  finished_at?: string
}

// API 响应
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export interface AIFillRequest {
  description: string
  only_fill_empty?: boolean
}

export interface AIFillResponse {
  suggested_config: Partial<ProjectConfig>
  explanation: string
}

// 配置选项
export interface ConfigOptions {
  genres: string[]
  audiences: string[]
  pacing_options: string[]
  language_styles: string[]
  comfyui_styles: string[]
  resolutions: string[]
  tts_voices: Array<{ value: string; label: string }>
  transitions: string[]
}

export interface ConfigTemplate {
  id: string
  name: string
  description: string
  config: Partial<ProjectConfig>
}
