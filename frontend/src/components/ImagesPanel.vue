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
            <!-- 放大预览按钮 -->
            <div 
              class="zoom-btn" 
              @click.stop="handlePreviewImage(asset)"
              title="查看大图"
            >
              <el-icon><ZoomIn /></el-icon>
            </div>
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

    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="90%"
      class="image-preview-dialog"
      :show-close="true"
      :close-on-click-modal="true"
      destroy-on-close
    >
      <div class="preview-wrapper">
        <div class="preview-container">
          <img 
            :src="previewUrl" 
            :alt="previewTitle"
            class="preview-image"
          />
        </div>
        <div class="preview-info" v-if="previewAsset">
          <!-- 原始中文提示词（如有） -->
          <div class="info-section" v-if="previewAsset.asset_metadata?.original_prompt">
            <div class="info-label">原始提示词 (中文)</div>
            <div class="info-content prompt-text">
              {{ previewAsset.asset_metadata.original_prompt }}
            </div>
          </div>
          <!-- 翻译后的英文提示词 / 实际使用的提示词 -->
          <div class="info-section">
            <div class="info-label">
              {{ previewAsset.asset_metadata?.original_prompt ? '翻译后提示词 (English)' : '提示词 (Prompt)' }}
            </div>
            <div class="info-content prompt-text">
              {{ previewAsset.asset_metadata?.prompt || '无提示词信息' }}
            </div>
          </div>
          <div class="info-row">
            <div class="info-item">
              <span class="info-label">生成引擎</span>
              <span class="info-value">{{ previewAsset.asset_metadata?.engine || '未知' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">随机种子</span>
              <span class="info-value">{{ previewAsset.asset_metadata?.seed || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">尺寸</span>
              <span class="info-value">
                {{ previewAsset.asset_metadata?.width || '?' }} × {{ previewAsset.asset_metadata?.height || '?' }}
              </span>
            </div>
            <div class="info-item" v-if="previewAsset.asset_metadata?.model">
              <span class="info-label">模型</span>
              <span class="info-value">{{ previewAsset.asset_metadata.model }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ZoomIn } from '@element-plus/icons-vue'
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

// 图片预览相关
const previewVisible = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')
const previewAsset = ref<Asset | null>(null)

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

const handlePreviewImage = (asset: Asset) => {
  previewUrl.value = getImageUrl(asset)
  previewTitle.value = asset.file_name || '图片预览'
  previewAsset.value = asset
  previewVisible.value = true
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
  
  .zoom-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 32px;
    height: 32px;
    background: rgba(0, 0, 0, 0.6);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: all 0.3s;
    cursor: pointer;
    
    .el-icon {
      font-size: 18px;
      color: #fff;
    }
    
    &:hover {
      background: var(--el-color-primary);
      transform: scale(1.1);
    }
  }
  
  &:hover {
    .image-overlay {
      opacity: 1;
    }
    
    .zoom-btn {
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

// 图片预览对话框样式
.image-preview-dialog {
  .el-dialog__body {
    padding: 0;
    max-height: 85vh;
    overflow: auto;
  }
  
  .preview-wrapper {
    display: flex;
    flex-direction: column;
  }
  
  .preview-container {
    display: flex;
    justify-content: center;
    align-items: center;
    background: #1a1a1a;
    min-height: 300px;
    max-height: 60vh;
    
    .preview-image {
      max-width: 100%;
      max-height: 60vh;
      object-fit: contain;
    }
  }
  
  .preview-info {
    padding: 16px 20px;
    background: #f5f7fa;
    border-top: 1px solid #e4e7ed;
    
    .info-section {
      margin-bottom: 12px;
      
      .info-label {
        font-size: 12px;
        color: #909399;
        margin-bottom: 6px;
        font-weight: 500;
      }
      
      .prompt-text {
        font-size: 13px;
        color: #303133;
        line-height: 1.6;
        padding: 10px 12px;
        background: #fff;
        border-radius: 6px;
        border: 1px solid #e4e7ed;
        max-height: 120px;
        overflow-y: auto;
        word-break: break-all;
      }
    }
    
    .info-row {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      
      .info-item {
        display: flex;
        align-items: center;
        gap: 8px;
        
        .info-label {
          font-size: 12px;
          color: #909399;
        }
        
        .info-value {
          font-size: 13px;
          color: #303133;
          font-weight: 500;
        }
      }
    }
  }
}
</style>
