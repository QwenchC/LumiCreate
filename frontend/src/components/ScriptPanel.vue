<template>
  <div class="script-panel">
    <!-- 顶部操作区 -->
    <div class="panel-header">
      <div class="header-left">
        <el-input 
          v-model="topic" 
          placeholder="输入主题，如：三国演义赤壁之战" 
          style="width: 300px"
          :disabled="generating"
        />
        <el-button type="primary" @click="handleGenerate" :loading="generating">
          <el-icon><EditPen /></el-icon>
          {{ generating ? '生成中...' : '生成文案' }}
        </el-button>
      </div>
      <div class="header-right">
        <el-button @click="handleAutoSplit" :disabled="!script" :loading="splitting">
          <el-icon><Scissor /></el-icon>
          自动切分
        </el-button>
      </div>
    </div>
    
    <!-- 生成进度提示 -->
    <div class="generation-progress" v-if="generating">
      <el-alert type="info" :closable="false" show-icon>
        <template #title>
          <span>{{ streamStatus }}</span>
        </template>
        <template #default>
          <span class="char-count">已生成 {{ generatedChars }} 字符</span>
        </template>
      </el-alert>
    </div>
    
    <!-- 原始文案编辑 -->
    <div class="raw-script-section" v-if="!segments.length">
      <el-input
        v-model="rawScript"
        type="textarea"
        :rows="15"
        placeholder="生成的文案将显示在这里，你也可以直接粘贴或编辑文案..."
        :readonly="generating"
      />
      <div class="script-actions" v-if="rawScript && !generating">
        <el-button type="primary" @click="handleParse">
          <el-icon><Check /></el-icon>
          解析并切分
        </el-button>
      </div>
    </div>
    
    <!-- 段落编辑器 -->
    <div class="segments-section" v-else>
      <div class="segments-header">
        <span>共 {{ segments.length }} 个段落</span>
        <el-button text type="primary" @click="showRawEditor = true">
          编辑原始文案
        </el-button>
      </div>
      
      <div class="segment-list">
        <div 
          v-for="(segment, index) in segments" 
          :key="segment.id"
          class="segment-item"
          :class="{ active: currentSegment?.id === segment.id }"
          @click="selectSegment(segment)"
        >
          <div class="segment-index">{{ index + 1 }}</div>
          <div class="segment-content">
            <div class="segment-title">{{ segment.segment_title || `段落 ${index + 1}` }}</div>
            <div class="segment-text">{{ segment.narration_text }}</div>
          </div>
          <div class="segment-status">
            <el-tag 
              :type="getSegmentStatusType(segment)" 
              size="small"
            >
              {{ getSegmentStatusLabel(segment) }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 段落详情编辑器 -->
    <el-drawer 
      v-model="showSegmentEditor" 
      title="编辑段落"
      size="500px"
      :destroy-on-close="false"
    >
      <div class="segment-editor" v-if="currentSegment">
        <el-form :model="currentSegment" label-position="top">
          <el-form-item label="段落标题">
            <el-input v-model="editingSegment.segment_title" placeholder="可选" />
          </el-form-item>
          <el-form-item label="旁白文本">
            <el-input 
              v-model="editingSegment.narration_text" 
              type="textarea" 
              :rows="6"
            />
          </el-form-item>
          <el-form-item label="画面描述 (用于生成图片)">
            <el-input 
              v-model="editingSegment.visual_prompt" 
              type="textarea" 
              :rows="4"
              placeholder="描述这个段落对应的画面场景..."
            />
          </el-form-item>
          <el-form-item label="屏幕文字">
            <el-input 
              v-model="editingSegment.on_screen_text" 
              placeholder="可选，显示在画面上的文字"
            />
          </el-form-item>
          <el-form-item label="情绪/氛围">
            <el-select v-model="editingSegment.mood" placeholder="选择氛围">
              <el-option label="紧张" value="紧张" />
              <el-option label="舒缓" value="舒缓" />
              <el-option label="悲伤" value="悲伤" />
              <el-option label="欢快" value="欢快" />
              <el-option label="神秘" value="神秘" />
              <el-option label="史诗" value="史诗" />
            </el-select>
          </el-form-item>
          <el-form-item label="镜头类型">
            <el-select v-model="editingSegment.shot_type" placeholder="选择镜头">
              <el-option label="远景" value="远景" />
              <el-option label="中景" value="中景" />
              <el-option label="近景" value="近景" />
              <el-option label="特写" value="特写" />
            </el-select>
          </el-form-item>
        </el-form>
        
        <div class="editor-actions">
          <el-button type="primary" @click="saveSegment">保存</el-button>
          <el-button @click="showSegmentEditor = false">取消</el-button>
          <el-popconfirm title="确定删除这个段落吗？" @confirm="deleteSegment">
            <template #reference>
              <el-button type="danger" text>删除段落</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </el-drawer>
    
    <!-- 原始文案编辑对话框 -->
    <el-dialog v-model="showRawEditor" title="编辑原始文案" width="800px">
      <el-input
        v-model="rawScript"
        type="textarea"
        :rows="20"
      />
      <template #footer>
        <el-button @click="showRawEditor = false">取消</el-button>
        <el-button type="primary" @click="handleReparse">重新解析</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { scriptApi, segmentApi } from '@/api'
import { useSegmentStore, type Segment } from '@/stores'

const props = defineProps<{
  projectId: number
}>()

const emit = defineEmits<{
  (e: 'segments-updated'): void
}>()

const segmentStore = useSegmentStore()

const topic = ref('')
const rawScript = ref('')
const script = ref<any>(null)
const generating = ref(false)
const splitting = ref(false)
const showSegmentEditor = ref(false)
const showRawEditor = ref(false)
const editingSegment = ref<Partial<Segment>>({})

// 流式生成状态
const streamStatus = ref('准备生成...')
const generatedChars = ref(0)

const segments = computed(() => segmentStore.segments)
const currentSegment = computed(() => segmentStore.currentSegment)

// 监听当前段落变化
watch(currentSegment, (segment) => {
  if (segment) {
    editingSegment.value = { ...segment }
    showSegmentEditor.value = true
  }
})

const handleGenerate = async () => {
  generating.value = true
  rawScript.value = ''
  streamStatus.value = '正在连接服务器...'
  generatedChars.value = 0
  
  try {
    // 使用流式生成
    const response = await scriptApi.generateStream(props.projectId, { topic: topic.value })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法获取响应流')
    }
    
    const decoder = new TextDecoder()
    let buffer = ''
    
    streamStatus.value = '正在生成文案...'
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      
      // 处理 SSE 事件
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // 保留不完整的行
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim()
          if (!dataStr) continue
          
          try {
            const data = JSON.parse(dataStr)
            
            if (data.type === 'start') {
              streamStatus.value = data.message || '开始生成...'
            } else if (data.type === 'chunk') {
              rawScript.value += data.content
              generatedChars.value = rawScript.value.length
            } else if (data.type === 'done') {
              streamStatus.value = data.message || '生成完成'
              script.value = { id: data.script_id }
              ElMessage.success('文案生成成功')
            } else if (data.type === 'error') {
              throw new Error(data.message || '生成失败')
            }
          } catch (e) {
            if (e instanceof SyntaxError) {
              console.warn('JSON 解析失败:', dataStr)
            } else {
              throw e
            }
          }
        }
      }
    }
    
  } catch (error: any) {
    console.error('生成文案失败:', error)
    ElMessage.error(error.message || '生成文案失败')
  } finally {
    generating.value = false
  }
}

const handleParse = async () => {
  if (!rawScript.value.trim()) {
    ElMessage.warning('请先生成或输入文案')
    return
  }
  
  generating.value = true
  try {
    const result: any = await scriptApi.parse(props.projectId, rawScript.value)
    script.value = result
    await segmentStore.fetchSegments(props.projectId)
    emit('segments-updated')
    ElMessage.success('文案解析成功')
  } finally {
    generating.value = false
  }
}

const handleAutoSplit = async () => {
  if (!script.value?.id) {
    ElMessage.warning('请先生成文案')
    return
  }
  
  splitting.value = true
  try {
    await scriptApi.autoSplit(script.value.id)
    await segmentStore.fetchSegments(props.projectId)
    emit('segments-updated')
    ElMessage.success('自动切分成功')
  } finally {
    splitting.value = false
  }
}

const handleReparse = async () => {
  showRawEditor.value = false
  await handleParse()
}

const selectSegment = (segment: Segment) => {
  segmentStore.selectSegment(segment)
}

const saveSegment = async () => {
  if (!currentSegment.value) return
  
  await segmentStore.updateSegment(currentSegment.value.id, editingSegment.value)
  showSegmentEditor.value = false
  ElMessage.success('段落已保存')
}

const deleteSegment = async () => {
  if (!currentSegment.value) return
  
  await segmentApi.delete(currentSegment.value.id)
  await segmentStore.fetchSegments(props.projectId)
  segmentStore.selectSegment(null)
  showSegmentEditor.value = false
  emit('segments-updated')
  ElMessage.success('段落已删除')
}

const getSegmentStatusType = (segment: Segment) => {
  if (segment.selected_image_asset_id && segment.audio_asset_id) return 'success'
  if (segment.selected_image_asset_id || segment.audio_asset_id) return 'warning'
  return 'info'
}

const getSegmentStatusLabel = (segment: Segment) => {
  if (segment.selected_image_asset_id && segment.audio_asset_id) return '就绪'
  if (segment.selected_image_asset_id) return '缺音频'
  if (segment.audio_asset_id) return '缺图片'
  return '待处理'
}
</script>

<style scoped lang="scss">
.script-panel {
  min-height: 500px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  
  .header-left {
    display: flex;
    gap: 12px;
  }
}

.generation-progress {
  margin-bottom: 16px;
  
  .char-count {
    font-size: 12px;
    color: #909399;
  }
}

.raw-script-section {
  .script-actions {
    margin-top: 16px;
    text-align: right;
  }
}

.segments-section {
  .segments-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    font-size: 14px;
    color: #606266;
  }
}

.segment-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.segment-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  
  &:hover {
    background: #e8ecf1;
  }
  
  &.active {
    background: var(--el-color-primary-light-9);
    border: 1px solid var(--el-color-primary-light-5);
  }
  
  .segment-index {
    width: 28px;
    height: 28px;
    background: var(--el-color-primary);
    color: #fff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
    flex-shrink: 0;
  }
  
  .segment-content {
    flex: 1;
    min-width: 0;
    
    .segment-title {
      font-weight: 600;
      margin-bottom: 4px;
    }
    
    .segment-text {
      color: #606266;
      font-size: 13px;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }
  
  .segment-status {
    flex-shrink: 0;
  }
}

.segment-editor {
  .editor-actions {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid #ebeef5;
    display: flex;
    gap: 12px;
  }
}
</style>
