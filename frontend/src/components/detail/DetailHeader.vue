<template>
  <div class="fgbs-header">
    <div class="fgbs-head-main">
      <h2 class="fgbs-title">
        <slot name="title">{{ title }}</slot>
      </h2>
      <span v-if="$slots.badge" class="fgbs-badge"><slot name="badge" /></span>
      <div class="fgbs-head-spacer"></div>
      <div v-if="$slots.actions" class="fgbs-actions"><slot name="actions" /></div>
    </div>
    <!-- 基本信息卡片: 由父组件通过默认插槽传入 -->
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string;
}>();
</script>

<style scoped>
.fgbs-header {
  background: #fff;
  border: 1px solid #e9edf6;
  border-top: 3px solid #2979ff;
  border-radius: 10px;
  padding: 18px 22px 16px;
  margin-bottom: 14px;
}
.fgbs-head-main {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.fgbs-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2d3d;
  margin: 0;
  line-height: 1.3;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.fgbs-badge { display: inline-flex; align-items: center; gap: 6px; }
.fgbs-head-spacer { flex: 1; }
.fgbs-actions { display: inline-flex; align-items: center; gap: 8px; }
</style>
