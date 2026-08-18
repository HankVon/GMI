<template>
  <div id="ssm-app">
    <el-container class="layout">
      <!-- 侧边导航 -->
      <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
        <div class="logo">
          <div class="logo-icon">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <span v-if="!isCollapse" class="logo-text">GMI 数据平台</span>
          <span v-else class="logo-text">GMI</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          router
          :collapse="isCollapse"
          class="side-menu"
        >
          <el-sub-menu index="biz">
            <template #title>
              <el-icon><Briefcase /></el-icon>
              <span>业务管理</span>
            </template>
            <el-menu-item index="/workspace/business">
              <el-icon><Monitor /></el-icon>
              <span>商业信息</span>
            </el-menu-item>
            <el-menu-item index="/workspace/projects">
              <el-icon><FolderOpened /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item index="/workspace/persons">
              <el-icon><UserFilled /></el-icon>
              <span>人员管理</span>
            </el-menu-item>
            <el-menu-item index="/workspace/companies">
              <el-icon><OfficeBuilding /></el-icon>
              <span>单位管理</span>
            </el-menu-item>
            <el-menu-item index="/workspace/web-clues">
              <el-icon><Compass /></el-icon>
              <span>网页线索</span>
            </el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="intel">
            <template #title>
              <el-icon><DataAnalysis /></el-icon>
              <span>情报中心</span>
            </template>
            <el-menu-item index="/workspace/intelligence">
              <el-icon><Search /></el-icon>
              <span>行业情报</span>
            </el-menu-item>
            <el-menu-item index="/workspace/pipeline">
              <el-icon><Cpu /></el-icon>
              <span>数据流水线</span>
            </el-menu-item>
            <el-menu-item index="/workspace/intents">
              <el-icon><Promotion /></el-icon>
              <span>意向信息</span>
            </el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="admin">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>管理后台</span>
            </template>
            <el-menu-item index="/admin/fields">
              <el-icon><Grid /></el-icon>
              <span>字段管理</span>
            </el-menu-item>
            <el-menu-item index="/admin/options">
              <el-icon><List /></el-icon>
              <span>选项集管理</span>
            </el-menu-item>
            <el-menu-item index="/admin/rbac">
              <el-icon><Lock /></el-icon>
              <span>角色权限</span>
            </el-menu-item>
            <el-menu-item index="/admin/audit">
              <el-icon><Document /></el-icon>
              <span>审计日志</span>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
        <div class="aside-footer" v-if="!isCollapse">
          <div class="aside-footer-icon"><el-icon><DataLine /></el-icon></div>
          <div class="aside-footer-text">
            <div class="aside-footer-title">GMI 数据平台</div>
            <div class="aside-footer-sub">v1.0 · 统一商情中台</div>
          </div>
        </div>
      </el-aside>

      <!-- 主内容 -->
      <el-container>
        <el-header class="header">
          <div class="header-left">
            <el-button
              text
              @click="isCollapse = !isCollapse"
            >
              <el-icon :size="20"><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
            </el-button>
            <el-breadcrumb separator="/">
              <el-breadcrumb-item>GMI平台</el-breadcrumb-item>
              <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <div class="header-right">
            <el-dropdown trigger="click" @command="handleUserCommand">
              <div class="user-trigger">
                <div class="user-avatar" :style="{ background: avatarGradient }">
                  {{ avatarChar }}
                </div>
                <span class="user-name">{{ userStore.displayName || userStore.username }}</span>
                <el-icon class="user-arrow"><ArrowDown /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu class="user-menu">
                  <div class="user-menu-head">
                    <div class="user-menu-avatar" :style="{ background: avatarGradient }">{{ avatarChar }}</div>
                    <div class="user-menu-info">
                      <div class="user-menu-name">{{ userStore.displayName || userStore.username }}</div>
                      <div class="user-menu-role">{{ userStore.username }}</div>
                    </div>
                  </div>
                  <el-dropdown-item command="ai-config">
                    <el-icon><MagicStick /></el-icon>
                    <span>AI 模型配置</span>
                  </el-dropdown-item>
                  <el-dropdown-item command="me">
                    <el-icon><User /></el-icon>
                    <span>我的信息</span>
                  </el-dropdown-item>
                  <el-dropdown-item divided command="logout">
                    <el-icon><SwitchButton /></el-icon>
                    <span>退出登录</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <AIModelConfig v-model="aiConfigVisible" />
          </div>
        </el-header>

        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "@/stores/user";
import AIModelConfig from "@/components/AIModelConfig.vue";
import {
  Monitor, FolderOpened, UserFilled, OfficeBuilding, Setting,
  Grid, List, Lock, Document, Fold, Expand, ArrowDown,
  MagicStick, User, SwitchButton, DataAnalysis, DataLine, Compass, Promotion, Briefcase, Search, Cpu,
} from "@element-plus/icons-vue";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const isCollapse = ref(false);
const aiConfigVisible = ref(false);

const activeMenu = computed(() => route.path);
const currentPageTitle = computed(() => route.meta?.title || "");

const avatarChar = computed(() =>
  (userStore.displayName || userStore.username || "?").trim().charAt(0).toUpperCase()
);
const avatarGradient = "linear-gradient(135deg, #409eff, #7c4dff)";

function handleUserCommand(cmd: string) {
  if (cmd === "ai-config") {
    aiConfigVisible.value = true;
  } else if (cmd === "me") {
    router.push("/me");
  } else if (cmd === "logout") {
    userStore.logout();
    router.push("/login");
  }
}
</script>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background: linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%);
  border-right: 1px solid #e8edf8;
  transition: width 0.3s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid #eef1f8;
  flex-shrink: 0;
}
.logo-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2979ff, #4f8aff);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  box-shadow: 0 3px 8px rgba(41, 121, 255, 0.3);
}
.logo-text {
  color: #1f2d3d;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
/* 侧边菜单: 浅色 + 悬浮圆角 + 主色激活 */
.side-menu {
  border-right: none !important;
  background: transparent !important;
  padding: 8px;
  flex: 1;
  overflow-y: auto;
}
.side-menu :deep(.el-menu-item),
.side-menu :deep(.el-sub-menu__title) {
  height: 46px;
  line-height: 46px;
  margin: 2px 0;
  border-radius: 8px;
  color: #4b5264;
  font-size: 14px;
  transition: all 0.18s ease;
}
.side-menu :deep(.el-menu-item:hover),
.side-menu :deep(.el-sub-menu__title:hover) {
  background: #eef4ff;
  color: #2979ff;
}
.side-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #2979ff, #4f8aff);
  color: #fff !important;
  box-shadow: 0 4px 12px rgba(41, 121, 255, 0.3);
}
.side-menu :deep(.el-menu-item.is-active .el-icon) {
  color: #fff;
}
.side-menu :deep(.el-sub-menu .el-menu) {
  background: transparent !important;
  border-radius: 8px;
}
.side-menu :deep(.el-sub-menu .el-menu-item) {
  padding-left: 48px !important;
  background: transparent;
}
.side-menu :deep(.el-sub-menu .el-menu-item.is-active) {
  background: linear-gradient(135deg, #2979ff, #4f8aff);
}
.side-menu :deep(.el-icon) {
  color: #8a94a6;
}
.side-menu :deep(.el-menu-item.is-active .el-icon),
.side-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title .el-icon) {
  color: #2979ff;
}
.side-menu :deep(.el-menu-item.is-active .el-icon) {
  color: #fff;
}
/* 折叠时去掉 padding, 让图标居中 */
.side-menu.el-menu--collapse {
  padding: 8px 6px;
}
.side-menu.el-menu--collapse :deep(.el-menu-item),
.side-menu.el-menu--collapse :deep(.el-sub-menu__title) {
  margin: 2px 0;
  justify-content: center;
}

/* 侧边底部版本信息 */
.aside-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-top: 1px solid #eef1f8;
}
.aside-footer-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: #eef4ff;
  color: #2979ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
}
.aside-footer-title {
  font-size: 12.5px;
  font-weight: 600;
  color: #1f2d3d;
}
.aside-footer-sub {
  font-size: 11px;
  color: #a3adc0;
  margin-top: 2px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(90deg, #ffffff 0%, #f4f9ff 100%);
  border-bottom: 1px solid #e8edf8;
  box-shadow: 0 1px 4px rgba(30, 60, 114, 0.04);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
/* 右上角用户触发按钮 */
.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 20px;
  cursor: pointer;
  border: 1px solid #e8edf8;
  transition: all 0.2s ease;
  background: #fff;
  box-shadow: 0 1px 4px rgba(30, 60, 114, 0.05);
}
.user-trigger:hover {
  background: #f0f6ff;
  border-color: #cfe0ff;
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12);
}
.user-name {
  font-size: 13.5px;
  color: #303133;
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-arrow {
  color: #909399;
  font-size: 12px;
  transition: transform 0.2s ease;
}
.el-dropdown:hover .user-arrow { transform: translateY(2px); }
/* 下拉菜单头部 */
.user-menu { padding-top: 0 !important; }
.user-menu-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  margin-bottom: 4px;
  background: linear-gradient(135deg, #f0f7ff, #f5f0ff);
  border-bottom: 1px solid #f0f0f0;
}
.user-menu-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}
.user-menu-info { display: flex; flex-direction: column; }
.user-menu-name { font-weight: 600; color: #303133; font-size: 14px; }
.user-menu-role { color: #909399; font-size: 12px; margin-top: 2px; }
.user-menu .el-dropdown-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
}
.user-menu .el-dropdown-menu__item .el-icon { color: #606266; }
.user-menu .el-dropdown-menu__item:hover .el-icon { color: #409eff; }
.main-content {
  background:
    radial-gradient(1200px 400px at 100% 0%, rgba(41, 121, 255, 0.04) 0%, transparent 60%),
    var(--ssm-bg, #f0f3f8);
  min-height: calc(100vh - 60px);
  padding: 16px;
}
</style>
