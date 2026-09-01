<!-- 情报检索中心 — 行业情报(统一检索) + 组合查询(高级检索) 合并宿主页 -->
<template>
  <div class="intelligence-hub">
    <el-tabs v-model="activeTab" type="border-card" class="hub-tabs">
      <el-tab-pane label="统一检索" name="search" lazy>
        <keep-alive><Intelligence v-if="activeTab === 'search'" /></keep-alive>
      </el-tab-pane>
      <el-tab-pane label="高级组合查询" name="advanced" lazy>
        <keep-alive><CombinedQuery v-if="activeTab === 'advanced'" /></keep-alive>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import Intelligence from "@/views/workspace/Intelligence.vue";
import CombinedQuery from "@/views/workspace/CombinedQuery.vue";

const route = useRoute();
const activeTab = ref("search");

function syncTab() {
  const t = route.query.tab;
  if (t === "advanced" || t === "search") activeTab.value = t;
}
onMounted(syncTab);
watch(() => route.query.tab, syncTab);
</script>

<style scoped>
.intelligence-hub {
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
