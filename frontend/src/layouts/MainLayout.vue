<template>
  <div class="main-layout">
    <!-- 顶部导航 -->
    <el-header class="header">
      <div class="header-left">
        <router-link to="/" class="logo">
          <el-icon size="24"><VideoCamera /></el-icon>
          <span>LumiCreate</span>
        </router-link>
      </div>
      <div class="header-right">
        <el-button text @click="router.push('/tasks')">
          <el-icon><Bell /></el-icon>
          任务中心
        </el-button>
        <el-button text @click="router.push('/settings')">
          <el-icon><Setting /></el-icon>
          设置
        </el-button>
      </div>
    </el-header>
    
    <!-- 主内容区 -->
    <el-main class="main-content">
      <router-view />
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped lang="scss">
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: #333;
  font-size: 18px;
  font-weight: 600;
  
  .el-icon {
    color: var(--el-color-primary);
  }
}

.main-content {
  padding: 20px 24px;
  background: #f5f7fa;
  min-height: calc(100vh - 60px);
}
</style>
