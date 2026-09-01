<template>
  <div class="ai-banner" :class="bannerClass">
    <div class="ai-banner-left">
      <span class="ai-banner-label">
        <el-icon><MagicStick /></el-icon>
        <b>AI分析:</b>
      </span>
      <span
        v-for="c in chips" :key="c" class="ai-chip"
        @click="$emit('select-chip', c)"
      >{{ c }}</span>
    </div>
    <el-link type="primary" :underline="false" class="ai-more" @click="$emit('more')">
      更多分析 <el-icon><ArrowRight /></el-icon>
    </el-link>
  </div>
</template>

<script setup lang="ts">
import { MagicStick, ArrowRight } from "@element-plus/icons-vue";

defineProps<{
  chips?: string[];
  bannerClass?: string;
}>();
defineEmits<{
  (e: "select-chip", chip: string): void;
  (e: "more"): void;
}>();
</script>

<style scoped>
.ai-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  background: #f0f6ff;
  border: 1px solid #d3e5ff;
  border-radius: 10px;
  padding: 10px 14px;
  margin: 6px 0 14px;
}
.ai-banner-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
}
.ai-banner-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #2979ff;
  margin-right: 4px;
}
.ai-banner-label :deep(.el-icon) { font-size: 15px; }
.ai-banner-label b { font-weight: 700; }
.ai-chip {
  font-size: 12px;
  color: #2979ff;
  background: #eaf2ff;
  border: 1px solid #cfe1ff;
  border-radius: 14px;
  padding: 3px 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.ai-chip:hover {
  background: #2979ff;
  color: #fff;
  border-color: #2979ff;
  box-shadow: 0 2px 6px rgba(41, 121, 255, 0.25);
}
.ai-more { font-size: 13px; }
</style>
