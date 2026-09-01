<template>
  <div class="my-subscriptions">
    <!-- 顶部面包屑 -->
    <el-breadcrumb separator="/" class="bc">
      <el-breadcrumb-item :to="{ path: '/site/account' }">个人中心</el-breadcrumb-item>
      <el-breadcrumb-item>功能菜单</el-breadcrumb-item>
      <el-breadcrumb-item>我的订阅</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- Tabs: 商机 / 标讯 -->
    <el-tabs v-model="tab" class="sub-tabs">
      <el-tab-pane label="商机信息" name="opp" />
      <el-tab-pane label="拟建信息" name="tender" />
      <el-tab-pane label="招投标信息" name="bid" />
    </el-tabs>

    <!-- 工具栏: 新建 / 批量启停 -->
    <div class="toolbar">
      <h3 class="tb-h">我的订阅</h3>
      <div class="tb-actions">
        <el-button v-if="visibleSubs.length" :icon="Refresh" :loading="loading || searching" @click="loadList">刷新</el-button>
        <el-button type="success" :icon="Plus" @click="openCreate()">新建订阅</el-button>
      </div>
    </div>

    <!-- 订阅 chips 标签(点 chip 过滤下方列表) -->
    <div class="sub-chips">
      <span
        v-for="s in allSubs"
        :key="s.id"
        class="sub-chip"
        :class="{ on: activeSubId === s.id, deleted: s.enabled === 0 }"
        @click="selectSub(s)"
      >
        <el-tag v-if="s.enabled === 0" size="small" type="info" effect="plain" round>已停用</el-tag>
        <strong>{{ s.name }}</strong>
        <em>({{ countBySubId[s.id] || 0 }})</em>
        <el-icon class="sub-chip-edit" @click.stop="openCreate(s)"><EditPen /></el-icon>
        <el-icon class="sub-chip-del" @click.stop="removeOne(s)"><Delete /></el-icon>
      </span>
    </div>

    <el-empty v-if="!loading && !allSubs.length" description="暂无订阅,点击右上角「新建订阅」开始订阅" />

    <!-- 条件区: 切换订阅后,展示当前订阅的查询条件 + 重置/查询 -->
    <div v-if="activeSub" class="search-bar">
      <div class="sb-row">
        <el-input v-model="filter.keyword" placeholder="请输入项目关键词" clearable class="sb-input" />
        <el-input v-model="filter.region" placeholder="请选择省份" clearable class="sb-input" />
        <el-input v-model="filter.owner" placeholder="请输入业主名称" clearable class="sb-input" />
        <el-select v-model="filter.stage" placeholder="项目阶段" clearable class="sb-input">
          <el-option label="意向征集" value="意向征集" />
          <el-option label="立项阶段" value="立项阶段" />
          <el-option label="可研阶段" value="可研阶段" />
          <el-option label="筹备阶段" value="筹备阶段" />
          <el-option label="设计" value="设计" />
          <el-option label="动工" value="动工" />
        </el-select>
        <el-select v-model="filter.amount" placeholder="金额范围" clearable class="sb-input">
          <el-option label="500万以下" value="0-500" />
          <el-option label="500-2000万" value="500-2000" />
          <el-option label="2000万-1亿" value="2000-10000" />
          <el-option label="1亿以上" value="10000+" />
        </el-select>
      </div>
      <div class="sb-actions">
        <el-button type="primary" @click="runCurrent(1)">查询</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </div>
    </div>

    <!-- 项目列表 -->
    <div v-if="activeSub" class="results" v-loading="searching">
      <div class="results-head">
        <span>搜索到 <strong>{{ total }}</strong> 条结果</span>
        <span class="results-sort">排序: 默认 <el-icon><CaretBottom /></el-icon></span>
      </div>
      <el-empty v-if="!searching && !results.length" description="该订阅下暂无匹配结果" />
      <ul v-else class="card-list">
        <li v-for="(r, i) in results" :key="r.id" class="list-item">
          <span class="li-no">{{ (currentPage - 1) * pageSize + i + 1 }}</span>
          <div class="li-body">
            <div class="li-tags" v-if="(r.tags || r.industries || []).length">
              <el-tag v-for="(t, idx) in (r.tags || r.industries || []).slice(0, 4)" :key="idx" size="small" type="warning" effect="plain">{{ t }}</el-tag>
            </div>
            <a class="li-title" :href="r.url || 'javascript:;'" @click.prevent="openItem(r)">{{ r.title || r.projectName }}</a>
            <div class="li-meta">
              <span>业主: <em>{{ r.owner || r.ownerName || '—' }}</em></span>
              <span>代理: <em>{{ r.agent || '—' }}</em></span>
              <span>区域: <em>{{ r.region || `${r.regionProvince || ''} ${r.regionCity || ''}` || '—' }}</em></span>
              <span v-if="r.amount || r.amountWan">金额: <em class="li-amount">{{ formatAmount(r.amount, r.amountWan) }}</em></span>
              <span>发布时间: <em>{{ formatDate(r.publishedAt || r.updatedAt) }}</em></span>
            </div>
          </div>
        </li>
      </ul>
      <div v-if="total > 0" class="pager-wrap">
        <el-pagination
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- 新建/编辑订阅对话框 -->
    <el-dialog
      v-model="dlg.visible"
      :title="dlg.id ? '编辑订阅' : '新建订阅'"
      width="640px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form :model="dlg" label-width="100px" label-position="right">
        <el-form-item label="订阅名称" required>
          <el-input v-model="dlg.name" placeholder="请输入订阅方案名称" maxlength="15" show-word-limit />
        </el-form-item>

        <div class="form-section-title">基本条件</div>
        <el-form-item label="业主名称">
          <el-input v-model="dlg.owner" placeholder="请输入业主名称关键词,多个用空格隔开" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="业主类型">
          <el-select v-model="dlg.ownerType" placeholder="请选择业主类型" clearable>
            <el-option label="政府" value="government" />
            <el-option label="国企" value="soe" />
            <el-option label="央企" value="central" />
            <el-option label="民营" value="private" />
          </el-select>
        </el-form-item>
        <el-form-item label="省份地区">
          <el-input v-model="dlg.region" placeholder="请输入省份/市关键词" />
        </el-form-item>

        <div class="form-section-title">项目关键词</div>
        <el-form-item label="项目关键词">
          <el-input v-model="dlg.keywords" placeholder="请输入关键词,多个用空格隔开" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="排除词">
          <el-input v-model="dlg.excludeKeywords" placeholder="多个排除词用空格隔开" maxlength="100" show-word-limit />
        </el-form-item>

        <div class="form-section-title">金额与资质</div>
        <el-form-item label="项目金额">
          <el-input v-model="dlg.minAmount" placeholder="最小金额" class="amount-input">
            <template #append>万</template>
          </el-input>
          <span class="dash">—</span>
          <el-input v-model="dlg.maxAmount" placeholder="最大金额" class="amount-input">
            <template #append>万</template>
          </el-input>
        </el-form-item>
        <el-form-item label="资质要求">
          <el-select v-model="dlg.qualification" placeholder="请选择资质要求" clearable>
            <el-option label="甲级勘查资质" value="grade_a_survey" />
            <el-option label="乙级勘查资质" value="grade_b_survey" />
            <el-option label="地质灾害甲级" value="hazard_grade_a" />
            <el-option label="施工总承包一级" value="gc1" />
            <el-option label="工程勘察甲级" value="eng_survey_a" />
            <el-option label="CMA 计量认证" value="cma" />
          </el-select>
          <el-button link size="small" class="add-qual">+ 增加条件</el-button>
        </el-form-item>

        <div class="form-section-title">项目与公告</div>
        <el-form-item label="项目类型">
          <el-checkbox-group v-model="dlg.projectTypes" class="type-checks">
            <el-checkbox v-for="pt in projectTypeOptions" :key="pt" :value="pt">{{ pt }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="项目类型2">
          <el-checkbox-group v-model="dlg.projectStages" class="type-checks">
            <el-checkbox v-for="s in projectStageOptions" :key="s" :value="s">{{ s }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="招标方式">
          <el-checkbox-group v-model="dlg.bidMethods" class="type-checks">
            <el-checkbox v-for="m in bidMethodOptions" :key="m" :value="m">{{ m }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="公告类型">
          <el-checkbox-group v-model="dlg.noticeTypes" class="type-checks">
            <el-checkbox v-for="t in noticeTypeOptions" :key="t" :value="t">{{ t }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <div class="form-section-title">公告来源</div>
        <el-form-item label="">
          <el-radio-group v-model="dlg.sourceScope">
            <el-radio value="all">全部</el-radio>
            <el-radio value="specific">指定公告源</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="dlg.sourceScope === 'specific'" label="选择来源">
          <el-select v-model="dlg.sources" placeholder="请选择 1 个或多个公告源" multiple filterable>
            <el-option v-for="src in availableSources" :key="src.value" :label="src.label" :value="src.value" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dlg.visible = false">取消</el-button>
        <el-button type="primary" @click="saveSub">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Plus, Refresh, EditPen, Delete, Search, CaretBottom,
} from "@element-plus/icons-vue";
import api from "@/api";
import {
  listOpportunitySubscriptions, createOpportunitySubscription,
  toggleOpportunitySubscription, deleteOpportunitySubscription,
} from "@/api/opportunityAdmin";

const loading = ref(false);
const tab = ref("opp");
const router = useRouter();

interface SubItem {
  id: number;
  name: string;
  condition: any;
  enabled: 0 | 1;
  lastRunAt: string | null;
  lastMatchCount: number;
  updatedAt: string;
}

const allSubs = ref<SubItem[]>([]);
const activeSubId = ref<number | null>(null);
const activeSub = computed<SubItem | null>(() => allSubs.value.find((s) => s.id === activeSubId.value) || null);
const countBySubId = ref<Record<number, number>>({});

const visibleSubs = computed(() => allSubs.value.filter((s) => s.enabled === 1));

const filter = reactive({
  keyword: "",
  region: "",
  owner: "",
  stage: "",
  amount: "",
});

// 项目结果(根据当前订阅拉取)
const results = ref<any[]>([]);
// 分页状态(与后端 /public/opportunities/search 的 page / page_size / total 对应)
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);
// 结果区加载态(切换页码/每页条数/查询时显示)
const searching = ref(false);

const projectTypeOptions = ["房屋", "公路", "铁路", "港航", "水利", "电力", "矿山", "冶金", "石化", "市政", "通信", "机电", "消防", "桥梁", "隧道", "装修装饰", "幕墙", "民航", "核工程", "海洋石油", "环保", "园林绿化", "照明", "古建筑", "特种工程", "林业", "弱电", "人防", "地质灾害", "交安设施", "新能源"];
const projectStageOptions = ["施工", "勘察", "设计", "监理", "前期"];
const bidMethodOptions = ["公开招标", "邀标", "询价", "竞谈", "竞磋", "单一来源", "竞价", "其他"];
const noticeTypeOptions = ["招标公告", "招标计划", "澄清答疑", "变更"];
const availableSources = [
  { label: "四川省公共资源交易中心", value: "scggzyjy" },
  { label: "中国政府采购网", value: "ccgp" },
  { label: "重庆市公共资源交易网", value: "cqggzyjy" },
  { label: "矿业权交易网", value: "kyqjy" },
  { label: "全国建设工程信息网", value: "jzgcgc" },
];

// 新建订阅表单
const dlg = reactive({
  visible: false,
  id: null as number | null,
  name: "",
  owner: "",
  ownerType: "",
  region: "",
  keywords: "",
  excludeKeywords: "",
  minAmount: "",
  maxAmount: "",
  qualification: "",
  projectTypes: [] as string[],
  projectStages: [] as string[],
  bidMethods: [] as string[],
  noticeTypes: [] as string[],
  sourceScope: "all",
  sources: [] as string[],
});

function resetDlg() {
  Object.assign(dlg, {
    visible: false, id: null, name: "", owner: "", ownerType: "",
    region: "", keywords: "", excludeKeywords: "",
    minAmount: "", maxAmount: "",
    projectTypes: [], projectStages: [], bidMethods: [], noticeTypes: [],
    sourceScope: "all", sources: [], qualification: "",
  });
}

function openCreate(s?: SubItem) {
  if (s) {
    const c = (s.condition || {}) as any;
    Object.assign(dlg, {
      visible: true, id: s.id, name: s.name,
      owner: c.owner || "", ownerType: c.ownerType || "",
      region: c.region || "", keywords: c.keywords || "",
      excludeKeywords: c.excludeKeywords || "",
      minAmount: c.minAmount || "", maxAmount: c.maxAmount || "",
      qualification: c.qualification || "",
      projectTypes: Array.isArray(c.projectTypes) ? c.projectTypes : [],
      projectStages: Array.isArray(c.projectStages) ? c.projectStages : [],
      bidMethods: Array.isArray(c.bidMethods) ? c.bidMethods : [],
      noticeTypes: Array.isArray(c.noticeTypes) ? c.noticeTypes : [],
      sourceScope: c.sourceScope || "all",
      sources: Array.isArray(c.sources) ? c.sources : [],
    });
  } else {
    resetDlg();
    dlg.visible = true;
  }
}

async function loadList() {
  loading.value = true;
  try {
    const res: any = await listOpportunitySubscriptions();
    // ★ P1-1: 后端 enabled 序列化为 bool, 这里归一化为 0/1, 使后续 === 1 / === 0 比较与停用切换逻辑正确
    const items: SubItem[] = ((res?.data || []) as SubItem[]).map((s) => ({ ...s, enabled: s.enabled ? 1 : 0 }));
    // 过滤掉 product_type=opportunity 的(本组件仅展示商机订阅,订阅里的 sub byType 由 product_type 区分)
    allSubs.value = items;
    // 默认激活: 取 enabled=1 的第一个
    if (!activeSubId.value || !items.find((i) => i.id === activeSubId.value)) {
      const first = items.find((s) => s.enabled === 1) || items[0];
      activeSubId.value = first?.id ?? null;
    }
    countBySubId.value = {};
    items.forEach((s) => { countBySubId.value[s.id] = s.lastMatchCount || 0; });
    runCurrent();
  } catch (e) {
    // api 拦截器已弹错
  } finally {
    loading.value = false;
  }
}

// 解析金额范围字符串: "500-2000" | "10000+" → [min, max]
function parseAmountRange(v: string): [number | undefined, number | undefined] {
  if (!v) return [undefined, undefined];
  if (v.endsWith("+")) { const n = Number(v.slice(0, -1)); return [Number.isFinite(n) ? n : undefined, undefined]; }
  const [a, b] = v.split("-");
  const min = a ? Number(a) : undefined;
  const max = b ? Number(b) : undefined;
  return [Number.isFinite(min as number) ? min : undefined, Number.isFinite(max as number) ? max : undefined];
}

async function runCurrent(page = 1) {
  if (!activeSub.value) { results.value = []; total.value = 0; return; }
  searching.value = true;
  try {
    const cond = (activeSub.value.condition || {}) as Record<string, any>;
    const fAmt = parseAmountRange(filter.amount);
    // 排除词: 订阅对话框存的是空格分隔字符串, 统一拆为数组下发
    const excl = cond.excludeKeywords
      ? String(cond.excludeKeywords).split(/\s+/).map((s: string) => s.trim()).filter(Boolean)
      : undefined;

    if (tab.value === "bid") {
      // 招投标信息: 查 BidNotice(公告类型/招标方式/来源/排除词均参与过滤, P1-7)
      const bidPayload: Record<string, any> = {
        keyword: cond.keywords || filter.keyword || undefined,
        region: cond.region || filter.region || undefined,
        notice_types: cond.noticeTypes && cond.noticeTypes.length ? cond.noticeTypes : undefined,
        bid_methods: cond.bidMethods && cond.bidMethods.length ? cond.bidMethods : undefined,
        sources: cond.sources && cond.sources.length ? cond.sources : undefined,
        exclude_keywords: excl,
        page,
        page_size: pageSize.value,
      };
      Object.keys(bidPayload).forEach((k) => bidPayload[k] === undefined && delete bidPayload[k]);
      const res: any = await api.post("/public/bids/search", bidPayload);
      results.value = (res?.data?.items || []) as any[];
      total.value = (res?.data?.total || 0) as number;
    } else {
      // 商机 / 拟建信息: 查 Opportunity, 数据集随 Tab 切换(P1-11 假多 Tab 修正)
      const ds = tab.value === "tender" ? "proposed" : "project";
      const payload: Record<string, any> = {
        dataset_type: ds,
        owner_name: cond.owner || filter.owner || undefined,
        owner_type: cond.ownerType || cond.owner_type || undefined,
        region_province: cond.region || filter.region || undefined,
        project_name: cond.keywords || filter.keyword || undefined,
        stage: cond.stage || filter.stage || undefined,
        amount_min: cond.minAmount ? Number(cond.minAmount) : fAmt[0],
        amount_max: cond.maxAmount ? Number(cond.maxAmount) : fAmt[1],
        project_type: (cond.projectTypes && cond.projectTypes.length) ? cond.projectTypes[0]
          : (cond.project_type || undefined),
        exclude_keywords: excl,
        tags: Array.isArray(cond.tags) && cond.tags.length ? cond.tags : undefined,
        page,
        page_size: pageSize.value,
      };
      Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
      const res: any = await api.post("/public/opportunities/search", payload);
      results.value = (res?.data?.items || []) as any[];
      total.value = (res?.data?.total || 0) as number;
    }
    currentPage.value = page;
    countBySubId.value = { ...countBySubId.value, [activeSub.value.id]: total.value };
  } catch {
    results.value = [];
    total.value = 0;
  } finally {
    searching.value = false;
  }
}

// 页码切换: 保留当前筛选/排序条件, 仅翻页
function handlePageChange(p: number) {
  currentPage.value = p;
  runCurrent(p);
}

// 每页条数切换: 重置到第 1 页并保留筛选/排序条件
function handleSizeChange(s: number) {
  pageSize.value = s;
  currentPage.value = 1;
  runCurrent(1);
}

// 切换订阅方案: 回到第 1 页并重新拉取(保留筛选框内容)
function selectSub(s: SubItem) {
  if (activeSubId.value === s.id) return;
  activeSubId.value = s.id;
  currentPage.value = 1;
  runCurrent(1);
}

function resetFilter() {
  filter.keyword = ""; filter.region = ""; filter.owner = ""; filter.stage = ""; filter.amount = "";
  currentPage.value = 1;
  runCurrent(1);
}

async function saveSub() {
  if (!dlg.name.trim()) { ElMessage.warning("请输入订阅名称"); return; }
  const condition = {
    owner: dlg.owner.trim(),
    ownerType: dlg.ownerType,
    region: dlg.region.trim(),
    keywords: dlg.keywords.trim(),
    excludeKeywords: dlg.excludeKeywords.trim(),
    minAmount: dlg.minAmount,
    maxAmount: dlg.maxAmount,
    qualification: dlg.qualification,
    projectTypes: dlg.projectTypes,
    projectStages: dlg.projectStages,
    bidMethods: dlg.bidMethods,
    noticeTypes: dlg.noticeTypes,
    sourceScope: dlg.sourceScope,
    sources: dlg.sources,
  };
  try {
    if (dlg.id) {
      // 更新: 走 toggle 或新增一个 PUT 接口简化版(client-side 暂用 create 新建+删除旧;以减少后端改动)
      // 这里直接调用原 toggle 函数更新 enabled;名称/条件编辑需要 PUT,先简化为删除+重建
      ElMessageBox.confirm("编辑订阅将删除旧订阅并重新创建,继续?", "提示", { type: "warning" })
        .then(async () => {
          await deleteOpportunitySubscription(dlg.id!);
          await createOpportunitySubscription({ name: dlg.name.trim(), condition });
          dlg.visible = false;
          ElMessage.success("已更新");
          loadList();
        })
        .catch(() => {});
    } else {
      await createOpportunitySubscription({ name: dlg.name.trim(), condition });
      dlg.visible = false;
      ElMessage.success("订阅已创建");
      loadList();
    }
  } catch {/* 拦截器处理 */}
}

async function toggleEnabled(s: SubItem) {
  try {
    await toggleOpportunitySubscription(s.id, s.enabled === 1 ? false : true);
    s.enabled = s.enabled === 1 ? 0 : 1;
    ElMessage.success("已切换");
  } catch {/* 拦截器处理 */}
}

async function removeOne(s: SubItem) {
  await ElMessageBox.confirm(`确认删除订阅「${s.name}」?`, "提示", { type: "warning" });
  try {
    await deleteOpportunitySubscription(s.id);
    ElMessage.success("已删除");
    if (activeSubId.value === s.id) activeSubId.value = null;
    loadList();
  } catch {/* 拦截器处理 */}
}

function openItem(r: any) {
  const id = r.id;
  if (!id) return;
  // P1-6: 优先跳底层情报详情(含 intentId); 招投标结果跳真实来源; 均无则回情报列表, 不再开空白页
  if (r.intentId) {
    router.push(`/site/intelligence/${r.intentId}`);
    return;
  }
  if (tab.value === "bid") {
    if (r.url) window.open(r.url, "_blank", "noopener");
    return;
  }
  router.push("/site/intelligence");
}

function formatAmount(amount?: number | string, wan?: number | string) {
  const v = amount ?? (wan ? Number(wan) : null);
  if (!v) return "";
  if (typeof v === "number" && v > 100) return `${v.toLocaleString()} 万`;
  if (typeof v === "number") return `${v.toLocaleString()} 万`;
  return `${v} 万`;
}

function formatDate(s?: string | null) {
  if (!s) return "—";
  try { return new Date(s).toISOString().slice(0, 10); } catch { return "—"; }
}

onMounted(() => {
  if (!allSubs.value.length) loadList();
});
</script>

<style scoped>
.bc {
  margin-bottom: 16px;
  font-size: 13px;
}
.bc :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--site-text, #141414);
  font-weight: 600;
}
.sub-tabs {
  margin-bottom: 8px;
}
.sub-tabs :deep(.el-tabs__nav-wrap)::after {
  background: #f0f2f5;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0 12px;
  border-bottom: 1px solid #f0f2f5;
}
.tb-h {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--site-text, #141414);
}
.tb-actions {
  display: flex;
  gap: 8px;
}
.sub-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 0;
}
.sub-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #c8d3e3;
  border-radius: 999px;
  padding: 4px 12px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
}
.sub-chip strong {
  font-weight: 600;
  color: var(--site-text, #141414);
}
.sub-chip em {
  font-style: normal;
  font-size: 11.5px;
  color: var(--site-text-mute, #9ca3af);
}
.sub-chip.on {
  border-color: var(--site-brand, #c8102e);
  background: #fdf2f3;
}
.sub-chip.on strong {
  color: var(--site-brand, #c8102e);
}
.sub-chip.deleted {
  opacity: 0.55;
}
.sub-chip-edit, .sub-chip-del {
  font-size: 13px;
  color: var(--site-text-mute, #9ca3af);
  cursor: pointer;
  padding: 2px;
}
.sub-chip-edit:hover {
  color: var(--site-brand, #c8102e);
}
.sub-chip-del:hover {
  color: var(--el-color-danger);
}
.search-bar {
  background: #f7f9fc;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}
.sb-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}
.sb-input {
  width: 100%;
}
.sb-actions {
  margin-top: 12px;
  text-align: right;
}
.results-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 4px 10px;
  font-size: 13px;
  color: var(--site-text-dim, #525252);
}
.results-head strong {
  color: var(--site-brand, #c8102e);
  font-weight: 700;
  font-family: var(--site-font-display);
  font-size: 16px;
  padding: 0 4px;
}
.results-sort {
  cursor: pointer;
}
.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed #f0f2f5;
}
.pager-wrap :deep(.el-pagination) {
  font-weight: 400;
}
@media (max-width: 900px) {
  .pager-wrap {
    justify-content: center;
  }
  .pager-wrap :deep(.el-pagination .el-pagination__sizes),
  .pager-wrap :deep(.el-pagination .el-pagination__jump) {
    display: none;
  }
}
.card-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.list-item {
  display: flex;
  gap: 14px;
  padding: 14px 6px;
  border-bottom: 1px dashed #f0f2f5;
}
.li-no {
  width: 28px;
  height: 22px;
  background: #f3f5f9;
  color: var(--site-text-mute, #9ca3af);
  font-size: 12px;
  text-align: center;
  border-radius: 4px;
  padding-top: 4px;
  flex-shrink: 0;
}
.li-body {
  flex: 1;
  min-width: 0;
}
.li-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}
.li-title {
  display: block;
  font-size: 14.5px;
  font-weight: 600;
  color: #1d4ba1;
  text-decoration: none;
  margin-bottom: 6px;
}
.li-title:hover {
  color: var(--site-brand, #c8102e);
}
.li-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12.5px;
  color: var(--site-text-dim, #525252);
}
.li-meta em {
  font-style: normal;
  color: var(--site-text, #141414);
}
.li-amount {
  color: var(--site-brand, #c8102e) !important;
  font-weight: 700;
}
.amount-input {
  width: 110px;
  margin-right: 8px;
}
.amount-input :deep(.el-input-group__append) {
  background: #f3f5f9;
  color: var(--site-text-dim, #525252);
  padding: 0 8px;
  border-left: 1px solid #dcdfe6;
}
.dash {
  color: var(--site-text-mute, #9ca3af);
  margin: 0 8px;
}
.type-checks {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 6px 14px;
  width: 100%;
  align-items: center;
}
.type-checks :deep(.el-checkbox) {
  margin-right: 0;
  width: 100%;
}
.type-checks :deep(.el-checkbox__label) {
  padding-left: 6px;
  font-size: 13px;
}
.add-qual {
  margin-left: 8px;
  color: var(--site-brand, #c8102e);
}
/* 自定义分组标题: 避开 el-divider 文字被全局规则隐藏问题 */
.form-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--site-text, #141414);
  padding: 8px 0 4px;
  margin: 8px 0 6px;
  border-bottom: 1px solid var(--site-panel-border, #e5e7eb);
  position: relative;
}
.form-section-title::before {
  content: "";
  position: absolute;
  left: 0;
  bottom: -1px;
  width: 32px;
  height: 2px;
  background: var(--site-brand, #c8102e);
}
.form-section-title:first-of-type {
  margin-top: 12px;
}
/* 弹窗 body 滚动 */
:deep(.el-dialog__body) {
  max-height: 65vh;
  overflow-y: auto;
  padding-right: 8px;
}
@media (max-width: 900px) {
  .sb-row { grid-template-columns: repeat(2, 1fr); }
  .type-checks { grid-template-columns: repeat(2, 1fr); }
}
</style>
