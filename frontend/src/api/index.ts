import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 180000,  // 3分钟，足够生成多张图片
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 可以在这里添加 token 等
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default api

// 项目 API
export const projectApi = {
  list: (params?: { skip?: number; limit?: number; status_filter?: string }) =>
    api.get('/projects', { params }),
  
  get: (id: number) => api.get(`/projects/${id}`),
  
  getSummary: (id: number) => api.get(`/projects/${id}/summary`),
  
  create: (data: { name: string; description?: string; project_config?: any }) =>
    api.post('/projects', data),
  
  update: (id: number, data: { name?: string; description?: string; status?: string }) =>
    api.patch(`/projects/${id}`, data),
  
  updateConfig: (id: number, config: any) =>
    api.patch(`/projects/${id}/config`, { project_config: config }),
  
  aiFill: (id: number, data: { description: string; only_fill_empty?: boolean }) =>
    api.post(`/projects/${id}/config/ai-fill`, data),
  
  applyAiFill: (id: number, config: any) =>
    api.post(`/projects/${id}/config/ai-fill/apply`, { project_config: config }),
  
  delete: (id: number) => api.delete(`/projects/${id}`),
}

// 文案 API
export const scriptApi = {
  generate: (projectId: number, data?: { topic?: string; additional_instructions?: string }) =>
    api.post(`/scripts/projects/${projectId}/generate`, data || {}),
  
  // 流式生成文案（简单模式）
  generateStream: (projectId: number, data?: { topic?: string; additional_instructions?: string }) => {
    const body = JSON.stringify(data || {})
    return fetch(`/api/scripts/projects/${projectId}/generate/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body
    })
  },
  
  // 分阶段生成文案（推荐用于长文本）
  generatePhased: (projectId: number, data?: { topic?: string; additional_instructions?: string }, signal?: AbortSignal) => {
    const body = JSON.stringify(data || {})
    return fetch(`/api/scripts/projects/${projectId}/generate/phased`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
      signal
    })
  },
  
  parse: (projectId: number, rawText: string) =>
    api.post(`/scripts/projects/${projectId}/parse`, { raw_text: rawText }),
  
  get: (projectId: number) => api.get(`/scripts/projects/${projectId}`),
  
  update: (scriptId: number, data: any) => api.patch(`/scripts/${scriptId}`, data),
  
  autoSplit: (scriptId: number) => api.post(`/scripts/${scriptId}/segments/auto-split`),
}

// 段落 API
export const segmentApi = {
  list: (projectId: number) => api.get(`/segments/projects/${projectId}`),
  
  get: (id: number) => api.get(`/segments/${id}`),
  
  create: (projectId: number, data: any) => api.post(`/segments/projects/${projectId}`, data),
  
  update: (id: number, data: any) => api.patch(`/segments/${id}`, data),
  
  delete: (id: number) => api.delete(`/segments/${id}`),
  
  split: (id: number, position: number) =>
    api.post(`/segments/${id}/split`, { split_at_position: position }),
  
  merge: (id: number, targetId: number) =>
    api.post(`/segments/${id}/merge`, { merge_with_segment_id: targetId }),
  
  reorder: (projectId: number, segmentIds: number[]) =>
    api.post(`/segments/projects/${projectId}/reorder`, { segment_ids: segmentIds }),
  
  // 图片相关
  listImages: (segmentId: number) => api.get(`/segments/${segmentId}/images`),
  
  generateImages: (segmentId: number, data?: { count?: number; override_prompt?: string }) =>
    api.post(`/segments/${segmentId}/images/generate`, data || {}),
  
  selectImage: (segmentId: number, assetId: number) =>
    api.post(`/segments/${segmentId}/images/${assetId}/select`),
  
  selectSceneImage: (segmentId: number, sceneIndex: number, assetId: number) =>
    api.post(`/segments/${segmentId}/scenes/${sceneIndex}/select/${assetId}`),
  
  // 音频相关
  generateAudio: (segmentId: number, data?: { override_text?: string }) =>
    api.post(`/segments/${segmentId}/audio/generate`, data || {}),
}

// 资产 API
export const assetApi = {
  list: (projectId: number, assetType?: string) =>
    api.get(`/assets/projects/${projectId}`, { params: { asset_type: assetType } }),
  
  get: (id: number) => api.get(`/assets/${id}`),
  
  download: (id: number) => api.get(`/assets/${id}/download`, { responseType: 'blob' }),
  
  delete: (id: number) => api.delete(`/assets/${id}`),
}

// 任务 API
export const jobApi = {
  list: (projectId: number, params?: { job_type?: string; status_filter?: string }) =>
    api.get(`/jobs/projects/${projectId}`, { params }),
  
  get: (id: number) => api.get(`/jobs/${id}`),
  
  cancel: (id: number) => api.post(`/jobs/${id}/cancel`),
  
  retry: (id: number) => api.post(`/jobs/${id}/retry`),
  
  delete: (id: number) => api.delete(`/jobs/${id}`),
  
  retryFailed: (projectId: number, jobIds?: number[]) =>
    api.post(`/jobs/projects/${projectId}/retry-failed`, { job_ids: jobIds }),
  
  // 批量操作
  generateAllImages: (projectId: number, segmentIds?: number[]) =>
    api.post(`/jobs/projects/${projectId}/images/generate-all`, { segment_ids: segmentIds }),
  
  generateAllAudio: (projectId: number, segmentIds?: number[]) =>
    api.post(`/jobs/projects/${projectId}/audio/generate-all`, { segment_ids: segmentIds }),
  
  composeVideo: (projectId: number) =>
    api.post(`/jobs/projects/${projectId}/video/compose`),
}

// 配置 API
export const configApi = {
  getDefault: () => api.get('/config/default'),
  
  getOptions: () => api.get('/config/options'),
  
  getTemplates: () => api.get('/config/templates'),
}
