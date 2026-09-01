<!--
  情报中心 · 数据看板
  后端: GET /api/v1/admin/intelligence/stats
-->
<template>
  <div class="intent-dashboard">
    <div class="page-head">
      <h2>情报中心数据看板</h2>
      <div class="head-actions">
        <el-button size="small" type="primary" :loading="loading" @click="loadStats">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <el-row :gutter="14" class="stat-row">
      <el-col :xs="12" :sm="8" :md="4">
        <div class="stat-card main">
          <div class="stat-num">{{ stats.total ?? 0 }}</div>
          <div class="stat-label">情报总量</div>
        </div>
      </el-col>
      <el-col v-for="s in statusCards" :key="s.key" :xs="12" :sm="8" :md="4">
        <div class="stat-card">
          <div class="stat-num">{{ stats.wf_status?.[s.key] ?? 0 }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="4">
        <div class="stat-card">
          <div class="stat-num">{{ stats.contact_count ?? 0 }}</div>
          <div class="stat-label">已录联系人</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="14">
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title">近 12 个月情报发布趋势</span></template>
          <TrendChart v-if="trendOption.series?.length" :options="trendOption" height="300px" />
          <el-empty v-else description="暂无趋势数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title">流转状态构成</span></template>
          <TrendChart v-if="pieOption.series?.length" :options="pieOption" height="300px" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title">行业分布 Top10</span></template>
          <TrendChart v-if="industryOption.series?.length" :options="industryOption" height="300px" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title">地域分布 Top10</span></template>
          <TrendChart v-if="regionOption.series?.length" :options="regionOption" height="300px" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="24">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title">来源采集 Top10</span></template>
          <TrendChart v-if="sourceOption.series?.length" :options="sourceOption" height="280px" />
          <el-empty v-else description="暂无来源数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import api from "@/api";
import TrendChart from "@/components/TrendChart.vue";

const loading = ref(false);
const stats = ref<any>({ wf_status: {} });

const statusCards = [
  { key: "draft", label: "草稿" },
  { key: "pending", label: "待审核" },
  { key: "approved", label: "审核通过" },
  { key: "published", label: "已发布" },
  { key: "offline", label: "已下架" },
];

async function loadStats() {
  loading.value = true;
  try {
    const r: any = await api.get("/admin/intelligence/stats");
    if (r?.success) stats.value = r;
  } finally {
    loading.value = false;
  }
}

const trendOption = computed(() => {
  const list = stats.value.monthly_trend || [];
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    xAxis: { type: "category", data: list.map((m: any) => m.month) },
    yAxis: { type: "value", minInterval: 1 },
    series: [{
      type: "line", smooth: true, data: list.map((m: any) => m.count),
      areaStyle: { opacity: 0.15 }, itemStyle: { color: "#2f7be0" },
    }],
  };
});

const pieOption = computed(() => {
  const wf = stats.value.wf_status || {};
  const labels: Record<string, string> = {
    draft: "草稿", pending: "待审核", approved: "审核通过",
    published: "已发布", offline: "已下架", rejected: "已驳回",
  };
  const data = Object.entries(wf)
    .filter(([, v]: any) => v > 0)
    .map(([k, v]: any) => ({ name: labels[k] || k, value: v }));
  return data.length ? {
    tooltip: { trigger: "item" },
    legend: { bottom: 0 },
    color: ["#8a8e99", "#f5a623", "#36a3d6", "#18ac4f", "#f56c00", "#e65b7a"],
    series: [{
      type: "pie", radius: ["42%", "68%"], center: ["50%", "45%"],
      data, label: { show: false },
    }],
  } : { series: [] as any[] };
});

const industryOption = computed(() => {
  const list = stats.value.industry_top || [];
  return list.length ? {
    tooltip: { trigger: "axis" },
    grid: { left: 100, right: 20, top: 10, bottom: 30 },
    xAxis: { type: "value", minInterval: 1 },
    yAxis: { type: "category", data: list.map((m: any) => m.name).reverse() },
    series: [{
      type: "bar", data: list.map((m: any) => m.count).reverse(),
      itemStyle: { color: "#2f7be0", borderRadius: [0, 3, 3, 0] }, barMaxWidth: 18,
    }],
  } : { series: [] as any[] };
});

const regionOption = computed(() => {
  const list = stats.value.region_top || [];
  return list.length ? {
    tooltip: { trigger: "axis" },
    grid: { left: 70, right: 20, top: 10, bottom: 30 },
    xAxis: { type: "value", minInterval: 1 },
    yAxis: { type: "category", data: list.map((m: any) => m.name).reverse() },
    series: [{
      type: "bar", data: list.map((m: any) => m.count).reverse(),
      itemStyle: { color: "#f5a623", borderRadius: [0, 3, 3, 0] }, barMaxWidth: 18,
    }],
  } : { series: [] as any[] };
});

const sourceOption = computed(() => {
  const list = stats.value.source_top || [];
  return list.length ? {
    tooltip: { trigger: "axis" },
    grid: { left: 130, right: 30, top: 10, bottom: 30 },
    xAxis: { type: "value", minInterval: 1 },
    yAxis: { type: "category", data: list.map((m: any) => m.name).reverse() },
    series: [{
      type: "bar", data: list.map((m: any) => m.count).reverse(),
      itemStyle: { color: "#18ac4f", borderRadius: [0, 3, 3, 0] }, barMaxWidth: 18,
    }],
  } : { series: [] as any[] };
});

onMounted(loadStats);
</script>

<style scoped>
.intent-dashboard { padding: 4px 0 30px; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.page-head h2 { margin: 0; font-size: 16px; color: #1c2a3a; }
.head-actions { display: flex; gap: 8px; }
.stat-row { margin-bottom: 14px; }
.stat-card {
  background: #fff; border: 1px solid #e6ebf1; border-radius: 6px;
  padding: 14px 16px; margin-bottom: 14px;
}
.stat-card.main { border-left: 3px solid #2f7be0; }
.stat-num { font-size: 22px; font-weight: 700; color: #1c2a3a; }
.stat-card.main .stat-num { color: #2f7be0; }
.stat-label { font-size: 12px; color: #8a8e99; margin-top: 2px; }
.chart-card { border-radius: 6px; margin-bottom: 14px; }
.card-title { font-size: 13.5px; font-weight: 600; color: #1c2a3a; }
</style>
