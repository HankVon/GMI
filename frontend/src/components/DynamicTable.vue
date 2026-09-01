<!--
  ★ DynamicTable.vue ★
  动态表格组件 — 列定义由元数据驱动

  使用方式：
    <DynamicTable
      entity-type="project"
      :data="projectList"
      :loading="loading"
      @row-click="handleRowClick"
      @page-change="handlePage"
    />
-->
<template>
  <div class="dynamic-table">
    <!-- 工具栏：筛选 + 全局搜索 + 导出 -->
    <div class="table-toolbar">
      <div class="toolbar-filters">
        <!-- 页面自定义筛选区(如项目类别下拉) -->
        <slot name="toolbar-extra" />
        <el-input
          v-model="searchKeyword"
          placeholder="搜索..."
          clearable
          style="width: 280px"
          @keyup.enter="emit('search', searchKeyword)"
          @clear="emit('search', '')"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
      <div class="toolbar-actions">
        <el-button
          v-if="props.searchFields?.length"
          type="primary" size="small"
          :class="{ 'is-active': hasActiveFilters }"
          @click="toggleSearchPanel"
        >
          <el-icon><Filter /></el-icon>高级搜索
          <span v-if="activeFilterCount" class="filter-badge">{{ activeFilterCount }}</span>
        </el-button>
        <el-button
          v-if="canExport"
          type="primary" size="small"
          @click="handleExport"
        >
          <el-icon><Download /></el-icon>导出
        </el-button>
        <el-button
          v-if="canImport"
          type="primary" size="small"
          @click="triggerImport"
        >
          <el-icon><Upload /></el-icon>导入
        </el-button>
        <template v-if="selectable && selectedRows.length">
          <el-button type="danger" size="small" :loading="batchDeleting" @click="batchDelete">
            <el-icon><Delete /></el-icon>批量删除({{ selectedRows.length }})
          </el-button>
          <el-button
            v-if="canBatchDept"
            type="primary" size="small"
            @click="openBatchDept"
          >
            <el-icon><OfficeBuilding /></el-icon>批量改部门
          </el-button>
        </template>
      </div>
    </div>

    <!-- 高级搜索面板(可收起, 三字段同屏并列复选) -->
    <div v-show="searchPanelOpen" class="search-panel">
      <div class="sp-cols">
        <div
          v-for="fc in searchFields"
          :key="fc.field_key"
          class="sp-col"
        >
          <div class="sp-col-head">
            <span class="sp-col-title">{{ fc.display_name }}</span>
            <div class="sp-col-ops">
              <el-button link size="small" @click="selectFieldAll(fc)">全选</el-button>
              <el-button link size="small" @click="clearField(fc)">清空</el-button>
            </div>
          </div>
          <div class="sp-col-list">
            <template v-for="o in fc.options" :key="o.value">
              <div class="sp-opt sp-opt-prov">
                <el-checkbox
                  :model-value="isChecked(fc, o.value)"
                  @change="(v: any) => toggleFieldOpt(fc, o.value, !!v)"
                />
                <span class="sp-opt-label" :title="o.label">{{ o.label }}</span>
                <el-icon
                  v-if="o.children && o.children.length"
                  class="sp-expand"
                  @click="toggleExpand(fc, o.value)"
                >
                  <component :is="expandedProvs[fc.field_key + '|' + o.value] ? ArrowDown : ArrowRight" />
                </el-icon>
              </div>
              <div v-if="o.children && o.children.length && expandedProvs[fc.field_key + '|' + o.value]" class="sp-children">
                <label
                  v-for="c in o.children"
                  :key="c.value"
                  class="sp-opt sp-opt-city"
                >
                  <el-checkbox
                    :model-value="isChecked(fc, c.value)"
                    @change="(v: any) => toggleFieldOpt(fc, c.value, !!v)"
                  />
                  <span class="sp-opt-label" :title="c.label">{{ c.label }}</span>
                </label>
              </div>
            </template>
            <div v-if="!fc.options.length" class="sp-col-empty">暂无选项</div>
          </div>
        </div>
      </div>
      <div class="sp-actions">
        <span v-if="activeFilterCount" class="sp-count">
          已选 {{ activeFilterCount }} 项
        </span>
        <span class="sp-spacer" />
        <el-button size="small" @click="resetSearch">重置</el-button>
        <el-button size="small" type="primary" @click="applySearch">搜索</el-button>
      </div>
    </div>

    <!-- 表格 -->
    <el-table
      :data="data"
      v-loading="loading"
      stripe
      highlight-current-row
      @row-click="(row: any) => emit('rowClick', row)"
      @sort-change="(s: any) => emit('sortChange', s)"
      @selection-change="onSelectionChange"
      style="width: 100%"
      max-height="calc(100vh - 200px)"
    >
      <!-- 批量选择列 -->
      <el-table-column v-if="selectable" type="selection" width="42" fixed="left" />

      <!-- 内置列 -->
      <el-table-column
        v-for="col in visibleColumns"
        :key="col.field_key"
        :prop="col.field_key"
        :label="col.display_name"
        :width="col.width"
        :sortable="col.sortable ? 'custom' : false"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <!-- 状态字段：标签 -->
          <el-tag
            v-if="col.data_type === 'select' && col.options"
            :color="getOptionColor(col.options, getCellValue(row, col))"
            size="small"
            effect="dark"
          >
            {{ getOptionLabel(col.options, getCellValue(row, col)) || getCellValue(row, col) }}
          </el-tag>
          <!-- 开关 -->
          <el-switch
            v-else-if="col.data_type === 'switch'"
            :model-value="getCellValue(row, col)"
            disabled
            size="small"
          />
          <!-- 金额 -->
          <span v-else-if="col.data_type === 'money' && getCellValue(row, col)">
            {{ formatMoney(getCellValue(row, col)) }}
          </span>
          <!-- 日期 -->
          <span v-else-if="col.data_type === 'date'">
            {{ formatDate(getCellValue(row, col)) }}
          </span>
          <!-- 日期时间 -->
          <span v-else-if="col.data_type === 'datetime'">
            {{ formatDateTime(getCellValue(row, col)) }}
          </span>
          <!-- 链接列(名称/编码等主列) -->
          <span
            v-else-if="col.isLink"
            class="cell-link"
          >{{ getCellValue(row, col) ?? "-" }}</span>
          <!-- 默认文本 -->
          <span v-else class="cell-text">{{ getCellValue(row, col) ?? "-" }}</span>
        </template>
      </el-table-column>

      <!-- 操作列 -->
      <el-table-column v-if="hasActions" label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <!-- @click.stop 阻止操作按钮冒泡到行的 row-click(跳详情) -->
          <div class="table-actions" @click.stop>
            <slot name="actions" :row="row" />
          </div>
        </template>
      </el-table-column>

      <template #empty>
        <el-empty description="暂无数据" />
      </template>
    </el-table>

    <!-- 分页 -->
    <div class="table-pagination" v-if="total > 0">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @update:current-page="(p: number) => emit('pageChange', { page: p, pageSize })"
        @update:page-size="(s: number) => emit('pageChange', { page: currentPage, pageSize: s })"
      />
    </div>

    <!-- 隐藏的文件上传 -->
    <input
      ref="fileInput"
      type="file"
      accept=".xlsx,.xls"
      style="display: none"
      @change="handleFileUpload"
    />

    <!-- 批量改部门 -->
    <el-dialog v-model="batchDeptDialog" title="批量改部门" width="420px">
      <el-form label-width="80px">
        <el-form-item label="部门">
          <el-select v-model="batchDeptId" placeholder="选择目标部门" style="width: 100%" clearable>
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="import-stats">共选中 {{ selectedRows.length }} 条记录，将全部更新到所选部门。</div>
      <template #footer>
        <el-button @click="batchDeptDialog = false">取消</el-button>
        <el-button type="primary" :loading="batchDeptLoading" @click="submitBatchDept">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导入后台任务进度 -->
    <el-dialog
      v-model="importDialog"
      title="导入进度"
      width="560px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="importTask?.status !== 'running'"
    >
      <div v-if="importTask">
        <div class="import-stage">
          <span class="import-stage-text">{{ importTask.stage }}</span>
          <span v-if="importTask.status === 'running'" class="import-spin" />
        </div>
        <el-progress
          :percentage="importPercent"
          :status="importTask.status === 'failed' ? 'exception' : (importTask.status === 'done' ? 'success' : undefined)"
          :stroke-width="14"
        />
        <div class="import-stats">
          已新建 {{ importTask.imported }} · 更新 {{ importTask.updated }}
          · 跳过 {{ importTask.skipped }} · 失败 {{ importTask.failed }}
        </div>
        <div class="import-logs">
          <div v-for="(lg, i) in importTask.logs" :key="i" class="import-log-line">{{ lg }}</div>
          <div v-if="!importTask.logs.length" class="import-log-empty">准备中…</div>
        </div>
        <el-alert
          v-if="importTask.error"
          type="error"
          :title="importTask.error"
          :closable="false"
          style="margin-top: 8px"
        />
      </div>
      <template #footer>
        <el-button v-if="importTask?.status !== 'running'" @click="importDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Filter, Search, ArrowDown, ArrowUp, ArrowRight, Delete, OfficeBuilding } from "@element-plus/icons-vue";
import dayjs from "dayjs";
import * as XLSX from "xlsx";
import api from "@/api";
import { CHINA_REGIONS } from "@/utils/china-regions";

interface ColumnMeta {
  field_key: string;
  display_name: string;
  data_type?: string;
  width?: string;
  sortable?: boolean;
  options?: Array<{ value: string; label: string; color?: string }>;
  isLink?: boolean;
}

interface SearchFieldDef {
  field_key: string;
  display_name: string;
  option_set_code?: string;
}

const props = defineProps<{
  entityType: string;
  data: any[];
  columns: ColumnMeta[];
  loading?: boolean;
  total?: number;
  canExport?: boolean;
  canImport?: boolean;
  /** 当前生效的筛选条件(用于回显与角标), 由父组件维护 */
  filters?: Record<string, string[]>;
  /** 高级搜索面板展示的字段(三组并列复选); 不传则隐藏高级搜索按钮 */
  searchFields?: SearchFieldDef[];
  /** 外部控制的关键词(如重置时清空搜索框); 传入时内部搜索框同步该值 */
  keyword?: string;
  /** 是否显示操作列(默认 true; 前台展示模式可传 false 隐藏整个操作列) */
  showActions?: boolean;
  /** 是否启用批量选择与批量操作(默认 false) */
  selectable?: boolean;
  /** 是否显示「批量改部门」(仅 person/project 等有部门列的实体开启) */
  canBatchDept?: boolean;
}>();

const emit = defineEmits<{
  (e: "search", keyword: string): void;
  (e: "rowClick", row: any): void;
  (e: "pageChange", params: { page: number; pageSize: number }): void;
  (e: "sortChange", sort: { prop: string; order: "ascending" | "descending" | null }): void;
  (e: "export"): void;
  (e: "filterChange", filters: Record<string, string[]>): void;
}>();

/* ─────────── 高级搜索(内嵌可收起, 三字段同屏并列复选) ─────────── */
const searchPanelOpen = ref(false);
const draftFilters = ref<Record<string, string[]>>({});

interface FilterOpt { value: string; label: string }

// 面板字段: 由父组件 searchFields 指定; 选项集字段异步从后端拉完整选项,
// 内置省列表字段用全国行政区, 其余从列表数据去重
const searchFields = ref<any[]>([]);

function buildSearchFields() {
  const defs = props.searchFields || [];
  searchFields.value = defs.map((def) => {
    // 内置省市区: 全国两级行政区(省 -> 市), 直辖市/经济特区无下辖市
    if (def.option_set_code === "__china_province__") {
      return {
        ...def,
        options: CHINA_REGIONS.map((r) => ({
          value: r.value,
          label: r.label,
          children: r.children
            ? r.children.map((c) => ({ value: c.value, label: c.label }))
            : undefined,
        })),
      };
    }
    // 其余先用列表数据去重占位, 选项集异步补齐
    return { ...def, options: resolveFieldOptions(def) };
  });
  // 异步拉取选项集字段的完整选项
  for (const def of defs) {
    if (def.option_set_code && def.option_set_code !== "__china_province__") {
      loadOptionSetOptions(def);
    }
  }
}

async function loadOptionSetOptions(def: SearchFieldDef) {
  try {
    const res: any = await api.get(`/option-sets/${def.option_set_code}/items`);
    const items: any[] = res?.items || [];
    const opts = items.map((o) => ({
      value: String(o.value ?? o.label ?? ""),
      label: String(o.label ?? o.value ?? ""),
    }));
    const target = searchFields.value.find((f) => f.field_key === def.field_key);
    if (target) target.options = opts;
  } catch { /* 选项集不可用时保留列表数据去重选项 */ }
}

// 解析字段选项: 优先在可见列里找预置 options, 否则从列表数据去重
function resolveFieldOptions(def: SearchFieldDef): FilterOpt[] {
  const col = visibleColumns.value.find((c) => c.field_key === def.field_key);
  if (col?.options?.length) {
    return col.options.map((o) => ({
      value: String(o.value ?? o.label ?? ""),
      label: String(o.label ?? o.value ?? ""),
    }));
  }
  const seen = new Map<string, string>();
  for (const row of props.data) {
    const v = getCellValue(row, { field_key: def.field_key } as ColumnMeta);
    if (v === null || v === undefined || v === "") continue;
    const arr = Array.isArray(v) ? v : [v];
    for (const x of arr) {
      if (x === null || x === undefined || x === "") continue;
      const s = String(x);
      if (!seen.has(s)) seen.set(s, s);
    }
  }
  return [...seen.entries()].map(([value, label]) => ({ value, label }));
}

const activeFilters = computed<Record<string, string[]>>(() => props.filters || {});
const activeFilterCount = computed(() =>
  Object.values(activeFilters.value).reduce((n, arr) => n + (arr?.length || 0), 0)
);
const hasActiveFilters = computed(() => activeFilterCount.value > 0);

function isChecked(fc: any, value: string): boolean {
  return (draftFilters.value[fc.field_key] || []).includes(value);
}

function toggleFieldOpt(fc: any, value: string, checked: boolean) {
  const cur = draftFilters.value[fc.field_key] || [];
  draftFilters.value[fc.field_key] = checked
    ? [...cur, value]
    : cur.filter((x) => x !== value);
}

function selectFieldAll(fc: any) {
  // 仅勾选省级(省值已通过后端前缀匹配覆盖其下所有市), 避免与市级冗余
  draftFilters.value[fc.field_key] = fc.options.map((o: FilterOpt) => o.value);
}

function clearField(fc: any) {
  draftFilters.value[fc.field_key] = [];
}

// 省 -> 市 展开状态(按 字段|省值 记录)
const expandedProvs = ref<Record<string, boolean>>({});
function toggleExpand(fc: any, provValue: string) {
  const key = fc.field_key + "|" + provValue;
  expandedProvs.value[key] = !expandedProvs.value[key];
}

function toggleSearchPanel() {
  searchPanelOpen.value = !searchPanelOpen.value;
  if (searchPanelOpen.value) {
    draftFilters.value = JSON.parse(JSON.stringify(activeFilters.value));
  }
}

function applySearch() {
  const out: Record<string, string[]> = {};
  for (const f of searchFields.value) {
    const arr = draftFilters.value[f.field_key] || [];
    if (arr.length) out[f.field_key] = arr.map(String);
  }
  emit("filterChange", out);
}

function resetSearch() {
  draftFilters.value = {};
  emit("filterChange", {});
}

const searchKeyword = ref("");
// 外部 keyword 变化(如重置)时同步内部搜索框
watch(
  () => props.keyword,
  (v) => { searchKeyword.value = v || ""; },
  { immediate: true }
);
const currentPage = ref(1);
const pageSize = ref(20);
const fileInput = ref<HTMLInputElement>();

// 选项集选项缓存: option_set_code -> [{value,label,color}]
const optionSetCache = new Map<string, any[]>();

// 名称/编码类主列自动标记为链接样式，增强可点击提示
// 必须在使用它的 watch/函数之前声明，避免 setup 期 TDZ 报错
const visibleColumns = computed(() =>
  props.columns.map((c) => {
    // select 字段: 从选项集缓存补充 options(含 color), 保证列表标签颜色与选项集管理一致
    let options = c.options;
    if (c.option_set_code && optionSetCache.has(c.option_set_code)) {
      options = optionSetCache.get(c.option_set_code) || [];
    }
    return {
      ...c,
      options,
      isLink: c.isLink ?? /^(name|code|title|keyword)$|名称|姓名|编码/.test(c.field_key + c.display_name),
    };
  })
);

// 加载列引用的选项集(含 color), 使 select 列渲染彩色标签
async function loadColumnOptionSets() {
  const codes = new Set<string>();
  props.columns.forEach((c: any) => {
    if (c.option_set_code && c.option_set_code !== "__china_province__") codes.add(c.option_set_code);
  });
  (props.searchFields || []).forEach((f: any) => {
    if (f.option_set_code && f.option_set_code !== "__china_province__") codes.add(f.option_set_code);
  });
  for (const code of codes) {
    try {
      const res: any = await api.get(`/option-sets/${code}/items`);
      const items: any[] = res?.items || [];
      optionSetCache.set(code, items.map((o) => ({
        value: String(o.value ?? o.label ?? ""),
        label: String(o.label ?? o.value ?? ""),
        color: o.color || "",
      })));
    } catch { /* 忽略不可用的选项集 */ }
  }
}
const hasActions = computed(() => props.showActions !== false && !!useSlots().actions);

// 动态列加载完成后重建筛选字段(visibleColumns 变化), 配置变化也重建
// visibleColumns 已在本块上方声明, 此处访问不再 TDZ; immediate:false 避免 setup 期立即求值
watch(
  () => [props.searchFields, visibleColumns.value] as const,
  () => buildSearchFields(),
  { deep: true, immediate: false }
);
onMounted(() => { buildSearchFields(); loadColumnOptionSets(); });
onUnmounted(() => stopImportPoll());

function getOptionLabel(options: any[], val: any): string {
  // val 可能是枚举值或中文标签(取决于 getCellValue 是否已转换)
  const found = options.find((o) => o.value === val) || options.find((o) => o.label === val);
  return found?.label || "";
}

function getOptionColor(options: any[], val: any): string {
  // val 可能是枚举值或中文标签(取决于 getCellValue 是否已转换)
  const found = options.find((o) => o.value === val) || options.find((o) => o.label === val);
  return found?.color || "";
}

// 取单元格值：先取 row[key]，再回退 row.ext_attrs[key]
function getCellValue(row: any, col: any): any {
  let v = row[col.field_key];
  if (v === undefined) v = row.ext_attrs?.[col.field_key];
  // select / multi_select 字段: 值 → 中文标签(选项集配置)
  if ((col.data_type === "select" || col.data_type === "multi_select")
    && col.options?.length && v != null && v !== "") {
    const map: Record<string, string> = {};
    for (const o of col.options) map[String(o.value ?? o.label ?? "")] = String(o.label ?? o.value ?? "");
    if (Array.isArray(v)) v = v.map((x) => map[x] ?? x).join("、");
    else v = map[v] ?? v;
  }
  return v;
}

function formatMoney(val: number): string {
  return "¥" + Number(val).toLocaleString("zh-CN", { minimumFractionDigits: 2 });
}

function formatDate(val: string): string {
  return val ? dayjs(val).format("YYYY-MM-DD") : "-";
}

function formatDateTime(val: string): string {
  return val ? dayjs(val).format("YYYY-MM-DD HH:mm:ss") : "-";
}

async function handleExport() {
  const token = localStorage.getItem("ssm_token");
  try {
    const resp = await fetch(`/api/v1/excel/export/${apiPath(props.entityType)}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) throw new Error("export failed");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${props.entityType}_${dayjs().format("YYYYMMDDHHmmss")}.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
  } catch {
    ElMessage.error("导出失败");
  }
}

function triggerImport() {
  fileInput.value?.click();
}

/* ─────────── 导入后台任务(大文件: 提交后轮询进度) ─────────── */
const importDialog = ref(false);
const importTask = ref<any>(null);
let importPollTimer: any = null;

const importPercent = computed(() => {
  const t = importTask.value;
  if (!t) return 0;
  if (t.status === "done" || t.status === "failed") return 100;
  // running: 按日志条数估算(最多 95, 留 5% 给收尾)
  const logs = t.logs?.length || 0;
  return Math.min(95, Math.max(5, logs));
});

function refreshAfterImport() {
  emit("pageChange", { page: currentPage, pageSize: pageSize });
}

/* ─────────── 批量操作(批量删除 / 批量改部门) ─────────── */
/** entityType → 删除/更新 API 路径(部分实体列表 entityType 与接口路径不一致) */
function apiPath(et: string): string {
  return ({ company: "companies", web_clue: "web-clues" } as Record<string, string>)[et] || et;
}

const selectedRows = ref<any[]>([]);
const batchDeleting = ref(false);
const batchDeptDialog = ref(false);
const batchDeptLoading = ref(false);
const batchDeptId = ref<number | null>(null);
const departments = ref<any[]>([]);

function onSelectionChange(rows: any[]) {
  selectedRows.value = rows;
}

async function batchDelete() {
  const rows = selectedRows.value;
  if (!rows.length) return;
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${rows.length} 条记录? 此操作不可恢复。`,
      "批量删除",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch { return; }
  batchDeleting.value = true;
  let ok = 0, fail = 0;
  for (const row of rows) {
    try {
      await api.delete(`/${apiPath(props.entityType)}/${row.id}`);
      ok++;
    } catch { fail++; }
  }
  batchDeleting.value = false;
  ElMessage.success(`批量删除完成: 成功 ${ok} 条, 失败 ${fail} 条`);
  refreshAfterImport();
}

async function openBatchDept() {
  if (!departments.value.length) {
    try {
      const res: any = await api.get("/rbac/departments");
      departments.value = res?.data || [];
    } catch { /* 部门加载失败不阻塞 */ }
  }
  batchDeptId.value = null;
  batchDeptDialog.value = true;
}

async function submitBatchDept() {
  if (!batchDeptId.value) return ElMessage.warning("请选择目标部门");
  const rows = selectedRows.value;
  batchDeptLoading.value = true;
  let ok = 0, fail = 0;
  for (const row of rows) {
    try {
      await api.put(`/${apiPath(props.entityType)}/${row.id}`, { department_id: batchDeptId.value });
      ok++;
    } catch { fail++; }
  }
  batchDeptLoading.value = false;
  batchDeptDialog.value = false;
  ElMessage.success(`批量改部门完成: 成功 ${ok} 条, 失败 ${fail} 条`);
  refreshAfterImport();
}

function stopImportPoll() {
  if (importPollTimer) {
    clearInterval(importPollTimer);
    importPollTimer = null;
  }
}

async function pollImportTask(taskId: string) {
  stopImportPoll();
  const tick = async () => {
    try {
      const res: any = await api.get(`/excel/import/task/${taskId}`);
      const t = res?.data;
      if (!t) return;
      importTask.value = t;
      if (t.status === "done") {
        stopImportPoll();
        const d = t.result || {};
        ElMessage.success(d?.message || "导入完成");
        refreshAfterImport();
      } else if (t.status === "failed") {
        stopImportPoll();
        ElMessage.error(t.error || "导入失败");
      }
    } catch {
      stopImportPoll();
      ElMessage.error("获取导入进度失败");
    }
  };
  await tick();
  if (importTask.value?.status === "running") {
    importPollTimer = setInterval(tick, 1500);
  }
}

async function handleFileUpload(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  try {
    const formData = new FormData();
    formData.append("file", file);
    // 项目走「真实项目完整导入」、人员走「真实人员花名册导入(按姓名复用)」, 其他实体走标准 excel 导入
    const isSpecial = props.entityType === "projects" || props.entityType === "persons";
    const url = isSpecial
      ? `/${props.entityType}/import-real`
      : `/excel/import/${apiPath(props.entityType)}`;

    // 项目导入: 让用户选择「快速导入(跳过 AI 补全)」或「深度补全(慢)」
    if (isSpecial && props.entityType === "projects") {
      try {
        await ElMessageBox.confirm(
          "选择导入模式：\n\n「快速导入」跳过 AI 分类与单位信息补全，只入库源数据并建图谱（大文件推荐，快）。\n「深度补全」会逐单位调用 AI/企查查补全法人/电话/地址（慢）。",
          "项目导入模式",
          { confirmButtonText: "快速导入", cancelButtonText: "深度补全", type: "info" }
        );
        formData.append("deep_enrich", "false");
      } catch {
        formData.append("deep_enrich", "true");
      }
    }
    const res: any = await api.post(url, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    // 后台任务: 打开进度弹窗并轮询
    if (res?.task_id) {
      importTask.value = {
        status: "running", stage: "已提交, 等待后台解析…",
        imported: 0, updated: 0, skipped: 0, failed: 0, logs: [],
      };
      importDialog.value = true;
      pollImportTask(res.task_id);
      return;
    }
    // 通用同步导入(companies 等)
    const d = (res && res.data) ? res.data : res;
    const msg = `导入完成: 成功 ${d.imported || 0} 条, 失败 ${d.failed || 0} 条`;
    ElMessage.success(msg);
    refreshAfterImport();
  } catch {
    ElMessage.error("导入失败");
  } finally {
    input.value = "";
  }
}

import { useSlots } from "vue";
</script>

<style scoped>
/* 导入进度弹窗 */
.import-stage {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 13.5px;
  color: var(--ssm-text-main, #1f2d3d);
  font-weight: 500;
}
.import-spin {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(165, 28, 48, 0.18);
  border-top-color: #a51c30;
  animation: import-rotate 0.8s linear infinite;
}
@keyframes import-rotate {
  to { transform: rotate(360deg); }
}
.import-stats {
  margin: 8px 0;
  font-size: 12.5px;
  color: #606266;
}
.import-logs {
  max-height: 220px;
  overflow-y: auto;
  background: #f7f9fc;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  padding: 8px 10px;
  margin-top: 6px;
}
.import-log-line {
  font-size: 12px;
  line-height: 1.7;
  color: #4a5568;
  word-break: break-all;
}
.import-log-empty {
  font-size: 12px;
  color: #a0a8b8;
  text-align: center;
  padding: 12px 0;
}
.dynamic-table {
  background: #fff;
  border: 1px solid var(--ssm-border, #e9edf6);
  border-radius: 12px;
  box-shadow: var(--ssm-shadow, 0 2px 12px rgba(30, 60, 114, 0.06));
  overflow: hidden;
}
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f7;
  background: linear-gradient(90deg, #fbfcff 0%, #fff 100%);
}
.toolbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.toolbar-actions .is-active {
  background: var(--ssm-primary-dark, #1d63e0);
  border-color: var(--ssm-primary-dark, #1d63e0);
  color: #fff;
  font-weight: 600;
}
.filter-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 8px;
  background: #f56c6c;
  color: #fff;
  font-size: 11px;
  line-height: 16px;
}
/* ── 高级搜索面板(可收起, 三字段并列复选) ── */
.search-panel {
  padding: 14px 16px 10px;
  border-bottom: 1px solid #eef1f7;
  background: linear-gradient(180deg, #f2f7ff, #fbfdff);
}
.sp-cols {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.sp-col {
  border: 1px solid #e9edf6;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 180px;
  box-shadow: 0 1px 3px rgba(30, 60, 114, 0.04);
}
.sp-col-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f4f8ff;
  border-bottom: 1px solid #e9edf6;
}
.sp-col-title {
  font-size: 13.5px;
  font-weight: 600;
  color: #1f2d3d;
}
.sp-col-ops {
  display: flex;
  gap: 2px;
}
.sp-col-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 8px;
  max-height: 220px;
}
.sp-opt {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
  font-size: 13px;
  color: #4b5264;
}
.sp-opt-prov {
  font-weight: 500;
}
.sp-opt-city {
  padding-left: 22px;
  color: #6b7280;
}
.sp-expand {
  margin-left: auto;
  color: #909399;
  cursor: pointer;
  transition: color 0.15s ease, transform 0.15s ease;
}
.sp-expand:hover {
  color: #2979ff;
}
.sp-children {
  display: block;
}
.sp-opt:hover {
  background: #eef2ff;
}
.sp-opt-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sp-col-empty {
  color: #c0c4cc;
  font-size: 12.5px;
  text-align: center;
  padding: 24px 0;
}
.sp-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #e6eaf2;
}
.sp-spacer {
  flex: 1;
}
.sp-count {
  font-size: 12.5px;
  color: #909399;
}
@media (max-width: 1100px) {
  .sp-cols { grid-template-columns: 1fr; }
}

.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;  /* 防止子项溢出撑大容器 */
}
.table-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 14px 16px;
  border-top: 1px solid #f0f2f8;
  background: #fbfcff;
}

/* ── 行点击视觉增强 ── */
:deep(.el-table__row) {
  cursor: pointer;
  transition: background-color 0.2s ease;
}
:deep(.el-table__row td) {
  transition: background-color 0.2s ease;
}
/* 行 hover: 浅蓝渐变背景 + 左侧主色竖条 */
:deep(.el-table__row:hover > td.el-table__cell) {
  background-color: #eef5ff !important;
}
:deep(.el-table__row:hover td.el-table__cell:first-child) {
  box-shadow: inset 3px 0 0 #2979ff;
}
/* 当前选中行: 更深一层浅蓝 */
:deep(.el-table__row.current-row > td.el-table__cell) {
  background-color: #dbeafe !important;
}
:deep(.el-table__row.current-row td.el-table__cell:first-child) {
  box-shadow: inset 3px 0 0 #2979ff;
}
/* 主列(名称/编码)链接样式 */
.cell-link {
  color: #2979ff;
  font-weight: 500;
  transition: color 0.2s ease;
}
:deep(.el-table__row:hover) .cell-link {
  color: #1d6fe0;
  text-decoration: underline;
  text-underline-offset: 3px;
}
/* 普通文本 hover 变主色, 提示可点击 */
.cell-text {
  color: #303133;
  transition: color 0.2s ease;
}
:deep(.el-table__row:hover) .cell-text {
  color: #2979ff;
}
</style>
