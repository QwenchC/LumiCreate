<template>
  <div class="compose-panel">
    <!-- 合成状态概览 -->
    <div class="compose-overview">
      <div class="overview-card">
        <div class="card-icon segments">
          <el-icon><Document /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">{{ segments.length }}</div>
          <div class="card-label">总段落数</div>
        </div>
      </div>
      
      <div class="overview-card">
        <div class="card-icon images" :class="{ ready: imagesReady }">
          <el-icon><Picture /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">{{ imageCount }} / {{ segments.length }}</div>
          <div class="card-label">图片就绪</div>
        </div>
      </div>
      
      <div class="overview-card">
        <div class="card-icon audio" :class="{ ready: audioReady }">
          <el-icon><Microphone /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">{{ audioCount }} / {{ segments.length }}</div>
          <div class="card-label">音频就绪</div>
        </div>
      </div>
      
      <div class="overview-card">
        <div class="card-icon duration">
          <el-icon><Timer /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">{{ formatDuration(totalDuration) }}</div>
          <div class="card-label">预估时长</div>
        </div>
      </div>
    </div>
    
    <!-- 合成检查 -->
    <div class="compose-checklist">
      <h3>合成前检查</h3>
      <div class="checklist-items">
        <div class="check-item" :class="{ passed: segments.length > 0 }">
          <el-icon><Check v-if="segments.length > 0" /><Close v-else /></el-icon>
          <span>已生成段落</span>
        </div>
        <div class="check-item" :class="{ passed: imagesReady }">
          <el-icon><Check v-if="imagesReady" /><Close v-else /></el-icon>
          <span>所有段落已选择图片</span>
        </div>
        <div class="check-item" :class="{ passed: audioReady }">
          <el-icon><Check v-if="audioReady" /><Close v-else /></el-icon>
          <span>所有段落已生成音频</span>
        </div>
      </div>
    </div>
    
    <!-- 合成操作 -->
    <div class="compose-actions">
      <el-button 
        type="primary" 
        size="large"
        :disabled="!canCompose || isGlobalComposing"
        :loading="isGlobalComposing"
        @click="handleCompose"
      >
        <el-icon><VideoCamera /></el-icon>
        {{ isGlobalComposing ? '正在合成中...' : '开始合成视频' }}
      </el-button>
      <p class="action-hint" v-if="!canCompose && !isGlobalComposing">
        请确保所有段落都有图片和音频
      </p>
      <p class="action-hint" v-else-if="isGlobalComposing">
        视频合成中，请耐心等待...
      </p>
    </div>
    
    <!-- 合成任务列表 -->
    <div class="compose-jobs" v-if="composeJobs.length">
      <h3>合成任务</h3>
      <div class="job-list">
        <div 
          v-for="job in composeJobs" 
          :key="job.id"
          class="job-item"
        >
          <div class="job-header">
            <div class="job-info">
              <el-tag :type="getJobStatusType(job.status)" size="small">
                {{ getJobStatusLabel(job.status) }}
              </el-tag>
              <span class="job-time">{{ formatDate(job.created_at) }}</span>
            </div>
            <div class="job-controls">
              <!-- 取消按钮：仅排队中或运行中显示 -->
              <el-button 
                v-if="job.status === 'queued' || job.status === 'running'"
                type="warning" 
                size="small" 
                @click="cancelJob(job)"
                :loading="cancelingJobId === job.id"
              >
                <el-icon><Close /></el-icon>
                取消
              </el-button>
              <!-- 删除按钮：已完成、失败、已取消时显示 -->
              <el-popconfirm
                v-if="job.status === 'succeeded' || job.status === 'failed' || job.status === 'canceled'"
                title="确定要删除此任务记录吗？"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="deleteJob(job)"
              >
                <template #reference>
                  <el-button 
                    type="danger" 
                    size="small"
                    :loading="deletingJobId === job.id"
                  >
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-progress 
            :percentage="job.progress" 
            :status="job.status === 'failed' ? 'exception' : job.status === 'succeeded' ? 'success' : ''"
          />
          <div class="job-actions" v-if="job.status === 'succeeded' && job.result?.output_path">
            <el-button type="primary" size="small" @click="downloadVideo(job)">
              <el-icon><Download /></el-icon>
              下载视频
            </el-button>
            <el-button size="small" @click="previewVideo(job)">
              <el-icon><VideoPlay /></el-icon>
              预览
            </el-button>
          </div>
          <div class="job-error" v-if="job.status === 'failed' && job.error_message">
            {{ job.error_message }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- 视频预览对话框 -->
    <el-dialog v-model="showPreview" title="视频预览" width="800px">
      <video 
        v-if="previewUrl" 
        :src="previewUrl" 
        controls 
        class="preview-video"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { useSegmentStore, useJobStore, type Job } from '@/stores'
import { jobApi } from '@/api'

const props = defineProps<{
  projectId: number
}>()

const segmentStore = useSegmentStore()
const jobStore = useJobStore()

const composing = ref(false)
const composeJobs = ref<Job[]>([])
const showPreview = ref(false)
const previewUrl = ref('')
const cancelingJobId = ref<number | null>(null)
const deletingJobId = ref<number | null>(null)

let pollTimer: number | null = null

const segments = computed(() => segmentStore.segments)

// 使用全局合成状态来禁用按钮
const isGlobalComposing = computed(() => jobStore.isComposing || composing.value)

const imageCount = computed(() => 
  segments.value.filter(s => s.selected_image_asset_id).length
)

const audioCount = computed(() => 
  segments.value.filter(s => s.audio_asset_id).length
)

const imagesReady = computed(() => 
  segments.value.length > 0 && imageCount.value === segments.value.length
)

const audioReady = computed(() => 
  segments.value.length > 0 && audioCount.value === segments.value.length
)

const canCompose = computed(() => imagesReady.value && audioReady.value)

const totalDuration = computed(() => 
  segments.value.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
)

onMounted(() => {
  fetchComposeJobs()
  // 每 5 秒刷新一次任务状态
  pollTimer = window.setInterval(fetchComposeJobs, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})

const fetchComposeJobs = async () => {
  try {
    const res: any = await jobApi.list(props.projectId, { job_type: 'video_compose' })
    composeJobs.value = res.items
    // 更新全局合成状态
    const hasRunningJob = res.items.some(
      (j: Job) => j.status === 'running' || j.status === 'queued'
    )
    jobStore.setComposing(hasRunningJob)
  } catch {
    // 静默处理
  }
}

const formatDuration = (ms: number) => {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

const formatDate = (date: string) => {
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

const getJobStatusType = (status: string) => {
  const map: Record<string, string> = {
    queued: 'info',
    running: 'warning',
    succeeded: 'success',
    failed: 'danger',
    canceled: 'info'
  }
  return map[status] || 'info'
}

const getJobStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '合成中',
    succeeded: '已完成',
    failed: '失败',
    canceled: '已取消'
  }
  return map[status] || status
}

const handleCompose = async () => {
  composing.value = true
  jobStore.setComposing(true)
  try {
    await jobApi.composeVideo(props.projectId)
    ElMessage.success('视频合成任务已创建')
    fetchComposeJobs()
  } catch {
    jobStore.setComposing(false)
  } finally {
    composing.value = false
  }
}

const downloadVideo = (job: Job) => {
  if (job.result?.output_path) {
    // 通过后端下载
    window.open(`/api/assets/download?path=${encodeURIComponent(job.result.output_path)}`, '_blank')
  }
}

const previewVideo = (job: Job) => {
  if (job.result?.output_path) {
    previewUrl.value = `/api/assets/download?path=${encodeURIComponent(job.result.output_path)}`
    showPreview.value = true
  }
}

const cancelJob = async (job: Job) => {
  cancelingJobId.value = job.id
  try {
    await jobApi.cancel(job.id)
    ElMessage.success('任务已取消')
    fetchComposeJobs()
  } catch {
    // 错误已在拦截器处理
  } finally {
    cancelingJobId.value = null
  }
}

const deleteJob = async (job: Job) => {
  deletingJobId.value = job.id
  try {
    await jobApi.delete(job.id)
    ElMessage.success('任务已删除')
    fetchComposeJobs()
  } catch {
    // 错误已在拦截器处理
  } finally {
    deletingJobId.value = null
  }
}
</script>

<style scoped lang="scss">
.compose-panel {
  max-width: 900px;
  margin: 0 auto;
}

.compose-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.overview-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 12px;
  
  .card-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    
    &.segments {
      background: #e6f4ff;
      color: #1677ff;
    }
    
    &.images {
      background: #fff7e6;
      color: #fa8c16;
      
      &.ready {
        background: #f6ffed;
        color: #52c41a;
      }
    }
    
    &.audio {
      background: #fff0f6;
      color: #eb2f96;
      
      &.ready {
        background: #f6ffed;
        color: #52c41a;
      }
    }
    
    &.duration {
      background: #f0f5ff;
      color: #2f54eb;
    }
  }
  
  .card-content {
    .card-value {
      font-size: 24px;
      font-weight: 600;
      color: #303133;
    }
    
    .card-label {
      font-size: 13px;
      color: #909399;
    }
  }
}

.compose-checklist {
  background: #f5f7fa;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 32px;
  
  h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
  }
  
  .checklist-items {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .check-item {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #909399;
    
    .el-icon {
      color: #dcdfe6;
    }
    
    &.passed {
      color: #52c41a;
      
      .el-icon {
        color: #52c41a;
      }
    }
  }
}

.compose-actions {
  text-align: center;
  padding: 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  margin-bottom: 32px;
  
  .el-button {
    font-size: 16px;
    padding: 20px 40px;
  }
  
  .action-hint {
    margin-top: 12px;
    color: rgba(255, 255, 255, 0.8);
    font-size: 13px;
  }
}

.compose-jobs {
  h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
  }
}

.job-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.job-item {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  
  .job-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  
  .job-info {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .job-time {
      font-size: 13px;
      color: #909399;
    }
  }
  
  .job-controls {
    display: flex;
    gap: 8px;
  }
  
  .job-actions {
    margin-top: 12px;
    display: flex;
    gap: 12px;
  }
  
  .job-error {
    margin-top: 12px;
    padding: 8px 12px;
    background: #fef0f0;
    color: #f56c6c;
    font-size: 13px;
    border-radius: 4px;
  }
}

.preview-video {
  width: 100%;
  max-height: 450px;
}
</style>
