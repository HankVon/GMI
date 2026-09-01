<!-- TrendChart.vue — 可复用 ECharts 图表包装 -->
<template>
  <div ref="chartRef" class="trend-chart" :style="{ height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, shallowRef } from "vue";
const props = defineProps<{ options: any; height?: string }>();
const chartRef = ref<HTMLElement>();
const chart = shallowRef<any>(null);
let resizeHandler: (() => void) | null = null;

async function render() {
  if (!chartRef.value) return;
  if (!chart.value) {
    const echarts = await import("echarts");
    chart.value = echarts.init(chartRef.value);
  }
  chart.value.setOption(props.options, true);
}

onMounted(async () => {
  await render();
  resizeHandler = () => chart.value?.resize();
  window.addEventListener("resize", resizeHandler);
});

onBeforeUnmount(() => {
  if (resizeHandler) window.removeEventListener("resize", resizeHandler);
  chart.value?.dispose();
});

watch(() => props.options, render, { deep: true });
</script>

<style scoped>
.trend-chart { width: 100%; min-height: 260px; }
</style>
