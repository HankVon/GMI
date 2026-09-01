<template>
  <SiteLayout>
    <div class="account-layout">
      <!-- 顶部栏: Logo + 用户区 -->
      <!-- <div class="account-topbar">
        <router-link to="/site" class="account-brand">
          <span class="brand-mark">建</span>
          <strong>建设通个人中心</strong>
        </router-link>
        <div class="account-topbar-right">
          <el-input v-model="searchKw" placeholder="搜索标讯..." size="default" class="account-search" clearable>
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <span class="welcome-text">您好，{{ userStore.displayName || userStore.username || '用户' }}</span>
          <el-avatar :size="34" class="account-avatar">{{ avatarChar }}</el-avatar>
        </div>
      </div> -->

      <div class="account-body">
        <!-- 左侧菜单 -->
        <aside class="account-aside">
          <div class="aside-title">个人中心首页</div>
          <el-menu :default-active="activeMenu" class="aside-menu" @select="onMenuSelect">
            <div class="aside-group-title">功能菜单</div>
            <el-menu-item index="account">个人首页</el-menu-item>
            <el-menu-item index="account-subscriptions">我的订阅</el-menu-item>
            <el-menu-item index="account-collection">我的收藏</el-menu-item>
            <el-menu-item index="account-monitor">我的监控</el-menu-item>
          </el-menu>
        </aside>

        <!-- 主区 -->
        <main class="account-main">
          <router-view />
        </main>
      </div>
    </div>
  </SiteLayout>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import SiteLayout from "@/components/site/SiteLayout.vue";
import { Search } from "@element-plus/icons-vue";
import { useUserStore } from "@/stores/user";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const searchKw = ref("");

const avatarChar = computed(() => {
  const s = (userStore.displayName || userStore.username || "U").trim();
  return s.charAt(0).toUpperCase();
});

const activeMenu = computed(() => {
  const p = route.path;
  if (p.includes("/subscriptions")) return "account-subscriptions";
  if (p.includes("/collection")) return "account-collection";
  if (p.includes("/monitor")) return "account-monitor";
  return "account";
});

function onMenuSelect(key: string) {
  const map: Record<string, string> = {
    "account-subscriptions": "/site/account/subscriptions",
    "account-collection": "/site/account/collection",
    "account-monitor": "/site/account/monitor",
  };
  router.push(map[key] || "/site/account");
}
</script>

<style scoped>
.account-layout {
  background: #f5f7fa;
  min-height: calc(100vh - 80px);
}
.account-topbar {
  height: 56px;
  background: linear-gradient(90deg, #2c66b8 0%, #357ec9 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  color: #fff;
}
.account-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: #fff;
}
.brand-mark {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #fff;
  color: #2c66b8;
  font-weight: 900;
  font-size: 16px;
  display: grid;
  place-items: center;
}
.account-brand strong {
  font-family: var(--site-font-display);
  font-size: 18px;
  letter-spacing: 2px;
  font-weight: 600;
}
.account-topbar-right {
  display: flex;
  align-items: center;
  gap: 18px;
}
.account-search {
  width: 220px;
}
.account-search :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.92);
  border-radius: 999px;
  box-shadow: none;
}
.welcome-text {
  font-size: 13.5px;
}
.account-avatar {
  background: var(--site-brand, #c8102e) !important;
  font-weight: 700;
  color: #fff;
}
.account-body {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  max-width: 1280px;
  margin: 16px auto 32px;
  padding: 0 16px;
}
.account-aside {
  background: #fff;
  border-radius: 8px;
  padding: 12px 0;
  height: fit-content;
  position: sticky;
  top: 88px;
}
.aside-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--site-text, #141414);
  padding: 10px 18px 8px;
  border-bottom: 1px solid var(--site-hairline, #ececec);
  margin-bottom: 6px;
}
.aside-menu {
  border-right: none;
}
.aside-menu :deep(.el-menu-item-group__title) {
  padding: 10px 18px 4px;
  font-size: 11.5px !important;
  letter-spacing: 0.06em;
}
.aside-menu :deep(.el-menu-item) {
  height: 38px;
  line-height: 38px;
  font-size: 13px;
}
.aside-group-title {
  padding: 10px 18px 4px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #b0a79f;
  text-transform: uppercase;
  border-top: 1px dashed #f0f2f5;
}
.aside-group-title:first-child {
  border-top: none;
  padding-top: 6px;
}
.account-main {
  background: #fff;
  border-radius: 8px;
  min-height: 600px;
  padding: 16px 20px 28px;
}
@media (max-width: 768px) {
  .account-body {
    grid-template-columns: 1fr;
  }
  .account-aside {
    position: static;
  }
  .account-search {
    width: 140px;
  }
  .welcome-text {
    display: none;
  }
}
</style>
