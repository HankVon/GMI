<template>
  <div class="list-page">
    <div class="page-head">
      <h2 class="page-title">人员管理</h2>
      <el-button type="primary" @click="showAdd = true"><el-icon><Plus /></el-icon>新增人员</el-button>
    </div>
    <DynamicTable
      entity-type="persons"
      :data="list"
      :columns="columns"
      :loading="loading"
      :total="total"
    :can-export="true"
    :can-import="true"
    :filters="filters"
    @search="handleSearch"
    @sort-change="handleSort"
    @filter-change="handleFilter"
    @row-click="(row: any) => $router.push(`/workspace/persons/${row.id}`)"
    @page-change="handlePage"
  >
      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="$router.push(`/workspace/persons/${row.id}`)">详情</el-button>
        <el-button link type="danger" size="small" @click="removePerson(row)">删除</el-button>
      </template>
    </DynamicTable>

    <el-dialog v-model="showAdd" title="新增人员" width="480px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="编码" required><el-input v-model="form.code" placeholder="如 EMP-001" /></el-form-item>
        <el-form-item label="姓名" required><el-input v-model="form.name" placeholder="如 张三" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="职位"><el-input v-model="form.position" /></el-form-item>
        <el-form-item label="所属单位">
          <el-select
            v-model="form.company_id"
            filterable remote clearable
            :remote-method="searchCompanies"
            placeholder="输入单位名称搜索"
            style="width:100%"
          >
            <el-option v-for="c in companyOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="在职" value="active" />
            <el-option label="离职" value="resigned" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doAdd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "@/api";
import DynamicTable from "@/components/DynamicTable.vue";

const list = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const page = ref(1);
const pageSize = ref(20);
const keyword = ref("");
const showAdd = ref(false);
const saving = ref(false);
const companyOptions = ref<any[]>([]);
const form = ref({ code: "", name: "", email: "", phone: "", position: "", company_id: null, status: "active" });

let companySearchSeq = 0;
async function searchCompanies(query: string) {
  if (!query) { companyOptions.value = []; return; }
  const seq = ++companySearchSeq;
  try {
    const res: any = await api.get("/companies", { params: { keyword: query, page_size: 20 } });
    if (seq !== companySearchSeq) return; // 丢弃过期响应, 避免竞态覆盖
    companyOptions.value = res.items || [];
  } catch { if (seq === companySearchSeq) companyOptions.value = []; }
}

const sortField = ref("");
const sortOrder = ref("desc");
const filters = ref<Record<string, string[]>>({});

// 固定列(顺序按用户要求) + 从字段管理(/dynamic/person/form-config)动态追加的列
const columns = ref<any[]>([
  { field_key: "code", display_name: "人员编码", data_type: "text", width: "150", sortable: true },
  { field_key: "name", display_name: "联系人", data_type: "text", width: "120", sortable: true },
  { field_key: "position", display_name: "联系人职位", data_type: "text", width: "140", sortable: true },
  { field_key: "company_name", display_name: "公司名称", data_type: "text", width: "220" },
  { field_key: "latest_project_time", display_name: "最新项目发布时间", data_type: "datetime", width: "170" },
  { field_key: "related_projects", display_name: "相关项目", data_type: "text", width: "220" },
]);

async function appendDynamicColumns() {
  try {
    const res: any = await api.get("/dynamic/person/form-config?mode=view");
    const dynFields = (res.fields || []).filter((f: any) => f.is_list_visible !== false);
    const existingKeys = new Set(columns.value.map((c: any) => c.field_key));
    for (const df of dynFields) {
      if (!existingKeys.has(df.field_key)) {
        columns.value.push({
          field_key: df.field_key,
          display_name: df.display_name,
          data_type: df.data_type,
          width: df.data_type === "relation" ? "160" : undefined,
          sortable: df.data_type === "money" || df.data_type === "number",
          options: df.options,
          option_set_code: df.option_set_code || "",
        });
      }
    }
  } catch { /* ignore */ }
}

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
    const res: any = await api.get("/persons", { params: { page: page.value, page_size: pageSize.value, keyword: keyword.value, sort_field: sortField.value || undefined, sort_order: sortOrder.value, filters: Object.keys(filters.value).length ? JSON.stringify(filters.value) : undefined } });
    list.value = res.items || [];
    total.value = res.total || 0;
    await appendDynamicColumns();
  } catch { list.value = []; }
  finally { loading.value = false; }
}

async function doAdd() {
  if (!form.value.code || !form.value.name) { ElMessage.warning("编码和姓名必填"); return; }
  saving.value = true;
  try {
    await api.post("/persons", form.value);
    ElMessage.success("人员已添加");
    showAdd.value = false;
    form.value = { code: "", name: "", email: "", phone: "", position: "", company_id: null, status: "active" };
    loadData();
  } catch { }
  finally { saving.value = false; }
}

function handleSearch(kw: string) { keyword.value = kw; page.value = 1; loadData(); }
function handlePage(params: { page: number; pageSize: number }) { page.value = params.page; pageSize.value = params.pageSize; loadData(); }

async function removePerson(row: any) {
  await ElMessageBox.confirm(`确认删除人员「${row.name}」？此操作会同步移除图谱节点。`, "删除人员", { type: "warning" });
  try {
    await api.delete(`/persons/${row.id}`);
    ElMessage.success("已删除");
    loadData();
  } catch { /* 拦截器处理 */ }
}
onMounted(loadData);
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
