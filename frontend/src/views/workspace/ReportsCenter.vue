<!-- 报表中心 — 按 实体/时间/区域/状态/部门 维度聚合统计 -->
<template>
  <div class="reports-center">
    <!-- 筛选区 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="实体">
          <el-select v-model="entity" style="width: 120px" @change="onEntityChange">
            <el-option v-for="o in entityOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="分组维度">
          <el-select v-model="group" style="width: 120px" @change="load">
            <el-option v-for="o in groupOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="指标">
          <el-select v-model="metric" style="width: 110px" @change="load">
            <el-option v-for="o in metricOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="supportDept" label="部门ID">
          <el-input-number v-model="deptId" :min="0" :controls="false" placeholder="全部" style="width: 110px"
            @change="load" />
        </el-form-item>
        <el-form-item label="创建时间">
          <el-date-picker v-model="dateRange" type="daterange" unlink-panels value-format="YYYY-MM-DD"
            range-separator="~" start-placeholder="起" end-placeholder="止" style="width: 240px" @change="load" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
          <el-button :disabled="!result" @click="exportXlsx">导出 Excel</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 概览卡 -->
    <div v-if="result" class="summary-row">
      <el-statistic title="维度分组数" :value="result.data.length" />
      <el-statistic :title="isAmount ? '合计金额' : '合计数量'" :value="totalValue" :precision="isAmount ? 2 : 0" />
      <div class="summary-meta">
        <el-tag type="info">{{ result.meta.entity_label }}</el-tag>
        <el-tag type="info">{{ result.meta.group_label }}</el-tag>
        <el-tag type="info">{{ isAmount ? '金额指标' : '数量指标' }}</el-tag>
      </div>
    </div>

    <!-- 图表 + 表格 -->
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="chart-card">
          <template #header>聚合趋势</template>
          <TrendChart v-if="result && result.data.length" :options="chartOptions" height="340px" />
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="table-card">
          <template #header>明细数据</template>
          <el-table v-loading="loading" :data="result?.data || []" height="340" size="small" stripe>
            <el-table-column prop="key" :label="result?.meta.group_label || '维度'" min-width="140" show-overflow-tooltip />
            <el-table-column prop="count" label="数量" width="100" align="right" />
            <el-table-column v-if="isAmount" prop="amount" label="金额" width="120" align="right">
              <template #default="{ row }">{{ row.amount != null ? Number(row.amount).toFixed(2) : '-' }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import api from "@/api";
import TrendChart from "@/components/TrendChart.vue";
import * as XLSX from "xlsx";

const entity = ref("project");
const group = ref("month");
const metric = ref("count");
const deptId = ref<number | null>(null);
const dateRange = ref<[string, string] | null>(null);

const loading = ref(false);
const result = ref<any>(null);

const ENTITY_LABELS: Record<string, string> = { project: "项目", person: "人员", company: "单位", bid: "中标" };
const GROUP_LABELS: Record<string, string> = {
  month: "月份", quarter: "季度", year: "年份", status: "状态", department: "部门", province: "区域",
};
const METRIC_LABELS: Record<string, string> = { count: "数量", amount: "金额" };

const entityOptions = Object.keys(ENTITY_LABELS).map((v) => ({ value: v, label: ENTITY_LABELS[v] }));

const supportDept = computed(() => entity.value === "project" || entity.value === "person");
const supportStatus = computed(() => entity.value === "project" || entity.value === "person");
const supportAmount = computed(() => entity.value === "project");

const groupOptions = computed(() => {
  const keys = ["month", "quarter", "year", "province"];
  if (supportStatus.value) keys.push("status");
  if (supportDept.value) keys.push("department");
  return keys.map((k) => ({ value: k, label: GROUP_LABELS[k] }));
});
const metricOptions = computed(() =>
  (supportAmount.value ? ["count", "amount"] : ["count"]).map((k) => ({ value: k, label: METRIC_LABELS[k] }))
);

const isAmount = computed(() => metric.value === "amount" && result.value?.meta?.metric === "amount");
const totalValue = computed(() => {
  const rows = result.value?.data || [];
  if (isAmount.value) return rows.reduce((s: number, r: any) => s + (Number(r.amount) || 0), 0);
  return rows.reduce((s: number, r: any) => s + (Number(r.count) || 0), 0);
});

const chartOptions = computed(() => {
  const rows = result.value?.data || [];
  const cats = rows.map((r: any) => String(r.key));
  const vals = rows.map((r: any) => (isAmount.value ? Number(r.amount) || 0 : Number(r.count) || 0));
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 56, right: 24, top: 24, bottom: cats.length > 8 ? 72 : 36 },
    xAxis: {
      type: "category",
      data: cats,
      axisLabel: { interval: 0, rotate: cats.length > 8 ? 30 : 0 },
    },
    yAxis: { type: "value" },
    series: [
      {
        type: "bar",
        data: vals,
        name: isAmount.value ? "金额" : "数量",
        barMaxWidth: 42,
        itemStyle: { color: "#a51c30", borderRadius: [4, 4, 0, 0] },
      },
    ],
  };
});

function onEntityChange() {
  // 实体切换后, 复位不支持的维度/指标
  if (!groupOptions.value.some((o) => o.value === group.value)) group.value = "month";
  if (!metricOptions.value.some((o) => o.value === metric.value)) metric.value = "count";
  if (!supportDept.value) deptId.value = null;
  load();
}

async function load() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      entity_type: entity.value,
      group_by: group.value,
      metric: metric.value,
      limit: 100,
    };
    if (deptId.value != null) params.department_id = deptId.value;
    if (dateRange.value && dateRange.value[0]) params.date_from = dateRange.value[0];
    if (dateRange.value && dateRange.value[1]) params.date_to = dateRange.value[1];
    const res: any = await api.get("/reports/aggregate", { params });
    result.value = res; // 拦截器已解包: { success, data, meta }
  } catch {
    // 错误提示由响应拦截器统一处理
    result.value = null;
  } finally {
    loading.value = false;
  }
}

function exportXlsx() {
  const rows = result.value?.data || [];
  const meta = result.value?.meta || {};
  const aoa: any[][] = [[meta.group_label || "维度", "数量", isAmount.value ? "金额" : ""]];
  rows.forEach((r: any) => aoa.push([r.key, r.count, isAmount.value ? r.amount ?? "" : ""]));
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "报表");
  XLSX.writeFile(wb, `报表_${meta.entity || entity.value}_${meta.group_by || group.value}.xlsx`);
}

onMounted(load);
</script>

<style scoped>
.reports-center { padding: 4px 0 24px; }
.filter-card { margin-bottom: 16px; border-radius: 12px; }
.filter-form :deep(.el-form-item) { margin-bottom: 0; }
.summary-row {
  display: flex; align-items: center; gap: 32px;
  background: #fff; border: 1px solid #ece8e4; border-radius: 12px;
  padding: 16px 20px; margin-bottom: 16px;
}
.summary-meta { display: flex; gap: 8px; margin-left: auto; }
.chart-card, .table-card { border-radius: 12px; }
</style>
