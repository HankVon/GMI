<!-- 元数据配置 — 字段管理 + 选项集管理 合并宿主页 -->
<template>
  <div class="metadata-manager">
    <el-tabs v-model="activeTab" type="border-card" class="hub-tabs">
      <el-tab-pane label="字段管理" name="fields" lazy>
        <keep-alive><FieldManager v-if="activeTab === 'fields'" /></keep-alive>
      </el-tab-pane>
      <el-tab-pane label="选项集管理" name="options" lazy>
        <keep-alive><OptionManager v-if="activeTab === 'options'" /></keep-alive>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import FieldManager from "@/components/FieldManager.vue";
import OptionManager from "@/views/admin/OptionManager.vue";

const route = useRoute();
const activeTab = ref("fields");

function syncTab() {
  const t = route.query.tab;
  if (t === "options" || t === "fields") activeTab.value = t;
}
onMounted(syncTab);
watch(() => route.query.tab, syncTab);
</script>

<style scoped>
.metadata-manager {
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
