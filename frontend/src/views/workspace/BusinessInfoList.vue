<template>
  <div class="list-page">
    <h2 class="page-title">商业信息</h2>

    <!-- 筛选区(与项目管理一致): 关键词 + 类别 + 阶段 + 地域级联 + 时间窗 -->
    <el-card class="filter-card" shadow="never">
      <div class="filters">
        <el-input
          v-model="keyword" placeholder="搜索项目名称/编号" clearable style="width: 220px"
          @keyup.enter="handleSearch(keyword)" @clear="handleSearch('')"
        />
        <el-select v-model="categoryFilter" placeholder="项目类别" clearable style="width: 160px" @change="handleSearch(keyword)">
          <el-option v-for="c in categoryOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="stageFilter" placeholder="项目阶段" clearable style="width: 160px" @change="handleSearch(keyword)">
          <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <RegionCascader v-model="regionVal" width="160px" @change="onRegionChange" />
        <el-select v-model="daysFilter" style="width: 130px" @change="handleSearch(keyword)">
          <el-option label="近30天" :value="30" />
          <el-option label="近90天" :value="90" />
          <el-option label="近一年" :value="365" />
          <el-option label="全部" :value="0" />
        </el-select>
        <el-button type="primary" @click="handleSearch(keyword)">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <DynamicTable
      entity-type="projects"
    :data="list"
    :columns="columns"
    :loading="loading"
    :total="total"
    :can-export="true"
    @sort-change="handleSort"
    @row-click="(row: any) => $router.push(`/workspace/business/${row.id}`)"
    @page-change="handlePage"
  >
    </DynamicTable>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import api from "@/api";
import DynamicTable from "@/components/DynamicTable.vue";
import RegionCascader from "@/components/RegionCascader.vue";

const list = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const page = ref(1);
const pageSize = ref(20);
const keyword = ref("");
const categoryFilter = ref("");
const categoryOptions = ref<any[]>([]);
const stageFilter = ref("");
const stageOptions = ref<any[]>([]);
const regionVal = ref<string[]>([]);
const daysFilter = ref(0);
const sortField = ref("");
const sortOrder = ref("desc");

// 列定义：与项目管理一致(同数据源 /projects)
const columns = ref<any[]>([
  { field_key: "id", display_name: "ID", data_type: "text", width: "80", sortable: true },
  { field_key: "name", display_name: "项目名称", data_type: "text", width: "200", sortable: true },
  { field_key: "province_city", display_name: "省份城市", data_type: "text", width: "140" },
  { field_key: "last_progress_title", display_name: "项目阶段", data_type: "text", width: "180" },
  { field_key: "last_progress_date", display_name: "更新时间", data_type: "datetime", width: "160", sortable: true },
  { field_key: "amount", display_name: "总投资额", data_type: "money", width: "130", sortable: true },
]);

function handleSort(s: { prop: string; order: "ascending" | "descending" | null }) {
  if (!s.prop || !s.order) {
    sortField.value = "";
    sortOrder.value = "desc";
  } else {
    sortField.value = s.prop;
    sortOrder.value = s.order === "ascending" ? "asc" : "desc";
  }
  page.value = 1;
  loadData();
}

function onRegionChange(v: { province: string; city: string; county: string }) {
  regionVal.value = [v.province, v.city, v.county].filter(Boolean) as string[];
  page.value = 1;
  loadData();
}

function resetFilters() {
  keyword.value = "";
  categoryFilter.value = "";
  stageFilter.value = "";
  regionVal.value = [];
  daysFilter.value = 0;
  page.value = 1;
  loadData();
}

async function loadData() {
  loading.value = true;
  try {
    const filters: Record<string, string[]> = {};
    if (regionVal.value.length) {
      filters.province_city = [regionVal.value.join("|")];
    }
    if (stageFilter.value) {
      filters.last_progress_title = [stageFilter.value];
    }
    const res: any = await api.get("/projects", {
      params: {
        page: page.value,
        page_size: pageSize.value,
        keyword: keyword.value || undefined,
        category: categoryFilter.value || undefined,
        days: daysFilter.value || undefined,
        sort_field: sortField.value || undefined,
        sort_order: sortOrder.value,
        filters: Object.keys(filters).length ? JSON.stringify(filters) : undefined,
      },
    });
    list.value = res.items || [];
    total.value = res.total || 0;
    await appendDynamicColumns();
  } catch { list.value = []; }
  finally { loading.value = false; }
}

async function loadCategories() {
  try {
    const res: any = await api.get("/option-sets/project_category/items");
    categoryOptions.value = (res.items || []).map((i: any) => ({ value: i.value, label: i.label }));
  } catch { categoryOptions.value = []; }
}

async function loadStages() {
  try {
    const res: any = await api.get("/option-sets/project_progress_stage/items");
    stageOptions.value = (res.items || []).map((i: any) => ({ value: i.value, label: i.label }));
  } catch { stageOptions.value = []; }
}

async function appendDynamicColumns() {
  try {
    const res: any = await api.get("/dynamic/project/form-config?mode=view");
    const dynFields = (res.fields || []).filter((f: any) => f.is_list_visible !== false);
    const existingKeys = new Set(columns.value.map((c) => c.field_key));
    for (const df of dynFields) {
      if (!existingKeys.has(df.field_key)) {
        columns.value.push({
          field_key: df.field_key,
          display_name: df.display_name,
          data_type: df.data_type,
          width: undefined,
          sortable: df.data_type === "money" || df.data_type === "number",
          options: df.options,
          option_set_code: df.option_set_code || "",
        });
      }
    }
  } catch { /* ignore */ }
}

function handleSearch(kw: string) {
  keyword.value = kw;
  page.value = 1;
  loadData();
}

function handlePage(params: { page: number; pageSize: number }) {
  page.value = params.page;
  pageSize.value = params.pageSize;
  loadData();
}

onMounted(() => { loadCategories(); loadStages(); loadData(); });
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.page-title { margin: 0; font-size: 20px; color: #1f2d3d; }
.filter-card { margin-bottom: 12px; border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
</style>
