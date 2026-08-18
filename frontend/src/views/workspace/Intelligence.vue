<!-- 行业情报中心: 跨 意向公告/招标线索/中标公告 统一检索(阶段+地域+时间+关键词) -->
<template>
  <div class="intel-page">
    <div class="page-head">
      <div>
        <h2>行业情报中心</h2>
        <p class="page-desc">政策动态 · 规划公告 · 投资意向 · 招标 · 中标公示 — 按阶段/地域(川藏新)/时间统一检索</p>
      </div>
      <div class="head-actions">
        <el-button :loading="loading" @click="loadList"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <!-- 筛选区 -->
    <el-card class="filter-card" shadow="never">
      <div class="filters">
        <el-input
          v-model="query.keyword" placeholder="搜索标题/采购人" clearable style="width: 220px"
          @keyup.enter="loadList" @clear="loadList"
        />
        <el-select v-model="query.stage" placeholder="项目阶段" clearable style="width: 170px" @change="loadList">
          <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value">
            <div class="stage-opt">
              <span>{{ s.label }}</span>
              <span class="stage-desc">{{ s.desc }}</span>
            </div>
          </el-option>
        </el-select>
        <RegionCascader v-model="regionVal" @change="onRegionChange" />
        <el-select v-model="query.days" style="width: 130px" @change="loadList">
          <el-option label="近30天" :value="30" />
          <el-option label="近90天" :value="90" />
          <el-option label="近一年" :value="365" />
          <el-option label="全部" :value="0" />
        </el-select>
        <el-button type="primary" @click="loadList">查询</el-button>
      </div>
    </el-card>

    <!-- 结果统计 -->
    <div class="stat-bar">
      <span class="stat-total">共 <b>{{ total }}</b> 条情报</span>
      <template v-if="query.stage">
        <el-tag size="small" type="primary" closable @close="query.stage = ''; loadList()">
          {{ stageLabel(query.stage) }}
        </el-tag>
      </template>
      <template v-if="regionVal.length">
        <el-tag size="small" type="success" closable @close="clearRegion">
          {{ regionVal.join(' / ') }}
        </el-tag>
      </template>
      <span class="stage-hint">阶段说明：投资意向期=提前获取·机会最大 | 招标期=可报名参与 | 中标公示期=成交结果参考</span>
    </div>

    <!-- 结果列表(按发布时间排序) -->
    <el-card class="list-card" shadow="never">
      <el-table :data="list" v-loading="loading" size="default" stripe @row-click="(r:any)=>r.url && openUrl(r.url)" class="clickable-table">
        <el-table-column label="阶段" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="stageType(row.stage)">{{ row.stage_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="130" sortable prop="published_at">
          <template #default="{ row }">{{ row.published_at || '-' }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="title-link">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="地域" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.region" size="small" effect="plain" type="warning">{{ row.region }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="采购人/部门" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.purchaser || row.source_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="预算" width="110">
          <template #default="{ row }">{{ row.amount || '-' }}</template>
        </el-table-column>
        <el-table-column label="摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.summary || '-' }}</template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next" :total="total" :page-size="query.page_size"
          :current-page="query.page" @current-change="(p: number) => { query.page = p; loadList(); }"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import api from "@/api";
import RegionCascader from "@/components/RegionCascader.vue";

const loading = ref(false);
const list = ref<any[]>([]);
const total = ref(0);
const regionVal = ref<string[]>([]);
const stageOptions = ref<any[]>([]);

const query = ref<any>({ page: 1, page_size: 20, keyword: "", stage: "", days: 90, province: "", city: "", county: "" });

function openUrl(url: string) { window.open(url, "_blank", "noopener"); }

function stageLabel(v: string) {
  return stageOptions.value.find((s) => s.value === v)?.label || v;
}
function stageType(v: string) {
  return v === "investment" ? "success" : v === "bidding" ? "primary" : "warning";
}
function onRegionChange(v: { province: string; city: string; county: string }) {
  query.value.province = v.province || "";
  query.value.city = v.city || "";
  query.value.county = v.county || "";
  query.value.page = 1;
  loadList();
}
function clearRegion() {
  regionVal.value = [];
  query.value.province = "";
  query.value.city = "";
  query.value.county = "";
  query.value.page = 1;
  loadList();
}

async function loadList() {
  loading.value = true;
  try {
    const params: any = {
      page: query.value.page, page_size: query.value.page_size,
      keyword: query.value.keyword || undefined,
      stage: query.value.stage || undefined,
      days: query.value.days || undefined,
      province: query.value.province || undefined,
      city: query.value.city || undefined,
      county: query.value.county || undefined,
    };
    const res: any = await api.get("/intelligence/search", { params });
    list.value = res.items || [];
    total.value = res.total || 0;
    if (!stageOptions.value.length && res.stages) stageOptions.value = res.stages;
  } catch { /* 拦截器处理 */ }
  finally { loading.value = false; }
}

onMounted(loadList);
</script>

<style scoped>
.intel-page { max-width: 1440px; padding-bottom: 32px; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.page-head h2 { margin: 0; font-size: 20px; color: #1f2d3d; }
.page-desc { margin: 4px 0 0; font-size: 12.5px; color: #909399; }
.head-actions { display: flex; gap: 8px; }
.filter-card { margin-bottom: 12px; border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.stage-opt { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.stage-desc { font-size: 11px; color: #c0c4cc; }
.stat-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 13px; color: #606266; }
.stat-total b { color: #2979ff; font-size: 15px; }
.stage-hint { margin-left: auto; font-size: 12px; color: #c0c4cc; }
.list-card { border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.title-link { color: #2979ff; cursor: pointer; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.clickable-table :deep(.el-table__row) { cursor: pointer; }
.clickable-table :deep(.el-table__row:hover > td.el-table__cell) { background-color: #eef5ff !important; }
</style>
