<template>
  <div ref="el" class="e-chart" :style="{ height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from "vue";
import type { ECharts } from "echarts";

const props = defineProps<{ option: any; height?: string }>();
const emit = defineEmits<{ (e: "chart-click", params: any): void }>();
const el = ref<HTMLElement | null>(null);
let chart: ECharts | null = null;

async function render() {
  if (!el.value) return;
  if (!chart) {
    const echarts = await import("echarts");
    chart = echarts.init(el.value, undefined, { renderer: "canvas" });
    chart.on("click", (params) => emit("chart-click", params));
  }
  chart.setOption(props.option, true);
}
function resize() { chart?.resize(); }
onMounted(async () => { await nextTick(); await render(); window.addEventListener("resize", resize); });
onUnmounted(() => { window.removeEventListener("resize", resize); chart?.dispose(); });
watch(() => props.option, render, { deep: true });
</script>

<style scoped>
.e-chart { width: 100%; }
</style>
