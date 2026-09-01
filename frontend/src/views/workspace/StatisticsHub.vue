<!-- 统计中心 — 经营看板 + 情报看板 合并宿主页 -->
<template>
  <div class="statistics-hub">
    <el-tabs v-model="activeTab" type="border-card" class="hub-tabs">
      <el-tab-pane label="经营看板" name="dashboard" lazy>
        <keep-alive><Dashboard v-if="activeTab === 'dashboard'" /></keep-alive>
      </el-tab-pane>
      <el-tab-pane label="情报看板" name="intent" lazy>
        <keep-alive><IntentDashboard v-if="activeTab === 'intent'" /></keep-alive>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import Dashboard from "@/views/dashboard/Dashboard.vue";
import IntentDashboard from "@/views/workspace/IntentDashboard.vue";

const route = useRoute();
const activeTab = ref("dashboard");

function syncTab() {
  const t = route.query.tab;
  if (t === "intent" || t === "dashboard") activeTab.value = t;
}
onMounted(syncTab);
watch(() => route.query.tab, syncTab);
</script>

<style scoped>
.statistics-hub {
  padding: 4px 0 30px;
}
.hub-tabs {
  border-radius: 12px;
  overflow: hidden;
}
.hub-tabs :deep(.el-tabs__content) {
  padding: 4px 4px 20px;
}
</style>
