<template>
  <div class="sub-query-page">
    <!-- 顶部 tabs (参考建设通) -->
    <div class="sq-tabs">
      <div
        v-for="t in tabs"
        :key="t.key"
        class="sq-tab"
        :class="{ active: tab === t.key, vip: t.vip }"
        @click="switchTab(t)"
      >
        <span class="sq-tab-label">{{ t.label }}</span>
        <sup v-if="t.suffix" class="sq-suffix">{{ t.suffix }}</sup>
      </div>
    </div>

    <!-- 查企业: 多行筛选 + 结果(仅 company tab 显示) -->
    <template v-if="tab === 'company'">
    <div class="sq-filters">
      <div class="sq-row">
        <span class="sq-label">选择地区：</span>
        <span class="sq-links">
          <a :class="{ active: !filter.province }" @click="filter.province = ''; search(1)">不限</a>
          <a v-for="p in provinces" :key="p" :class="{ active: filter.province === p }" @click="filter.province = p; search(1)">{{ p }}</a>
        </span>
      </div>
      <div class="sq-row">
        <span class="sq-label">注册资金：</span>
        <span class="sq-links">
          <a :class="{ active: !filter.capitalPreset }" @click="filter.capitalPreset = ''; search(1)">不限</a>
          <a v-for="cp in capitalPresets" :key="cp.value" :class="{ active: filter.capitalPreset === cp.value }" @click="pickCapital(cp); search(1)">{{ cp.label }}</a>
        </span>
        <span class="sq-min-max">
          最小金额 <input v-model.number="filter.capitalMin" type="number" class="sq-input-num" @change="search(1)" /> ~ 最大金额 <input v-model.number="filter.capitalMax" type="number" class="sq-input-num" @change="search(1)" /> 万
        </span>
      </div>
      <div class="sq-row">
        <span class="sq-label">企业入库：</span>
        <el-select v-model="filter.stock" placeholder="企业入库" clearable style="width: 220px" @change="search(1)">
          <el-option v-for="s in stockList" :key="s" :value="s" :label="s" />
        </el-select>
        <span class="sq-label sq-label-inline">成立时间：</span>
        <el-date-picker v-model="filter.dateRange" type="daterange" range-separator=" ~ " start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 360px" @change="search(1)" />
      </div>
      <div class="sq-row">
        <span class="sq-label sq-label-vip">企业性质：</span>
        <el-select v-model="filter.nature" placeholder="企业性质" clearable style="width: 220px" @change="search(1)">
          <el-option v-for="n in NATURES" :key="n" :value="n" :label="n" />
        </el-select>
        <!-- 企业标签/体系认证/安许证: 后端 ext_attrs 暂未采集对应字段, 隐藏控件避免「假筛选」 -->
      </div>
      <div class="sq-row">
        <span class="sq-label">注册地址：</span>
        <input v-model="filter.address" class="sq-text" placeholder="企业注册地址关键字，如：开发区" />
        <span class="sq-label sq-label-inline">经营范围：</span>
        <input v-model="filter.scope" class="sq-text" placeholder="多关键词用空格隔开，如 公路 道路" />
      </div>
      <div class="sq-row sq-row-actions-row">
        <span class="sq-label">企业名称：</span>
        <input v-model="filter.name" class="sq-text" placeholder="如 地质" @keyup.enter="search(1)" />
        <button class="sq-go" :disabled="loading" @click="search(1)">查询</button>
        <a class="sq-help" href="javascript:void(0)" @click="showHelp">更多业绩/资质/荣誉等专科需求前往组合查询</a>
      </div>
    </div>

    <!-- 结果摘要 + 检索模式 -->
    <div class="sq-summary">
      <span class="sq-summary-left">
        共找到 <b>{{ total }}</b> 家符合条件的 <b class="text-brand">{{ typeLabel }}</b>。
      </span>
      <span class="sq-summary-right">
        检索模式：
        <el-radio-group v-model="searchMode" size="small" @change="search(1)">
          <el-radio-button label="fuzzy">模糊检索</el-radio-button>
          <el-radio-button label="exact">精准检索</el-radio-button>
        </el-radio-group>
        <el-tooltip content="模糊检索: 关键词拆分匹配; 精准检索: 关键词完整匹配" placement="top">
          <el-icon class="sq-info"><QuestionFilled /></el-icon>
        </el-tooltip>
      </span>
    </div>

    <!-- 结果列表 -->
    <div v-loading="loading" class="sq-list">
      <div
        v-for="(row, idx) in list"
        :key="row.id"
        class="sq-result"
        @click="open(row)"
      >
        <div class="sq-idx">{{ idx + 1 + (page - 1) * pageSize }}</div>
        <div class="sq-main">
          <div class="sq-name-row">
            <span class="sq-name" v-html="highlightedName(row)"></span>
            <el-tag v-if="row.is_local" size="small" type="warning" effect="dark">属地</el-tag>
            <el-tag v-else size="small" type="info" effect="plain" v-if="row.company_kind">{{ row.company_kind }}</el-tag>
          </div>
          <div v-if="row.alias" class="sq-alias">
            <el-tag size="small" effect="plain">曾用名</el-tag>
            <span class="sq-alias-text">{{ row.alias }}</span>
          </div>
          <div class="sq-stats">
            <span class="sq-stat"><span class="sq-stat-label">中标：</span><b>{{ row.bid_count ?? 0 }}</b></span>
            <span class="sq-stat"><span class="sq-stat-label">资质：</span><b>{{ row.qua_count ?? 0 }}</b></span>
            <span class="sq-stat"><span class="sq-stat-label">诚信：</span><b>{{ row.credit_score ?? 30 }}</b></span>
            <span class="sq-stat"><span class="sq-stat-label">备案地：</span><b>{{ row.province ?? '—' }}</b><b v-if="row.city">{{ '·' + row.city }}</b></span>
            <span class="sq-stat"><span class="sq-stat-label">最近中标：</span>{{ row.latest_bid_at || '—' }}</span>
            <span class="sq-stat"><span class="sq-stat-label">联系电话：</span>{{ row.contact_phone || '—' }}</span>
            <span class="sq-stat"><span class="sq-stat-label">注册地：</span>{{ row.registered_address || row.province + (row.city ? ('·' + row.city) : '') || '—' }}</span>
          </div>
        </div>
        <div class="sq-row-actions">
          <el-button class="sq-act-btn sq-act-portrait" @click.stop="open(row)">企业画像</el-button>
        </div>
      </div>
      <div v-if="!loading && list.length === 0 && searched" class="sq-empty">
        没有找到匹配的记录，请调整筛选条件后重试。
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="sq-pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, jumper"
        background
        @current-change="search"
      />
    </div>
    </template>

    <!-- 查人员 / 查项目经理: 复用站内 /persons 接口(登录态, 真实姓名不脱敏) -->
    <PersonSubQuery
      v-else-if="tab === 'person' || tab === 'manager'"
      :mode="(tab as 'person' | 'manager')"
    />
    <!-- 其余未实现 tab 占位 -->
    <div
      v-else
      style="text-align:center;padding:60px 20px;color:var(--site-text-mute);font-size:14px;background:#fff;border-radius:8px;border:1px dashed var(--site-hairline);"
    >该功能建设中，敬请期待。</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { QuestionFilled } from "@element-plus/icons-vue";
import api from "@/api";
import PersonSubQuery from "@/views/site/PersonSubQuery.vue";

const props = defineProps<{
  /** 接收的初始 tab: company / person / project ... */
  initialTab?: "company" | "person" | "project";
  /** 接收父级传入的初始关键词 */
  initialKeyword?: string;
}>();

const route = useRoute();
const router = useRouter();
const searchMode = ref<"fuzzy" | "exact">("fuzzy");

/* ─────────── 顶部 tabs (建设通风格) ─────────── */
const tabs = [
  { key: "company", label: "查企业" },
  { key: "achievement", label: "查业绩", vip: true },
  { key: "person", label: "查人员" },
  { key: "manager", label: "查项目经理" },
  { key: "qualification", label: "查资质" },
  { key: "honor", label: "查荣誉" },
  { key: "credit", label: "查诚信" },
  { key: "credit_evaluate", label: "信用评价" },
  { key: "owner", label: "查业主", suffix: "SVIP" },
  { key: "bid_open", label: "开标记录", suffix: "SVIP" },
];
const tab = ref<"company" | "achievement" | "person" | "manager" | "qualification" | "honor" | "credit" | "credit_evaluate" | "owner" | "bid_open">(
  (props.initialTab as any) || "company"
);

const typeLabel = computed(() => {
  const map: Record<string, string> = {
    company: "单位",
    person: "人员",
    project: "项目",
    achievement: "企业业绩",
    manager: "项目经理",
    qualification: "资质记录",
    honor: "企业荣誉",
    credit: "诚信记录",
    credit_evaluate: "信用评价记录",
    owner: "业主单位",
    bid_open: "开标记录",
  };
  return map[tab.value] || "单位";
});

function switchTab(t: any) {
  tab.value = t.key;
  /* 查企业 / 查人员 / 查项目经理 均已实现; 其余 tab 提示建设中 */
  if (t.key === "company") {
    search(1);
  } else if (t.key !== "person" && t.key !== "manager") {
    ElMessage.info(`「${t.label}」功能建设中`);
  }
  /* person / manager: 由模板渲染 PersonSubQuery(挂载时自行检索) */
}

/* ─────────── 筛选状态 ─────────── */
const provinces = [
  "北京", "天津", "上海", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
  "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
  "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
];
const capitalPresets = [
  { value: "500w", label: "500万以上", min: 500, max: undefined },
  { value: "1000w", label: "1000万以上", min: 1000, max: undefined },
  { value: "5000w", label: "5000万以上", min: 5000, max: undefined },
  { value: "1y", label: "1亿以上", min: 10000, max: undefined },
];
const stockList = ["AAAA", "AAA", "AA", "A", "B", "C"];
const NATURES = ["国有", "集体", "私营", "股份", "联营", "有限责任", "个人独资", "外商投资", "港澳台投资"];
const TAGS = ["高新技术企业", "小微企业", "科技型中小企业", "专精特新", "上市企业"];
const SYSTEMS = ["ISO9001 质量管理体系", "ISO14001 环境管理体系", "ISO45001 职业健康安全", "ISO27001 信息安全"];
const SAFETIES = ["建筑施工安全许可证", "安全生产许可证(矿山)", "安全生产许可证(危化品)"];

const filter = reactive({
  province: "",
  capitalPreset: "",
  capitalMin: undefined as number | undefined,
  capitalMax: undefined as number | undefined,
  stock: "",
  dateRange: undefined as [string, string] | undefined,
  nature: "",
  tag: "",
  system: "",
  safety: "",
  address: "",
  scope: "",
  name: props.initialKeyword || ((route.query.keyword as string) || ""),
});
function pickCapital(cp: { value: string; min: number; max?: number }) {
  filter.capitalPreset = cp.value;
  filter.capitalMin = cp.min;
  filter.capitalMax = cp.max;
}

/* ─────────── 列表数据 ─────────── */
const list = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const searched = ref(false);

/* ─────────── API: 调 /api/v1/companies ─────────── */
const lastKeyword = ref("");
async function search(p: number = page.value) {
  page.value = p;
  loading.value = true;
  lastKeyword.value = filter.name || "";
  try {
    // 数字类参数: 空串/0 都转为 undefined, 避免 0 被 || 误判丢弃
    const toNum = (v: any) => (v === "" || v == null ? undefined : Number(v));
    const params: Record<string, any> = {
      page: p,
      page_size: pageSize,
      keyword: filter.name || undefined,
      province: filter.province || undefined,
      registered_capital_min: toNum(filter.capitalMin),
      registered_capital_max: toNum(filter.capitalMax),
      ownership: filter.nature || undefined,
      address: filter.address || undefined,
      scope: filter.scope || undefined,
      credit_level: filter.stock || undefined, // 企业入库=信用等级
      q_mode: searchMode.value,
    };
    if (filter.dateRange && filter.dateRange.length === 2) {
      params.est_from = filter.dateRange[0];
      params.est_to = filter.dateRange[1];
    }
    Object.keys(params).forEach((k) => params[k] === undefined && delete params[k]);

    const res: any = await api.get("/companies", { params });
    list.value = res.items || [];
    total.value = res.total || 0;
    searched.value = true;
  } catch {
    list.value = [];
    total.value = 0;
    ElMessage.error("查询失败，请稍后重试");
  } finally {
    loading.value = false;
  }
}

/* ─────────── 行点击: 进入详情 ─────────── */
function open(row: any) {
  if (!row?.id) return;
  router.push(`/site/data-center/companies/${row.id}`);
}

/* ─────────── 搜索词高亮 ─────────── */
function escapeHtml(s: string): string {
  return String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" } as any)[c]
  );
}
function highlightedName(row: any): string {
  const raw = String(row.name || "");
  const kw = String(lastKeyword.value || "").trim();
  if (!kw) return escapeHtml(raw);
  const safe = escapeHtml(raw);
  const safeKw = escapeHtml(kw);
  try {
    const re = new RegExp(safeKw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    return safe.replace(re, (m) => `<span class="sq-hlkw">${m}</span>`);
  } catch {
    return safe;
  }
}

/* ─────────── 帮助 ─────────── */
function showHelp() {
  router.push("/workspace/combined-query");
}

/* ─────────── 钩子 ─────────── */
onMounted(() => {
  /* URL ?keyword=xx 自动套到搜索框 (来自首页公开检索跳转) */
  const q = route.query.keyword;
  if (q && typeof q === "string" && !filter.name) {
    filter.name = q;
  }
  search(1);
});
</script>

<style scoped>
.sub-query-page { padding: 12px 6px 24px; }

/* ── 顶部 tabs ── */
.sq-tabs {
  display: flex;
  align-items: center;
  gap: 0;
  border-bottom: 1px solid var(--site-panel-border);
  background: #fff;
  padding: 0 12px;
  overflow-x: auto;
}
.sq-tab {
  flex: 0 0 auto;
  padding: 14px 22px;
  font-size: 15px;
  color: var(--site-text-dim);
  cursor: pointer;
  position: relative;
  white-space: nowrap;
  transition: color 0.2s ease;
  font-weight: 600;
}
.sq-tab:hover { color: var(--site-brand); }
.sq-tab.active { color: var(--site-brand); }
.sq-tab.active::after {
  content: "";
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: -1px;
  height: 2px;
  background: var(--site-brand);
  border-radius: 2px;
}
.sq-tab.vip { color: var(--site-text-mute); }
.sq-tab.vip:hover { color: var(--site-brand-dark); }
.sq-suffix {
  margin-left: 2px;
  padding: 1px 4px;
  font-size: 9px;
  font-weight: 700;
  font-style: normal;
  color: #fff;
  background: linear-gradient(135deg, #ffa726 0%, #fb8c00 100%);
  border-radius: 3px;
  vertical-align: top;
  line-height: 1.2;
}
.sq-tab.vip .sq-suffix {
  background: linear-gradient(135deg, #f06292 0%, #e91e63 100%);
}

/* ── 筛选区 (建设通风格) ── */
.sq-filters {
  background: #fff;
  border: 1px solid var(--site-panel-border);
  border-top: none;
  padding: 14px 18px 4px;
}
.sq-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  padding: 10px 0;
  border-bottom: 1px dashed var(--site-hairline);
  gap: 10px;
}
.sq-row:last-child { border-bottom: none; }
.sq-label {
  flex: 0 0 80px;
  font-size: 14px;
  color: var(--site-text-dim);
  text-align: right;
  padding-right: 8px;
  font-weight: 500;
}
.sq-label-vip::after {
  content: "VIP";
  display: inline-block;
  margin-left: 2px;
  padding: 0 4px;
  font-size: 9px;
  color: #fff;
  background: linear-gradient(135deg, #f06292 0%, #e91e63 100%);
  border-radius: 3px;
  vertical-align: middle;
  line-height: 1.4;
}
.sq-label-inline { margin-left: 18px; }
.sq-links { display: flex; flex-wrap: wrap; gap: 4px 14px; flex: 1; }
.sq-links a {
  font-size: 13.5px;
  color: var(--site-text-dim);
  cursor: pointer;
  text-decoration: none;
  padding: 2px 4px;
  transition: color 0.15s ease;
}
.sq-links a:hover { color: var(--site-brand); text-decoration: underline; }
.sq-links a.active {
  background: var(--site-brand);
  color: #fff;
  border-radius: 3px;
  padding: 2px 8px;
}
.sq-min-max { display: inline-flex; align-items: center; gap: 4px; margin-left: 18px; font-size: 13px; color: var(--site-text-mute); }
.sq-input-num { width: 70px; padding: 3px 6px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 13px; }
.sq-text {
  flex: 1 1 220px;
  max-width: 360px;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 14px;
}
.sq-text:focus { outline: none; border-color: var(--site-brand); }
.sq-row-actions-row { align-items: center; }
.sq-go {
  background: var(--site-brand);
  color: #fff;
  border: none;
  padding: 7px 36px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-left: 6px;
}
.sq-go:hover:not(:disabled) { background: var(--site-brand-dark); }
.sq-go:disabled { opacity: 0.6; cursor: not-allowed; }
.sq-help {
  display: inline-block;
  margin-left: 18px;
  font-size: 13px;
  color: var(--site-brand);
  text-decoration: none;
}
.sq-help:hover { text-decoration: underline; }

/* ── 结果摘要 ── */
.sq-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20px 6px 14px;
  font-size: 14px;
  color: var(--site-text-dim);
  flex-wrap: wrap;
  gap: 12px;
}
.sq-summary b { color: var(--site-brand); font-size: 16px; padding: 0 3px; }
.text-brand { color: var(--site-brand); }
.sq-info { color: var(--site-text-mute); cursor: help; margin-left: 4px; vertical-align: middle; }

/* ── 列表卡片 ── */
.sq-list { display: flex; flex-direction: column; gap: 8px; }
.sq-result {
  display: flex;
  align-items: stretch;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 8px;
  padding: 14px 20px 14px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.sq-result:hover {
  border-color: var(--site-brand);
  background: linear-gradient(135deg, #fff 0%, #fdf6f7 100%);
  box-shadow: 0 4px 14px rgba(165, 28, 48, 0.08);
}
.sq-idx {
  flex: 0 0 36px;
  color: var(--site-text-mute);
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  padding-top: 4px;
}
.sq-main { flex: 1; min-width: 0; }
.sq-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.sq-name {
  font-size: 15.5px;
  font-weight: 700;
  color: var(--site-text);
}
:deep(.sq-hlkw) {
  color: var(--site-brand);
  font-weight: 700;
}
.sq-alias {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--site-text-mute);
  margin-bottom: 6px;
}
.sq-alias-text { color: var(--site-text-dim); }
.sq-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 22px;
  font-size: 13px;
  color: var(--site-text-dim);
  margin-top: 4px;
}
.sq-stat b {
  color: var(--site-brand);
  font-weight: 700;
  margin-right: 4px;
}
.sq-stat-label { color: var(--site-text-mute); margin-right: 2px; }
.sq-row-actions {
  flex: 0 0 140px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  gap: 6px;
  border-left: 1px dashed var(--site-hairline);
  padding-left: 16px;
}
.sq-act-btn {
  border: 1px solid var(--site-panel-border);
  background: #fff;
  border-radius: 4px;
  font-size: 13px;
  color: var(--site-text-dim);
  padding: 5px 0;
  height: 32px;
}
.sq-act-btn:hover { border-color: var(--site-brand); color: var(--site-brand); background: var(--site-brand-soft); }
.sq-act-verify {
  background: linear-gradient(135deg, #f9a825 0%, #f57f17 100%);
  border-color: transparent;
  color: #fff !important;
}
.sq-act-verify:hover { background: linear-gradient(135deg, #f57f17 0%, #e65100 100%); border-color: transparent; }

.sq-empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--site-text-mute);
  font-size: 14px;
  background: #fff;
  border-radius: 8px;
  border: 1px dashed var(--site-hairline);
}

/* ── 分页 ── */
.sq-pagination {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .sq-label { flex: 0 0 70px; font-size: 13px; }
  .sq-row-actions { flex: 0 0 100px; padding-left: 10px; }
}
</style>
