<!--
  情报中心 · 情报管理
  功能: 情报列表(多条件筛选) / 录入 / 编辑 / 提交审核 / 审核(通过·驳回) /
        发布 / 下架 / 恢复 / 删除 / AI研判 / 联系人管理
  后端: /api/v1/admin/intelligence/*
-->
<template>
  <div class="intent-admin">
    <!-- 顶部统计 -->
    <el-row :gutter="14" class="stat-row">
      <el-col v-for="s in statCards" :key="s.key" :xs="12" :sm="8" :md="4">
        <div class="stat-card" @click="quickFilter(s.key)">
          <div class="stat-num">{{ stats.wf_status?.[s.key] ?? 0 }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 筛选 -->
    <el-card class="filter-card" shadow="never">
      <div class="filters">
        <el-input v-model="filters.keyword" placeholder="标题/部门 模糊搜索" clearable size="small" style="width: 190px" @keyup.enter="loadList(1)" />
        <el-input v-model="filters.province" placeholder="省" clearable size="small" style="width: 90px" />
        <el-input v-model="filters.city" placeholder="市" clearable size="small" style="width: 90px" />
        <el-select v-model="filters.wf_status" placeholder="流转状态" clearable size="small" style="width: 120px">
          <el-option label="草稿" value="draft" />
          <el-option label="待审核" value="pending" />
          <el-option label="审核通过" value="approved" />
          <el-option label="已发布" value="published" />
          <el-option label="已下架" value="offline" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-select v-model="filters.industry" placeholder="行业" clearable size="small" style="width: 130px" filterable>
          <el-option v-for="c in industryOptions" :key="c.id" :label="c.label" :value="c.label" />
        </el-select>
        <el-select v-model="filters.dataset_type" placeholder="数据集" clearable size="small" style="width: 120px">
          <el-option label="项目" value="project" />
          <el-option label="拟建" value="proposed" />
          <el-option label="土地交易" value="landTrade" />
        </el-select>
        <el-select v-model="filters.quality_level" placeholder="字段体检" clearable size="small" style="width: 150px">
          <el-option label="完整(可发布)" value="ok" />
          <el-option label="缺加分项(可发布)" value="warn" />
          <el-option label="缺核心字段(不可发布)" value="poor" />
        </el-select>
        <el-input v-model="filters.min_amount" placeholder="金额下限(万)" clearable size="small" style="width: 120px" type="number" />
        <el-button type="primary" size="small" @click="loadList(1)">
          <el-icon><Search /></el-icon>查询
        </el-button>
        <el-button size="small" @click="resetFilters">
          <el-icon><Refresh /></el-icon>重置
        </el-button>
        <el-button size="small" :loading="exporting" @click="exportCsv">
          <el-icon><Download /></el-icon>导出
        </el-button>
        <el-button type="success" size="small" class="ml-auto" @click="createItem">
          <el-icon><Plus /></el-icon>录入情报
        </el-button>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card class="list-card" shadow="never">
      <!-- 批量操作条 -->
      <div class="batch-bar" :class="selected.length ? 'is-active' : ''">
        <template v-if="selected.length">
          <span class="batch-count">已选 <b>{{ selected.length }}</b> 条</span>
          <el-button size="small" :loading="batching" @click="batchRecheck">重检字段</el-button>
          <el-button size="small" type="warning" :loading="batching" @click="batchSubmit">提交审核</el-button>
          <el-button size="small" type="success" :loading="batching" @click="batchReview(true)">审核通过</el-button>
          <el-button size="small" type="primary" :loading="batching" @click="batchPublish">发布</el-button>
          <el-button size="small" type="danger" :loading="batching" @click="batchReview(false)">驳回</el-button>
          <el-button size="small" link @click="clearSelection">清空选择</el-button>
        </template>
        <template v-else>
          <span class="batch-count">勾选情报后可批量审核 / 发布</span>
          <el-button size="small" :loading="recheckAlling" @click="recheckAll">
            重检全部{{ filters.wf_status ? '(当前状态)' : '' }}
          </el-button>
          <span class="batch-tip">历史数据首次使用请先重检, 否则显示「未检测」</span>
        </template>
      </div>
      <el-table
        ref="tableRef" :data="items" size="small" v-loading="loading" row-key="id"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="46" :reserve-selection="true" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="320" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="editItem(row)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="流转" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="wfColor(row.wf_status)">{{ row.wf_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="业务状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.status === 'new' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="字段体检" width="170">
          <template #default="{ row }">
            <div class="qc-cell">
              <el-tooltip
                v-if="row.quality?.missing_labels?.length"
                :content="`缺失: ${row.quality.missing_labels.join('、')}`" placement="top"
              >
                <el-tag size="small" effect="plain" :type="qcType(row.quality?.level)" class="qc-tag">
                  {{ row.quality.completeness }}% · 缺{{ row.quality.missing_labels.length }}项
                </el-tag>
              </el-tooltip>
              <el-tag v-else-if="row.quality" size="small" effect="plain" type="success" class="qc-tag">
                {{ row.quality.completeness }}% · 完整
              </el-tag>
              <span v-else class="qc-none" @click.stop="openQuality(row)">未检测</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="industry" label="行业" width="120" show-overflow-tooltip />
        <el-table-column prop="dept" label="发布部门" width="150" show-overflow-tooltip />
        <el-table-column label="金额(万)" width="100">
          <template #default="{ row }">{{ row.amount != null ? Number(row.amount).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="region" label="地域" width="110" show-overflow-tooltip />
        <el-table-column label="发布时间" width="100">
          <template #default="{ row }">{{ row.published_at ? row.published_at.slice(0, 10) : '-' }}</template>
        </el-table-column>
        <el-table-column label="商机" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.opp_version" size="small" type="warning" effect="plain">{{ row.opp_version }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="editItem(row)">编辑</el-button>
            <el-button v-if="row.wf_status === 'draft' || row.wf_status === 'rejected'" type="warning" link size="small" @click="submitItem(row)">提交审核</el-button>
            <el-button v-if="row.wf_status === 'pending'" type="success" link size="small" @click="openReview(row)">审核</el-button>
            <el-button v-if="row.wf_status === 'approved'" type="success" link size="small" @click="publishItem(row)">发布</el-button>
            <el-button v-if="row.wf_status === 'published'" type="danger" link size="small" @click="offlineItem(row)">下架</el-button>
            <el-button v-if="row.wf_status === 'offline'" type="success" link size="small" @click="restoreItem(row)">恢复</el-button>
            <el-button link size="small" @click="openQuality(row)">体检</el-button>
            <el-button link size="small" @click="openAi(row)">AI研判</el-button>
            <el-button v-if="row.opp_id" link size="small" @click="openVersions(row)">版本</el-button>
            <!-- <el-button link size="small" @click="openContacts(row)">联系人</el-button> -->
            <el-button type="danger" link size="small" @click="deleteItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page" v-model:page-size="pageSize"
        :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next"
        class="pager" @change="loadList()"
      />
    </el-card>

    <!-- 审核对话框 -->
    <el-dialog v-model="reviewVisible" title="情报审核" width="480px" append-to-body>
      <div class="review-intro">
        <div class="review-title">{{ reviewTarget?.title }}</div>
        <div class="review-meta">
          <span>行业: {{ reviewTarget?.industry || '-' }}</span>
          <span>地域: {{ reviewTarget?.region || '-' }}</span>
          <span>金额: {{ reviewTarget?.amount ?? '-' }}万</span>
        </div>
      </div>
      <el-input v-model="reviewComment" type="textarea" :rows="3" placeholder="审核意见(驳回时必填)" />
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="danger" :disabled="!reviewComment.trim()" :loading="reviewing" @click="doReview(false)">驳回</el-button>
        <el-button type="success" :loading="reviewing" @click="doReview(true)">通过</el-button>
      </template>
    </el-dialog>

    <!-- 字段体检报告 -->
    <el-drawer v-model="qcVisible" :title="`字段体检报告 · #${qcTarget?.id || ''}`" size="440px" append-to-body>
      <div v-if="qcTarget" class="qc-report">
        <div class="qc-head">
          <div class="qc-score" :class="qcTarget.quality?.level || 'none'">
            {{ qcTarget.quality?.completeness ?? 0 }}<small>%</small>
          </div>
          <div class="qc-head-right">
            <el-tag size="small" :type="qcType(qcTarget.quality?.level)">{{ qcLabel(qcTarget.quality?.level) }}</el-tag>
            <div class="qc-time">检测于 {{ qcTarget.quality?.checked_at || '-' }}</div>
          </div>
        </div>

        <div class="qc-block">
          <div class="qc-block-title">
            核心必填
            <span class="qc-hint">缺失将禁止发布</span>
          </div>
          <div v-if="qcTarget.quality?.missing_required_labels?.length" class="qc-tags">
            <el-tag v-for="l in qcTarget.quality.missing_required_labels" :key="l" size="small" type="danger" effect="plain">{{ l }}</el-tag>
          </div>
          <div v-else class="qc-pass">全部齐全</div>
        </div>

        <div class="qc-block">
          <div class="qc-block-title">
            加分项
            <span class="qc-hint">缺失可发布, 建议补全</span>
          </div>
          <div v-if="qcTarget.quality?.missing_optional_labels?.length" class="qc-tags">
            <el-tag v-for="l in qcTarget.quality.missing_optional_labels" :key="l" size="small" type="warning" effect="plain">{{ l }}</el-tag>
          </div>
          <div v-else class="qc-pass">全部齐全</div>
        </div>

        <div class="qc-actions">
          <el-button type="primary" size="small" @click="editItem(qcTarget)">去补全字段</el-button>
          <el-button size="small" :loading="rechecking" @click="recheckOne">重新检测</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- AI 研判结果 -->
    <el-dialog v-model="aiVisible" title="AI 深度研判" width="560px" append-to-body>
      <div v-if="aiLoading" class="ai-loading">
        <el-icon class="spin"><Loading /></el-icon>
        <span>正在调用本地大模型研判，弱算力下约需 1–2 分钟，请稍候…</span>
      </div>
      <template v-else-if="aiData">
        <div class="ai-summary">{{ aiData.analysis?.summary }}</div>
        <div class="ai-metrics">
          <div class="ai-metric"><span class="m-label">意向热度</span><span class="m-val heat">{{ aiData.analysis?.heat ?? '-' }}</span></div>
          <div class="ai-metric"><span class="m-label">合作概率</span><span class="m-val coop">{{ aiData.analysis?.coop_prob ?? '-' }}</span></div>
          <div class="ai-metric"><span class="m-label">研判来源</span><span class="m-val">{{ aiData.source }}</span></div>
        </div>
        <div v-if="aiData.analysis?.advice?.length" class="ai-block">
          <div class="ai-block-label">行动建议</div>
          <ul class="ai-list">
            <li v-for="(a, i) in aiData.analysis.advice" :key="i">{{ a }}</li>
          </ul>
        </div>
        <div v-if="aiData.note" class="ai-note">{{ aiData.note }}</div>
      </template>
    </el-dialog>

    <!-- 联系人抽屉 -->
    <el-drawer v-model="contactVisible" :title="`联系人管理 · #${contactTarget?.id || ''}`" size="480px" append-to-body>
      <el-form :inline="false" label-width="70px" class="contact-form">
        <el-form-item label="分组">
          <el-select v-model="contactForm.group" size="small" style="width: 100%">
            <el-option label="甲方" value="甲方" />
            <el-option label="设计师" value="设计师" />
            <el-option label="建造商" value="建造商" />
            <el-option label="分包" value="分包" />
          </el-select>
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="contactForm.name" size="small" /></el-form-item>
        <el-form-item label="职务"><el-input v-model="contactForm.role" size="small" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="contactForm.department" size="small" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="contactForm.phone" size="small" /></el-form-item>
        <el-form-item label="手机"><el-input v-model="contactForm.mobile" size="small" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="contactForm.address" size="small" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="contactForm.remark" type="textarea" :rows="2" size="small" /></el-form-item>
        <el-form-item>
          <el-button type="primary" size="small" :loading="contactSaving" @click="saveContact">保存联系人</el-button>
        </el-form-item>
      </el-form>
      <el-divider>已录入联系人</el-divider>
      <div v-for="c in contacts" :key="c.id" class="contact-item">
        <div class="c-main">
          <el-tag size="small" type="info" effect="plain">{{ c.group }}</el-tag>
          <span class="c-name">{{ c.name || '未命名' }}</span>
          <span class="c-role">{{ c.role || '' }}</span>
        </div>
        <div class="c-sub">
          <span>{{ c.phone || c.mobile || '-' }}</span>
          <el-button type="danger" link size="small" @click="deleteContact(c)">删除</el-button>
        </div>
      </div>
      <div v-if="!contacts.length" class="contact-empty">暂无联系人，请在上方录入</div>
    </el-drawer>

    <!-- 商机版本历史 -->
    <el-drawer v-model="versionsVisible" :title="`商机版本历史 · #${versionTarget?.id || ''}`" size="440px" append-to-body>
      <el-timeline>
        <el-timeline-item
          v-for="v in versions" :key="v.id"
          :timestamp="v.released_at || ''" placement="top"
          :color="v.version === versionTarget?.opp_version ? '#18ac4f' : '#cfdcf3'"
        >
          <div class="ver-row">
            <el-tag size="small" :type="v.version === versionTarget?.opp_version ? 'success' : 'info'" effect="plain">
              {{ v.version }}
            </el-tag>
            <span class="ver-op">{{ v.operator }}</span>
          </div>
          <div class="ver-summary">{{ v.change_summary }}</div>
        </el-timeline-item>
      </el-timeline>
      <div v-if="!versions.length" class="contact-empty">暂无版本记录</div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Refresh, Plus, Loading, Download } from "@element-plus/icons-vue";
import api from "@/api";

const router = useRouter();

const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const stats = ref<any>({ wf_status: {} });
const industryOptions = ref<any[]>([]);

const filters = reactive<Record<string, any>>({
  keyword: "", province: "", city: "",
  wf_status: "", industry: "", dataset_type: "", min_amount: "",
  quality_level: "",
});

const statCards = [
  { key: "draft", label: "草稿" },
  { key: "pending", label: "待审核" },
  { key: "approved", label: "审核通过" },
  { key: "published", label: "已发布" },
  { key: "offline", label: "已下架" },
];

const wfColor = (s: string): "success" | "warning" | "danger" | "info" | "primary" | undefined =>
  ({ draft: "info", pending: "warning", approved: "success", published: "success", offline: "danger", rejected: "danger" } as Record<string, "success" | "warning" | "danger" | "info" | "primary">)[s] || "info";

const statusLabel = (s: string) =>
  ({ new: "最新", qualified: "合格", skip: "跳过", expired: "过期" } as Record<string, string>)[s] || s || "-";

function loadStats() {
  api.get("/admin/intelligence/stats").then((r: any) => {
    if (r?.success) stats.value = r;
  }).catch(() => {});
}

async function loadList(targetPage?: number) {
  if (targetPage) page.value = targetPage;
  loading.value = true;
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value };
    if (filters.keyword) params.keyword = filters.keyword;
    if (filters.province) params.province = filters.province;
    if (filters.city) params.city = filters.city;
    if (filters.wf_status) params.wf_status = filters.wf_status;
    if (filters.industry) params.industry = filters.industry;
    if (filters.dataset_type) params.dataset_type = filters.dataset_type;
    if (filters.quality_level) params.quality_level = filters.quality_level;
    if (filters.min_amount) params.min_amount = filters.min_amount;
    const r: any = await api.get("/admin/intelligence/list", { params });
    if (r?.success) {
      items.value = r.items || [];
      total.value = r.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

function quickFilter(key: string) {
  filters.wf_status = key === filters.wf_status ? "" : key;
  loadList(1);
}

function resetFilters() {
  Object.keys(filters).forEach((k) => (filters[k] = ""));
  loadList(1);
}

async function loadCategories() {
  try {
    const r: any = await api.get("/admin/intelligence/categories", { params: { category: "industry" } });
    if (r?.success) industryOptions.value = r.items || [];
  } catch { /* 静默 */ }
}

function createItem() {
  router.push({ path: "/workspace/intent-admin/edit" });
}
function editItem(row: any) {
  router.push({ path: `/workspace/intent-admin/edit/${row.id}` });
}

async function submitItem(row: any) {
  const r: any = await api.post(`/admin/intelligence/${row.id}/submit`);
  if (r?.success) {
    ElMessage.success("已提交审核");
    loadList();
  }
}

// ── 审核 ──
const reviewVisible = ref(false);
const reviewTarget = ref<any>(null);
const reviewComment = ref("");
const reviewing = ref(false);

function openReview(row: any) {
  reviewTarget.value = row;
  reviewComment.value = "";
  reviewVisible.value = true;
}

async function doReview(approve: boolean) {
  if (!reviewTarget.value) return;
  reviewing.value = true;
  try {
    const r: any = await api.post(`/admin/intelligence/${reviewTarget.value.id}/review`, {
      approve, comment: reviewComment.value,
    });
    if (r?.success) {
      ElMessage.success(approve ? "审核通过" : "已驳回");
      reviewVisible.value = false;
      loadList();
      loadStats();
    }
  } finally {
    reviewing.value = false;
  }
}

// ── 发布 / 下架 / 恢复 ──
async function publishItem(row: any) {
  await ElMessageBox.confirm(`确认发布「${row.title.slice(0, 30)}」？发布后前台立即可见。`, "发布情报", { type: "warning" });
  const r: any = await api.post(`/admin/intelligence/${row.id}/publish`);
  if (r?.success) { ElMessage.success("已发布"); loadList(); loadStats(); }
}
async function offlineItem(row: any) {
  await ElMessageBox.confirm(`确认下架「${row.title.slice(0, 30)}」？前台将不再展示。`, "下架情报", { type: "warning" });
  const r: any = await api.post(`/admin/intelligence/${row.id}/offline`);
  if (r?.success) { ElMessage.success("已下架"); loadList(); loadStats(); }
}
async function restoreItem(row: any) {
  const r: any = await api.post(`/admin/intelligence/${row.id}/restore`);
  if (r?.success) { ElMessage.success("已恢复发布"); loadList(); loadStats(); }
}
async function deleteItem(row: any) {
  await ElMessageBox.confirm(`确认删除「${row.title.slice(0, 30)}」？此操作不可恢复。`, "删除情报", { type: "error" });
  const r: any = await api.delete(`/admin/intelligence/${row.id}`);
  if (r?.success) { ElMessage.success("已删除"); loadList(); loadStats(); }
}

// ── 字段体检 ──
const qcVisible = ref(false);
const qcTarget = ref<any>(null);
const rechecking = ref(false);

function qcType(level?: string): "success" | "warning" | "danger" | "info" | undefined {
  return ({ ok: "success", warn: "warning", poor: "danger" } as Record<string, "success" | "warning" | "danger" | "info">)[level || ""] || "info";
}
function qcLabel(level?: string) {
  return ({ ok: "完整 · 可发布", warn: "缺加分项 · 可发布", poor: "缺核心字段 · 不可发布" } as Record<string, string>)[level || ""] || "未检测";
}
function openQuality(row: any) {
  qcTarget.value = row;
  qcVisible.value = true;
}
async function recheckOne() {
  if (!qcTarget.value) return;
  rechecking.value = true;
  try {
    const r: any = await api.post(`/admin/intelligence/${qcTarget.value.id}/recheck`);
    if (r?.success) {
      const fresh = r.data;
      // 同步回列表行(避免整表刷新丢失勾选)
      const hit = items.value.find((i) => i.id === qcTarget.value.id);
      if (hit) hit.quality = fresh;
      qcTarget.value = { ...qcTarget.value, quality: fresh };
      ElMessage.success(`已重检: 完整度 ${fresh.completeness}%`);
    }
  } finally {
    rechecking.value = false;
  }
}

// ── 批量操作 ──
const tableRef = ref<any>(null);
const selected = ref<any[]>([]);
const batching = ref(false);

function onSelectionChange(rows: any[]) {
  selected.value = rows;
}
function clearSelection() {
  tableRef.value?.clearSelection();
  selected.value = [];
}
function batchIds() {
  return selected.value.map((s) => s.id);
}
/** 把后端返回的体检结果同步回列表行 */
function syncQuality(list: any[]) {
  const map = new Map(list.map((i: any) => [i.id, i.quality]));
  items.value.forEach((it) => { if (map.has(it.id)) it.quality = map.get(it.id); });
}

async function batchRecheck() {
  batching.value = true;
  try {
    const r: any = await api.post("/admin/intelligence/batch/recheck", { ids: batchIds() });
    if (r?.success) {
      syncQuality(r.data?.items || []);
      ElMessage.success(r.message || "重检完成");
    }
  } finally {
    batching.value = false;
  }
}

/** 全量重检: 为存量(未做过体检的)情报补齐体检结果 */
const recheckAlling = ref(false);
async function recheckAll() {
  recheckAlling.value = true;
  try {
    const r: any = await api.post("/admin/intelligence/batch/recheck-all", {
      wf_status: filters.wf_status || null,
      limit: 5000,
    });
    if (r?.success) {
      ElMessage.success(r.message || "已重检");
      loadList(); loadStats();
    }
  } finally {
    recheckAlling.value = false;
  }
}

async function batchSubmit() {
  batching.value = true;
  try {
    const r: any = await api.post("/admin/intelligence/batch/submit", { ids: batchIds() });
    if (r?.success) {
      ElMessage.success(r.message || "已提交审核");
      clearSelection(); loadList(); loadStats();
    }
  } finally {
    batching.value = false;
  }
}

async function batchReview(approve: boolean) {
  let comment = "";
  if (!approve) {
    try {
      const { value } = await ElMessageBox.prompt(
        "驳回原因将应用到所有选中项", "批量驳回",
        { inputType: "textarea", inputPlaceholder: "如: 核心字段缺失, 请补全后重新提交",
          inputValidator: (v: string) => (v && v.trim().length > 0) || "请填写驳回原因" },
      );
      comment = value || "";
    } catch {
      return; // 用户取消
    }
  }
  batching.value = true;
  try {
    const r: any = await api.post("/admin/intelligence/batch/review", {
      ids: batchIds(), approve, comment,
    });
    if (r?.success) {
      ElMessage.success(r.message || "已审核");
      clearSelection(); loadList(); loadStats();
    }
  } finally {
    batching.value = false;
  }
}

async function batchPublish() {
  batching.value = true;
  let blocked: any[] = [];
  try {
    const r: any = await api.post("/admin/intelligence/batch/publish", { ids: batchIds() });
    if (r?.success) {
      const data = r.data || {};
      blocked = data.blocked || [];
      const warned = (data.published || []).filter((p: any) => p.missing_optional?.length);
      let msg = r.message || "已发布";
      if (warned.length) msg += `；其中 ${warned.length} 条缺加分项, 已放行发布(建议后续补全)`;
      ElMessage({ type: blocked.length ? "warning" : "success", message: msg, duration: 4500, showClose: true });
      clearSelection(); loadList(); loadStats();
    }
  } finally {
    batching.value = false;
  }
  if (blocked.length) showBlocked(blocked);
}

function showBlocked(blocked: any[]) {
  const lines = blocked.slice(0, 8)
    .map((b) => `#${b.id} ${(b.title || "").slice(0, 24)} — ${b.reason}`);
  if (blocked.length > 8) lines.push(`...等共 ${blocked.length} 条`);
  ElMessageBox.alert(
    lines.join("<br/>"), "以下情报未发布(需先补全核心字段)",
    { dangerouslyUseHTMLString: true, confirmButtonText: "知道了" },
  ).catch(() => {}); // 关闭即忽略
}

// ── AI 研判 ──
const aiVisible = ref(false);
const aiLoading = ref(false);
const aiData = ref<any>(null);

async function openAi(row: any) {
  aiVisible.value = true;
  aiLoading.value = true;
  aiData.value = null;
  try {
    // 优先读缓存, 无缓存则触发生成
    const cached: any = await api.get(`/admin/intelligence/${row.id}/ai`);
    if (cached?.success && cached.found) {
      aiData.value = cached.data;
      return;
    }
    const r: any = await api.post(`/admin/intelligence/${row.id}/ai`);
    if (r?.success) aiData.value = r.data;
  } catch { /* 错误提示由拦截器处理 */ }
  finally {
    aiLoading.value = false;
  }
}

// ── 联系人 ──
const contactVisible = ref(false);
const contactTarget = ref<any>(null);
const contacts = ref<any[]>([]);
const contactSaving = ref(false);
const contactForm = reactive({
  group: "甲方", name: "", role: "", department: "",
  phone: "", mobile: "", address: "", remark: "",
});

async function openContacts(row: any) {
  contactTarget.value = row;
  contactVisible.value = true;
  Object.keys(contactForm).forEach((k) => (contactForm[k as keyof typeof contactForm] = ""));
  contactForm.group = "甲方";
  await loadContacts();
}

async function loadContacts() {
  if (!contactTarget.value) return;
  try {
    const r: any = await api.get(`/admin/intelligence/${contactTarget.value.id}/contacts`);
    if (r?.success) contacts.value = r.items || [];
  } catch { /* 静默 */ }
}

async function saveContact() {
  if (!contactTarget.value) return;
  contactSaving.value = true;
  try {
    const r: any = await api.post(`/admin/intelligence/${contactTarget.value.id}/contacts`, { ...contactForm });
    if (r?.success) {
      ElMessage.success("联系人已保存");
      Object.keys(contactForm).forEach((k) => (contactForm[k as keyof typeof contactForm] = ""));
      contactForm.group = "甲方";
      loadContacts();
    }
  } finally {
    contactSaving.value = false;
  }
}

async function deleteContact(c: any) {
  await ElMessageBox.confirm(`确认删除联系人「${c.name || '未命名'}」？`, "删除联系人", { type: "warning" });
  const r: any = await api.delete(`/admin/intelligence/contacts/${c.id}`);
  if (r?.success) { ElMessage.success("已删除"); loadContacts(); }
}

// ── 导出 CSV ──
const exporting = ref(false);
async function exportCsv() {
  exporting.value = true;
  try {
    const params: Record<string, any> = {};
    if (filters.keyword) params.keyword = filters.keyword;
    if (filters.province) params.province = filters.province;
    if (filters.city) params.city = filters.city;
    if (filters.wf_status) params.wf_status = filters.wf_status;
    if (filters.industry) params.industry = filters.industry;
    if (filters.dataset_type) params.dataset_type = filters.dataset_type;
    if (filters.quality_level) params.quality_level = filters.quality_level;
    if (filters.min_amount) params.min_amount = filters.min_amount;
    const resp: any = await api.get("/admin/intelligence/export", { params, responseType: "blob" });
    const url = URL.createObjectURL(new Blob([resp]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `intelligence_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}

// ── 商机版本历史 ──
const versionsVisible = ref(false);
const versions = ref<any[]>([]);
const versionTarget = ref<any>(null);
async function openVersions(row: any) {
  versionTarget.value = row;
  versionsVisible.value = true;
  versions.value = [];
  try {
    const r: any = await api.get(`/admin/intelligence/${row.id}/versions`);
    if (r?.success) versions.value = r.items || [];
  } catch { /* 静默 */ }
}

onMounted(() => {
  loadList(1);
  loadStats();
  loadCategories();
});
</script>

<style scoped>
.intent-admin { padding: 4px 0 30px; }
.stat-row { margin-bottom: 14px; }
.stat-card {
  background: #fff; border: 1px solid #e6ebf1; border-radius: 6px;
  padding: 12px 16px; cursor: pointer; transition: box-shadow .2s;
}
.stat-card:hover { box-shadow: 0 2px 10px rgba(47,123,224,.12); }
.stat-num { font-size: 22px; font-weight: 700; color: #2f7be0; }
.stat-label { font-size: 12px; color: #8a8e99; margin-top: 2px; }
.filter-card { margin-bottom: 14px; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.ml-auto { margin-left: auto; }
.list-card { border-radius: 6px; }
.pager { margin-top: 12px; justify-content: flex-end; }

/* 批量操作条 */
.batch-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 10px; padding: 8px 12px;
  background: #eef5ff; border: 1px solid #cfe2ff; border-radius: 6px;
}
.batch-count { font-size: 13px; color: #4a5260; }
.batch-count b { color: #2f7be0; font-size: 15px; }
.batch-bar:not(.is-active) { background: #f7f9fc; border-color: #e6ebf1; }
.batch-tip { font-size: 12px; color: #c0c4cc; }

/* 列表「字段体检」列 */
.qc-cell { display: flex; align-items: center; gap: 6px; }
.qc-tag { cursor: default; }
.qc-none { font-size: 12px; color: #c0c4cc; cursor: pointer; text-decoration: underline dotted; }
.qc-none:hover { color: #2f7be0; }

/* 体检报告抽屉 */
.qc-report { padding-bottom: 20px; }
.qc-head { display: flex; align-items: center; gap: 16px; margin-bottom: 18px; }
.qc-score { font-size: 32px; font-weight: 700; line-height: 1; color: #2f7be0; }
.qc-score small { font-size: 14px; margin-left: 2px; }
.qc-score.ok { color: #18ac4f; }
.qc-score.warn { color: #e6a23c; }
.qc-score.poor { color: #f56c6c; }
.qc-score.none { color: #c0c4cc; }
.qc-head-right { display: flex; flex-direction: column; gap: 4px; }
.qc-time { font-size: 12px; color: #a8adb8; }
.qc-block { margin-bottom: 16px; }
.qc-block-title { font-size: 13px; font-weight: 600; color: #1c2a3a; margin-bottom: 8px; }
.qc-hint { font-weight: normal; font-size: 12px; color: #a8adb8; margin-left: 6px; }
.qc-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.qc-pass { font-size: 13px; color: #18ac4f; }
.qc-actions { display: flex; gap: 8px; margin-top: 20px; }

.review-intro { margin-bottom: 14px; padding: 12px; background: #f4f7fb; border-radius: 6px; }
.review-title { font-size: 14px; font-weight: 600; color: #1c2a3a; margin-bottom: 6px; }
.review-meta { display: flex; gap: 14px; font-size: 12px; color: #8a8e99; flex-wrap: wrap; }

.ai-loading { display: flex; align-items: center; gap: 10px; padding: 30px 0; color: #4a5260; font-size: 13px; }
.ai-loading .spin { font-size: 18px; color: #2f7be0; animation: spin 1.1s linear infinite; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
.ai-summary {
  font-size: 13.5px; line-height: 1.8; color: #1c2a3a;
  background: #f4f7fb; border-left: 3px solid #2f7be0;
  padding: 12px 14px; border-radius: 4px; margin-bottom: 14px;
}
.ai-metrics { display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.ai-metric {
  flex: 1; min-width: 120px; background: #fff; border: 1px solid #e6ebf1;
  border-radius: 6px; padding: 10px; text-align: center;
}
.m-label { display: block; font-size: 12px; color: #8a8e99; }
.m-val { font-size: 20px; font-weight: 700; color: #1c2a3a; }
.m-val.heat { color: #f56c00; }
.m-val.coop { color: #18ac4f; }
.ai-block { margin-bottom: 12px; }
.ai-block-label { font-size: 13px; font-weight: 600; color: #2f7be0; margin-bottom: 6px; }
.ai-list { margin: 0; padding-left: 22px; }
.ai-list li { font-size: 13px; line-height: 1.9; color: #4a5260; }
.ai-note { font-size: 12px; color: #8a8e99; background: #fff8e1; padding: 8px 12px; border-radius: 4px; }

.contact-item {
  border: 1px solid #e6ebf1; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px;
}
.c-main { display: flex; align-items: center; gap: 8px; }
.c-name { font-size: 13.5px; font-weight: 600; color: #1c2a3a; }
.c-role { font-size: 12px; color: #8a8e99; }
.c-sub { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 12.5px; color: #4a5260; }
.contact-empty { text-align: center; color: #b5b9c2; font-size: 13px; padding: 30px 0; }
.ver-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.ver-op { font-size: 12px; color: #8a8e99; }
.ver-summary { font-size: 13px; color: #4a5260; line-height: 1.6; }
</style>
