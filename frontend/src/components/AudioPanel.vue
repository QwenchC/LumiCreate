<template>
  <div class="audio-panel">
    <!-- 批量操作区 -->
    <div class="panel-header">
      <div class="header-left">
        <el-checkbox 
          v-model="selectAll" 
          :indeterminate="isIndeterminate"
          @change="handleSelectAll"
        >
          全选
        </el-checkbox>
        <span class="selected-count" v-if="selectedIds.length">
          已选 {{ selectedIds.length }} 个段落
        </span>
      </div>
      <div class="header-right">
        <el-button 
          type="primary" 
          @click="handleBatchGenerate"
          :disabled="!selectedIds.length"
          :loading="batchGenerating"
        >
          <el-icon><Microphone /></el-icon>
          批量生成语音
        </el-button>
        <el-button @click="handleGenerateAll" :loading="batchGenerating">
          为所有段落生成
        </el-button>
      </div>
    </div>
    
    <!-- 段落音频列表 -->
    <div class="segment-audio-list" v-loading="loading">
      <div 
        v-for="segment in segments" 
        :key="segment.id"
        class="segment-audio-item"
      >
        <div class="item-header">
          <el-checkbox 
            :model-value="selectedIds.includes(segment.id)"
            @change="(val: boolean) => toggleSelect(segment.id, val)"
          />
          <span class="segment-title">
            {{ segment.segment_title || `段落 ${segment.order_index + 1}` }}
          </span>
          <el-tag v-if="segment.duration_ms" size="small" type="info">
            {{ formatDuration(segment.duration_ms) }}
          </el-tag>
          <el-button 
            text 
            type="primary" 
            size="small"
            @click="handleGenerateSingle(segment.id)"
            :loading="generatingIds.includes(segment.id)"
          >
            <el-icon><Refresh /></el-icon>
            重新生成
          </el-button>
        </div>
        
        <div class="segment-text">
          {{ segment.narration_text }}
        </div>
        
        <div class="audio-player" v-if="segment.audio_asset_id">
          <audio 
            :src="getAudioUrl(segment.audio_asset_id)" 
            controls 
            class="audio-element"
          />
          <div class="audio-actions">
            <el-button text size="small" @click="downloadAudio(segment.audio_asset_id)">
              <el-icon><Download /></el-icon>
              下载
            </el-button>
          </div>
        </div>
        
        <div class="no-audio" v-else>
          <el-button size="small" @click="handleGenerateSingle(segment.id)">
            <el-icon><Microphone /></el-icon>
            生成语音
          </el-button>
        </div>
      </div>
      
      <!-- 空状态 -->
      <el-empty v-if="!segments.length" description="请先生成文案并切分段落" />
    </div>
    
    <!-- 总时长统计 -->
    <div class="duration-summary" v-if="totalDuration > 0">
      <el-divider />
      <div class="summary-content">
        <span>总时长: {{ formatDuration(totalDuration) }}</span>
        <span class="audio-count">
          已生成: {{ audioCount }} / {{ segments.length }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useSegmentStore } from '@/stores'
import { jobApi, assetApi } from '@/api'

const props = defineProps<{
  projectId: number
}>()

const segmentStore = useSegmentStore()

const loading = ref(false)
const batchGenerating = ref(false)
const generatingIds = ref<number[]>([])
const selectedIds = ref<number[]>([])

const segments = computed(() => segmentStore.segments)

const selectAll = computed({
  get: () => selectedIds.value.length === segments.value.length && segments.value.length > 0,
  set: () => {}
})

const isIndeterminate = computed(() => 
  selectedIds.value.length > 0 && selectedIds.value.length < segments.value.length
)

const totalDuration = computed(() => 
  segments.value.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
)

const audioCount = computed(() => 
  segments.value.filter(s => s.audio_asset_id).length
)

onMounted(async () => {
  loading.value = true
  try {
    await segmentStore.fetchSegments(props.projectId)
  } finally {
    loading.value = false
  }
})

const formatDuration = (ms: number) => {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

const getAudioUrl = (assetId: number) => {
  return `/api/assets/${assetId}/download`
}

const handleSelectAll = (val: boolean) => {
  if (val) {
    selectedIds.value = segments.value.map(s => s.id)
  } else {
    selectedIds.value = []
  }
}

const toggleSelect = (id: number, val: boolean) => {
  if (val) {
    selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter(i => i !== id)
  }
}

const handleGenerateSingle = async (segmentId: number) => {
  generatingIds.value.push(segmentId)
  try {
    const { segmentApi } = await import('@/api')
    await segmentApi.generateAudio(segmentId)
    ElMessage.success('语音生成任务已提交')
    // 稍后刷新段落状态
    setTimeout(() => {
      segmentStore.fetchSegments(props.projectId)
    }, 2000)
  } finally {
    generatingIds.value = generatingIds.value.filter(id => id !== segmentId)
  }
}

const handleBatchGenerate = async () => {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择段落')
    return
  }
  
  batchGenerating.value = true
  try {
    await jobApi.generateAllAudio(props.projectId, selectedIds.value)
    ElMessage.success(`已为 ${selectedIds.value.length} 个段落创建语音生成任务`)
    selectedIds.value = []
  } finally {
    batchGenerating.value = false
  }
}

const handleGenerateAll = async () => {
  batchGenerating.value = true
  try {
    await jobApi.generateAllAudio(props.projectId)
    ElMessage.success('已为所有段落创建语音生成任务')
  } finally {
    batchGenerating.value = false
  }
}

const downloadAudio = async (assetId: number) => {
  window.open(`/api/assets/${assetId}/download`, '_blank')
}
</script>

<style scoped lang="scss">
.audio-panel {
  min-height: 500px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    
    .selected-count {
      color: var(--el-color-primary);
      font-size: 14px;
    }
  }
  
  .header-right {
    display: flex;
    gap: 12px;
  }
}

.segment-audio-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.segment-audio-item {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  
  .item-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
    
    .segment-title {
      font-weight: 600;
      flex: 1;
    }
  }
  
  .segment-text {
    font-size: 13px;
    color: #606266;
    margin-bottom: 12px;
    line-height: 1.6;
    padding: 12px;
    background: #fff;
    border-radius: 6px;
    border-left: 3px solid var(--el-color-primary);
  }
}

.audio-player {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .audio-element {
    flex: 1;
    height: 40px;
  }
}

.no-audio {
  padding: 12px;
  text-align: center;
  background: #fff;
  border-radius: 6px;
  border: 1px dashed #dcdfe6;
}

.duration-summary {
  margin-top: 24px;
  
  .summary-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 14px;
    color: #606266;
    
    .audio-count {
      color: var(--el-color-primary);
    }
  }
}
</style>
