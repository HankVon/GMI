<template>
  <div class="ds-page">
    <div class="page-head">
      <div>
        <h2>统一数据源管理中心</h2>
        <p class="sub">
          集中管理所有 crawl4ai 抓取来源（政府采购网 / 北京政采 / 查询式 / 整站爬取），
          配置筛选规则、一键触发抓取、查看运行健康度。
        </p>
      </div>
      <div class="head-actions">
        <el-button size="small" :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" size="small" @click="openCreate">
          <el-icon><Plus /></el-icon>新增数据源
        </el-button>
      </div>
    </div>

    <!-- 概览卡片 -->
    <div class="stat-row" v-if="!loading">
      <div class="stat-card">
        <div class="stat-num">{{ sources.length }}</div>
        <div class="stat-label">数据源总数</div>
      </div>
      <div class="stat-card ok">
        <div class="stat-num">{{ enabledCount }}</div>
        <div class="stat-label">启用中</div>
      </div>
      <div class="stat-card warn">
        <div class="stat-num">{{ sources.length - enabledCount }}</div>
        <div class="stat-label">已停用</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-num">{{ errorCount }}</div>
        <div class="stat-label">存在运行异常</div>
      </div>
      <div class="stat-card info">
        <div class="stat-num">{{ recentRunCount }}</div>
        <div class="stat-label">近 7 天有抓取</div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="keyword" placeholder="搜索来源名称 / URL" clearable style="width: 280px"
        @keyup.enter="load" @clear="load"
      />
      <el-select v-model="modeFilter" placeholder="抓取模式" clearable style="width: 160px" @change="load">
        <el-option v-for="(lbl, val) in SCRAPE_MODES" :key="val" :label="lbl" :value="val" />
      </el-select>
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 130px" @change="load">
        <el-option label="启用" value="enabled" />
        <el-option label="停用" value="disabled" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-card shadow="never">
      <el-table
        :data="rows" size="small" v-loading="loading" row-key="id"
        empty-text="暂无数据源 — 点击右上角「新增数据源」添加抓取来源"
        :default-sort="{ prop: 'last_run_at', order: 'descending' }"
      >
        <el-table-column prop="name" label="来源名称" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="name-cell">
              <span class="ds-name">{{ row.name }}</span>
              <el-tag v-if="row.last_error" size="small" type="danger" effect="plain">异常</el-tag>
            </div>
            <div class="ds-url" :title="row.url">
              <a :href="row.url" target="_blank" rel="noopener" @click.stop>{{ shortUrl(row.url) }}</a>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="抓取模式" width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="light">{{ SCRAPE_MODES[row.scrape_mode] || row.scrape_mode }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              :loading="row._toggling"
              @change="(v: boolean) => toggleEnabled(row, v)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" label="上次抓取" width="170" sortable>
          <template #default="{ row }">
            <span v-if="row.last_run_at">{{ fmtTime(row.last_run_at) }}</span>
            <span v-else class="muted">从未运行</span>
          </template>
        </el-table-column>
        <el-table-column label="运行结果" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.last_error" class="err-text" :title="row.last_error">{{ row.last_error }}</span>
            <span v-else-if="row.last_run_result" class="ok-text">{{ row.last_run_result }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :loading="row._crawling" @click="crawl(row)">
              <el-icon><VideoPlay /></el-icon>抓取
            </el-button>
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增 / 编辑 弹窗 -->
    <el-dialog
      v-model="showForm" :title="editingId ? '编辑数据源' : '新增数据源'"
      width="680px" top="5vh" @close="resetForm"
    >
      <el-form :model="form" label-width="110px" class="ds-form">
        <el-row :gutter="16">
          <el-col :span="14">
            <el-form-item label="来源名称" required>
              <el-input v-model="form.name" placeholder="如：四川省公共资源交易中心" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="启用">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="来源 URL" required>
          <el-input v-model="form.url" placeholder="列表页 / 种子页地址" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" placeholder="可选" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="抓取模式">
              <el-select v-model="form.scrape_mode" style="width: 100%" @change="onModeChange">
                <el-option v-for="(lbl, val) in SCRAPE_MODES" :key="val" :label="lbl" :value="val" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="最大深度">
              <el-input-number v-model="form.max_depth" :min="0" :max="10" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="最多页数">
              <el-input-number v-model="form.max_pages" :min="1" :max="1000" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="域名白名单">
          <el-input v-model="form.allow_domains" placeholder="逗号分隔，空=不限制域名" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="命中关键词">
              <el-input v-model="form.keywords" placeholder="逗号分隔，命中任一即通过" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排除关键词">
              <el-input v-model="form.exclude_keywords" placeholder="逗号分隔，命中即丢弃" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="地域限定">
          <el-input v-model="form.regions" placeholder="逗号分隔，空=不限" />
        </el-form-item>
        <el-form-item label="仅抓取匹配">
          <el-input v-model="form.include_urls" placeholder="仅抓取匹配的 URL 模式（可选）" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="LLM 增强">
              <el-select v-model="form.llm_enhance" style="width: 100%">
                <el-option v-for="(lbl, val) in LLM_MODES" :key="val" :label="lbl" :value="val" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="查询式配置" v-if="form.scrape_mode === 'query'">
          <el-input
            v-model="queryConfigText" type="textarea" :rows="5"
            placeholder='JSON，如 {"captcha_placeholder":"请输入验证码","query_button_text":"查询","result_rows_jsonpath":"$.data.list"}'
          />
          <div class="form-tip">仅在「查询式抓取」模式下生效；留空则使用默认配置。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 抓取日志抽屉 -->
    <el-drawer v-model="showLog" :title="`抓取：${crawlSourceName}`" size="540px" :close-on-click-modal="false">
      <div class="crawl-log-toolbar">
        <span class="crawl-log-status" :class="{ done: crawlDone, running: crawlRunning }">
          {{ crawlRunning ? "抓取中..." : (crawlDone ? "已完成" : "待开始") }}
        </span>
        <el-button size="small" @click="loadLogs" :disabled="!crawlTaskId">刷新</el-button>
      </div>
      <div class="crawl-log-box" ref="logBoxRef">
        <div v-for="(l, i) in crawlLogs" :key="i" class="crawl-log-line" :class="l.level">
          <span class="crawl-log-ts">{{ l.ts }}</span>
          <span class="crawl-log-msg">{{ l.msg }}</span>
        </div>
        <div v-if="!crawlLogs.length" class="crawl-log-empty">暂无日志</div>
      </div>
      <div v-if="crawlResult" class="crawl-result-mini">
        <el-tag type="info" size="small">共 {{ crawlResult.total }}</el-tag>
        <el-tag type="success" size="small">入库 {{ crawlResult.accepted }}</el-tag>
        <el-tag type="danger" size="small">丢弃 {{ crawlResult.rejected }}</el-tag>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh, Plus, VideoPlay } from "@element-plus/icons-vue";
import api from "@/api";

const SCRAPE_MODES: Record<string, string> = {
  crawl: "整站爬取",
  scrape: "单页抓取",
  query: "查询式抓取",
  ccgp_list: "政府采购网列表",
  beijing_list: "北京政采列表",
};
const LLM_MODES: Record<string, string> = {
  "": "关闭",
  filter: "AI 筛选",
  extract: "AI 抽取",
  summary: "AI 总结",
  all: "AI 全增强",
};

const loading = ref(false);
const sources = ref<any[]>([]);
const keyword = ref("");
const modeFilter = ref("");
const statusFilter = ref("");

const enabledCount = computed(() => sources.value.filter((s) => s.enabled).length);
const errorCount = computed(() => sources.value.filter((s) => s.last_error).length);
const recentRunCount = computed(() => {
  const cut = Date.now() - 7 * 24 * 3600 * 1000;
  return sources.value.filter((s) => s.last_run_at && new Date(s.last_run_at).getTime() >= cut).length;
});

const rows = computed(() => {
  let list = sources.value;
  if (modeFilter.value) list = list.filter((s) => s.scrape_mode === modeFilter.value);
  if (statusFilter.value === "enabled") list = list.filter((s) => s.enabled);
  else if (statusFilter.value === "disabled") list = list.filter((s) => !s.enabled);
  if (keyword.value.trim()) {
    const k = keyword.value.trim().toLowerCase();
    list = list.filter((s) => (s.name || "").toLowerCase().includes(k) || (s.url || "").toLowerCase().includes(k));
  }
  return list;
});

async function load() {
  loading.value = true;
  try {
    const res: any = await api.get("/web-clues/sources", { params: { page: 1, page_size: 100 } });
    sources.value = (res.items || []).map((s: any) => ({ ...s, _toggling: false, _crawling: false }));
  } catch {
    /* 拦截器处理 */
  } finally {
    loading.value = false;
  }
}

function fmtTime(t?: string) {
  if (!t) return "-";
  return t.replace("T", " ").slice(0, 16);
}
function shortUrl(u: string): string {
  if (!u) return "-";
  try {
    const p = new URL(u);
    return p.host + p.pathname.slice(0, 36);
  } catch {
    return u.slice(0, 50);
  }
}

// ---------- 启用/停用 ----------
async function toggleEnabled(row: any, val: boolean) {
  row._toggling = true;
  try {
    await api.put(`/web-clues/sources/${row.id}`, { enabled: val });
    row.enabled = val;
    ElMessage.success(val ? "已启用" : "已停用");
  } catch {
    /* 拦截器处理 */
  } finally {
    row._toggling = false;
  }
}

// ---------- 删除 ----------
async function remove(row: any) {
  await ElMessageBox.confirm(`确认删除数据源「${row.name}」？此操作不可恢复。`, "删除", { type: "warning" });
  try {
    await api.delete(`/web-clues/sources/${row.id}`);
    ElMessage.success("已删除");
    load();
  } catch {
    /* 拦截器处理 */
  }
}

// ---------- 新增 / 编辑 表单 ----------
const showForm = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
const queryConfigText = ref("");

const emptyForm = () => ({
  name: "",
  url: "",
  description: "",
  allow_domains: "",
  keywords: "",
  exclude_keywords: "",
  regions: "",
  scrape_mode: "crawl",
  max_depth: 1,
  max_pages: 50,
  include_urls: "",
  llm_enhance: "filter",
  enabled: true,
});
const form = reactive(emptyForm());

function resetForm() {
  Object.assign(form, emptyForm());
  queryConfigText.value = "";
  editingId.value = null;
}
function openCreate() {
  resetForm();
  showForm.value = true;
}
function openEdit(row: any) {
  Object.assign(form, {
    name: row.name,
    url: row.url,
    description: row.description || "",
    allow_domains: row.allow_domains || "",
    keywords: row.keywords || "",
    exclude_keywords: row.exclude_keywords || "",
    regions: row.regions || "",
    scrape_mode: row.scrape_mode,
    max_depth: row.max_depth ?? 1,
    max_pages: row.max_pages ?? 50,
    include_urls: row.include_urls || "",
    llm_enhance: row.llm_enhance || "",
    enabled: row.enabled,
  });
  queryConfigText.value = row.query_config ? JSON.stringify(row.query_config, null, 2) : "";
  editingId.value = row.id;
  showForm.value = true;
}
function onModeChange() {
  if (form.scrape_mode !== "query") queryConfigText.value = "";
}

async function submitForm() {
  if (!form.name.trim()) { ElMessage.warning("请填写来源名称"); return; }
  if (!form.url.trim()) { ElMessage.warning("请填写来源 URL"); return; }
  const payload: any = { ...form, name: form.name.trim(), url: form.url.trim() };
  if (form.scrape_mode === "query" && queryConfigText.value.trim()) {
    try {
      payload.query_config = JSON.parse(queryConfigText.value);
    } catch {
      ElMessage.error("查询式配置不是合法 JSON");
      return;
    }
  } else {
    payload.query_config = null;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await api.put(`/web-clues/sources/${editingId.value}`, payload);
      ElMessage.success("已保存");
    } else {
      await api.post("/web-clues/sources", payload);
      ElMessage.success("已新增");
    }
    showForm.value = false;
    load();
  } catch {
    /* 拦截器处理 */
  } finally {
    saving.value = false;
  }
}

// ---------- 抓取日志 ----------
const showLog = ref(false);
const crawlSourceName = ref("");
const crawlLogs = ref<any[]>([]);
const crawlTaskId = ref("");
const crawlRunning = ref(false);
const crawlDone = ref(false);
const crawlResult = ref<{ total: number; accepted: number; rejected: number } | null>(null);
const crawlRow = ref<any>(null);
const logBoxRef = ref<any>(null);
let logTimer: any = null;

function stopLogPolling() {
  if (logTimer) { clearInterval(logTimer); logTimer = null; }
}

async function crawl(row: any) {
  if (!row.enabled) {
    try {
      await ElMessageBox.confirm("该数据源已停用，仍要立即抓取吗？", "提示", { type: "warning" });
    } catch {
      return; // 用户取消
    }
  }
  row._crawling = true;
  crawlRow.value = row;
  showLog.value = true;
  crawlSourceName.value = row.name;
  crawlLogs.value = [];
  crawlTaskId.value = "";
  crawlRunning.value = true;
  crawlDone.value = false;
  crawlResult.value = null;
  try {
    const res: any = await api.post(`/web-clues/crawl-source/${row.id}`);
    crawlTaskId.value = res.task_id || "";
    if (res.resumed) {
      ElMessage.info("该来源已有抓取任务在运行，正复用其日志");
    }
    loadLogs();
    stopLogPolling();
    logTimer = setInterval(loadLogs, 2000);
  } catch {
    crawlRunning.value = false;
    row._crawling = false;
  }
}

async function loadLogs() {
  if (!crawlTaskId.value) return;
  try {
    const res: any = await api.get("/web-clues/logs", { params: { task_id: crawlTaskId.value } });
    crawlLogs.value = res.logs || [];
    nextTick(() => {
      const el = logBoxRef.value?.$el || logBoxRef.value;
      if (el) el.scrollTop = el.scrollHeight;
    });
    // 抓取完成判定
    const finished = crawlLogs.value.some((l: any) => /抓取完成|抓取失败/.test(l.msg));
    if (finished) {
      crawlRunning.value = false;
      crawlDone.value = true;
      stopLogPolling();
      if (crawlRow.value) crawlRow.value._crawling = false;
      const summary = crawlLogs.value.find((l: any) => /抓取完成/.test(l.msg));
      const m = summary?.msg.match(/共 (\d+) 条, 入库 (\d+) 条, 丢弃 (\d+) 条/);
      if (m) crawlResult.value = { total: +m[1], accepted: +m[2], rejected: +m[3] };
      // 刷新列表的运行结果
      load();
    }
  } catch {
    /* 忽略 */
  }
}

onMounted(load);
onUnmounted(stopLogPolling);
</script>

<style scoped>
.ds-page { padding: 4px 0 30px; }
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;
}
.page-head h2 { margin: 0 0 4px; font-size: 16px; color: #1c2a3a; }
.sub { margin: 0; font-size: 12px; color: #8a91a0; max-width: 760px; line-height: 1.6; }
.head-actions { display: flex; gap: 8px; }
.stat-row { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.stat-card {
  flex: 1; min-width: 120px; background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 14px 16px;
}
.stat-num { font-size: 24px; font-weight: 700; color: #1c2a3a; }
.stat-label { font-size: 12px; color: #8a91a0; margin-top: 4px; }
.stat-card.ok .stat-num { color: #67c23a; }
.stat-card.warn .stat-num { color: #e6a23c; }
.stat-card.danger .stat-num { color: #f56c6c; }
.stat-card.info .stat-num { color: #409eff; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.name-cell { display: flex; align-items: center; gap: 6px; }
.ds-name { font-weight: 600; color: #1c2a3a; }
.ds-url { font-size: 12px; color: #909399; margin-top: 2px; }
.ds-url a { color: #909399; text-decoration: none; }
.ds-url a:hover { color: #409eff; text-decoration: underline; }
.ok-text { color: #67c23a; font-size: 12px; }
.err-text { color: #f56c6c; font-size: 12px; }
.muted { color: #b5b9c2; }
.ds-form { padding-right: 10px; }
.form-tip { font-size: 12px; color: #8a91a0; margin-top: 4px; }
.crawl-log-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.crawl-log-status { font-size: 13px; font-weight: 600; }
.crawl-log-status.running { color: #2979ff; }
.crawl-log-status.done { color: #67c23a; }
.crawl-log-box {
  background: #0f172a; border-radius: 8px; padding: 12px; height: 64vh; overflow-y: auto;
  font-family: "Cascadia Code", Consolas, monospace; font-size: 12px;
}
.crawl-log-line { display: flex; gap: 8px; padding: 3px 0; line-height: 1.6; }
.crawl-log-ts { color: #64748b; flex-shrink: 0; }
.crawl-log-msg { color: #cbd5e1; word-break: break-all; }
.crawl-log-line.error .crawl-log-msg { color: #f87171; }
.crawl-log-line.warn .crawl-log-msg { color: #fbbf24; }
.crawl-log-line.success .crawl-log-msg { color: #4ade80; }
.crawl-log-empty { color: #64748b; text-align: center; padding: 40px 0; }
.crawl-result-mini { display: flex; gap: 8px; margin-top: 12px; }
</style>
