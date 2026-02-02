<template>
  <div class="project-list">
    <div class="page-header">
      <h1>我的项目</h1>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        创建项目
      </el-button>
    </div>
    
    <div class="project-grid" v-loading="store.loading">
      <div 
        v-for="project in store.projects" 
        :key="project.id"
        class="project-card"
        @click="router.push(`/project/${project.id}`)"
      >
        <div class="project-card-header">
          <h3>{{ project.name }}</h3>
          <el-tag :type="getStatusType(project.status)" size="small">
            {{ getStatusLabel(project.status) }}
          </el-tag>
        </div>
        <p class="project-desc">{{ project.description || '暂无描述' }}</p>
        <div class="project-meta">
          <span>创建于 {{ formatDate(project.created_at) }}</span>
        </div>
        <div class="project-actions" @click.stop>
          <el-button text size="small" type="danger" @click="handleDelete(project.id)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
      
      <!-- 空状态 -->
      <div v-if="!store.loading && store.projects.length === 0" class="empty-state">
        <el-empty description="还没有项目，创建一个开始吧！">
          <el-button type="primary" @click="showCreateDialog = true">创建项目</el-button>
        </el-empty>
      </div>
    </div>
    
    <!-- 创建项目对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建新项目" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="createForm.name" placeholder="输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input 
            v-model="createForm.description" 
            type="textarea" 
            :rows="3"
            placeholder="简单描述这个项目（可选）" 
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { useProjectStore } from '@/stores'

const router = useRouter()
const store = useProjectStore()

const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  description: ''
})

onMounted(() => {
  store.fetchProjects()
})

const formatDate = (date: string) => {
  // 使用固定 +8 时区显示（本地时区为 UTC+8）
  return dayjs(date).utcOffset(8).format('YYYY-MM-DD HH:mm')
}

const getStatusType = (status: string) => {
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

const getStatusLabel = (status: string) => {
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

const handleCreate = async () => {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  
  creating.value = true
  try {
    const project = await store.createProject(createForm.value)
    showCreateDialog.value = false
    createForm.value = { name: '', description: '' }
    ElMessage.success('项目创建成功')
    router.push(`/project/${project.id}`)
  } finally {
    creating.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除这个项目吗？此操作不可恢复。', '删除确认', {
      type: 'warning'
    })
    await store.deleteProject(id)
    ElMessage.success('项目已删除')
  } catch {
    // 取消删除
  }
}
</script>

<style scoped lang="scss">
.project-list {
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

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.project-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  border: 1px solid #ebeef5;
  
  &:hover {
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }
  
  &-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
    /* 给 header 右侧留出空间，避免标签与绝对定位的操作按钮重叠 */
    padding-right: 72px;
    
    h3 {
      font-size: 16px;
      font-weight: 600;
      margin: 0;
    }
  }
}

.project-desc {
  color: #909399;
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-meta {
  font-size: 12px;
  color: #c0c4cc;
}

.project-actions {
  position: absolute;
  top: 16px;
  right: 16px;
  opacity: 0;
  transition: opacity 0.3s;
  
  .project-card:hover & {
    opacity: 1;
  }
}

.empty-state {
  grid-column: 1 / -1;
  padding: 60px 0;
}
</style>
