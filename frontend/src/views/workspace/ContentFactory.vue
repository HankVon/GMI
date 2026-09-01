<!-- 内容工厂: 用中台数据自动生成「被 AI 引擎引用」的内容资产(草稿→审核→发布) -->
<template>
  <div class="content-page">
    <div class="page-head">
      <div>
        <h2>内容工厂</h2>
        <p class="page-desc">
          招标/中标/意向数据 → 自动生成行业报告/FAQ/公司档案 → 人工审核 → 发布为 AI 可引用的内容资产
        </p>
      </div>
      <div class="head-actions">
        <el-button type="primary" @click="openGenerate">
          <el-icon style="margin-right: 4px"><MagicStick /></el-icon>智能生成内容
        </el-button>
        <el-button :loading="loading" @click="loadAll"><el-icon style="margin-right: 4px"><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="14">
      <el-col :span="4" v-for="c in statCards" :key="c.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-num" :style="{ color: c.color }">{{ c.value }}</div>
          <div class="stat-label">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 内容列表 -->
    <el-card shadow="never" class="panel-card" style="margin-top: 14px">
      <div class="filter-bar">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 130px" @change="loadAssets">
          <el-option v-for="(label, v) in statusLabels" :key="v" :label="label" :value="v" />
        </el-select>
        <el-select v-model="filters.kind" placeholder="类型" clearable style="width: 160px" @change="loadAssets">
          <el-option v-for="k in kinds" :key="k.value" :label="k.label" :value="k.value" />
        </el-select>
        <span class="filter-total">共 {{ assetTotal }} 条</span>
      </div>
      <el-table :data="assets" size="small" :loading="loadingAssets">
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="openDetail(row)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="130">
          <template #default="{ row }">{{ kindLabel(row.kind) }}</template>
        </el-table-column>
        <el-table-column prop="channel_name" label="渠道" width="100" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusLabels[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建者" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="140" />
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openDetail(row)">查看</el-button>
            <el-button v-if="row.status === 'draft'" size="small" text type="warning" @click="submit(row)">提交审核</el-button>
            <el-button v-if="row.status === 'review'" size="small" text type="success" @click="approve(row)">发布</el-button>
            <el-button v-if="row.status === 'review'" size="small" text type="danger" @click="reject(row)">驳回</el-button>
            <el-button size="small" text type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page" :page-size="pageSize" :total="assetTotal"
        layout="prev, pager, next" small style="margin-top: 10px; justify-content: flex-end"
        @current-change="loadAssets"
      />
    </el-card>

    <!-- 生成对话框 -->
    <el-dialog v-model="genVisible" title="智能生成内容" width="600px">
      <el-form label-width="100px">
        <el-form-item label="内容类型" required>
          <el-radio-group v-model="genForm.kind" @change="onKindChange">
            <el-radio-button v-for="k in kinds" :key="k.value" :value="k.value">{{ k.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <template v-if="genForm.kind === 'industry_report'">
          <el-form-item label="统计窗口">
            <el-input-number v-model="genForm.days" :min="30" :max="1095" :step="30" /> 天
          </el-form-item>
        </template>
        <template v-if="genForm.kind === 'faq' || genForm.kind === 'article'">
          <el-form-item label="主题" required>
            <el-input v-model="genForm.topic" placeholder="例如: 生态修复项目招标" />
          </el-form-item>
        </template>
        <template v-if="genForm.kind === 'company_profile'">
          <el-form-item label="选择单位" required>
            <el-select v-model="genForm.company_id" filterable placeholder="选择平台中的单位" style="width: 100%">
              <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="目标渠道">
          <el-select v-model="genForm.channel" style="width: 100%">
            <el-option v-for="c in channels" :key="c.code" :label="c.name" :value="c.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <p class="gen-tip">
        生成由本地 Ollama 完成(约 10~60 秒); 若 Ollama 不可用将自动降级为数据模板。生成后为草稿, 需人工审核发布。
      </p>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="doGenerate">生成草稿</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="detail?.title || '内容详情'" size="680px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="类型">{{ kindLabel(detail.kind) }}</el-descriptions-item>
          <el-descriptions-item label="渠道">{{ detail.channel_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusType(detail.status)">{{ statusLabels[detail.status] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建者">{{ detail.created_by_name }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.published_url" label="发布链接" :span="2">
            <el-link :href="detail.published_url" target="_blank" type="primary" :underline="false">{{ detail.published_url }}</el-link>
          </el-descriptions-item>
        </el-descriptions>
        <el-alert
          v-if="detail.geo_feedback?.cite_count"
          type="success" :closable="false" style="margin-bottom: 10px"
          :title="`🎉 已被 AI 引用 ${detail.geo_feedback.cite_count} 次(最近 ${detail.geo_feedback.last_cited_at || '-'}) — GEO 闭环生效`"
        />
        <el-alert v-if="detail.review_comment" type="error" :closable="false" :title="`审核意见: ${detail.review_comment}`" style="margin-bottom: 10px" />
        <h4>摘要</h4>
        <p class="detail-summary">{{ detail.summary || '—' }}</p>
        <h4>正文(Markdown)</h4>
        <pre class="content-pre">{{ detail.content }}</pre>
        <template v-if="Object.keys(detail.source_data || {}).length">
          <h4>生成依据数据</h4>
          <pre class="content-pre small">{{ JSON.stringify(detail.source_data, null, 2) }}</pre>
        </template>
        <div class="detail-actions">
          <el-button type="primary" plain @click="loadJsonld(detail)">
            <el-icon style="margin-right: 4px"><DataAnalysis /></el-icon>生成 JSON-LD
          </el-button>
          <el-button v-if="detail.status === 'draft'" type="warning" @click="submit(detail)">提交审核</el-button>
          <el-button v-if="detail.status === 'review'" type="success" @click="approve(detail)">发布</el-button>
          <el-button v-if="detail.status === 'review'" type="danger" @click="reject(detail)">驳回</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- JSON-LD 对话框 -->
    <el-dialog v-model="jsonldVisible" title="Schema.org JSON-LD 结构化标注" width="680px">
      <p class="gen-tip">
        把下方代码粘贴到官网对应页面的 <code>&lt;head&gt;</code> 中，AI 引擎即可结构化理解该内容（{{ jsonldData?.schema_type || '' }} 类型），显著提升被引用概率。
      </p>
      <pre class="content-pre jsonld-pre">{{ jsonldData?.script_tag || jsonldData?.pretty || '生成中…' }}</pre>
      <template #footer>
        <el-button @click="jsonldVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyJsonld">
          <el-icon style="margin-right: 4px"><CopyDocument /></el-icon>复制代码
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "@/api";
import { Refresh, MagicStick, DataAnalysis, CopyDocument } from "@element-plus/icons-vue";

const loading = ref(false);
const stats = ref<any>({});
const assets = ref<any[]>([]);
const assetTotal = ref(0);
const page = ref(1);
const pageSize = 15;
const loadingAssets = ref(false);
const kinds = ref<any[]>([]);
const channels = ref<any[]>([]);
const companies = ref<any[]>([]);
const filters = reactive<any>({ status: "", kind: "" });

const statusLabels: any = { draft: "草稿", review: "待审核", published: "已发布", rejected: "已驳回" };
const statCards = computed(() => [
  { label: "内容资产总数", value: stats.value.total ?? 0, color: "#4d6bfe" },
  { label: "草稿", value: countOf("draft"), color: "#909399" },
  { label: "待审核", value: countOf("review"), color: "#ff9f43" },
  { label: "已发布", value: stats.value.published_count ?? 0, color: "#00b894" },
  { label: "已驳回", value: countOf("rejected"), color: "#ff6b6b" },
]);
function countOf(name: string) {
  return (stats.value.by_status || []).find((s: any) => s.name === name)?.count ?? 0;
}
function statusType(s: string) {
  return { draft: "info", review: "warning", published: "success", rejected: "danger" }[s] || "info";
}
function kindLabel(k: string) {
  return kinds.value.find((x) => x.value === k)?.label || k;
}

async function loadAll() {
  loading.value = true;
  await Promise.all([loadStats(), loadAssets(), loadKinds(), loadChannels(), loadCompanies()]);
  loading.value = false;
}
async function loadStats() {
  const r: any = await api.get("/content/stats");
  stats.value = r;
}
async function loadAssets() {
  loadingAssets.value = true;
  try {
    const params: any = { page: page.value, page_size: pageSize };
    if (filters.status) params.status = filters.status;
    if (filters.kind) params.kind = filters.kind;
    const r: any = await api.get("/content/assets", { params });
    assets.value = r.items || [];
    assetTotal.value = r.total || 0;
  } finally { loadingAssets.value = false; }
}
async function loadKinds() {
  const r: any = await api.get("/content/kinds");
  kinds.value = r.items || [];
}
async function loadChannels() {
  const r: any = await api.get("/content/channels");
  channels.value = r.items || [];
}
async function loadCompanies() {
  const r: any = await api.get("/companies", { params: { page: 1, page_size: 100 } });
  companies.value = r.items || [];
}

// ── 生成 ──
const genVisible = ref(false);
const generating = ref(false);
const genForm = reactive<any>({ kind: "industry_report", days: 365, topic: "", company_id: undefined, channel: "official_site" });
function openGenerate() { genVisible.value = true; }
function onKindChange() {
  if (genForm.kind === "industry_report") genForm.days = 365;
  if (genForm.kind === "faq" || genForm.kind === "article") genForm.topic = "";
}
async function doGenerate() {
  const params: any = { channel: genForm.channel };
  if (genForm.kind === "industry_report") params.days = genForm.days || 365;
  if (genForm.kind === "faq" || genForm.kind === "article") {
    if (!genForm.topic?.trim()) { ElMessage.warning("请填写主题"); return; }
    params.topic = genForm.topic.trim();
  }
  if (genForm.kind === "company_profile") {
    if (!genForm.company_id) { ElMessage.warning("请选择单位"); return; }
    params.company_id = genForm.company_id;
  }
  generating.value = true;
  try {
    const r: any = await api.post("/content/generate", { kind: genForm.kind, params });
    ElMessage.success(`已生成草稿：《${r.item.title}》`);
    genVisible.value = false;
    loadStats(); loadAssets();
  } catch { /* 拦截器已提示 */ }
  generating.value = false;
}

// ── 详情 / 流转 ──
const detailVisible = ref(false);
const detail = ref<any>(null);
function openDetail(row: any) { detail.value = row; detailVisible.value = true; }
async function submit(row: any) {
  await api.post(`/content/assets/${row.id}/submit`);
  ElMessage.success("已提交审核");
  refreshAfter();
}
async function approve(row: any) {
  const { value } = await ElMessageBox.prompt("发布链接(可空, 留空自动生成)", "发布内容", {
    confirmButtonText: "发布", cancelButtonText: "取消",
  }).catch(() => ({ value: "" }));
  await api.post(`/content/assets/${row.id}/approve`, { published_url: value });
  ElMessage.success("已发布");
  refreshAfter();
}
async function reject(row: any) {
  const { value } = await ElMessageBox.prompt("驳回意见", "驳回内容", {
    confirmButtonText: "驳回", cancelButtonText: "取消",
  }).catch(() => ({ value: "" }));
  await api.post(`/content/assets/${row.id}/reject`, { comment: value });
  ElMessage.success("已驳回");
  refreshAfter();
}
async function del(row: any) {
  await ElMessageBox.confirm(`删除内容《${row.title}》?`, "确认", { type: "warning" });
  await api.delete(`/content/assets/${row.id}`);
  refreshAfter();
}
function refreshAfter() {
  loadStats(); loadAssets();
  if (detail.value?.id) {
    api.get(`/content/assets/${detail.value.id}`).then((r: any) => { detail.value = r.item; });
  }
}

// ── JSON-LD ──
const jsonldVisible = ref(false);
const jsonldData = ref<any>(null);
async function loadJsonld(row: any) {
  const r: any = await api.get(`/content/assets/${row.id}/jsonld`);
  jsonldData.value = r;
  jsonldVisible.value = true;
}
async function copyJsonld() {
  const text = jsonldData.value?.script_tag || jsonldData.value?.pretty || "";
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success("已复制到剪贴板");
  } catch {
    ElMessage.warning("复制失败，请手动选择复制");
  }
}

onMounted(loadAll);
</script>

<style scoped>
.content-page { display: flex; flex-direction: column; gap: 14px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; }
.page-head h2 { margin: 0; font-size: 20px; color: #111827; }
.page-desc { margin: 6px 0 0; color: #8a94a6; font-size: 13px; }
.stat-card { border-radius: 12px; border: 1px solid #eef1f8; text-align: center; padding: 6px 0; }
.stat-num { font-size: 26px; font-weight: 700; }
.stat-label { color: #909399; font-size: 12.5px; margin-top: 4px; }
.panel-card { border-radius: 12px; border: 1px solid #eef1f8; }
.filter-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.filter-total { color: #909399; font-size: 12.5px; }
.gen-tip { color: #909399; font-size: 12.5px; margin: 4px 0 0 100px; }
h4 { margin: 14px 0 8px; color: #111827; font-size: 13.5px; }
.detail-summary { color: #4b5563; font-size: 13px; line-height: 1.6; background: #f6f8fc; border-radius: 8px; padding: 10px 12px; }
.content-pre {
  background: #f6f8fc; border-radius: 8px; padding: 12px; font-size: 12.5px;
  white-space: pre-wrap; word-break: break-word; max-height: 420px; overflow-y: auto; color: #4b5563; line-height: 1.7;
}
.content-pre.small { max-height: 240px; font-size: 11.5px; }
.detail-actions { margin-top: 16px; display: flex; gap: 8px; }
</style>
