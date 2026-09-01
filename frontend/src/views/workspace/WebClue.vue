<template>
  <div class="webclue-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">网页线索</h2>
        <p class="page-desc">原始采集台账 · 中标/招标公告已自动解析进「项目管理」，采购意向见「意向信息」</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openManualDialog">
          <el-icon style="margin-right: 4px"><Link /></el-icon>手动抓取 URL
        </el-button>
      </div>
    </div>

    <div class="toolbar">
          <el-input
            v-model="query.keyword" placeholder="搜索标题/摘要" clearable style="width: 220px"
            @keyup.enter="loadClues" @clear="loadClues"
          />
          <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="loadClues">
            <el-option label="已通过" value="accepted" />
            <el-option label="已转实体" value="imported" />
          </el-select>
          <RegionCascader v-model="clueRegionVal" @change="onClueRegionChange" />
          <el-button type="primary" @click="loadClues">查询</el-button>
          <div style="flex: 1" />
          <el-button type="success" plain :loading="derivedLoading" @click="backfillDerived">
            <el-icon style="margin-right: 4px"><Link /></el-icon>补全解析关联
          </el-button>
          <el-button
            type="primary" plain :disabled="!selectedClues.length" :loading="enhancing" @click="enhanceClues"
          >
            AI 增强 ({{ selectedClues.length }})
          </el-button>
          <el-button
            type="danger" plain :disabled="!selectedClues.length" @click="batchRemoveClues"
          >
            批量删除 ({{ selectedClues.length }})
          </el-button>
          <el-button type="warning" plain :loading="exporting" @click="exportWebClues">
            <el-icon style="margin-right: 4px"><Download /></el-icon>导出 Excel
          </el-button>
        </div>

        <el-alert
          v-if="enhanceProg.show" type="info" :closable="false" show-icon
          style="margin: 12px 0"
        >
          <template #title>
            <span>AI 增强中 {{ enhanceProg.current }}/{{ enhanceProg.total }}：{{ enhanceProg.title }}</span>
          </template>
          <el-progress
            :percentage="Math.round((enhanceProg.current / enhanceProg.total) * 100)"
            :status="enhanceProg.current >= enhanceProg.total ? 'success' : ''"
            style="margin-top: 6px"
          />
          <div v-if="enhanceProg.lastResult" style="margin-top: 4px; font-size: 12px; color: #909399">
            {{ enhanceProg.lastResult }}
          </div>
        </el-alert>

        <el-table
          :data="clues" v-loading="clueLoading" stripe style="width: 100%"
          highlight-current-row
          @row-click="(row: any) => goDetail(row)"
          @selection-change="(rows: any[]) => selectedClues = rows"
        >
          <el-table-column type="selection" width="44" />
          <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="title-cell">
                <span class="clue-title" @click.stop="goDetail(row)">{{ row.title }}</span>
                <el-tag v-if="hasLLM(row)" size="small" type="success" effect="light" class="ai-tag">AI</el-tag>
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="source_name" label="来源" width="180" show-overflow-tooltip />
          <el-table-column prop="region" label="地域" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.region" size="small" type="warning">{{ row.region }}</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="hit_keywords" label="命中关键词" width="200">
            <template #default="{ row }">
              <el-tag
                v-for="k in (row.hit_keywords || '').split(',').filter(Boolean)"
                :key="k" size="small" style="margin-right: 4px"
              >{{ k }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="fetched_at" label="抓取时间" width="160">
            <template #default="{ row }">{{ formatTime(row.fetched_at) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="clueTypeOf(row).tag" size="small" effect="light">
                {{ clueTypeOf(row).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="解析状态" width="110">
            <template #default="{ row }">
              <el-tag v-if="hasDerived(row)" type="success" effect="light" size="small">已解析</el-tag>
              <el-tag v-else-if="hasBackfilled(row)" type="warning" effect="light" size="small">待解析</el-tag>
              <el-tag v-else type="info" effect="plain" size="small">未处理</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
              <el-button link type="danger" size="small" @click="removeClue(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pager">
          <el-pagination
            layout="total, prev, pager, next" :total="clueTotal" :page-size="query.page_size"
            :current-page="query.page" @current-change="(p: number) => { query.page = p; loadClues(); }"
          />
        </div>

    <!-- 手动抓取弹窗 -->
    <el-dialog v-model="showManual" title="手动抓取 URL（通过筛选才入库）" width="560px">
      <el-alert type="info" :closable="false" style="margin-bottom: 12px"
        title="支持逗号/换行分隔多个 URL；不满足关键词/地域规则的网页将被丢弃，不会进入列表。" />
      <el-form label-width="90px">
        <el-form-item label="URLs">
          <el-input v-model="manualForm.urls" type="textarea" :rows="5" placeholder="每行一个 URL" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="manualForm.keywords" placeholder="命中任一即通过，逗号分隔（可空=全部通过）" />
        </el-form-item>
        <el-form-item label="排除词">
          <el-input v-model="manualForm.exclude_keywords" placeholder="命中即丢弃，逗号分隔（可空）" />
        </el-form-item>
        <el-form-item label="地域">
          <el-input v-model="manualForm.regions" placeholder="命中地域词才标记，逗号分隔（可空=不限）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showManual = false">取消</el-button>
        <el-button type="primary" :loading="crawling" @click="submitManual">开始抓取</el-button>
      </template>
    </el-dialog>

    <!-- 抓取日志抽屉 -->
    <el-drawer v-model="showCrawlLog" :title="crawlLogTitle" size="520px" :close-on-click-modal="false">
      <div class="crawl-log-toolbar">
        <span class="crawl-log-status" :class="{ done: crawlDone, running: crawlRunning }">
          {{ crawlRunning ? "抓取中..." : (crawlDone ? "已完成" : "待开始") }}
        </span>
        <el-button size="small" @click="loadCrawlLogs" :disabled="!crawlTaskId">刷新</el-button>
      </div>
      <div class="crawl-log-box" ref="crawlLogBoxRef">
        <div v-for="(l, i) in crawlLogs" :key="i" class="crawl-log-line" :class="l.level">
          <span class="crawl-log-ts">{{ l.ts }}</span>
          <span class="crawl-log-msg">{{ l.msg }}</span>
        </div>
        <div v-if="!crawlLogs.length" class="crawl-log-empty">暂无日志</div>
      </div>
    </el-drawer>

    <!-- 抓取结果弹窗 -->
    <el-dialog v-model="showCrawlResult" title="抓取结果" width="760px" top="6vh">
      <div v-if="crawlResult" class="crawl-result">
        <!-- 统计卡片 -->
        <div class="result-stats">
          <div class="stat-card total">
            <div class="stat-num">{{ crawlResult.total }}</div>
            <div class="stat-label">共抓取</div>
          </div>
          <div class="stat-card ok">
            <div class="stat-num">{{ crawlResult.accepted }}</div>
            <div class="stat-label">入库</div>
          </div>
          <div class="stat-card drop">
            <div class="stat-num">{{ crawlResult.rejected }}</div>
            <div class="stat-label">丢弃</div>
          </div>
          <div class="stat-card rate">
            <div class="stat-num">{{ crawlResult.acceptedRate }}%</div>
            <div class="stat-label">通过率</div>
          </div>
        </div>

        <!-- 明细 -->
        <el-table :data="crawlResult.items" size="small" max-height="340" stripe class="result-table">
          <el-table-column label="#" type="index" width="46" />
          <el-table-column label="结果" width="90">
            <template #default="{ row }">
              <el-tag :type="row.ok ? 'success' : 'danger'" size="small" effect="light">
                {{ row.ok ? "入库" : "丢弃" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="公告标题" min-width="240" show-overflow-tooltip />
          <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.ok" class="reason-ok">—</span>
              <span v-else class="reason-drop">{{ row.reason }}</span>
            </template>
          </el-table-column>
        </el-table>

        <el-alert
          v-if="crawlResult.accepted === 0" type="warning" :closable="false"
          title="未抓到可入库线索：目标站点可能为 JS 动态页(需登录/验签)，或关键词未命中正文。可尝试更换来源或调整关键词。"
          style="margin-top: 12px"
        />
      </div>
      <template #footer>
        <el-button type="primary" @click="showCrawlResult = false">知道了</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "WebClue" });
import { ref, reactive, nextTick, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Link, Plus, Download } from "@element-plus/icons-vue";
import api from "@/api";
import RegionCascader from "@/components/RegionCascader.vue";

const router = useRouter();

// 线索列表地域筛选
const clueRegionVal = ref<string[]>([]);
const clueProvince = ref("");
const clueCity = ref("");
const clueCounty = ref("");
function onClueRegionChange(v: { province: string; city: string; county: string }) {
  clueProvince.value = v.province || "";
  clueCity.value = v.city || "";
  clueCounty.value = v.county || "";
  query.page = 1;
  loadClues();
}

// ---------- 线索列表 ----------
const clues = ref<any[]>([]);
const clueTotal = ref(0);
const clueLoading = ref(false);
const exporting = ref(false);
const query = reactive({ page: 1, page_size: 20, keyword: "", status: "" });

async function loadClues() {
  clueLoading.value = true;
  try {
    const params: any = { page: query.page, page_size: query.page_size, keyword: query.keyword, status: query.status };
    if (clueProvince.value) params.province = clueProvince.value;
    if (clueCity.value) params.city = clueCity.value;
    if (clueCounty.value) params.county = clueCounty.value;
    const res: any = await api.get("/web-clues", { params });
    clues.value = res.items || [];
    clueTotal.value = res.total || 0;
  } catch { /* 拦截器处理 */ }
  finally { clueLoading.value = false; }
}

async function exportWebClues() {
  exporting.value = true;
  try {
    const token = localStorage.getItem("ssm_token");
    const resp = await fetch("/api/v1/excel/export/web-clues", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) throw new Error("export failed");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `web_clues_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success("已导出 Excel");
  } catch {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

function formatTime(t?: string) {
  if (!t) return "-";
  return t.replace("T", " ").slice(0, 19);
}

// ---------- 抓取日志抽屉 ----------
const showCrawlLog = ref(false);
const crawlLogs = ref<any[]>([]);
const crawlLogTitle = ref("抓取日志");
const crawlTaskId = ref("");
const crawlRunning = ref(false);
const crawlDone = ref(false);
const crawlLogBoxRef = ref<any>(null);

// ---------- 抓取结果弹窗 ----------
const showCrawlResult = ref(false);
const crawlResult = ref<{ total: number; accepted: number; rejected: number; acceptedRate: number; items: any[] }>({
  total: 0, accepted: 0, rejected: 0, acceptedRate: 0, items: [],
});

// 从抓取日志解析结构化结果(统计 + 逐条明细)
function buildCrawlResult(logs: any[]) {
  const summary = logs.find((l) => /抓取完成|抓取失败/.test(l.msg));
  const m = summary?.msg.match(/共 (\d+) 条, 入库 (\d+) 条, 丢弃 (\d+) 条/);
  if (!m) {
    // 无统计行(失败), 只给基础信息
    showCrawlResult.value = false;
    return;
  }
  const total = Number(m[1]);
  const accepted = Number(m[2]);
  const rejected = Number(m[3]);
  const items = logs
    .filter((l) => /\[(\d+)\/\d+\]/.test(l.msg))
    .map((l) => {
      const idx = l.msg.match(/\[(\d+)\/\d+\]/)?.[1] || "";
      const isOk = /入库|✓/.test(l.msg);
      // 提取标题与原因: "[i/N] 入库: 标题" 或 "[i/N] 丢弃: 标题 — 原因" 或 "[i/N] ✗ 标题 — 原因"
      let title = l.msg.replace(/\[\d+\/\d+\]\s*/, "").replace(/^(入库|丢弃|✓|✗):?\s*/, "");
      let reason = "";
      const sep = title.indexOf("—");
      if (sep >= 0 && !isOk) {
        reason = title.slice(sep + 1).trim();
        title = title.slice(0, sep).trim();
      }
      return { idx, ok: isOk, title: title || l.msg, reason };
    });
  crawlResult.value = {
    total,
    accepted,
    rejected,
    acceptedRate: total ? Math.round((accepted / total) * 100) : 0,
    items,
  };
  showCrawlResult.value = true;
}
let crawlPollTimer: any = null;

async function loadCrawlLogs() {
  if (!crawlTaskId.value) return;
  try {
    const res: any = await api.get("/web-clues/logs", { params: { task_id: crawlTaskId.value } });
    crawlLogs.value = res.logs || [];
    // 自动滚到底部
    nextTick(() => {
      const el = crawlLogBoxRef.value?.$el || crawlLogBoxRef.value;
      if (el) el.scrollTop = el.scrollHeight;
    });
  } catch { /* 忽略 */ }
}

function stopCrawlPolling() {
  if (crawlPollTimer) { clearInterval(crawlPollTimer); crawlPollTimer = null; }
}

// ---------- 手动抓取 ----------
const showManual = ref(false);
const crawling = ref(false);
const manualForm = ref({ urls: "", keywords: "", exclude_keywords: "", regions: "" });

function openManualDialog() {
  showManual.value = true;
}

async function submitManual() {
  const urls = manualForm.value.urls.split(/\n|,/).map((u) => u.trim()).filter(Boolean);
  if (!urls.length) { ElMessage.warning("请填写 URL"); return; }
  crawling.value = true;
  try {
    const res: any = await api.post("/web-clues/crawl-manual", {
      urls, keywords: manualForm.value.keywords,
      exclude_keywords: manualForm.value.exclude_keywords,
      regions: manualForm.value.regions,
    });
    ElMessage.success(`抓取 ${res.total} 页, 通过 ${res.accepted} 条, 丢弃 ${res.rejected} 条`);
    showManual.value = false;
    manualForm.value.urls = "";
    loadClues();
  } catch { /* 拦截器处理 */ }
  finally { crawling.value = false; }
}

// ---------- 线索详情/删除 ----------
const selectedClues = ref<any[]>([]);
const enhancing = ref(false);
const enhanceProg = ref<{ show: boolean; current: number; total: number; title: string; lastResult: string }>({
  show: false, current: 0, total: 0, title: "", lastResult: "",
});

function goDetail(row: any) {
  router.push(`/workspace/web-clues/${row.id}`);
}

// 线索是否有 AI 增强结果(meta.llm)
function hasLLM(row: any) {
  const m = row?.meta;
  if (!m || typeof m !== "object") return false;
  return !!(m.llm && (m.llm.ai_summary || m.llm.ai_filter || m.llm.ai_extract));
}

// 线索是否已回填(backfill 处理过)
function hasBackfilled(row: any) {
  const m = row?.meta;
  return !!(m && typeof m === "object" && m.backfill_done);
}

// 线索是否已解析出实体关联(derived_project_id)
function hasDerived(row: any) {
  const m = row?.meta;
  return !!(m && typeof m === "object" && m.derived_project_id);
}

// 线索类型(按标题特征): 中标/成交 → 已入项目管理(completed); 招标/采购 → 招标中; 意向 → 超前信息
function clueTypeOf(row: any) {
  const t = row?.title || "";
  if (/中标|成交|结果公告/.test(t)) return { label: "中标", tag: "success" as const };
  if (/意向|采购需求|需求公示|采购计划|预公告/.test(t)) return { label: "意向", tag: "warning" as const };
  if (/招标|采购|磋商|询价|比选|谈判|竞价/.test(t)) return { label: "招标", tag: "primary" as const };
  return { label: "其他", tag: "info" as const };
}

// 补全历史线索的解析关联(只查不建)
const derivedLoading = ref(false);
async function backfillDerived() {
  derivedLoading.value = true;
  try {
    const res: any = await api.post("/web-clues/backfill-derived", null, { timeout: 120000 });
    if (res?.updated) ElMessage.success(`已补写 ${res.updated} 条线索的关联实体`);
    else ElMessage.info(res?.message || "无可补写的线索");
    loadClues();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "补全失败");
  } finally {
    derivedLoading.value = false;
  }
}

async function enhanceClues() {
  if (!selectedClues.value.length) return;
  const mode = await ElMessageBox.confirm(
    "对选中线索逐条执行 AI 增强？\n- 逐条生成 3 句要点总结\n- 逐条补充 LLM 抽取的结构化字段(项目编号/预算/资质/联系人)\n\n" +
    `耗时约 ${selectedClues.value.length * 15} 秒，会逐条回填并实时显示进度，请耐心等待。`,
    "AI 增强", { confirmButtonText: "开始", cancelButtonText: "取消", type: "info" }
  ).then(() => "all").catch(() => null);
  if (!mode) return;
  enhancing.value = true;
  enhanceProg.value = { show: true, current: 0, total: selectedClues.value.length, title: "准备中…", lastResult: "" };
  let done = 0;
  let errs = 0;
  try {
    // 逐条串行: 喂一条 → 后端处理并回填库 → 再喂下一条
    for (let i = 0; i < selectedClues.value.length; i++) {
      const row = selectedClues.value[i];
      enhanceProg.value.current = i + 1;
      enhanceProg.value.title = row.title?.slice(0, 24) || String(row.id);
      try {
        const res: any = await api.post("/web-clues/enhance", { ids: [row.id], mode }, { timeout: 600000 });
        if (res?.done?.length) {
          done++;
          const r = res.done[0];
          enhanceProg.value.lastResult = `✓ ${row.title?.slice(0, 16)}… 已回填（${r.mode || mode}）`;
        } else {
          errs++;
          const reason = res?.errors?.[0]?.error || "未知错误";
          enhanceProg.value.lastResult = `✗ ${row.title?.slice(0, 16)}… 失败：${reason}`;
        }
      } catch (e: any) {
        errs++;
        const reason = e?.response?.data?.detail || e?.message || "网络错误";
        enhanceProg.value.lastResult = `✗ ${row.title?.slice(0, 16)}… 异常：${reason}`;
      }
    }
    enhanceProg.value.title = "完成";
    if (errs) ElMessage.warning(`AI 增强完成: 成功 ${done} 条, 失败 ${errs} 条`);
    else ElMessage.success(`AI 增强完成: 成功 ${done} 条`);
    selectedClues.value = [];
    loadClues();
  } catch {
    enhanceProg.value.title = "已取消";
  } finally {
    enhancing.value = false;
    // 保留进度展示 3 秒后收起
    setTimeout(() => { enhanceProg.value.show = false; }, 3000);
  }
}

async function removeClue(row: any) {
  await ElMessageBox.confirm("确认删除该线索？", "提示", { type: "warning" });
  try {
    await api.delete(`/web-clues/${row.id}`);
    ElMessage.success("已删除");
    loadClues();
  } catch { /* 拦截器处理 */ }
}

async function batchRemoveClues() {
  if (!selectedClues.value.length) return;
  await ElMessageBox.confirm(
    `确认删除选中的 ${selectedClues.value.length} 条线索？此操作不可恢复。`,
    "批量删除", { type: "warning" }
  );
  try {
    const ids = selectedClues.value.map((c) => c.id);
    const res: any = await api.post("/web-clues/batch-delete", { ids });
    ElMessage.success(`已删除 ${res.deleted || ids.length} 条`);
    selectedClues.value = [];
    loadClues();
  } catch { /* 拦截器处理 */ }
}

onMounted(() => { loadClues(); });
onUnmounted(stopCrawlPolling);
</script>

<style scoped>
.webclue-page { padding: 4px; }
.intent-divider {
  margin: 20px 0 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #303133;
  font-size: 14px;
  font-weight: 600;
}
.intent-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: #e4e7ed;
}
.supplier-tag {
  display: inline-block; margin-right: 8px; margin-bottom: 2px;
  font-size: 12px; color: #4b6cb7; background: #eef4ff; border-radius: 4px; padding: 1px 6px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title { margin: 0; font-size: 20px; font-weight: 600; color: #1f2733; }
.page-desc { margin: 4px 0 0; font-size: 13px; color: #8a94a6; }
.header-actions { display: flex; gap: 8px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.pager { display: flex; justify-content: flex-end; margin-top: 14px; }
.form-tip { font-size: 12px; color: #8a94a6; margin-top: 4px; }
.clue-title { color: #2979ff; text-decoration: none; cursor: pointer; }
.clue-title:hover { text-decoration: underline; }
.title-cell { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; }
.ai-tag { flex-shrink: 0; }
.crawl-log-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.crawl-log-status { font-size: 13px; font-weight: 600; }
.crawl-log-status.running { color: #2979ff; }
.crawl-log-status.done { color: #67c23a; }
.crawl-log-box {
  background: #0f172a; border-radius: 8px; padding: 12px; height: 70vh;
  overflow-y: auto; font-family: "Cascadia Code", Consolas, monospace; font-size: 12px;
}
.crawl-log-line { display: flex; gap: 8px; padding: 3px 0; line-height: 1.6; }
.crawl-log-ts { color: #64748b; flex-shrink: 0; }
.crawl-log-msg { color: #cbd5e1; word-break: break-all; }
.crawl-log-line.error .crawl-log-msg { color: #f87171; }
.crawl-log-line.warn .crawl-log-msg { color: #fbbf24; }
.crawl-log-line.success .crawl-log-msg { color: #4ade80; }
.crawl-log-empty { color: #64748b; text-align: center; padding: 40px 0; }

/* ---------- 抓取结果弹窗 ---------- */
.crawl-result .result-stats {
  display: flex; gap: 12px; margin-bottom: 16px;
}
.crawl-result .stat-card {
  flex: 1; border-radius: 10px; padding: 14px 8px; text-align: center;
  background: #f7f9fc; border: 1px solid #ebeef5;
}
.crawl-result .stat-card .stat-num { font-size: 24px; font-weight: 700; }
.crawl-result .stat-card .stat-label { font-size: 12px; color: #8a94a6; margin-top: 4px; }
.crawl-result .stat-card.total .stat-num { color: #2979ff; }
.crawl-result .stat-card.ok .stat-num { color: #67c23a; }
.crawl-result .stat-card.drop .stat-num { color: #f56c6c; }
.crawl-result .stat-card.rate .stat-num { color: #e6a23c; }
.crawl-result .result-table { margin-top: 4px; }
.crawl-result .reason-ok { color: #b4bcc8; }
.crawl-result .reason-drop { color: #f56c6c; font-size: 12px; }

</style>
