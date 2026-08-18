<!-- 意向性项目信息页: 政务源(发改委/自然资源厅等)意向项目结构化列表 -->
<template>
  <div class="intent-page">
    <div class="page-head">
      <h2>意向性项目信息</h2>
      <div class="head-actions">
        <el-button type="primary" size="small" :loading="crawling" @click="runCrawl">
          <el-icon><Refresh /></el-icon>抓取意向源
        </el-button>
      </div>
    </div>

    <!-- 统计 -->
    <el-row :gutter="14" class="stat-row">
      <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ stats.total ?? 0 }}</div><div class="stat-label">意向总数</div></div></el-col>
      <el-col :span="6">
        <div class="stat-card"><div class="stat-num">{{ typeStats.length }}</div><div class="stat-label">项目类型</div></div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card"><div class="stat-num">{{ recentCount }}</div><div class="stat-label">近90天</div></div>
      </el-col>
      <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ crawlResult?.stored ?? '-' }}</div><div class="stat-label">最近抓取</div></div></el-col>
    </el-row>

    <!-- 筛选 -->
    <el-card class="filter-card" shadow="never">
      <div class="filters">
        <el-select v-model="filters.project_type" placeholder="项目类型" clearable size="small" style="width: 150px">
          <el-option v-for="(t, i) in typeStats" :key="i" :label="t.type" :value="t.type" />
        </el-select>
        <RegionCascader v-model="regionVal" @change="onRegionChange" />
        <el-input v-model="filters.min_amount" placeholder="金额下限(万)" clearable size="small" style="width: 130px" type="number" />
        <el-select v-model="filters.days" size="small" style="width: 130px">
          <el-option label="近30天" :value="30" />
          <el-option label="近90天" :value="90" />
          <el-option label="近一年" :value="365" />
          <el-option label="全部" :value="0" />
        </el-select>
        <el-button type="primary" size="small" @click="loadList">查询</el-button>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card class="list-card" shadow="never">
      <el-table :data="items" size="small" v-loading="loading">
        <el-table-column prop="title" label="标题" min-width="360" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link v-if="row.url" type="primary" :underline="false" @click="openUrl(row.url)" target="_blank">{{ row.title }}</el-link>
            <span v-else>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="typeColor(row.project_type)">{{ row.industry || row.project_type || '未分类' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dept" label="发布部门" width="160" show-overflow-tooltip />
        <el-table-column prop="region" label="地域" width="110" />
        <el-table-column label="金额(万)" width="100">
          <template #default="{ row }">{{ row.amount != null ? Number(row.amount).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="contact" label="联系方式" width="130" show-overflow-tooltip />
        <el-table-column prop="published_at" label="抓取时间" width="100" />
      </el-table>
      <el-pagination
        v-model:current-page="page" v-model:page-size="pageSize"
        :total="total" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next"
        class="pager" @change="loadList"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import api from "@/api";
import RegionCascader from "@/components/RegionCascader.vue";

const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const crawling = ref(false);
const stats = ref<any>({});
const crawlResult = ref<any>(null);
const filters = ref<any>({ project_type: "", min_amount: "", days: 90 });
const regionVal = ref<string[]>([]);
function onRegionChange(v: { province: string; city: string; county: string }) {
  filters.value.province = v.province || undefined;
  filters.value.city = v.city || undefined;
  filters.value.county = v.county || undefined;
  loadList();
}

const typeStats = computed(() => stats.value.types || []);
const recentCount = computed(() => {
  const d = filters.value.days || 90;
  return items.value.filter((i) => {
    if (!i.published_at) return false;
    const t = new Date(i.published_at).getTime();
    return Date.now() - t < d * 86400000;
  }).length;
});

function openUrl(url: string) { window.open(url, "_blank", "noopener"); }
function typeColor(t: string): string {
  const m: Record<string, string> = {
    transport: "primary", geo_hazard: "danger", geo_survey: "warning",
    eco_restoration: "success", mining_rights: "info", energy: "primary",
    municipal: "warning", water: "primary", education: "info", healthcare: "danger",
  };
  return m[t] || "info";
}

async function loadStats() {
  try { stats.value = (await api.get("/intent/stats")) || {}; } catch { stats.value = {}; }
}
async function loadList() {
  loading.value = true;
  try {
    const params: any = {
      page: page.value, page_size: pageSize.value, days: filters.value.days || undefined,
    };
    if (filters.value.project_type) params.project_type = filters.value.project_type;
    if (filters.value.province) params.province = filters.value.province;
    if (filters.value.city) params.city = filters.value.city;
    if (filters.value.county) params.county = filters.value.county;
    if (filters.value.min_amount) params.min_amount = filters.value.min_amount;
    const res: any = await api.get("/intent/list", { params });
    items.value = res.items || [];
    total.value = res.total || 0;
  } catch { items.value = []; }
  finally { loading.value = false; }
}
async function runCrawl() {
  crawling.value = true;
  try {
    const res: any = await api.post("/intent/crawl", {}, { timeout: 300000 });
    crawlResult.value = res.data || res;
    ElMessage.success(`抓取完成：${crawlResult.value.stored ?? 0} 条入库`);
    await loadStats();
    await loadList();
  } catch { /* 拦截器 */ }
  finally { crawling.value = false; }
}

onMounted(() => { loadStats(); loadList(); });
</script>

<style scoped>
.intent-page { max-width: 1400px; padding-bottom: 32px; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.page-head h2 { margin: 0; font-size: 20px; color: #1f2d3d; }
.stat-row { margin-bottom: 14px; }
.stat-card { background: #fff; border-radius: 8px; padding: 16px 20px; border: 1px solid #e9edf6; text-align: center; border-top: 3px solid #2979ff; }
.stat-num { font-size: 26px; font-weight: 700; color: #2979ff; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.filter-card { margin-bottom: 14px; border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.filters { display: flex; gap: 10px; flex-wrap: wrap; }
.list-card { border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
