<!-- TrendChart.vue — 可复用 ECharts 图表包装 -->
<template>
  <div ref="chartRef" class="trend-chart" :style="{ height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, shallowRef } from "vue";
import * as echarts from "echarts";

const props = defineProps<{ options: any; height?: string }>();
const chartRef = ref<HTMLElement>();
const chart = shallowRef<any>(null);

function render() {
  if (!chartRef.value) return;
  if (!chart.value) {
    chart.value = echarts.init(chartRef.value);
  }
  chart.value.setOption(props.options, true);
}

onMounted(() => {
  render();
  window.addEventListener("resize", () => chart.value?.resize());
});

onBeforeUnmount(() => {
  chart.value?.dispose();
  window.removeEventListener("resize", () => chart.value?.resize());
});

watch(() => props.options, render, { deep: true });
</script>

<style scoped>
.trend-chart { width: 100%; min-height: 260px; }
</style>
