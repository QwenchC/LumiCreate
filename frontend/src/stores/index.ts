import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { projectApi, segmentApi, assetApi, jobApi } from '@/api'

// 项目类型定义
export interface Project {
  id: number
  name: string
  description?: string
  status: string
  project_config: any
  created_at: string
  updated_at: string
}

export interface Segment {
  id: number
  project_id: number
  order_index: number
  segment_title?: string
  narration_text: string
  visual_prompt?: string
  on_screen_text?: string
  mood?: string
  shot_type?: string
  status: string
  selected_image_asset_id?: number
  audio_asset_id?: number
  duration_ms?: number
  created_at: string
  updated_at: string
}

export interface Asset {
  id: number
  project_id: number
  segment_id?: number
  asset_type: string
  file_path: string
  file_name: string
  file_size?: number
  metadata?: any
  duration_ms?: number
  version: number
  created_at: string
}

export interface Job {
  id: number
  project_id: number
  segment_id?: number
  job_type: string
  status: string
  progress: number
  error_message?: string
  params?: any
  result?: any
  created_at: string
  started_at?: string
  finished_at?: string
}

// 项目 Store
export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const loading = ref(false)
  
  const fetchProjects = async () => {
    loading.value = true
    try {
      const res: any = await projectApi.list()
      projects.value = res.items
    } finally {
      loading.value = false
    }
  }
  
  const fetchProject = async (id: number) => {
    loading.value = true
    try {
      currentProject.value = await projectApi.get(id) as unknown as Project
    } finally {
      loading.value = false
    }
  }
  
  const createProject = async (data: { name: string; description?: string }) => {
    const project = await projectApi.create(data) as unknown as Project
    projects.value.unshift(project)
    return project
  }
  
  const updateConfig = async (config: any) => {
    if (!currentProject.value) return
    await projectApi.updateConfig(currentProject.value.id, config)
    currentProject.value.project_config = config
  }
  
  const deleteProject = async (id: number) => {
    await projectApi.delete(id)
    projects.value = projects.value.filter(p => p.id !== id)
  }
  
  return {
    projects,
    currentProject,
    loading,
    fetchProjects,
    fetchProject,
    createProject,
    updateConfig,
    deleteProject,
  }
})

// 段落 Store
export const useSegmentStore = defineStore('segment', () => {
  const segments = ref<Segment[]>([])
  const currentSegment = ref<Segment | null>(null)
  const segmentAssets = ref<Map<number, Asset[]>>(new Map())
  const loading = ref(false)
  
  const fetchSegments = async (projectId: number) => {
    loading.value = true
    try {
      const res: any = await segmentApi.list(projectId)
      segments.value = res.items
    } finally {
      loading.value = false
    }
  }
  
  const selectSegment = (segment: Segment | null) => {
    currentSegment.value = segment
  }
  
  const updateSegment = async (id: number, data: Partial<Segment>) => {
    const updated = await segmentApi.update(id, data) as unknown as Segment
    const index = segments.value.findIndex(s => s.id === id)
    if (index !== -1) {
      segments.value[index] = updated
    }
    if (currentSegment.value?.id === id) {
      currentSegment.value = updated
    }
  }
  
  const fetchSegmentAssets = async (segmentId: number) => {
    const res: any = await segmentApi.listImages(segmentId)
    segmentAssets.value.set(segmentId, res.items)
  }
  
  const generateImages = async (segmentId: number, count = 3) => {
    return await segmentApi.generateImages(segmentId, { count })
  }
  
  const selectImage = async (segmentId: number, assetId: number) => {
    const segment = await segmentApi.selectImage(segmentId, assetId) as unknown as Segment
    const index = segments.value.findIndex(s => s.id === segmentId)
    if (index !== -1) {
      segments.value[index] = segment
    }
    if (currentSegment.value?.id === segmentId) {
      currentSegment.value = segment
    }
  }
  
  return {
    segments,
    currentSegment,
    segmentAssets,
    loading,
    fetchSegments,
    selectSegment,
    updateSegment,
    fetchSegmentAssets,
    generateImages,
    selectImage,
  }
})

// 任务 Store
export const useJobStore = defineStore('job', () => {
  const jobs = ref<Job[]>([])
  const loading = ref(false)
  
  const fetchJobs = async (projectId: number) => {
    loading.value = true
    try {
      const res: any = await jobApi.list(projectId)
      jobs.value = res.items
    } finally {
      loading.value = false
    }
  }
  
  const runningJobs = computed(() => 
    jobs.value.filter(j => j.status === 'running' || j.status === 'queued')
  )
  
  const failedJobs = computed(() => 
    jobs.value.filter(j => j.status === 'failed')
  )
  
  const retryJob = async (id: number) => {
    await jobApi.retry(id)
    const index = jobs.value.findIndex(j => j.id === id)
    if (index !== -1) {
      jobs.value[index].status = 'queued'
    }
  }
  
  const cancelJob = async (id: number) => {
    await jobApi.cancel(id)
    const index = jobs.value.findIndex(j => j.id === id)
    if (index !== -1) {
      jobs.value[index].status = 'canceled'
    }
  }
  
  return {
    jobs,
    loading,
    runningJobs,
    failedJobs,
    fetchJobs,
    retryJob,
    cancelJob,
  }
})
