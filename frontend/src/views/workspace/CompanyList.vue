<!-- 公司/单位列表页 -->
<template>
  <div class="list-page">
    <div class="page-head">
      <span class="eyebrow">ORGANIZATION DIRECTORY</span>
      <h2 class="page-title">单位管理</h2>
      <p class="page-desc">汇聚业主、竞对、合作方与潜在客户的全量单位档案，支撑公关路径与情报关联分析。</p>
    </div>
    <DynamicTable
      entity-type="company"
    :data="list"
    :columns="columns"
    :loading="loading"
    :total="total"
    :can-export="!isPortal"
    :can-import="!isPortal"
    :show-actions="!isPortal"
    :selectable="!isPortal"
    :filters="filters"
    :search-fields="searchFields"
    @search="handleSearch"
    @sort-change="handleSort"
    @filter-change="handleFilter"
    @row-click="goDetail"
    @page-change="handlePage"
  >
    <template #actions="{ row }">
      <el-popconfirm v-if="!isPortal" title="确定删除？" @confirm="handleDelete(row.id)">
        <template #reference>
          <el-button text type="danger" size="small" @click.stop>删除</el-button>
        </template>
      </el-popconfirm>
    </template>
    </DynamicTable>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "CompanyList" });
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import api from "@/api";
import DynamicTable from "@/components/DynamicTable.vue";
import { useNavBase } from "@/utils/navBase";
import { usePortalMode } from "@/utils/portalMode";

const router = useRouter();
const { navTo } = useNavBase();
const { isPortal } = usePortalMode();
function goDetail(row: any) {
  router.push(navTo(`/companies/${row.id}`));
}

const list = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const page = ref(1);
const pageSize = ref(20);
const keyword = ref("");
const sortField = ref("");
const sortOrder = ref("desc");
const filters = ref<Record<string, string[]>>({});

// 高级搜索面板字段(三组并列复选)
const searchFields = [
  { field_key: "province", display_name: "所在省市", option_set_code: "__china_province__" },
  { field_key: "company_type", display_name: "单位类型" },
  { field_key: "industry", display_name: "行业" },
];

// 只保留高填充字段(填充率>25%): 名称/单位类型/行业/省份/城市/联系方式
const columns = ref<any[]>([
  { field_key: "name", display_name: "单位名称", data_type: "text", width: "240", sortable: true },
  { field_key: "company_type", display_name: "单位类型", data_type: "text", width: "120", sortable: true },
  { field_key: "industry", display_name: "企业类别", data_type: "text", width: "120", sortable: true },
  { field_key: "province", display_name: "省份", data_type: "text", width: "100", sortable: true },
  { field_key: "city", display_name: "城市", data_type: "text", width: "100", sortable: true },
  { field_key: "contact", display_name: "甲方联系方式", data_type: "text", width: "170" },
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

function handleFilter(f: Record<string, string[]>) {
  filters.value = f || {};
  page.value = 1;
  loadData();
}

async function loadData() {
  loading.value = true;
  try {
    const res: any = await api.get("/companies", {
      params: { page: page.value, page_size: pageSize.value, keyword: keyword.value, sort_field: sortField.value || undefined, sort_order: sortOrder.value, filters: Object.keys(filters.value).length ? JSON.stringify(filters.value) : undefined },
    });
    list.value = res.items || [];
    total.value = res.total || 0;
    await appendDynamicColumns();
  } catch { list.value = []; }
  finally { loading.value = false; }
}

// 列表页仅追加高填充动态字段白名单(其余稀疏字段不展示, 保持列表清爽)
const DYNAMIC_LIST_WHITELIST = new Set([
  "contact_phone",  // 联系电话(25% 填充)
  "ownership",      // 企业性质(100% 填充, 三套分类)
]);

async function appendDynamicColumns() {
  try {
    const res: any = await api.get("/dynamic/company/form-config?mode=view");
    const dynFields = (res.fields || []).filter((f: any) => f.is_list_visible !== false && DYNAMIC_LIST_WHITELIST.has(f.field_key));
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
async function handleDelete(id: number) {
  try {
    await api.delete(`/companies/${id}`);
    ElMessage.success("已删除");
    loadData();
  } catch { /* handled by interceptor */ }
}

onMounted(loadData);
</script>

<style scoped>
.page-head {
  margin-bottom: 16px;
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
</style>
