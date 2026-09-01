<!-- MetricCard.vue — 可复用指标卡片 -->
<template>
  <div class="metric-card">
    <div class="metric-head">
      <span class="metric-title">{{ title }}</span>
      <div class="metric-icon" v-if="icon"><el-icon><component :is="icon" /></el-icon></div>
    </div>
    <div class="metric-body">
      <span class="metric-value">{{ formattedValue }}</span>
      <span v-if="suffix" class="metric-suffix">{{ suffix }}</span>
    </div>
    <div v-if="trend !== undefined" class="metric-trend">
      <el-icon :color="trend >= 0 ? '#2bb673' : '#f56c6c'">
        <CaretTop v-if="trend >= 0" /><CaretBottom v-else />
      </el-icon>
      <span :style="{ color: trend >= 0 ? '#2bb673' : '#f56c6c' }">
        {{ Math.abs(trend) }}{{ trendUnit }}
      </span>
      <span class="trend-hint">较上期</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  title: string;
  value: string | number;
  suffix?: string;
  trend?: number;
  trendUnit?: string;
  /** 图标组件名(可选, 来自 element-plus/icons) */
  icon?: any;
}>();

const formattedValue = computed(() => {
  if (typeof props.value === "number") {
    return props.value.toLocaleString("zh-CN");
  }
  return props.value;
});
</script>

<style scoped>
.metric-card {
  min-width: 180px;
  background: var(--ssm-card-bg, #fff);
  border: 1px solid var(--ssm-border, #ece8e4);
  border-radius: 10px;
  box-shadow: var(--ssm-shadow, 0 2px 12px rgba(60, 30, 30, 0.05));
  padding: 20px 22px;
  position: relative;
  overflow: hidden;
  transition: all 0.25s ease;
}
.metric-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 28px rgba(60, 30, 30, 0.11);
}
.metric-card::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--ssm-primary-grad, linear-gradient(90deg, #a51c30, #c0394d));
  border-radius: 3px 3px 0 0;
}
.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.metric-title { font-size: 13px; color: var(--ssm-text-secondary, #8c8784); font-weight: 500; }
.metric-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--ssm-primary-soft, #fbecee);
  color: var(--ssm-primary, #a51c30);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
}
.metric-body { display: flex; align-items: baseline; gap: 4px; }
.metric-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--ssm-text-main, #1c1a1a);
  font-family: "Georgia", "Times New Roman", serif;
  letter-spacing: 0.5px;
  line-height: 1;
}
.metric-suffix { font-size: 13px; color: var(--ssm-text-secondary, #8c8784); }
.metric-trend { margin-top: 10px; display: flex; align-items: center; gap: 4px; font-size: 12px; }
.trend-hint { color: #c0c4cc; margin-left: 4px; }
</style>
