<template>
  <div class="account-home">
    <div class="welcome-card">
      <div class="wc-left">
        <h2>您好，{{ userStore.displayName || userStore.username || '用户' }}</h2>
        <p>欢迎来到个人中心。这里可以管理您的订阅、收藏与监控，跟踪每日新增的项目商机。</p>
      </div>
      <el-avatar :size="64" class="wc-avatar">{{ avatarChar }}</el-avatar>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card" v-for="k in kpis" :key="k.title" @click="k.to && $router.push(k.to)">
        <el-icon class="kpi-icon" :style="{ color: k.color }"><component :is="k.icon" /></el-icon>
        <div class="kpi-meta">
          <div class="kpi-num">{{ k.value }}</div>
          <div class="kpi-label">{{ k.title }}</div>
        </div>
      </div>
    </div>

    <el-card class="quick-card" shadow="never">
      <template #header>
        <div class="card-hd"><strong>快捷入口</strong></div>
      </template>
      <div class="quick-grid">
        <a class="quick-item" @click="$router.push('/site/account/subscriptions')">
          <el-icon><Bell /></el-icon><span>我的订阅</span>
        </a>
        <a class="quick-item" @click="$router.push('/site/account/monitor')">
          <el-icon><Monitor /></el-icon><span>我的监控</span>
        </a>
        <a class="quick-item" @click="$router.push('/site/data-center')">
          <el-icon><DataBoard /></el-icon><span>数据中心</span>
        </a>
        <a class="quick-item" @click="$router.push('/site/intelligence')">
          <el-icon><Promotion /></el-icon><span>项目商机</span>
        </a>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Bell, Monitor, DataBoard, Promotion, User, Star } from "@element-plus/icons-vue";
import { useUserStore } from "@/stores/user";
import { listOpportunitySubscriptions } from "@/api/opportunityAdmin";

const userStore = useUserStore();
const avatarChar = computed(() => (userStore.displayName || userStore.username || "U").charAt(0).toUpperCase());
const subCount = ref(0);
const activeSubCount = ref(0);
const matchCount = ref(0);

const kpis = computed(() => [
  { title: "我的订阅", value: subCount.value, color: "#c8102e", icon: Bell, to: "/site/account/subscriptions" },
  { title: "活跃订阅", value: activeSubCount.value, color: "#1f6db8", icon: Star, to: "/site/account/subscriptions" },
  { title: "匹配商机", value: matchCount.value, color: "#2f8f5b", icon: Promotion, to: "/site/account/subscriptions" },
  { title: "账号设置", value: "—", color: "#9c6bff", icon: User },
]);

async function loadStats() {
  try {
    const res: any = await listOpportunitySubscriptions();
    // ★ P1-1: 后端 enabled 序列化为 bool, 归一化为 0/1 以正确统计活跃订阅数
    const items = (res?.data || []).map((i: any) => ({ ...i, enabled: i.enabled ? 1 : 0 }));
    subCount.value = items.length;
    activeSubCount.value = items.filter((i: any) => i.enabled === 1).length;
    matchCount.value = items.reduce((s: number, i: any) => s + (i.lastMatchCount || 0), 0);
  } catch {/* ignore */}
}

onMounted(loadStats);
</script>

<style scoped>
.welcome-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  background: linear-gradient(135deg, #fdf6f7 0%, #f7e9eb 100%);
  border-radius: 8px;
  margin-bottom: 18px;
  border: 1px solid #f0cdd2;
}
.wc-left h2 {
  margin: 0 0 6px;
  font-family: var(--site-font-display);
  font-weight: 600;
  color: var(--site-text, #141414);
  font-size: 22px;
}
.wc-left p {
  color: var(--site-text-dim, #525252);
  font-size: 14px;
  margin: 0;
}
.wc-avatar {
  background: var(--site-brand, #c8102e) !important;
  color: #fff;
  font-weight: 800;
  font-family: var(--site-font-display);
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 16px;
  background: #fff;
  border: 1px solid #f0f2f5;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.25s ease;
}
.kpi-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 22px -12px rgba(200, 16, 46, 0.25);
  border-color: var(--site-brand, #c8102e);
}
.kpi-icon {
  font-size: 28px;
}
.kpi-meta {
  flex: 1;
}
.kpi-num {
  font-family: var(--site-font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--site-text, #141414);
  line-height: 1.2;
}
.kpi-label {
  font-size: 12.5px;
  color: var(--site-text-mute, #9ca3af);
}
.card-hd {
  font-size: 14px;
}
.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 18px 12px;
  border: 1px solid #f0f2f5;
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
  color: var(--site-text, #141414);
  transition: all 0.2s ease;
}
.quick-item:hover {
  background: #fdf6f7;
  border-color: var(--site-brand, #c8102e);
  color: var(--site-brand, #c8102e);
}
.quick-item .el-icon {
  font-size: 24px;
}
@media (max-width: 768px) {
  .kpi-grid, .quick-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
