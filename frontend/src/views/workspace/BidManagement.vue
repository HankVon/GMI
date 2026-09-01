<!-- 标讯管理 — 浏览检索(标讯中心) + 台账治理(标讯管理) 合并宿主页 -->
<template>
  <div class="bid-management">
    <el-tabs v-model="activeTab" type="border-card" class="hub-tabs">
      <el-tab-pane label="浏览检索" name="center" lazy>
        <keep-alive><BidCenter v-if="activeTab === 'center'" /></keep-alive>
      </el-tab-pane>
      <el-tab-pane label="台账治理" name="admin" lazy>
        <keep-alive><BidAdmin v-if="activeTab === 'admin'" /></keep-alive>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import BidCenter from "@/views/workspace/BidCenter.vue";
import BidAdmin from "@/views/workspace/BidAdmin.vue";

const route = useRoute();
const activeTab = ref("admin");

function syncTab() {
  const t = route.query.tab;
  if (t === "center" || t === "admin") activeTab.value = t;
}
onMounted(syncTab);
watch(() => route.query.tab, syncTab);
</script>

<style scoped>
.bid-management {
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
