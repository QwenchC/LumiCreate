<template>
  <div class="images-panel">
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
          <el-icon><Picture /></el-icon>
          批量生成图片
        </el-button>
        <el-button @click="handleGenerateAll" :loading="batchGenerating">
          为所有段落生成
        </el-button>
      </div>
    </div>
    
    <!-- 段落图片列表 -->
    <div class="segment-images-list" v-loading="loading">
      <div 
        v-for="segment in segments" 
        :key="segment.id"
        class="segment-images-item"
      >
        <div class="item-header">
          <el-checkbox 
            :model-value="selectedIds.includes(segment.id)"
            @change="(val: boolean) => toggleSelect(segment.id, val)"
          />
          <span class="segment-title">
            {{ segment.segment_title || `段落 ${segment.order_index + 1}` }}
          </span>
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
        
        <div class="segment-text-preview">
          {{ segment.visual_prompt || segment.narration_text }}
        </div>
        
        <div class="images-grid">
          <div 
            v-for="asset in getSegmentImages(segment.id)" 
            :key="asset.id"
            class="image-candidate"
            :class="{ selected: segment.selected_image_asset_id === asset.id }"
            @click="handleSelectImage(segment.id, asset.id)"
          >
            <img :src="getImageUrl(asset)" :alt="asset.file_name" />
            <div class="image-overlay">
              <el-icon v-if="segment.selected_image_asset_id === asset.id"><Check /></el-icon>
            </div>
            <div class="image-version">v{{ asset.version }}</div>
          </div>
          
          <!-- 空状态 -->
          <div 
            v-if="!getSegmentImages(segment.id).length" 
            class="empty-images"
          >
            <el-empty description="暂无图片" :image-size="60">
              <el-button size="small" @click="handleGenerateSingle(segment.id)">
                生成图片
              </el-button>
            </el-empty>
          </div>
        </div>
      </div>
      
      <!-- 空状态 -->
      <el-empty v-if="!segments.length" description="请先生成文案并切分段落" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useSegmentStore, type Segment, type Asset } from '@/stores'
import { jobApi } from '@/api'

const props = defineProps<{
  projectId: number
}>()

const segmentStore = useSegmentStore()

const loading = ref(false)
const batchGenerating = ref(false)
const generatingIds = ref<number[]>([])
const selectedIds = ref<number[]>([])

const segments = computed(() => segmentStore.segments)
const segmentAssets = computed(() => segmentStore.segmentAssets)

const selectAll = computed({
  get: () => selectedIds.value.length === segments.value.length && segments.value.length > 0,
  set: () => {}
})

const isIndeterminate = computed(() => 
  selectedIds.value.length > 0 && selectedIds.value.length < segments.value.length
)

onMounted(async () => {
  loading.value = true
  try {
    // 获取所有段落的图片
    for (const segment of segments.value) {
      await segmentStore.fetchSegmentAssets(segment.id)
    }
  } finally {
    loading.value = false
  }
})

// 监听段落变化，重新加载图片
watch(segments, async (newSegments) => {
  for (const segment of newSegments) {
    if (!segmentAssets.value.has(segment.id)) {
      await segmentStore.fetchSegmentAssets(segment.id)
    }
  }
}, { deep: true })

const getSegmentImages = (segmentId: number): Asset[] => {
  return segmentAssets.value.get(segmentId) || []
}

const getImageUrl = (asset: Asset) => {
  return `/api/assets/${asset.id}/download`
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

const handleSelectImage = async (segmentId: number, assetId: number) => {
  await segmentStore.selectImage(segmentId, assetId)
  ElMessage.success('已选择图片')
}

const handleGenerateSingle = async (segmentId: number) => {
  generatingIds.value.push(segmentId)
  try {
    await segmentStore.generateImages(segmentId)
    // 刷新该段落的图片
    await segmentStore.fetchSegmentAssets(segmentId)
    ElMessage.success('图片生成任务已提交')
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
    await jobApi.generateAllImages(props.projectId, selectedIds.value)
    ElMessage.success(`已为 ${selectedIds.value.length} 个段落创建图片生成任务`)
    selectedIds.value = []
  } finally {
    batchGenerating.value = false
  }
}

const handleGenerateAll = async () => {
  batchGenerating.value = true
  try {
    await jobApi.generateAllImages(props.projectId)
    ElMessage.success('已为所有段落创建图片生成任务')
  } finally {
    batchGenerating.value = false
  }
}
</script>

<style scoped lang="scss">
.images-panel {
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

.segment-images-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.segment-images-item {
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
  
  .segment-text-preview {
    font-size: 13px;
    color: #909399;
    margin-bottom: 12px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.image-candidate {
  position: relative;
  aspect-ratio: 16 / 9;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  border: 3px solid transparent;
  transition: all 0.3s;
  
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  
  .image-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.3);
    opacity: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.3s;
    
    .el-icon {
      font-size: 32px;
      color: #fff;
    }
  }
  
  .image-version {
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 4px;
  }
  
  &:hover {
    .image-overlay {
      opacity: 1;
    }
  }
  
  &.selected {
    border-color: var(--el-color-primary);
    
    .image-overlay {
      opacity: 1;
      background: rgba(var(--el-color-primary-rgb), 0.5);
    }
  }
}

.empty-images {
  grid-column: 1 / -1;
  padding: 20px;
  text-align: center;
}
</style>
