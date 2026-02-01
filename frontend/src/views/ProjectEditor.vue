<template>
  <div class="project-editor" v-loading="loading">
    <!-- 项目头部 -->
    <div class="editor-header">
      <div class="header-left">
        <el-button text @click="router.push('/')">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h2>{{ project?.name }}</h2>
        <el-tag :type="getStatusType(project?.status)" size="small">
          {{ getStatusLabel(project?.status) }}
        </el-tag>
      </div>
      <div class="header-right">
        <el-button @click="handleExport" :disabled="project?.status !== 'exported'">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        <el-button 
          type="primary" 
          @click="handleCompose" 
          :disabled="!canCompose"
          :loading="isComposing"
        >
          <el-icon><VideoCamera /></el-icon>
          {{ isComposing ? '合成中...' : '合成视频' }}
        </el-button>
      </div>
    </div>
    
    <!-- 标签页 -->
    <el-tabs v-model="activeTab" class="editor-tabs">
      <!-- 配置 Tab -->
      <el-tab-pane label="配置" name="config">
        <ConfigPanel 
          :config="project?.project_config || {}"
          @update="handleConfigUpdate"
        />
      </el-tab-pane>
      
      <!-- 脚本 Tab -->
      <el-tab-pane label="脚本" name="script">
        <ScriptPanel 
          :project-id="projectId"
          @segments-updated="handleSegmentsUpdated"
        />
      </el-tab-pane>
      
      <!-- 图片 Tab -->
      <el-tab-pane label="图片" name="images">
        <ImagesPanel :project-id="projectId" />
      </el-tab-pane>
      
      <!-- 语音 Tab -->
      <el-tab-pane label="语音" name="audio">
        <AudioPanel :project-id="projectId" />
      </el-tab-pane>
      
      <!-- 合成 Tab -->
      <el-tab-pane label="合成导出" name="compose">
        <ComposePanel :project-id="projectId" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useProjectStore, useSegmentStore, useJobStore } from '@/stores'
import { jobApi } from '@/api'
import ConfigPanel from '@/components/ConfigPanel.vue'
import ScriptPanel from '@/components/ScriptPanel.vue'
import ImagesPanel from '@/components/ImagesPanel.vue'
import AudioPanel from '@/components/AudioPanel.vue'
import ComposePanel from '@/components/ComposePanel.vue'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const segmentStore = useSegmentStore()
const jobStore = useJobStore()

const projectId = computed(() => Number(route.params.id))
const project = computed(() => projectStore.currentProject)
const loading = ref(false)
const activeTab = ref('config')

// 全局合成状态
const isComposing = computed(() => jobStore.isComposing)

onMounted(async () => {
  loading.value = true
  try {
    await projectStore.fetchProject(projectId.value)
    await segmentStore.fetchSegments(projectId.value)
    // 获取任务列表以检查合成状态
    await jobStore.fetchJobs(projectId.value)
  } finally {
    loading.value = false
  }
})

const canCompose = computed(() => {
  const segments = segmentStore.segments
  // 检查是否所有段落都有选定的图片
  return segments.length > 0 && segments.every(s => s.selected_image_asset_id) && !isComposing.value
})

const getStatusType = (status?: string) => {
  if (!status) return 'info'
  const map: Record<string, string> = {
    draft: 'info',
    script_ready: 'warning',
    images_ready: 'warning',
    audio_ready: 'warning',
    composable: 'success',
    exported: 'success'
  }
  return map[status] || 'info'
}

const getStatusLabel = (status?: string) => {
  if (!status) return ''
  const map: Record<string, string> = {
    draft: '草稿',
    script_ready: '文案已生成',
    images_ready: '图片已生成',
    audio_ready: '音频已生成',
    composable: '可合成',
    exported: '已导出'
  }
  return map[status] || status
}

const handleConfigUpdate = async (config: any) => {
  await projectStore.updateConfig(config)
  // 提示消息已在 ConfigPanel 中显示，这里不再重复
}

const handleSegmentsUpdated = () => {
  segmentStore.fetchSegments(projectId.value)
}

const handleCompose = async () => {
  if (isComposing.value) return
  jobStore.setComposing(true)
  try {
    await jobApi.composeVideo(projectId.value)
    ElMessage.success('视频合成任务已创建')
    activeTab.value = 'compose'
    // 刷新任务列表
    await jobStore.fetchJobs(projectId.value)
  } catch (e) {
    jobStore.setComposing(false)
    // 错误已在拦截器处理
  }
}

const handleExport = () => {
  // TODO: 实现导出功能
  ElMessage.info('导出功能开发中')
}
</script>

<style scoped lang="scss">
.project-editor {
  max-width: 1600px;
  margin: 0 auto;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 16px;
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    
    h2 {
      font-size: 18px;
      font-weight: 600;
      margin: 0;
    }
  }
  
  .header-right {
    display: flex;
    gap: 12px;
  }
}

.editor-tabs {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  
  :deep(.el-tabs__content) {
    padding-top: 20px;
  }
}
</style>
