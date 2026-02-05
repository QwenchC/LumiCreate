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
        <el-button type="primary" @click="handleGenerate" :loading="generating" :disabled="generating">
          <el-icon><EditPen /></el-icon>
          {{ generating ? '生成中...' : '生成文案' }}
        </el-button>
        <el-button v-if="generating" type="danger" @click="handleAbort">
          <el-icon><CloseBold /></el-icon>
          终止生成
        </el-button>
        <el-button v-if="rawScript && !generating" type="warning" @click="handleClear">
          <el-icon><Delete /></el-icon>
          清除文案
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
          <div class="progress-info">
            <span class="char-count">已生成 {{ generatedChars }} 字符</span>
            <span v-if="generationProgress.totalChapters > 0" class="chapter-progress">
              · 章节进度: {{ generationProgress.currentChapter }} / {{ generationProgress.totalChapters }}
            </span>
          </div>
          <el-progress 
            v-if="generationProgress.totalChapters > 0"
            :percentage="Math.round((generationProgress.currentChapter / generationProgress.totalChapters) * 100)"
            :stroke-width="8"
            style="margin-top: 8px"
          />
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
          
          <!-- 多场景画面描述 -->
          <el-form-item v-if="hasMultipleVisualPrompts" label="画面描述 (多场景模式)">
            <div class="visual-prompts-list">
              <div 
                v-for="(prompt, index) in editingVisualPrompts" 
                :key="index" 
                class="visual-prompt-item"
              >
                <div class="prompt-header">
                  <el-tag size="small" type="primary">场景 {{ index + 1 }}</el-tag>
                </div>
                <el-input 
                  v-model="editingVisualPrompts[index]" 
                  type="textarea" 
                  :rows="3"
                  :placeholder="`描述场景 ${index + 1} 的画面...`"
                />
              </div>
            </div>
          </el-form-item>
          
          <!-- 单场景画面描述（向后兼容） -->
          <el-form-item v-else label="画面描述 (用于生成图片)">
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
const editingVisualPrompts = ref<string[]>([])
const abortController = ref<AbortController | null>(null)

// 流式生成状态
const streamStatus = ref('准备生成...')
const generatedChars = ref(0)
const generationProgress = ref({
  currentChapter: 0,
  totalChapters: 0,
  phase: ''
})

const segments = computed(() => segmentStore.segments)
const currentSegment = computed(() => segmentStore.currentSegment)

// 检查当前段落是否有多个场景
const hasMultipleVisualPrompts = computed(() => {
  const prompts = currentSegment.value?.segment_metadata?.visual_prompts
  return Array.isArray(prompts) && prompts.length > 1
})

// 监听当前段落变化
watch(currentSegment, (segment) => {
  if (segment) {
    editingSegment.value = { ...segment }
    // 初始化多场景编辑数组
    const visualPrompts = segment.segment_metadata?.visual_prompts
    if (Array.isArray(visualPrompts) && visualPrompts.length > 0) {
      editingVisualPrompts.value = [...visualPrompts]
    } else if (segment.visual_prompt) {
      editingVisualPrompts.value = [segment.visual_prompt]
    } else {
      editingVisualPrompts.value = []
    }
    showSegmentEditor.value = true
  }
})

const handleGenerate = async () => {
  generating.value = true
  rawScript.value = ''
  streamStatus.value = '正在连接服务器...'
  generatedChars.value = 0
  generationProgress.value = { currentChapter: 0, totalChapters: 0, phase: '' }
  
  // 创建新的 AbortController
  abortController.value = new AbortController()
  
  try {
    // 使用分阶段流式生成（更适合长文本）
    const response = await scriptApi.generatePhased(
      props.projectId, 
      { topic: topic.value },
      abortController.value.signal
    )
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法获取响应流')
    }
    
    const decoder = new TextDecoder()
    let buffer = ''
    let accumulatedSegments: any[] = []
    let scriptTitle = ''
    let scriptHook = ''
    
    streamStatus.value = '正在生成大纲...'
    
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
            const event = JSON.parse(dataStr)
            
            if (event.type === 'progress') {
              // 进度更新
              const progress = event.data
              generationProgress.value = {
                currentChapter: progress.current_chapter || 0,
                totalChapters: progress.total_chapters || 0,
                phase: progress.phase || ''
              }
              streamStatus.value = progress.message || '生成中...'
              
            } else if (event.type === 'outline') {
              // 大纲生成完成
              const outline = event.data
              scriptTitle = outline.title || ''
              scriptHook = outline.hook || ''
              generationProgress.value.totalChapters = outline.chapters?.length || 0
              
              // 显示大纲内容
              rawScript.value = `【标题】${scriptTitle}\n\n【钩子】${scriptHook}\n\n【正在生成章节内容...】\n`
              generatedChars.value = rawScript.value.length
              streamStatus.value = '大纲已生成，开始生成章节内容...'
              
            } else if (event.type === 'chapter') {
              // 单个章节生成完成
              const chapterData = event.data
              const chapterSegments = chapterData.segments || []
              accumulatedSegments.push(...chapterSegments)
              
              // 更新进度
              generationProgress.value.currentChapter = chapterData.chapter_index + 1
              
              // 更新显示的文本
              let fullText = `【标题】${scriptTitle}\n\n【钩子】${scriptHook}\n\n`
              accumulatedSegments.forEach((seg, idx) => {
                fullText += `---段落 ${idx + 1}---\n`
                if (seg.segment_title) fullText += `[${seg.segment_title}]\n`
                fullText += `${seg.narration_text}\n\n`
              })
              rawScript.value = fullText
              generatedChars.value = rawScript.value.length
              
              streamStatus.value = `已完成 ${chapterData.chapter_index + 1}/${generationProgress.value.totalChapters} 章节`
              
            } else if (event.type === 'complete') {
              // 全部生成完成
              const finalData = event.data
              scriptTitle = finalData.title || scriptTitle
              scriptHook = finalData.hook || scriptHook
              accumulatedSegments = finalData.segments || accumulatedSegments
              
              // 最终显示
              let fullText = `【标题】${scriptTitle}\n\n【钩子】${scriptHook}\n\n`
              accumulatedSegments.forEach((seg, idx) => {
                fullText += `---段落 ${idx + 1}---\n`
                if (seg.segment_title) fullText += `[${seg.segment_title}]\n`
                fullText += `${seg.narration_text}\n\n`
              })
              rawScript.value = fullText
              generatedChars.value = rawScript.value.length
              streamStatus.value = '生成完成！'
              
            } else if (event.type === 'saved') {
              // 保存成功
              script.value = { id: event.script_id }
              ElMessage.success(`文案生成成功！共 ${accumulatedSegments.length} 个段落，${generatedChars.value} 字符`)
              
            } else if (event.type === 'error') {
              throw new Error(event.data?.message || '生成失败')
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
    // 检查是否是用户主动终止
    if (error.name === 'AbortError') {
      streamStatus.value = '已终止生成'
      ElMessage.info('已终止文案生成')
    } else {
      console.error('生成文案失败:', error)
      ElMessage.error(error.message || '生成文案失败')
    }
  } finally {
    generating.value = false
    abortController.value = null
  }
}

// 终止生成
const handleAbort = () => {
  if (abortController.value) {
    abortController.value.abort()
    streamStatus.value = '正在终止...'
  }
}

// 清除文案
const handleClear = () => {
  rawScript.value = ''
  generatedChars.value = 0
  streamStatus.value = ''
  generationProgress.value = { currentChapter: 0, totalChapters: 0, phase: '' }
  script.value = null
  ElMessage.success('已清除文案')
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
  
  // 准备更新数据
  const updateData = { ...editingSegment.value }
  
  // 如果有多场景，更新 segment_metadata 中的 visual_prompts
  if (editingVisualPrompts.value.length > 0) {
    const existingMetadata = currentSegment.value.segment_metadata || {}
    updateData.segment_metadata = {
      ...existingMetadata,
      visual_prompts: editingVisualPrompts.value
    }
    // 同时更新主 visual_prompt 为第一个场景
    updateData.visual_prompt = editingVisualPrompts.value[0] || ''
  }
  
  await segmentStore.updateSegment(currentSegment.value.id, updateData)
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
  
  // 多场景画面描述样式
  .visual-prompts-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    
    .visual-prompt-item {
      background: #f5f7fa;
      border-radius: 8px;
      padding: 12px;
      border: 1px solid #e4e7ed;
      
      .prompt-header {
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }
  }
}
</style>
