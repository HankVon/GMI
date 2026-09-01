<!-- 营销智能体 — GEO监测 + 内容工厂 + 智能体总览 合并宿主页 -->
<template>
  <div class="marketing-hub">
    <el-tabs v-model="activeTab" type="border-card" class="hub-tabs">
      <el-tab-pane label="智能体总览" name="overview" lazy>
        <keep-alive><Marketing v-if="activeTab === 'overview'" /></keep-alive>
      </el-tab-pane>
      <el-tab-pane label="内容工厂" name="content" lazy>
        <keep-alive><ContentFactory v-if="activeTab === 'content'" /></keep-alive>
      </el-tab-pane>
      <el-tab-pane label="GEO 监测" name="geo" lazy>
        <keep-alive><GeoMonitor v-if="activeTab === 'geo'" /></keep-alive>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import Marketing from "@/views/workspace/Marketing.vue";
import ContentFactory from "@/views/workspace/ContentFactory.vue";
import GeoMonitor from "@/views/workspace/GeoMonitor.vue";

const route = useRoute();
const activeTab = ref("overview");

function syncTab() {
  const t = route.query.tab;
  if (["overview", "content", "geo"].includes(t as string)) activeTab.value = t as string;
}
onMounted(syncTab);
watch(() => route.query.tab, syncTab);
</script>

<style scoped>
.marketing-hub {
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
