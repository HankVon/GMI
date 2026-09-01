<template>
  <div class="data-center-page">
    <!-- 顶部不再有 5 个内层 tab(已与 SiteLayout 外层导航 + SubQuery 内部 tabs 重复);
         activeTab 由 URL path 子段直接驱动, 切对象请用 SiteLayout 导航/分项查询页内 tabs -->
    <section v-if="activeTab === 'bid'" class="bid-workspace">
      <BidCenter />
    </section>
    <section v-else class="section alt">
      <div class="site-container">
        <div class="dc-card site-card">
          <KeepAlive><SubQuery v-if="activeTab === 'companies'" :initial-tab="'company'" :key="String(route.query.keyword || '') + '|' + activeTab" /></KeepAlive>
          <KeepAlive><PersonList v-if="activeTab === 'persons'" /></KeepAlive>
          <KeepAlive><ProjectList v-if="activeTab === 'projects'" /></KeepAlive>
          <KeepAlive><Intelligence v-if="activeTab === 'search'" /></KeepAlive>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "DataCenter" });
import { ref, watch } from "vue";
import { useRoute } from "vue-router";
import CompanyList from "@/views/workspace/CompanyList.vue";
import SubQuery from "@/views/site/SubQuery.vue";
import PersonList from "@/views/workspace/PersonList.vue";
import ProjectList from "@/views/workspace/ProjectList.vue";
import Intelligence from "@/views/workspace/Intelligence.vue";
import BidCenter from "@/views/workspace/BidCenter.vue";

// 支持 ?tab=xxx 直接定位到指定功能
const route = useRoute();
const tabs = [
  { name: "bid", label: "标讯中心" },
  { name: "companies", label: "单位画像" },
  { name: "persons", label: "人员画像" },
  { name: "projects", label: "项目库" },
  { name: "search", label: "行业检索" },
];
const TAB_KEY = "dc_active_tab";
const PATH_TAB_MAP: Record<string, string> = {
  overview: "bid",
  companies: "companies",
  persons: "persons",
  projects: "projects",
  search: "search",
};
// 优先级: URL path > sessionStorage(详情返回时恢复上次 tab) > 默认 bid
function resolveActiveTab(): string {
  const path = route.path.replace(/\/$/, "");
  const seg = path.split("/").filter(Boolean).pop() || "";
  if (PATH_TAB_MAP[seg]) return PATH_TAB_MAP[seg];
  const savedTab = sessionStorage.getItem(TAB_KEY);
  if (savedTab && ["bid", "companies", "persons", "projects", "search"].includes(savedTab)) return savedTab;
  return "bid";
}
const activeTab = ref(resolveActiveTab());
// 切换 tab 时持久化, 详情页返回列表可回到原 tab
watch(activeTab, (v) => sessionStorage.setItem(TAB_KEY, v));
</script>

<style scoped>
.page-hero { padding: 80px 0 30px; background: linear-gradient(180deg, #fff, #f6f5f3); }
.page-title { font-family: var(--site-font-display); font-size: var(--fs-h1); font-weight: var(--fw-display); line-height: var(--lh-display); letter-spacing: 0.01em; color: var(--site-text); margin: 12px 0; }
.page-sub { font-size: var(--fs-lead); line-height: var(--lh-body); color: var(--site-text-dim); max-width: 640px; }
.section { padding: 34px 0; }
.section.alt { background: #fff; }
.bid-workspace { background: var(--site-bg); padding: 12px 0 48px; }
.dc-card { padding: 20px 24px; min-height: 70vh; }
.dc-tabs :deep(.el-tabs__header) { margin-bottom: 18px; }
.dc-tabs :deep(.el-tabs__item) { font-size: 15px; font-weight: 600; color: var(--site-text-dim); }
.dc-tabs :deep(.el-tabs__item.is-active) { color: var(--site-brand); }
.dc-tabs :deep(.el-tabs__active-bar) { background-color: var(--site-brand); }
</style>
