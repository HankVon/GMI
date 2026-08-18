<template>
  <div class="list-page">
    <div class="page-head">
      <h2 class="page-title">项目管理</h2>
      <div class="head-actions">
        <el-button type="primary" @click="openCreate">
          <el-icon style="margin-right: 4px"><Plus /></el-icon>新增项目
        </el-button>
      </div>
    </div>

    <!-- 新增项目对话框(完整字段, 参照精铸项目) -->
    <el-dialog v-model="showCreate" title="新增项目" width="700px" top="8vh" :close-on-click-modal="false">
      <el-form :model="createForm" label-width="110px" ref="createFormRef" :rules="createRules">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目名称" prop="name">
              <el-input v-model="createForm.name" placeholder="如：XX县XX镇地质灾害防治项目" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目编码">
              <el-input v-model="createForm.code" placeholder="留空自动生成(PRJ-时间戳)" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="createForm.status" style="width: 100%">
                <el-option label="进行中" value="active" />
                <el-option label="挂起" value="suspended" />
                <el-option label="已完成" value="completed" />
                <el-option label="已取消" value="cancelled" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-select v-model="createForm.manager_id" filterable clearable placeholder="选择项目负责人" style="width: 100%">
                <el-option v-for="p in personOptions" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启动日期">
              <el-date-picker v-model="createForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计结束">
              <el-date-picker v-model="createForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="地域">
              <RegionCascader v-model="createRegionVal" width="100%" @change="onCreateRegionChange" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <DynamicForm ref="createDynamicRef" entity-type="project" v-model="createFormDynamic" mode="edit" />
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">创建项目</el-button>
      </template>
    </el-dialog>

    <DynamicTable
      entity-type="projects"
      :data="list"
      :columns="columns"
      :loading="loading"
      :total="total"
      :can-export="true"
      :can-import="true"
      :keyword="keyword"
      @search="handleSearch"
      @sort-change="handleSort"
      @row-click="(row: any) => $router.push(`/workspace/projects/${row.id}`)"
      @page-change="handlePage"
    >
    <template #toolbar-extra>
      <!-- 融合筛选栏: 类别 / 阶段 / 地域 / 时间窗 (关键词搜索用右侧统一搜索框) -->
      <el-select v-model="categoryFilter" placeholder="项目类别" clearable style="width: 150px" @change="handleCategoryChange">
        <el-option v-for="c in categoryOptions" :key="c.value" :label="c.label" :value="c.value" />
      </el-select>
      <el-select v-model="stageFilter" placeholder="项目阶段" clearable style="width: 150px" @change="handleCategoryChange">
        <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <RegionCascader v-model="regionVal" width="170px" @change="onRegionChange" />
      <el-select v-model="daysFilter" style="width: 120px" @change="handleCategoryChange">
        <el-option label="近30天" :value="30" />
        <el-option label="近90天" :value="90" />
        <el-option label="近一年" :value="365" />
        <el-option label="全部" :value="0" />
      </el-select>
      <el-divider direction="vertical" />
      <el-button text type="primary" size="small" @click="resetFilters">
        <el-icon style="margin-right: 4px"><RefreshLeft /></el-icon>重置
      </el-button>
    </template>

    <!-- 真实项目 Excel 导入对话框 -->
    <el-dialog v-model="showImport" title="导入真实项目" width="620px" top="8vh">
      <el-alert
        type="info" :closable="false" style="margin-bottom: 14px"
        title="上传「真实项目」Excel，系统将自动创建/复用公司、人员、项目并建立关联（含 Neo4j 知识图谱）。已存在的数据自动复用，可重复导入。"
      />
      <el-upload
        drag
        :auto-upload="false"
        accept=".xlsx,.xls"
        :limit="1"
        :on-change="handleFileChange"
        :on-remove="() => (importFile = null)"
        style="margin-bottom: 14px"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 xlsx 文件拖到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">必需列：项目名称 / 法人单位 / 项目负责人 / 合同金额 / 甲方单位名称 / 业主联系人 等</div>
        </template>
      </el-upload>

      <template v-if="importResult">
        <el-divider content-position="left">导入结果</el-divider>
        <div class="import-result">
          <div class="import-summary">
            <el-tag type="success" size="large">{{ importResult.success ? "导入完成" : "失败" }}</el-tag>
            <span v-if="importResult.project_name" class="import-project-name">{{ importResult.project_name }}</span>
          </div>
          <div v-if="importResult.log?.length" class="import-log">
            <div v-for="(l, i) in importResult.log" :key="i" class="import-log-line">✓ {{ l }}</div>
          </div>
          <div v-if="importResult.errors?.length" class="import-errors">
            <div v-for="(e, i) in importResult.errors" :key="i" class="import-error-line">✗ {{ e }}</div>
          </div>
        </div>
      </template>

      <template #footer>
        <el-button @click="showImport = false">关闭</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="doImport">
          {{ importing ? "导入中..." : "开始导入" }}
        </el-button>
      </template>
    </el-dialog>
    <template #actions="{ row }">
      <el-popconfirm title="确定删除？" @confirm="handleDelete(row.id)">
        <template #reference>
          <el-button text type="danger" size="small" @click.stop>删除</el-button>
        </template>
      </el-popconfirm>
    </template>
    </DynamicTable>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Plus, Upload, UploadFilled, RefreshLeft } from "@element-plus/icons-vue";
import api from "@/api";
import DynamicTable from "@/components/DynamicTable.vue";
import RegionCascader from "@/components/RegionCascader.vue";
import DynamicForm from "@/components/DynamicForm.vue";

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

// ---------- 新增项目(完整字段, 参照精铸项目) ----------
const showCreate = ref(false);
const creating = ref(false);
const createFormRef = ref<any>(null);
const createDynamicRef = ref<any>(null);
const createForm = ref<any>({ name: "", code: "", status: "active", manager_id: null, start_date: "", end_date: "", description: "" });
const createFormDynamic = ref<any>({ ext_attrs: {} });
const createRegionVal = ref<string[]>([]);
const personOptions = ref<any[]>([]);
const createRules = {
  name: [{ required: true, message: "项目名称为必填项", trigger: "blur" }],
};

function openCreate() {
  createForm.value = { name: "", code: "", status: "active", manager_id: null, start_date: "", end_date: "", description: "" };
  createFormDynamic.value = { ext_attrs: {} };
  createRegionVal.value = [];
  showCreate.value = true;
}

function onCreateRegionChange(v: { province: string; city: string; county: string }) {
  const ext = createFormDynamic.value.ext_attrs || {};
  if (v.province) ext.province = v.province; else delete ext.province;
  if (v.city) ext.city = v.city; else delete ext.city;
  if (v.county) ext.county = v.county; else delete ext.county;
  createFormDynamic.value = { ...createFormDynamic.value, ext_attrs: { ...ext } };
}

async function doCreate() {
  try {
    await createFormRef.value.validate();
  } catch { return; }
  if (createDynamicRef.value) {
    const ok = await createDynamicRef.value.validate();
    if (!ok) return;
  }
  creating.value = true;
  try {
    // 组装 ext_attrs: DynamicForm 顶层字段 + 地域
    let dynamic: Record<string, any> = { ...(createFormDynamic.value.ext_attrs || {}) };
    const builtin = ["code","name","description","status","manager_id","ext_attrs","id","created_at","updated_at","is_deleted","start_date","end_date"];
    for (const [k, v] of Object.entries(createFormDynamic.value)) {
      if (!builtin.includes(k) && v !== undefined && v !== null && v !== "") dynamic[k] = v;
    }
    const code = createForm.value.code?.trim() || `PRJ-${Date.now()}`;
    const res: any = await api.post("/projects", {
      code,
      name: createForm.value.name,
      description: createForm.value.description || undefined,
      status: createForm.value.status,
      manager_id: createForm.value.manager_id || null,
      start_date: createForm.value.start_date || null,
      end_date: createForm.value.end_date || null,
      ext_attrs: Object.keys(dynamic).length ? dynamic : undefined,
    });
    ElMessage.success(`项目已创建 (ID ${res.id})`);
    showCreate.value = false;
    handlePage({ page: 1, pageSize: pageSize.value });
  } catch { /* 拦截器处理 */ }
  finally { creating.value = false; }
}

async function loadPersons() {
  try {
    const res: any = await api.get("/persons", { params: { page: 1, page_size: 200 } });
    personOptions.value = (res.items || []).map((p: any) => ({ id: p.id, name: p.name }));
  } catch { personOptions.value = []; }
}

// ---------- 真实项目 Excel 导入 ----------
const showImport = ref(false);
const importing = ref(false);
const importFile = ref<File | null>(null);
const importResult = ref<any>(null);

function handleFileChange(file: any) {
  importFile.value = file?.raw || null;
  importResult.value = null;
}

async function doImport() {
  if (!importFile.value) { ElMessage.warning("请先选择 Excel 文件"); return; }
  importing.value = true;
  importResult.value = null;
  const form = new FormData();
  form.append("file", importFile.value);
  try {
    const res: any = await api.post("/projects/import-real", form, {
      timeout: 300000,
      headers: { "Content-Type": "multipart/form-data" },
    });
    importResult.value = res;
    if (res?.success) {
      ElMessage.success("真实项目导入完成");
      handlePage({ page: 1, pageSize: pageSize.value });
    } else {
      ElMessage.error(res?.message || "导入失败");
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "导入失败");
  } finally {
    importing.value = false;
  }
}

// 列定义：固定列(顺序按用户要求) + 动态追加列(去重)
const columns = ref<any[]>([
  { field_key: "id", display_name: "ID", data_type: "text", width: "80", sortable: true },
  { field_key: "name", display_name: "项目名称", data_type: "text", width: "200", sortable: true },
  { field_key: "province_city", display_name: "省份城市", data_type: "text", width: "180" },
  { field_key: "last_progress_title", display_name: "项目阶段", data_type: "text", width: "180" },
  { field_key: "last_progress_date", display_name: "更新时间", data_type: "datetime", width: "160", sortable: true },
  { field_key: "amount", display_name: "总投资额", data_type: "money", width: "130", sortable: true },
]);

function handleSort(s: { prop: string; order: "ascending" | "descending" | null }) {
  // el-table 取消排序时 order 为 null → 回退默认(创建时间倒序)
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
    // 地域筛选: 省|市|县 拼成 filters.province_city
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

    // 从元数据追加动态列
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

// 类别下拉变化即触发查询
function handleCategoryChange() {
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
    await api.delete(`/projects/${id}`);
    ElMessage.success("已删除");
    loadData();
  } catch { /* handled by interceptor */ }
}

onMounted(() => { loadCategories(); loadStages(); loadPersons(); loadData(); });
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.page-title { margin: 0; font-size: 20px; color: #1f2d3d; }
.import-result .import-summary {
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.import-project-name { font-size: 14px; font-weight: 600; color: #303133; }
.import-log {
  background: #f0f9eb; border-radius: 6px; padding: 8px 12px; max-height: 180px;
  overflow-y: auto; font-size: 12px; color: #529b2e; line-height: 1.7;
}
.import-errors {
  background: #fef0f0; border-radius: 6px; padding: 8px 12px; margin-top: 8px;
  max-height: 120px; overflow-y: auto; font-size: 12px; color: #f56c6c; line-height: 1.7;
}
</style>
