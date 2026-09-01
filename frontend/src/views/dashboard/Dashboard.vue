<!-- 数据看板 — 项目经营+人员投入+动态维度 -->
<template>
  <div class="dashboard">
    <div class="page-head">
      <span class="eyebrow">DATA DASHBOARD</span>
      <h2 class="page-title">数据看板</h2>
      <p class="page-desc">项目经营、人员投入与动态维度的实时经营视图，支撑管理决策与资源调度。</p>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar ssm-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="12">
          <el-date-picker v-model="dateRange" type="daterange" range-separator="~"
            start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD"
            @change="refreshAll" style="width: 100%" />
        </el-col>
        <el-col :span="4">
          <el-select v-model="deptId" placeholder="选择部门" clearable @change="refreshAll" style="width:100%">
            <el-option label="全部" :value="null" />
          </el-select>
        </el-col>
      </el-row>
    </div>

    <!-- 指标卡片行 -->
    <el-row :gutter="16" class="metric-row">
      <el-col :span="6"><MetricCard title="活跃项目" :value="metrics.active_projects" suffix="个" icon="FolderOpened" /></el-col>
      <el-col :span="6"><MetricCard title="活跃成员" :value="metrics.active_members" suffix="人" icon="UserFilled" /></el-col>
      <el-col :span="6"><MetricCard title="平均周期" :value="metrics.avg_project_duration_days" suffix="天" icon="Timer" /></el-col>
      <el-col :span="6"><MetricCard title="今年完成" :value="metrics.completed_this_year" suffix="个" icon="CircleCheck" /></el-col>
    </el-row>

    <!-- 图表行1: 状态饼图 + 月度趋势 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12" v-loading="loading">
        <div class="chart-card ssm-card">
          <div class="section-title chart-card-title">项目状态分布</div>
          <TrendChart :options="statusChartOption" height="320px" v-if="!loading" />
          <el-empty v-else description="加载中" :image-size="60" />
        </div>
      </el-col>
      <el-col :span="12" v-loading="loading">
        <div class="chart-card ssm-card">
          <div class="section-title chart-card-title">月度新建与完成趋势</div>
          <TrendChart :options="monthChartOption" height="320px" v-if="!loading" />
          <el-empty v-else description="加载中" :image-size="60" />
        </div>
      </el-col>
    </el-row>

    <!-- 图表行2: 人员投入 Top10 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12" v-loading="loading">
        <div class="chart-card ssm-card">
          <div class="section-title chart-card-title">人员投入 Top10</div>
          <TrendChart :options="personChartOption" height="320px" v-if="!loading" />
          <el-empty v-else :image-size="60" />
        </div>
      </el-col>
      <el-col :span="12" v-loading="loading">
        <div class="chart-card ssm-card">
          <div class="section-title chart-card-title">动态维度分析</div>
          <el-row :gutter="8" style="margin-bottom:12px">
            <el-col :span="12">
              <el-select v-model="dimField" placeholder="选择分析字段" style="width:100%" @change="loadDynamicDim">
                <el-option v-for="f in filterableFields" :key="f.field_key" :label="f.display_name" :value="f.field_key" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-select v-model="dimAgg" style="width:100%" @change="loadDynamicDim">
                <el-option label="计数" value="count" /><el-option label="求和" value="sum" />
                <el-option label="均值" value="avg" /><el-option label="最大" value="max" />
              </el-select>
            </el-col>
          </el-row>
          <TrendChart v-if="dimBuckets.length" :options="dimChartOption" height="260px" />
          <el-empty v-else description="请选择分析字段" :image-size="40" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import api from "@/api";
import MetricCard from "@/components/MetricCard.vue";
import TrendChart from "@/components/TrendChart.vue";

const loading = ref(false);
const dateRange = ref<[string, string] | null>(null);
const deptId = ref<number | null>(null);

const metrics = ref<any>({ active_projects: 0, active_members: 0, avg_project_duration_days: 0, completed_this_year: 0 });
const projectSummary = ref<any>({ by_status: [], by_month: [] });
const personData = ref<any[]>([]);
const filterableFields = ref<any[]>([]);
const dimField = ref("");
const dimAgg = ref("count");
const dimBuckets = ref<any[]>([]);
/** 维度字段值→中文映射(select 字段按 option_set 加载) */
const dimLabelMap = ref<Record<string, string>>({});

async function refreshAll() {
  loading.value = true;
  try {
    const params: any = {};
    if (dateRange.value) { params.date_from = dateRange.value[0]; params.date_to = dateRange.value[1]; }
    if (deptId.value) params.department_id = deptId.value;

    const [mRes, sRes, pRes] = await Promise.all([
      api.get("/dashboard/metrics", { params }),
      api.get("/dashboard/project-summary", { params }),
      api.get("/dashboard/person-workload", { params }),
    ]);
    metrics.value = mRes.data || {};
    projectSummary.value = sRes.data || { by_status: [], by_month: [] };
    personData.value = (pRes.data?.persons || []).slice(0, 10);
  } catch { /* handled by interceptor */ }
  finally { loading.value = false; }
}

async function loadFilterableFields() {
  try {
    const res: any = await api.get("/field-metadata", { params: { entity_type: "project", status: "enabled", page_size: 100 } });
    filterableFields.value = (res.items || []).filter((f: any) => f.is_filterable);
  } catch { filterableFields.value = []; }
}

async function loadDynamicDim() {
  if (!dimField.value) return;
  try {
    const res: any = await api.get("/dashboard/dynamic-dimension", {
      params: { field_key: dimField.value, agg: dimAgg.value },
    });
    dimBuckets.value = res.data?.buckets || [];
  } catch { dimBuckets.value = []; }
  // 为 select 字段加载值→中文映射(避免 x 轴显示 geo_survey 等英文值)
  try {
    const f = filterableFields.value.find((x: any) => x.field_key === dimField.value);
    if (f?.option_set_code) {
      const or = await api.get(`/option-sets/${f.option_set_code}/items`);
      const m: Record<string, string> = {};
      for (const i of (or.items || [])) m[i.value] = i.label;
      dimLabelMap.value = m;
    } else {
      dimLabelMap.value = {};
    }
  } catch { dimLabelMap.value = {}; }
}

// ECharts options
const statusChartOption = computed(() => ({
  tooltip: { trigger: "item" },
  series: [{
    type: "pie", radius: ["40%", "65%"],
    data: (projectSummary.value.by_status || []).map((s: any) => ({
      name: s.label, value: s.count,
      itemStyle: { color: s.color },
    })),
  }],
}));

const monthChartOption = computed(() => ({
  tooltip: { trigger: "axis" },
  xAxis: { type: "category", data: (projectSummary.value.by_month || []).map((m: any) => m.month) },
  yAxis: { type: "value" },
  series: [
    { name: "新建", type: "line", data: (projectSummary.value.by_month || []).map((m: any) => m.created), smooth: true, color: "#a51c30" },
    { name: "完成", type: "line", data: (projectSummary.value.by_month || []).map((m: any) => m.completed), smooth: true, color: "#2bb673" },
  ],
}));

const personChartOption = computed(() => ({
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  yAxis: { type: "category", data: personData.value.map((p: any) => p.name).reverse(), axisLabel: { width: 80, overflow: "truncate" } },
  xAxis: { type: "value" },
  series: [{ type: "bar", data: personData.value.map((p: any) => p.project_count).reverse(), color: "#a51c30", label: { show: true, position: "right" } }],
  grid: { left: 100 },
}));

const dimChartOption = computed(() => ({
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  xAxis: { type: "category", data: dimBuckets.value.map((b: any) => dimLabelMap.value[b.key] || b.key), axisLabel: { rotate: 30 } },
  yAxis: { type: "value" },
  series: [{ type: "bar", data: dimBuckets.value.map((b: any) => b.value), color: "#E6A23C" }],
}));

onMounted(() => { refreshAll(); loadFilterableFields(); });
</script>

<style scoped>
.dashboard { padding: 8px; }
.page-head {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--ssm-hairline);
}
.eyebrow {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: var(--ssm-eyebrow-spacing);
  text-transform: uppercase;
  color: var(--ssm-eyebrow);
  margin-bottom: 6px;
}
.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--ssm-text-main);
  letter-spacing: 0.01em;
}
.page-desc {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ssm-text-secondary);
  max-width: 720px;
}
.filter-bar { margin-bottom: 16px; padding: 16px; }
.metric-row { margin: 0 0 16px; }
.chart-row { margin: 0 0 16px; }
.chart-card { padding: 18px 20px; border: 1px solid var(--ssm-border); border-radius: var(--ssm-radius); box-shadow: var(--ssm-shadow); }
.chart-card-title {
  margin-bottom: 14px;
  font-size: 16px;
  font-weight: 700;
  color: var(--ssm-text-main);
  padding-left: 10px;
  border-left: 3px solid var(--ssm-primary);
}
</style>
