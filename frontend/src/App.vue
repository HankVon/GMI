<template>
  <div id="ssm-app">
    <!-- 前台官网(含数据中心): 不经过后台 Layout -->
    <!-- v-slot 拦截懒加载期(Component 为 null) → 显示 loading, 避免闪后台 bar -->
    <router-view v-if="route.meta.site" v-slot="{ Component }">
      <template v-if="Component">
        <component :is="Component" />
      </template>
      <div v-else class="route-loading">
        <div class="rl-spinner"></div>
        <div class="rl-text">数据加载中…</div>
      </div>
    </router-view>

    <!-- 后台管理系统 -->
    <el-container v-else class="layout">
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
          <el-sub-menu v-if="canBiz" index="biz">
            <template #title>
              <el-icon><Briefcase /></el-icon>
              <span>业务管理</span>
            </template>
            <el-menu-item v-if="can('menu_workspace_projects')" index="/workspace/projects">
              <el-icon><FolderOpened /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item v-if="can('menu_workspace_persons')" index="/workspace/persons">
              <el-icon><UserFilled /></el-icon>
              <span>人员管理</span>
            </el-menu-item>
            <el-menu-item v-if="can('menu_workspace_companies')" index="/workspace/companies">
              <el-icon><OfficeBuilding /></el-icon>
              <span>单位管理</span>
            </el-menu-item>
            <el-menu-item v-if="can('menu_dashboard')" index="/dashboard">
              <el-icon><DataLine /></el-icon>
              <span>统计中心</span>
            </el-menu-item>
            <el-menu-item v-if="can('menu_dashboard')" index="/workspace/reports">
              <el-icon><Histogram /></el-icon>
              <span>报表中心</span>
            </el-menu-item>
          </el-sub-menu>
          <el-sub-menu v-if="canIntel" index="intel">
            <template #title>
              <el-icon><DataAnalysis /></el-icon>
              <span>情报中心</span>
            </template>
            <el-menu-item-group v-if="can('menu_intel_intelligence') || can('menu_bid_admin')" title="数据查询">
              <el-menu-item v-if="can('menu_intel_intelligence')" index="/workspace/intelligence">
                <el-icon><Search /></el-icon>
                <span>行业情报</span>
              </el-menu-item>
              <el-menu-item v-if="can('menu_bid_admin')" index="/workspace/bids-admin">
                <el-icon><Tickets /></el-icon>
                <span>标讯管理</span>
              </el-menu-item>
              <el-menu-item v-if="can('menu_bid_admin')" index="/workspace/attachment-gaps">
                <el-icon><Warning /></el-icon>
                <span>附件缺口看板</span>
              </el-menu-item>
            </el-menu-item-group>
            <el-menu-item-group v-if="can('menu_intel_pipeline') || can('menu_intel_intents') || can('menu_intel_admin') || can('menu_workspace_web_clues')" title="数据治理">
              <el-menu-item v-if="can('menu_intel_pipeline')" index="/workspace/pipeline">
                <el-icon><Cpu /></el-icon>
                <span>数据流水线</span>
              </el-menu-item>
              <el-menu-item v-if="can('menu_intel_intents')" index="/workspace/intents">
                <el-icon><Promotion /></el-icon>
                <span>意向信息</span>
              </el-menu-item>
              <el-menu-item v-if="can('menu_workspace_web_clues')" index="/workspace/web-clues">
                <el-icon><Link /></el-icon>
                <span>网页线索</span>
              </el-menu-item>
              <el-menu-item v-if="can('menu_workspace_web_clues')" index="/workspace/data-sources">
                <el-icon><Coin /></el-icon>
                <span>统一数据源</span>
              </el-menu-item>
            </el-menu-item-group>
            <el-menu-item-group v-if="can('menu_intel_admin') || can('menu_intel_intents') || can('menu_intel_opportunities')" title="情报运营">
              <el-menu-item v-if="can('menu_intel_admin') || can('menu_intel_intents')" index="/workspace/intent-admin">
                <el-icon><EditPen /></el-icon>
                <span>情报管理</span>
              </el-menu-item>
              <el-menu-item v-if="can('menu_intel_opportunities')" index="/workspace/opportunities">
                <el-icon><Coin /></el-icon>
                <span>商机管理</span>
              </el-menu-item>
              <el-menu-item v-if="can('menu_intel_opportunities')" index="/workspace/opportunity-tags">
                <el-icon><CollectionTag /></el-icon>
                <span>策展标签</span>
              </el-menu-item>
            </el-menu-item-group>
          </el-sub-menu>
          <el-sub-menu v-if="canMk" index="mk">
            <template #title>
              <el-icon><MagicStick /></el-icon>
              <span>营销智能体</span>
            </template>
            <el-menu-item v-if="can('menu_mk_marketing') || can('menu_mk_content') || can('menu_mk_geo')" index="/workspace/marketing">
              <el-icon><DataLine /></el-icon>
              <span>智能体驾驶舱</span>
            </el-menu-item>
          </el-sub-menu>
          <el-sub-menu v-if="canAdmin" index="admin">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>管理后台</span>
            </template>
            <el-menu-item v-if="can('menu_cms_home')" index="/admin/cms">
              <el-icon><Monitor /></el-icon>
              <span>页面配置</span>
            </el-menu-item>
            <el-menu-item v-if="can('menu_field_mgt') || can('menu_option_mgt')" index="/admin/fields">
              <el-icon><Grid /></el-icon>
              <span>元数据配置</span>
            </el-menu-item>
            <el-menu-item v-if="can('menu_rbac')" index="/admin/rbac">
              <el-icon><Lock /></el-icon>
              <span>角色权限</span>
            </el-menu-item>
            <el-menu-item v-if="can('menu_audit')" index="/admin/audit">
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
            <el-button text class="front-link" @click="router.push('/site')">
              <el-icon><DataAnalysis /></el-icon>前台
            </el-button>
            <!-- 通知中心 -->
            <el-popover placement="bottom-end" :width="360" trigger="click">
              <template #reference>
                <el-badge :value="unreadCount" :hidden="!unreadCount" :max="99" class="notif-badge">
                  <el-button text class="front-link" @click="openNotifList">
                    <el-icon :size="17"><Bell /></el-icon>
                  </el-button>
                </el-badge>
              </template>
              <div class="notif-panel">
                <div class="notif-head">
                  <span class="notif-title">通知</span>
                  <el-button v-if="unreadCount" link type="primary" size="small" @click="markAllRead">
                    全部已读
                  </el-button>
                </div>
                <div v-if="notifList.length" class="notif-list">
                  <div
                    v-for="n in notifList"
                    :key="n.id"
                    class="notif-item"
                    :class="{ unread: !n.is_read }"
                    @click="handleNotifClick(n)"
                  >
                    <div class="notif-item-title">{{ n.title }}</div>
                    <div v-if="n.content" class="notif-item-content">{{ n.content }}</div>
                    <div class="notif-item-time">{{ fmtNotifTime(n.created_at) }}</div>
                  </div>
                </div>
                <el-empty v-else description="暂无通知" :image-size="60" />
              </div>
            </el-popover>
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
          <router-view v-slot="{ Component }">
            <keep-alive :include="cachedViews">
              <component :is="Component" :key="route.path" />
            </keep-alive>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "@/stores/user";
import AIModelConfig from "@/components/AIModelConfig.vue";
import api from "@/api";
import {
  FolderOpened, UserFilled, OfficeBuilding, Setting,
  Grid, List, Lock, Document, Fold, Expand, ArrowDown,
  MagicStick, User, SwitchButton, DataAnalysis, DataLine, Compass, Promotion, Briefcase, Search, Cpu,
  Bell, Tickets, EditPen, Coin, CollectionTag, Management, Warning, Histogram,
} from "@element-plus/icons-vue";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const isCollapse = ref(false);
const aiConfigVisible = ref(false);

/** 页面级权限: 是否拥有指定菜单权限码 */
function can(code: string): boolean {
  return userStore.hasPermission(code);
}
/** 各组菜单的可见性(子项任一可见即显示分组) */
const canBiz = computed(() =>
  can("menu_workspace_projects") || can("menu_workspace_persons") ||
  can("menu_workspace_companies") || can("menu_dashboard"));
const canIntel = computed(() =>
  can("menu_intel_intelligence") || can("menu_intel_pipeline") || can("menu_intel_intents") ||
  can("menu_intel_opportunities") || can("menu_intel_admin") || can("menu_bid_admin") ||
  can("menu_workspace_web_clues"));
const canMk = computed(() =>
  can("menu_mk_geo") || can("menu_mk_content") || can("menu_mk_marketing"));
const canAdmin = computed(() =>
  can("menu_field_mgt") || can("menu_option_mgt") ||
  can("menu_rbac") || can("menu_audit") || can("menu_cms_home"));

/** 需要缓存(返回时保留页码/筛选)的列表页组件名 */
const cachedViews = [
  "CompanyList",
  "ProjectList",
  "PersonList",
  "WebClue",
  "ReportsCenter",
];

const activeMenu = computed(() => route.path);
const currentPageTitle = computed(() => route.meta?.title || "");

const avatarChar = computed(() =>
  (userStore.displayName || userStore.username || "?").trim().charAt(0).toUpperCase()
);
const avatarGradient = "linear-gradient(135deg, #a51c30, #c0394d)";

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

/* ─────────── 站内通知中心 ─────────── */
const unreadCount = ref(0);
const notifList = ref<any[]>([]);
let notifTimer: any = null;

async function loadUnreadCount() {
  try {
    const res: any = await api.get("/notifications/unread-count");
    unreadCount.value = res?.data?.unread || 0;
  } catch { /* 未登录/失败静默 */ }
}

function openNotifList() {
  loadNotifs();
}

async function loadNotifs() {
  try {
    const res: any = await api.get("/notifications?page=1&page_size=20");
    notifList.value = res?.data?.items || [];
  } catch { /* 忽略 */ }
}

async function markRead(n: any) {
  if (n.is_read) return;
  try {
    await api.post("/notifications/read", { ids: [n.id] });
    n.is_read = true;
    loadUnreadCount();
  } catch { /* 忽略 */ }
}

/** 通知项点击: 关联到业务页则跳转(如过期线索 → 网页线索列表), 并标记已读 */
function handleNotifClick(n: any) {
  if (n.related_type === "web_clue") {
    router.push("/workspace/web-clues");
  } else if (n.related_type === "intent_notice" && n.related_id) {
    router.push(`/workspace/intents?highlight=${n.related_id}`);
  } else if (n.related_type === "subscription" && n.type === "opp_new") {
    router.push("/workspace/opportunities");
  } else if (n.related_type === "subscription" && n.type === "bid_new") {
    router.push("/workspace/bid-center");
  }
  markRead(n);
}

async function markAllRead() {
  try {
    await api.post("/notifications/read", { all: true });
    notifList.value.forEach((n: any) => (n.is_read = true));
    loadUnreadCount();
  } catch { /* 忽略 */ }
}

function fmtNotifTime(v?: string) {
  if (!v) return "";
  return v.replace("T", " ").slice(5, 16);
}

function startNotifPolling() {
  loadUnreadCount();
  if (notifTimer) clearInterval(notifTimer);
  notifTimer = setInterval(loadUnreadCount, 30000);
}

onMounted(() => {
  // 仅登录态启动未读通知轮询; 未登录(如公开检索/登录页)不启动,
  // 避免轮询接口 401 触发拦截器跳登录造成「整页刷新 → 再 401」死循环。
  if (localStorage.getItem("ssm_token")) startNotifPolling();
});
onUnmounted(() => {
  if (notifTimer) clearInterval(notifTimer);
});
</script>

<style scoped>
/* 前台懒加载 loading(替代闪现的后台 bar) */
.route-loading {
  min-height: 80vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: #fff;
}
.rl-spinner {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 3px solid rgba(165, 28, 48, 0.14);
  border-top-color: #a51c30;
  animation: rl-spin 0.8s linear infinite;
}
@keyframes rl-spin {
  to { transform: rotate(360deg); }
}
.rl-text {
  font-size: 13px;
  color: #8c8784;
  letter-spacing: 1px;
}

.layout {
  height: 100vh;
}
.aside {
  background: linear-gradient(180deg, #ffffff 0%, #fbf9f8 100%);
  border-right: 1px solid #ece8e4;
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
  border-bottom: 1px solid #f1ecea;
  flex-shrink: 0;
}
.logo-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--ssm-primary-grad);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  box-shadow: 0 3px 8px rgba(165, 28, 48, 0.28);
}
.logo-text {
  color: var(--ssm-text-main);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
/* 侧边菜单: 浅色 + 悬浮圆角 + 红系激活 */
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
  color: var(--ssm-text-regular);
  font-size: 14px;
  transition: all 0.18s ease;
}
.side-menu :deep(.el-menu-item:hover),
.side-menu :deep(.el-sub-menu__title:hover) {
  background: var(--ssm-primary-soft);
  color: var(--ssm-primary);
}
.side-menu :deep(.el-menu-item.is-active) {
  background: var(--ssm-primary-grad);
  color: #fff !important;
  box-shadow: 0 4px 12px rgba(165, 28, 48, 0.28);
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
  background: var(--ssm-primary-grad);
}
/* 情报中心分组标题 */
.side-menu :deep(.el-menu-item-group__title) {
  padding: 10px 16px 2px 48px;
  font-size: 11px;
  font-weight: 600;
  color: #b0a79f;
  letter-spacing: 0.06em;
  line-height: 1.4;
  text-transform: uppercase;
}
.side-menu :deep(.el-menu-item-group .el-menu-item) {
  padding-left: 56px !important;
}
.side-menu :deep(.el-icon) {
  color: #a89e96;
}
.side-menu :deep(.el-menu-item.is-active .el-icon),
.side-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title .el-icon) {
  color: var(--ssm-primary);
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
  background: linear-gradient(90deg, #ffffff 0%, #fbf9f8 100%);
  border-bottom: 1px solid #ece8e4;
  box-shadow: 0 1px 4px rgba(60, 30, 30, 0.04);
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
/* 前台入口 */
.front-link {
  color: var(--ssm-text-regular);
  font-weight: 500;
}
.front-link:hover {
  color: var(--ssm-primary);
}
.front-link .el-icon { margin-right: 4px; }
/* 右上角用户触发按钮 */
.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 20px;
  cursor: pointer;
  border: 1px solid #ece8e4;
  transition: all 0.2s ease;
  background: #fff;
  box-shadow: 0 1px 4px rgba(60, 30, 30, 0.05);
}
.user-trigger:hover {
  background: var(--ssm-primary-soft);
  border-color: #eab4bc;
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--ssm-primary-grad);
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
  color: var(--ssm-text-main);
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
  background: linear-gradient(135deg, #fbecee, #fbf3f0);
  border-bottom: 1px solid #f0f0f0;
}
.user-menu-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--ssm-primary-grad);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}
.user-menu-info { display: flex; flex-direction: column; }
.user-menu-name { font-weight: 600; color: var(--ssm-text-main); font-size: 14px; }
.user-menu-role { color: #909399; font-size: 12px; margin-top: 2px; }
.user-menu .el-dropdown-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
}
.user-menu .el-dropdown-menu__item .el-icon { color: #606266; }
.user-menu .el-dropdown-menu__item:hover .el-icon { color: #409eff; }
/* 通知中心 */
.notif-badge { display: inline-flex; align-items: center; }
.notif-panel { padding: 4px 0; }
.notif-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 12px 8px; border-bottom: 1px solid #f0f0f0;
}
.notif-title { font-weight: 600; font-size: 14px; color: #1f2d3d; }
.notif-list { max-height: 320px; overflow-y: auto; }
.notif-item {
  padding: 10px 12px; border-bottom: 1px solid #f7f7f7; cursor: pointer;
  border-radius: 6px;
}
.notif-item:hover { background: #f7f9fc; }
.notif-item.unread { background: #fdf2f4; }
.notif-item-title { font-size: 13.5px; color: #1f2d3d; font-weight: 500; }
.notif-item.unread .notif-item-title::before {
  content: ""; display: inline-block; width: 6px; height: 6px;
  background: #a51c30; border-radius: 50%; margin-right: 6px; vertical-align: middle;
}
.notif-item-content {
  font-size: 12.5px; color: #606266; margin-top: 4px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.notif-item-time { font-size: 12px; color: #a0a8b8; margin-top: 4px; }
.main-content {
  background:
    radial-gradient(1200px 400px at 100% 0%, rgba(41, 121, 255, 0.04) 0%, transparent 60%),
    var(--ssm-bg, #f0f3f8);
  min-height: calc(100vh - 60px);
  padding: 16px;
}
</style>
