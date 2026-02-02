<template>
  <div class="task-center">
    <div class="page-header">
      <h1>任务中心</h1>
      <el-button @click="refreshJobs" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>
    
    <div class="task-stats">
      <div class="stat-card">
        <div class="stat-value">{{ runningJobs.length }}</div>
        <div class="stat-label">运行中</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ queuedJobs.length }}</div>
        <div class="stat-label">排队中</div>
      </div>
      <div class="stat-card warning">
        <div class="stat-value">{{ failedJobs.length }}</div>
        <div class="stat-label">失败</div>
      </div>
      <div class="stat-card success">
        <div class="stat-value">{{ succeededJobs.length }}</div>
        <div class="stat-label">完成</div>
      </div>
    </div>
    
    <div class="task-list card">
      <div class="card-header">
        <h3>任务列表</h3>
        <el-select v-model="filterType" placeholder="筛选类型" style="width: 150px" clearable>
          <el-option label="图片生成" value="image_gen" />
          <el-option label="音频生成" value="tts" />
          <el-option label="视频合成" value="video_compose" />
          <el-option label="文案生成" value="deepseek" />
        </el-select>
      </div>
      
      <el-table :data="filteredJobs" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="job_type" label="类型" width="120">
          <template #default="{ row }">
            {{ getJobTypeLabel(row.job_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.progress" 
              :status="row.status === 'failed' ? 'exception' : row.status === 'succeeded' ? 'success' : ''"
              :stroke-width="6"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="200">
          <template #default="{ row }">
            <span class="error-text" v-if="row.error_message">{{ row.error_message }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status === 'failed'" 
              text 
              size="small" 
              type="primary"
              @click="handleRetry(row.id)"
            >
              重试
            </el-button>
            <el-button 
              v-if="row.status === 'running' || row.status === 'queued'" 
              text 
              size="small" 
              type="danger"
              @click="handleCancel(row.id)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import { ElMessage } from 'element-plus'
import { jobApi } from '@/api'

dayjs.extend(utc)
import type { Job } from '@/stores'

const jobs = ref<Job[]>([])
const loading = ref(false)
const filterType = ref('')

// 轮询定时器
let pollTimer: number | null = null

onMounted(() => {
  refreshJobs()
  // 每 5 秒刷新一次
  pollTimer = window.setInterval(refreshJobs, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})

const refreshJobs = async () => {
  loading.value = true
  try {
    // TODO: 需要一个获取所有项目任务的接口，这里暂时模拟
    // 实际应该从所有项目中获取任务
    // const res = await jobApi.listAll()
    // jobs.value = res.items
  } finally {
    loading.value = false
  }
}

const filteredJobs = computed(() => {
  if (!filterType.value) return jobs.value
  return jobs.value.filter(j => j.job_type === filterType.value)
})

const runningJobs = computed(() => jobs.value.filter(j => j.status === 'running'))
const queuedJobs = computed(() => jobs.value.filter(j => j.status === 'queued'))
const failedJobs = computed(() => jobs.value.filter(j => j.status === 'failed'))
const succeededJobs = computed(() => jobs.value.filter(j => j.status === 'succeeded'))

// 后端返回 UTC 时间，转换到 UTC+8 显示
const formatDate = (date: string) => dayjs.utc(date).utcOffset(8).format('YYYY-MM-DD HH:mm:ss')

const getJobTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    image_gen: '图片生成',
    tts: '音频生成',
    video_compose: '视频合成',
    deepseek: '文案生成',
    script_parse: '文案解析',
    ai_fill: 'AI助填'
  }
  return map[type] || type
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    queued: 'info',
    running: 'warning',
    succeeded: 'success',
    failed: 'danger',
    canceled: 'info'
  }
  return map[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '运行中',
    succeeded: '完成',
    failed: '失败',
    canceled: '已取消'
  }
  return map[status] || status
}

const handleRetry = async (id: number) => {
  try {
    await jobApi.retry(id)
    ElMessage.success('任务已重新排队')
    refreshJobs()
  } catch {
    // 错误已处理
  }
}

const handleCancel = async (id: number) => {
  try {
    await jobApi.cancel(id)
    ElMessage.success('任务已取消')
    refreshJobs()
  } catch {
    // 错误已处理
  }
}
</script>

<style scoped lang="scss">
.task-center {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  
  h1 {
    font-size: 24px;
    font-weight: 600;
  }
}

.task-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  
  .stat-value {
    font-size: 32px;
    font-weight: 600;
    color: var(--el-color-primary);
  }
  
  .stat-label {
    font-size: 14px;
    color: #909399;
    margin-top: 4px;
  }
  
  &.warning .stat-value {
    color: var(--el-color-danger);
  }
  
  &.success .stat-value {
    color: var(--el-color-success);
  }
}

.task-list {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  
  h3 {
    font-size: 16px;
    font-weight: 600;
  }
}

.error-text {
  color: var(--el-color-danger);
  font-size: 12px;
}

.empty-text {
  color: #c0c4cc;
}
</style>
