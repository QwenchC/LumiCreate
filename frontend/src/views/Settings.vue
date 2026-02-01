<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>系统设置</h1>
      <el-button type="primary" @click="handleSave" :loading="saving">
        <el-icon><Check /></el-icon>
        保存设置
      </el-button>
    </div>
    
    <div class="settings-content">
      <!-- DeepSeek API 配置 -->
      <div class="settings-section">
        <div class="section-header">
          <el-icon><Key /></el-icon>
          <h2>DeepSeek API 配置</h2>
        </div>
        <div class="section-desc">用于文案生成和 AI 助填功能</div>
        
        <el-form :model="settings.deepseek" label-width="140px" class="settings-form">
          <el-form-item label="API Key" required>
            <el-input 
              v-model="settings.deepseek.api_key" 
              type="password"
              show-password
              placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
            />
          </el-form-item>
          <el-form-item label="API Base URL">
            <el-input 
              v-model="settings.deepseek.api_base" 
              placeholder="https://api.deepseek.com/v1"
            />
          </el-form-item>
          <el-form-item label="模型">
            <el-select v-model="settings.deepseek.model" placeholder="选择模型">
              <el-option label="deepseek-chat" value="deepseek-chat" />
              <el-option label="deepseek-coder" value="deepseek-coder" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button @click="testDeepSeek" :loading="testingDeepSeek">
              <el-icon><Connection /></el-icon>
              测试连接
            </el-button>
            <el-tag v-if="deepseekStatus === 'success'" type="success" class="status-tag">
              连接成功
            </el-tag>
            <el-tag v-else-if="deepseekStatus === 'error'" type="danger" class="status-tag">
              连接失败
            </el-tag>
          </el-form-item>
        </el-form>
      </div>
      
      <!-- ComfyUI 配置 -->
      <div class="settings-section">
        <div class="section-header">
          <el-icon><Picture /></el-icon>
          <h2>ComfyUI 配置</h2>
        </div>
        <div class="section-desc">用于本地 AI 图片生成（需要 GPU）</div>
        
        <el-form :model="settings.comfyui" label-width="140px" class="settings-form">
          <el-form-item label="API 地址" required>
            <el-input 
              v-model="settings.comfyui.api_url" 
              placeholder="http://localhost:8188"
            />
          </el-form-item>
          <el-form-item label="默认工作流">
            <el-input 
              v-model="settings.comfyui.default_workflow" 
              placeholder="workflow_api.json（可选）"
            />
          </el-form-item>
          <el-form-item>
            <el-button @click="testComfyUI" :loading="testingComfyUI">
              <el-icon><Connection /></el-icon>
              测试连接
            </el-button>
            <el-tag v-if="comfyuiStatus === 'success'" type="success" class="status-tag">
              连接成功
            </el-tag>
            <el-tag v-else-if="comfyuiStatus === 'error'" type="danger" class="status-tag">
              连接失败
            </el-tag>
          </el-form-item>
        </el-form>
      </div>
      
      <!-- Pollinations.ai 配置 -->
      <div class="settings-section">
        <div class="section-header">
          <el-icon><Cloudy /></el-icon>
          <h2>Pollinations.ai 配置</h2>
        </div>
        <div class="section-desc">云端 AI 图片生成（无需 GPU，推荐）</div>
        
        <el-form :model="settings.pollinations" label-width="140px" class="settings-form">
          <el-form-item label="API Key">
            <el-input 
              v-model="settings.pollinations.api_key" 
              type="password"
              show-password
              placeholder="可选，留空使用免费额度"
            />
            <div class="form-tip">API Key 可选，免费用户有速率限制</div>
          </el-form-item>
          <el-form-item label="默认模型">
            <el-select v-model="settings.pollinations.model" placeholder="选择模型" style="width: 100%">
              <el-option label="Flux (默认，质量均衡)" value="flux" />
              <el-option label="Turbo (快速生成)" value="turbo" />
              <el-option label="Flux Realism (写实风格)" value="flux-realism" />
              <el-option label="Flux Anime (动漫风格)" value="flux-anime" />
              <el-option label="Flux 3D (3D风格)" value="flux-3d" />
              <el-option label="Any Dark (暗黑风格)" value="any-dark" />
              <el-option label="Flux Pro (高质量)" value="flux-pro" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button @click="testPollinations" :loading="testingPollinations">
              <el-icon><Connection /></el-icon>
              测试连接
            </el-button>
            <el-tag v-if="pollinationsStatus === 'success'" type="success" class="status-tag">
              连接成功
            </el-tag>
            <el-tag v-else-if="pollinationsStatus === 'error'" type="danger" class="status-tag">
              连接失败
            </el-tag>
          </el-form-item>
        </el-form>
      </div>
      
      <!-- TTS 配置 -->
      <div class="settings-section">
        <div class="section-header">
          <el-icon><Microphone /></el-icon>
          <h2>TTS 语音合成配置</h2>
        </div>
        <div class="section-desc">用于生成旁白语音</div>
        
        <el-form :model="settings.tts" label-width="140px" class="settings-form">
          <el-form-item label="TTS 引擎">
            <el-radio-group v-model="settings.tts.engine">
              <el-radio value="edge-tts">Edge TTS（免费）</el-radio>
              <el-radio value="gpt-sovits" disabled>GPT-SoVITS（开发中）</el-radio>
            </el-radio-group>
          </el-form-item>
          
          <template v-if="settings.tts.engine === 'gpt-sovits'">
            <el-form-item label="GPT-SoVITS 地址">
              <el-input 
                v-model="settings.tts.sovits_url" 
                placeholder="http://localhost:9880"
              />
            </el-form-item>
          </template>
        </el-form>
      </div>
      
      <!-- FFmpeg 配置 -->
      <div class="settings-section">
        <div class="section-header">
          <el-icon><VideoCamera /></el-icon>
          <h2>FFmpeg 配置</h2>
        </div>
        <div class="section-desc">用于视频合成</div>
        
        <el-form :model="settings.ffmpeg" label-width="140px" class="settings-form">
          <el-form-item label="FFmpeg 路径">
            <el-input 
              v-model="settings.ffmpeg.path" 
              placeholder="ffmpeg（已加入PATH则直接填 ffmpeg）"
            />
          </el-form-item>
          <el-form-item>
            <el-button @click="testFFmpeg" :loading="testingFFmpeg">
              <el-icon><Connection /></el-icon>
              检测 FFmpeg
            </el-button>
            <el-tag v-if="ffmpegStatus === 'success'" type="success" class="status-tag">
              {{ ffmpegVersion }}
            </el-tag>
            <el-tag v-else-if="ffmpegStatus === 'error'" type="danger" class="status-tag">
              未检测到 FFmpeg
            </el-tag>
          </el-form-item>
        </el-form>
      </div>
      
      <!-- 存储配置 -->
      <div class="settings-section">
        <div class="section-header">
          <el-icon><Folder /></el-icon>
          <h2>存储配置</h2>
        </div>
        <div class="section-desc">生成文件的存储位置</div>
        
        <el-form :model="settings.storage" label-width="140px" class="settings-form">
          <el-form-item label="存储路径">
            <el-input 
              v-model="settings.storage.path" 
              placeholder="./storage"
            />
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

interface SystemSettings {
  deepseek: {
    api_key: string
    api_base: string
    model: string
  }
  comfyui: {
    api_url: string
    default_workflow: string
  }
  pollinations: {
    api_key: string
    model: string
  }
  tts: {
    engine: string
    sovits_url: string
  }
  ffmpeg: {
    path: string
  }
  storage: {
    path: string
  }
}

const settings = ref<SystemSettings>({
  deepseek: {
    api_key: '',
    api_base: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat'
  },
  comfyui: {
    api_url: 'http://localhost:8188',
    default_workflow: ''
  },
  pollinations: {
    api_key: '',
    model: 'flux'
  },
  tts: {
    engine: 'edge-tts',
    sovits_url: 'http://localhost:9880'
  },
  ffmpeg: {
    path: 'ffmpeg'
  },
  storage: {
    path: './storage'
  }
})

const saving = ref(false)
const testingDeepSeek = ref(false)
const testingComfyUI = ref(false)
const testingPollinations = ref(false)
const testingFFmpeg = ref(false)

const deepseekStatus = ref<'success' | 'error' | ''>('')
const comfyuiStatus = ref<'success' | 'error' | ''>('')
const pollinationsStatus = ref<'success' | 'error' | ''>('')
const ffmpegStatus = ref<'success' | 'error' | ''>('')
const ffmpegVersion = ref('')

onMounted(async () => {
  try {
    const res = await api.get('/settings')
    if (res) {
      // 合并服务器设置
      Object.assign(settings.value, res)
    }
  } catch {
    // 使用默认值
  }
})

const handleSave = async () => {
  saving.value = true
  try {
    await api.post('/settings', settings.value)
    ElMessage.success('设置已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const testDeepSeek = async () => {
  testingDeepSeek.value = true
  deepseekStatus.value = ''
  try {
    await api.post('/settings/test/deepseek', {
      api_key: settings.value.deepseek.api_key,
      api_base: settings.value.deepseek.api_base,
      model: settings.value.deepseek.model
    })
    deepseekStatus.value = 'success'
    ElMessage.success('DeepSeek 连接成功')
  } catch {
    deepseekStatus.value = 'error'
    ElMessage.error('DeepSeek 连接失败，请检查 API Key')
  } finally {
    testingDeepSeek.value = false
  }
}

const testComfyUI = async () => {
  testingComfyUI.value = true
  comfyuiStatus.value = ''
  try {
    await api.post('/settings/test/comfyui', {
      api_url: settings.value.comfyui.api_url
    })
    comfyuiStatus.value = 'success'
    ElMessage.success('ComfyUI 连接成功')
  } catch {
    comfyuiStatus.value = 'error'
    ElMessage.error('ComfyUI 连接失败，请确保 ComfyUI 正在运行')
  } finally {
    testingComfyUI.value = false
  }
}

const testPollinations = async () => {
  testingPollinations.value = true
  pollinationsStatus.value = ''
  try {
    await api.post('/settings/test/pollinations', {
      api_key: settings.value.pollinations.api_key,
      model: settings.value.pollinations.model
    })
    pollinationsStatus.value = 'success'
    ElMessage.success('Pollinations 连接成功')
  } catch {
    pollinationsStatus.value = 'error'
    ElMessage.error('Pollinations 连接失败')
  } finally {
    testingPollinations.value = false
  }
}

const testFFmpeg = async () => {
  testingFFmpeg.value = true
  ffmpegStatus.value = ''
  try {
    const res: any = await api.post('/settings/test/ffmpeg', {
      path: settings.value.ffmpeg.path
    })
    ffmpegStatus.value = 'success'
    ffmpegVersion.value = res.version || 'FFmpeg 可用'
    ElMessage.success('FFmpeg 检测成功')
  } catch {
    ffmpegStatus.value = 'error'
    ElMessage.error('FFmpeg 未检测到，请检查路径配置')
  } finally {
    testingFFmpeg.value = false
  }
}
</script>

<style scoped lang="scss">
.settings-page {
  max-width: 900px;
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

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  
  .section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    
    .el-icon {
      font-size: 20px;
      color: var(--el-color-primary);
    }
    
    h2 {
      font-size: 16px;
      font-weight: 600;
      margin: 0;
    }
  }
  
  .section-desc {
    font-size: 13px;
    color: #909399;
    margin-bottom: 20px;
    padding-left: 28px;
  }
}

.settings-form {
  max-width: 600px;
  
  :deep(.el-form-item__label) {
    font-weight: 500;
  }
}

.status-tag {
  margin-left: 12px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
