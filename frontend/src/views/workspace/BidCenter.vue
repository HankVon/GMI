<template>
  <div class="bid-center-page">
    <!-- 顶部 Tab 行：全部标讯 / 我的订阅 -->
    <div class="bc-top">
      <div class="bc-top-inner">
        <el-tabs v-model="savedView" class="bc-main-tabs" @tab-change="onViewChange">
          <el-tab-pane label="全部标讯" name="all" />
          <el-tab-pane label="我的订阅" name="subscriptions" />
        </el-tabs>
        <div class="bc-total-meta">
          搜索到 <b>{{ loading ? '...' : formatNum(total) }}</b> 条信息
          <span v-if="savedView === 'all' && appliedSub" class="bc-applied-sub">
            <el-icon><BellFilled /></el-icon>订阅：{{ appliedSub.name }}
            <el-icon class="bc-clear" @click="clearSub"><Close /></el-icon>
          </span>
        </div>
      </div>
    </div>

    <!-- 主体两列：左侧筛选 / 右侧列表 -->
    <div class="bc-body">
      <!-- 左：筛选面板（移动端可折叠） -->
      <FilterSidebar
        :model="filterModel"
        :exporting="exporting"
        @update="onSidebarUpdate"
        @subscribe="subDialogVisible = true"
        @export="exportCsv"
      />

      <!-- 右：查询区 + 列表 + 分页 -->
      <section class="bc-main">
        <!-- 快捷查询区(对标图片右侧查询区) -->
        <div class="bc-query">
          <div class="bc-query-row">
            <el-input v-model="query.keyword" class="bc-qi" placeholder="请输入标题关键词检索" clearable size="default" @keyup.enter="load(1)">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-input v-model="query.purchaser_keyword" class="bc-qi" placeholder="请输入招标单位关键词" clearable size="default" @keyup.enter="load(1)">
              <template #prefix><el-icon><OfficeBuilding /></el-icon></template>
            </el-input>
            <el-input v-model="query.supplier_keyword" class="bc-qi" placeholder="请输入中标单位关键词" clearable size="default" @keyup.enter="load(1)">
              <template #prefix><el-icon><Avatar /></el-icon></template>
            </el-input>
          </div>
          <div class="bc-query-row">
            <el-input v-model="query.title_extra" class="bc-qi bc-qi-wide" placeholder="标题关键词" clearable @keyup.enter="load(1)" />
            <div class="bc-query-actions">
              <el-switch
                v-model="query.only_matched"
                class="bc-only-matched"
                inline-prompt
                active-text="已关联"
                inactive-text="全部"
                @change="load(1)"
              />
              <el-button class="bc-btn-ghost" :loading="savingFilter" @click="openStoreSave">
                <el-icon><FolderAdd /></el-icon>保存筛选条件
              </el-button>
              <el-button class="bc-btn-ghost" @click="resetAll">
                <el-icon><RefreshLeft /></el-icon>重置
              </el-button>
              <el-button class="bc-btn-primary" type="primary" :loading="loading" @click="load(1)">
                <el-icon><Search /></el-icon>筛 选
              </el-button>
            </div>
          </div>
        </div>

        <!-- 已选条件 tag 回显 -->
        <div v-if="hasActiveFilter" class="bc-active-tags">
          <span class="bc-active-label">已选：</span>
          <el-tag v-if="query.keyword" closable size="small" type="info" @close="clearField('keyword')">关键词：{{ query.keyword }}</el-tag>
          <el-tag v-if="query.purchaser_keyword" closable size="small" type="info" @close="clearField('purchaser_keyword')">采购人：{{ query.purchaser_keyword }}</el-tag>
          <el-tag v-if="query.supplier_keyword" closable size="small" type="info" @close="clearField('supplier_keyword')">供应商：{{ query.supplier_keyword }}</el-tag>
          <el-tag v-if="filterModel.province" closable size="small" type="info" @close="clearSidebar('province')">地区：{{ filterModel.province }}</el-tag>
          <el-tag v-if="filterModel.category" closable size="small" type="info" @close="clearSidebar('category')">分类：{{ filterModel.category }}</el-tag>
          <el-tag v-if="filterModel.industry" closable size="small" type="info" @close="clearSidebar('industry')">行业：{{ filterModel.industry }}</el-tag>
          <el-tag v-if="filterModel.purchaseWay" closable size="small" type="info" @close="clearSidebar('purchaseWay')">采购方式：{{ filterModel.purchaseWay }}</el-tag>
          <el-tag v-if="filterModel.noticeType" closable size="small" type="info" @close="clearSidebar('noticeType')">公告：{{ filterModel.noticeType }}</el-tag>
          <el-tag v-if="filterModel.stage" closable size="small" type="info" @close="clearStage">阶段：{{ stageLabel(filterModel.stage) }}</el-tag>
          <el-tag v-if="filterModel.dateRange" closable size="small" type="info" @close="clearDate">时间：{{ filterModel.dateRange[0] }} ~ {{ filterModel.dateRange[1] }}</el-tag>
          <el-tag v-if="filterModel.amountMin || filterModel.amountMax" closable size="small" type="info" @close="clearAmount">金额：{{ filterModel.amountMin || 0 }}~{{ filterModel.amountMax || '∞' }} 万</el-tag>
          <el-tag v-if="query.only_matched" closable size="small" type="info" @close="query.only_matched = false; load(1)">已关联单位</el-tag>
        </div>

        <!-- 列表（包含两种视图）-->
        <div v-loading="loading" class="bc-list" :class="{ 'is-empty': !items.length && savedView === 'all' }">
          <!-- 全部标讯列表 -->
          <template v-if="savedView === 'all'">
            <div v-if="items.length" class="bc-card-list">
              <div v-for="(b, idx) in items" :key="b.id" class="bc-card" :class="{ selected: selectedIds.includes(String(b.id)) }">
                <el-checkbox :model-value="selectedIds.includes(String(b.id))" class="bc-row-check" @change="toggleRow(b.id, $event)">
                  <span class="sr-only">选择</span>
                </el-checkbox>
                <span class="bc-row-index">{{ (page - 1) * pageSize + idx + 1 }}</span>
                <div class="bc-card-main">
                  <div class="bc-card-top">
                    <TagGroup :tags="bidTags(b)" />
                    <span class="bc-card-date">
                      <el-icon><Clock /></el-icon>{{ b.published_at }}
                    </span>
                  </div>
                  <router-link :to="navTo(`/bids/${b.id}`)" target="_blank" rel="noopener" class="bc-card-title">
                    {{ b.title }}
                  </router-link>
                  <div class="bc-card-meta">
                    <span v-if="firstAmount(b) > 0" class="bc-meta-amount">
                      <span class="bc-amount-icon">¥</span>{{ fmtAmount(Number(firstAmount(b) || 0)) }}
                    </span>
                    <span class="bc-meta-item">
                      <span class="bc-meta-label">招标单位：</span>
                      <a v-if="b.purchaser_company_id" class="bc-company-link" @click.prevent="goCompany(b.purchaser_company_id)">
                        {{ b.purchaser || "未知业主" }}
                      </a>
                      <span v-else class="bc-company-text">{{ b.purchaser || "未知业主" }}</span>
                    </span>
                    <span v-if="b.region" class="bc-meta-item">
                      <span class="bc-meta-label">地区：</span>{{ b.region }}
                    </span>
                    <span class="bc-meta-item">
                      <span class="bc-meta-label">发布时间：</span>{{ b.published_at }}
                    </span>
                    <span v-if="b.suppliers?.length" class="bc-meta-item">
                      <el-icon><Connection /></el-icon>中标 <b>{{ b.suppliers.length }}</b> 家
                    </span>
                  </div>
                </div>
                <div class="bc-card-side">
                  <a class="bc-download-link" @click.prevent="navToNewTab(`/bids/${b.id}`)">
                    <el-icon><Download /></el-icon>下载招标公告
                  </a>
                  <span v-if="b.source_name" class="bc-source">{{ (b.source_name || '').split('-')[0] }}</span>
                </div>
              </div>
            </div>
            <div v-else class="bc-empty">
              <el-empty description="暂无标讯（可通过「数据流水线」导入或自动抓取）" :image-size="100" />
            </div>
          </template>

          <!-- 我的订阅视图 -->
          <div v-else class="bc-subscription-view">
            <div v-if="!savedFilters.length" class="bc-empty">
              <el-empty description="暂无保存的订阅，请先保存筛选条件" :image-size="100" />
            </div>
            <div v-else class="bc-saved-list">
              <button
                v-for="(s, index) in savedFilters"
                :key="`${s.name}-${index}`"
                class="bc-saved-item"
                @click="applySubscription(s)"
              >
                <strong class="bc-saved-name">{{ s.name }}</strong>
                <span class="bc-saved-summary">{{ subSummary(s) }}</span>
                <span class="bc-saved-time">{{ s.saved_at }}</span>
                <em class="bc-saved-action">打开订阅<el-icon><ArrowRight /></el-icon></em>
              </button>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="savedView === 'all' && total > pageSize" class="bc-pagination">
          <JumpPagination :total="total" :page="page" :page-size="pageSize" @change="load" />
        </div>
        <div v-else-if="savedView === 'all' && total > 0" class="bc-pagination-summary">
          共 <b>{{ total }}</b> 条信息，当前第 {{ page }} / {{ Math.max(1, Math.ceil(total / pageSize)) }} 页
        </div>
      </section>
    </div>

    <!-- 订阅弹窗 -->
    <el-dialog v-model="subDialogVisible" title="保存当前筛选为订阅" width="440px">
      <p class="bc-sub-tip">保存当前关键词 / 类型 / 地区 / 时间筛选条件，便于下次一键直达。</p>
      <el-input v-model="subName" placeholder="请输入订阅名称，如：四川地质类中标" maxlength="30" show-word-limit />
      <template #footer>
        <el-button @click="subDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!subName.trim()" @click="saveSubscription">保存订阅</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "BidCenter" });
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import {
  OfficeBuilding, Connection, Bell, BellFilled, Download,
  Close, Clock, Search, Avatar, FolderAdd, RefreshLeft, ArrowRight, InfoFilled,
} from "@element-plus/icons-vue";
import api from "@/api";
import { useNavBase } from "@/utils/navBase";
import FilterSidebar, { type FilterModel } from "@/components/bids/FilterSidebar.vue";
import TagGroup from "@/components/bids/TagGroup.vue";
import JumpPagination from "@/components/bids/JumpPagination.vue";
import { useBidFilterStore } from "@/stores/bidFilter";
import { ElMessageBox, ElMessage } from "element-plus";

const route = useRoute();
const { navTo, navToNewTab } = useNavBase();
const filterStore = useBidFilterStore();

/* ─────────── 视图状态 ─────────── */
const savedView = ref<'all' | 'subscriptions'>('all');
const loading = ref(false);
const exporting = ref(false);
const savingFilter = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;

/* 主查询条件（兼容旧 API：keyword / province / purchaser_keyword / supplier_keyword / only_matched） */
const query = reactive<{ keyword: string; province: string; purchaser_keyword: string; supplier_keyword: string; only_matched?: boolean; title_extra?: string }>({
  keyword: String(route.query.keyword || ""),
  province: String(route.query.province || ""),
  purchaser_keyword: "",
  supplier_keyword: "",
  title_extra: "",
  only_matched: false,
});

/* 侧栏筛选模型（前端组织：不会立即发请求，但命中后端兼容字段时会带过去） */
const filterModel = reactive<FilterModel>({
  province: "",
  category: "",
  industry: "",
  purchaseWay: "",
  noticeType: "",
  dateRange: null,
  amountMin: "",
  amountMax: "",
  priceType: "",
  stage: "",
});

/* 后端 notice_type 字段集合 + 后端可见 filter 字段映射(保留供扩展) */
const apiFilters = computed(() => ({
  province: filterModel.province || query.province,
  notice_type: filterModel.noticeType,
  date_from: filterModel.dateRange?.[0] || "",
  date_to: filterModel.dateRange?.[1] || "",
  only_matched: query.only_matched,
}));

/* 多选相关 */
const selectedIds = ref<string[]>([]);
const allSelected = computed(() => items.value.length > 0 && selectedIds.value.length === items.value.length);
const someSelected = computed(() => selectedIds.value.length > 0 && !allSelected.value);
function toggleAll(value: unknown) {
  selectedIds.value = value === true ? items.value.map((item) => String(item.id)) : [];
}
function toggleRow(id: number, value: unknown) {
  const key = String(id);
  if (value === true && !selectedIds.value.includes(key)) selectedIds.value.push(key);
  if (value !== true) selectedIds.value = selectedIds.value.filter((item) => item !== key);
}

/* ─────────── 订阅(本地保存筛选条件) ─────────── */
interface SavedFilter {
  name: string;
  keyword: string;
  province: string;
  notice_type: string;
  date_from: string;
  date_to: string;
  saved_at: string;
}
const SUB_KEY = "gmi_bid_subscriptions";
const savedFilters = ref<SavedFilter[]>([]);
const subDialogVisible = ref(false);
const subName = ref("");
const appliedSub = ref<SavedFilter | null>(null);

function loadSaved() {
  try {
    savedFilters.value = JSON.parse(localStorage.getItem(SUB_KEY) || "[]");
  } catch { savedFilters.value = []; }
}
function persistSaved() {
  localStorage.setItem(SUB_KEY, JSON.stringify(savedFilters.value));
}
function saveSubscription() {
  const name = subName.value.trim();
  if (!name) return;
  savedFilters.value.push({
    name,
    keyword: query.keyword,
    province: filterModel.province || query.province,
    notice_type: filterModel.noticeType || activeType.value,
    date_from: filterModel.dateRange?.[0] || "",
    date_to: filterModel.dateRange?.[1] || "",
    saved_at: new Date().toISOString().slice(0, 10),
  });
  persistSaved();
  subName.value = "";
  subDialogVisible.value = false;
  ElMessage.success("订阅已保存");
}
function subSummary(s: SavedFilter): string {
  const parts: string[] = [];
  if (s.keyword) parts.push(`词:${s.keyword}`);
  if (s.notice_type) parts.push(s.notice_type);
  if (s.province) parts.push(s.province);
  if (s.date_from) parts.push(`${s.date_from}~${s.date_to}`);
  return parts.join(" / ") || "全部标讯";
}
function onViewChange(view: string | number) {
  if (view === 'subscriptions') { savedView.value = 'subscriptions'; selectedIds.value = []; }
  else { savedView.value = 'all'; load(1); }
}
function applySubscription(s: SavedFilter) {
  query.keyword = s.keyword || "";
  query.purchaser_keyword = "";
  query.supplier_keyword = "";
  filterModel.province = s.province || "";
  filterModel.noticeType = s.notice_type || "";
  activeType.value = s.notice_type || "";
  filterModel.dateRange = s.date_from ? [s.date_from, s.date_to || ""] : null;
  appliedSub.value = s;
  savedView.value = 'all';
  load(1);
}
function clearSub() {
  appliedSub.value = null;
}
function removeSubscription(idx: number) {
  savedFilters.value.splice(idx, 1);
  persistSaved();
  if (appliedSub.value && !savedFilters.value.includes(appliedSub.value)) {
    appliedSub.value = null;
  }
}

/* ─────────── 兼容历史 activeType 变量（保留旧逻辑） ─────────── */
const activeType = ref("");

/* ─────────── FilterSidebar 回调 ─────────── */
function onSidebarUpdate(next: FilterModel) {
  Object.assign(filterModel, next);
  // 同步到后端兼容字段
  query.province = filterModel.province;
  activeType.value = filterModel.noticeType;
  load(1);
}
function clearField(field: keyof typeof query) {
  (query as any)[field] = "";
  load(1);
}
function clearSidebar(field: keyof typeof filterModel) {
  (filterModel as any)[field] = field === 'dateRange' ? null : '';
  query.province = filterModel.province;
  activeType.value = filterModel.noticeType;
  load(1);
}
function clearDate() { clearSidebar('dateRange'); }
function clearAmount() {
  filterModel.amountMin = "";
  filterModel.amountMax = "";
  load(1);
}
function clearStage() {
  filterModel.stage = "";
  filterModel.dateRange = null;
  load(1);
}
function stageLabel(stage: string): string {
  return ({ today: '今日', '7d': '近7天', '1m': '近1个月', '3m': '近3个月', '1y': '近1年', custom: '自定义' } as Record<string, string>)[stage] || stage;
}

const hasActiveFilter = computed(() => {
  return !!(
    query.keyword || query.purchaser_keyword || query.supplier_keyword ||
    filterModel.province || filterModel.category || filterModel.industry ||
    filterModel.purchaseWay || filterModel.noticeType || filterModel.stage ||
    filterModel.dateRange || filterModel.amountMin || filterModel.amountMax ||
    filterModel.priceType || query.only_matched
  );
});

/* ─────────── 快捷筛选: 点击采购人/供应商 Top 直接过滤(暂未用，保留扩展) ─────────── */
function quickQuery(field: "purchaser" | "supplier", name: string) {
  if (field === "purchaser") {
    query.purchaser_keyword = name;
    query.supplier_keyword = "";
  } else {
    query.supplier_keyword = name;
    query.purchaser_keyword = "";
  }
  query.keyword = "";
  load(1);
}

/* ─────────── 保存筛选条件 ─────────── */
async function openStoreSave() {
  try {
    savingFilter.value = true;
    const { value } = await ElMessageBox.prompt("请输入筛选条件名称", "保存筛选条件", {
      inputPlaceholder: "如：四川招标重点项目",
      inputValidator: (v) => !!v?.trim() || "请输入名称",
    });
    const name = value.trim();
    // 同步到 store
    filterStore.state.keyword = query.keyword;
    filterStore.state.province = filterModel.province;
    filterStore.state.noticeType = filterModel.noticeType || activeType.value;
    filterStore.state.amountMin = filterModel.amountMin;
    filterStore.state.amountMax = filterModel.amountMax;
    filterStore.state.purchaserKeyword = query.purchaser_keyword;
    filterStore.state.supplierKeyword = query.supplier_keyword;
    filterStore.state.onlyMatched = !!query.only_matched;
    filterStore.saveLocal(name);
    try {
      await api.post("/tenders/subscriptions", { name, condition_snapshot: filterStore.snapshot() });
      ElMessage.success("筛选条件已保存，并已同步到我的订阅");
    } catch (e: any) {
      // ★ P0-7/1.1: 订阅同步失败(如路由未挂载/后端 500)时不得再弹"已同步"
      const detail = e?.response?.data?.detail || "同步失败";
      ElMessage.warning(`筛选条件已保存到本地, 但同步到订阅失败: ${detail}`);
    }
    loadSaved();
  } catch (error: any) {
    if (error !== "cancel" && error !== 'close') ElMessage.error("保存失败，请稍后重试");
  } finally {
    savingFilter.value = false;
  }
}

/* ─────────── 重置 ─────────── */
function resetAll() {
  query.keyword = "";
  query.purchaser_keyword = "";
  query.supplier_keyword = "";
  query.title_extra = "";
  query.only_matched = false;
  activeType.value = "";
  Object.assign(filterModel, {
    province: "", category: "", industry: "", purchaseWay: "",
    noticeType: "", dateRange: null, amountMin: "", amountMax: "",
    priceType: "", stage: "",
  });
  appliedSub.value = null;
  load(1);
}

/* ─────────── 导出 CSV ─────────── */
function esc(v: any): string {
  const s = v == null ? "" : String(v).replace(/\s+/g, " ").trim();
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
function formatNum(n: number) {
  return n.toLocaleString();
}
async function exportCsv() {
  exporting.value = true;
  try {
    const rows: any[] = [];
    const MAX = 500;
    const BATCH = 100;
    for (let p = 1; p * BATCH <= MAX; p++) {
      const res: any = await api.get("/bids", {
        params: {
          page: p,
          page_size: BATCH,
          keyword: query.keyword || undefined,
          province: filterModel.province || undefined,
          notice_type: filterModel.noticeType || undefined,
          date_from: filterModel.dateRange?.[0] || undefined,
          date_to: filterModel.dateRange?.[1] || undefined,
          purchaser_keyword: query.purchaser_keyword || undefined,
          supplier_keyword: query.supplier_keyword || undefined,
          category: filterModel.category || undefined,
          industry: filterModel.industry || undefined,
          purchase_way: filterModel.purchaseWay || undefined,
          price_type: filterModel.priceType || undefined,
          budget_min: filterModel.amountMin ? Number(filterModel.amountMin) : undefined,
          budget_max: filterModel.amountMax ? Number(filterModel.amountMax) : undefined,
          only_matched: query.only_matched || undefined,
        },
      });
      rows.push(...(res?.items || []));
      if (rows.length >= (res?.total ?? 0) || !(res?.items || []).length) break;
    }
    const header = ["标题", "公告类型", "地区", "招标单位", "中标供应商", "中标金额", "发布时间", "来源", "原文链接"];
    const lines = rows.map((b) => {
      const suppliers = (b.suppliers || []).map((s: any) => s.supplier).join("；");
      const amount = firstAmount(b) > 0 ? firstAmount(b) : "";
      return [b.title, b.notice_type, b.region, b.purchaser, suppliers, amount, b.published_at, b.source_name, b.url]
        .map(esc).join(",");
    });
    const csv = "\uFEFF" + [header.map(esc).join(","), ...lines].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `标讯导出_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  } finally {
    exporting.value = false;
  }
}

/* ─────────── 数据加载 ─────────── */
function bidTags(b: any) {
  const tags: Array<{ label: string; kind: "status" | "category" | "warning" }> = [];
  if (b.notice_type) tags.push({ label: b.notice_type, kind: "status" });
  if (b.industry || b.meta?.industry) tags.push({ label: b.industry || b.meta.industry, kind: "category" });
  const deadline = b.deadline || b.meta?.timeline?.find?.((x: any) => x?.label?.includes("截止"))?.value;
  if (deadline) tags.push({ label: `截止 ${deadline}`, kind: "warning" });
  return tags;
}
function firstAmount(b: any): number {
  const s = (b.suppliers || [])[0];
  return s && s.amount != null ? Number(s.amount) : 0;
}
function fmtAmount(v: number): string {
  if (v >= 10000) return `${(v / 10000).toFixed(2)}万`;
  return v.toLocaleString();
}
function goCompany(id: number) {
  navToNewTab(`/companies/${id}`);
}

async function load(p: number = page.value) {
  loading.value = true;
  try {
    const composed = composeKeyword();
    const res: any = await api.get("/bids", {
      params: {
        page: p,
        page_size: pageSize,
        keyword: composed || undefined,
        province: filterModel.province || undefined,
        notice_type: filterModel.noticeType || undefined,
        date_from: filterModel.dateRange?.[0] || undefined,
        date_to: filterModel.dateRange?.[1] || undefined,
        purchaser_keyword: query.purchaser_keyword || undefined,
        supplier_keyword: query.supplier_keyword || undefined,
        category: filterModel.category || undefined,
        industry: filterModel.industry || undefined,
        purchase_way: filterModel.purchaseWay || undefined,
        price_type: filterModel.priceType || undefined,
        budget_min: filterModel.amountMin ? Number(filterModel.amountMin) : undefined,
        budget_max: filterModel.amountMax ? Number(filterModel.amountMax) : undefined,
        only_matched: query.only_matched || undefined,
      },
    });
    items.value = res?.items || [];
    selectedIds.value = [];
    total.value = res?.total || 0;
    page.value = p;
  } finally {
    loading.value = false;
  }
}

/* keyword 仅承载主标题关键词与第二个标题关键词框; 分类/行业/采购方式/询价已作为独立参数下发 */
function composeKeyword(): string {
  const parts: string[] = [];
  if (query.keyword) parts.push(query.keyword);
  if (query.title_extra) parts.push(query.title_extra);
  return parts.filter(Boolean).join(" ");
}

onMounted(() => {
  filterStore.restoreLocal();
  query.keyword = String(filterStore.state.keyword || (route.query.keyword || ""));
  filterModel.province = filterStore.state.province;
  query.purchaser_keyword = filterStore.state.purchaserKeyword;
  query.supplier_keyword = filterStore.state.supplierKeyword;
  query.only_matched = filterStore.state.onlyMatched;
  filterModel.noticeType = filterStore.state.noticeType || activeType.value;
  load(1);
  loadSaved();
});
</script>

<style scoped>
.bid-center-page {
  padding: 14px 0 36px;
  max-width: 1320px;
  margin: 0 auto;
}

/* ========== 顶部 Tab ========== */
.bc-top {
  background: #fff;
  border: 1px solid var(--site-panel-border, #ece8e4);
  border-radius: 10px;
  margin-bottom: 12px;
}
.bc-top-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  flex-wrap: wrap;
  gap: 8px;
}
.bc-main-tabs {
  flex: 1;
}
.bc-main-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}
.bc-main-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 600;
  height: 50px;
  line-height: 50px;
  color: var(--site-text-dim, #4a4646);
}
.bc-main-tabs :deep(.el-tabs__item.is-active) {
  color: var(--site-brand, #a51c30);
}
.bc-main-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--site-brand, #a51c30);
  height: 3px;
}
.bc-main-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--site-panel-border, #ece8e4);
}
.bc-total-meta {
  font-size: 13px;
  color: var(--site-text-dim, #4a4646);
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding-right: 4px;
}
.bc-total-meta b {
  color: var(--site-brand, #a51c30);
  font-size: 18px;
  font-weight: 700;
  margin: 0 4px;
  font-family: Georgia, "Source Han Serif SC", serif;
}
.bc-applied-sub {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--site-brand-soft, #fbecee);
  color: var(--site-brand, #a51c30);
  border-radius: 20px;
  padding: 3px 10px;
  font-size: 12.5px;
}
.bc-clear {
  margin-left: 2px;
  cursor: pointer;
}

/* ========== 主体两列 ========== */
.bc-body {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 14px;
  align-items: start;
}

/* ========== 右侧列表区 ========== */
.bc-main {
  background: #fff;
  border: 1px solid var(--site-panel-border, #ece8e4);
  border-radius: 10px;
  padding: 16px 18px 18px;
  min-width: 0;
}

/* 顶部查询区 */
.bc-query {
  background: linear-gradient(135deg, #fbecee 0%, #fdf6f7 100%);
  border: 1px solid #f3d4d8;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.bc-query-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.bc-query-row:last-child {
  margin-bottom: 0;
}
.bc-qi {
  flex: 1 1 0;
  min-width: 160px;
}
.bc-qi-wide {
  flex: 2 1 240px;
}
.bc-query-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.bc-btn-primary {
  background: var(--site-brand, #a51c30);
  border-color: var(--site-brand, #a51c30);
  color: #fff;
  font-weight: 600;
  min-width: 96px;
}
.bc-btn-primary:hover {
  background: var(--site-brand-dark, #851626);
  border-color: var(--site-brand-dark, #851626);
  color: #fff;
}
.bc-btn-ghost {
  border-color: #d8c2c6;
  color: var(--site-text-dim, #4a4646);
  background: #fff;
}
.bc-btn-ghost:hover {
  border-color: var(--site-brand, #a51c30);
  color: var(--site-brand, #a51c30);
}

/* 已选条件 */
.bc-active-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 2px 0;
  margin-bottom: 8px;
}
.bc-active-tags .bc-active-label {
  font-size: 12.5px;
  color: var(--site-text-mute, #8c8784);
  margin-right: 4px;
}

/* ========== 列表 ========== */
.bc-list { min-height: 320px; position: relative; }
.bc-list.is-empty { padding: 40px 0; }
.bc-empty { padding: 40px 0; text-align: center; }
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0;
  margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0;
}

.bc-card-list { display: flex; flex-direction: column; }
.bc-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 12px 14px 6px;
  border-bottom: 1px dashed var(--site-panel-border, #ece8e4);
  transition: background 0.2s ease;
}
.bc-card:last-child { border-bottom: none; }
.bc-card:hover { background: #fdf6f7; }
.bc-card.selected { background: #fdf6f7; }

.bc-row-check {
  margin: 5px 0 0 6px;
  flex: none;
}
.bc-row-index {
  flex: none;
  width: 30px;
  text-align: center;
  font-size: 12px;
  color: var(--site-text-mute, #8c8784);
  font-family: Georgia, serif;
  padding-top: 4px;
}
.bc-card-main {
  flex: 1;
  min-width: 0;
}
.bc-card-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.bc-card-date {
  font-size: 12px;
  color: var(--site-text-mute, #8c8784);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.bc-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--site-text, #1c1a1a);
  text-decoration: none;
  line-height: 1.6;
  display: inline-block;
  margin: 2px 0;
}
.bc-card-title:hover {
  color: var(--site-brand, #a51c30);
}
.bc-card-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 6px;
  flex-wrap: wrap;
  font-size: 12.5px;
  color: var(--site-text-dim, #4a4646);
}
.bc-meta-amount {
  color: var(--site-brand, #a51c30);
  font-weight: 700;
  font-size: 15px;
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
}
.bc-amount-icon { font-size: 12px; }
.bc-meta-item { display: inline-flex; align-items: center; gap: 3px; }
.bc-meta-label { color: var(--site-text-mute, #8c8784); }
.bc-company-link {
  color: #3b6fb6;
  cursor: pointer;
  text-decoration: none;
}
.bc-company-link:hover { text-decoration: underline; }
.bc-company-text { color: var(--site-text-dim, #4a4646); }
.bc-supplier-count b { color: var(--site-brand, #a51c30); }

/* 右侧操作区 */
.bc-card-side {
  flex: none;
  width: 130px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  padding-top: 22px;
}
.bc-download-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--site-brand, #a51c30);
  font-size: 12.5px;
  cursor: pointer;
  text-decoration: none;
  border: 1px solid var(--site-brand-soft, #fbecee);
  background: var(--site-brand-soft, #fbecee);
  border-radius: 16px;
  padding: 3px 12px;
  transition: all 0.2s ease;
}
.bc-download-link:hover {
  background: var(--site-brand, #a51c30);
  color: #fff;
  border-color: var(--site-brand, #a51c30);
}
.bc-source {
  font-size: 11px;
  color: #b08d57;
  background: #fbf6ec;
  border-radius: 3px;
  padding: 1px 6px;
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 订阅视图列表 */
.bc-saved-list { display: flex; flex-direction: column; gap: 10px; }
.bc-saved-item {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  border: 1px solid var(--site-panel-border, #ece8e4);
  background: #fff;
  border-radius: 8px;
  padding: 14px 18px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}
.bc-saved-item:hover {
  border-color: var(--site-brand, #a51c30);
  box-shadow: 0 4px 14px rgba(165, 28, 48, 0.08);
  transform: translateY(-1px);
}
.bc-saved-name {
  min-width: 160px;
  color: var(--site-brand, #a51c30);
  font-size: 14px;
}
.bc-saved-summary {
  flex: 1;
  color: #667085;
  font-size: 12.5px;
}
.bc-saved-time {
  font-size: 12px;
  color: var(--site-text-mute, #8c8784);
}
.bc-saved-action {
  color: #286bc2;
  font-style: normal;
  font-size: 12.5px;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

/* 分页 */
.bc-pagination {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}
.bc-pagination-summary {
  margin-top: 14px;
  text-align: right;
  font-size: 12.5px;
  color: var(--site-text-mute, #8c8784);
}
.bc-pagination-summary b {
  color: var(--site-brand, #a51c30);
  margin: 0 4px;
}

/* ========== 响应式 ========== */
@media (max-width: 1024px) {
  .bc-body { grid-template-columns: 220px 1fr; }
  .bc-card-side { width: 110px; }
}
@media (max-width: 768px) {
  .bc-body {
    grid-template-columns: 1fr;
  }
  .bc-card-side {
    width: auto;
    flex-direction: row;
    padding-top: 0;
    margin-top: 6px;
  }
  .bc-card {
    flex-wrap: wrap;
    padding: 12px 8px;
  }
  .bc-row-index { display: none; }
  .bc-query-row { gap: 8px; }
  .bc-qi { flex: 1 1 100%; min-width: 0; }
  .bc-qi-wide { flex: 1 1 100%; }
  .bc-query-actions {
    margin-left: 0;
    width: 100%;
    justify-content: stretch;
  }
  .bc-query-actions .el-button { flex: 1; }
  .bc-top-inner { padding: 0 12px; }
}
</style>
