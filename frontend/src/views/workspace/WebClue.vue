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
        <el-button @click="openSourceDialog()">
          <el-icon style="margin-right: 4px"><Plus /></el-icon>新增来源
        </el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <!-- 线索列表 -->
      <el-tab-pane label="线索列表" name="clues">
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
      </el-tab-pane>

      <!-- 来源站点 -->
      <el-tab-pane label="来源站点" name="sources">
        <el-table :data="sources" v-loading="sourceLoading" stripe style="width: 100%">
          <el-table-column prop="name" label="来源名称" width="200" show-overflow-tooltip />
          <el-table-column prop="url" label="URL" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <a :href="row.url" target="_blank" rel="noopener">{{ row.url }}</a>
            </template>
          </el-table-column>
          <el-table-column prop="keywords" label="关键词" width="180" show-overflow-tooltip />
          <el-table-column prop="regions" label="地域" width="140" show-overflow-tooltip />
          <el-table-column prop="scrape_mode" label="模式" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="row.scrape_mode === 'query' ? 'warning' : 'primary'">
                {{ modeLabel(row.scrape_mode) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="enabled" label="启用" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.enabled" @change="(v: boolean) => toggleSource(row, v)" />
            </template>
          </el-table-column>
          <el-table-column prop="last_run_result" label="上次抓取" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="crawlSource(row)">立即抓取</el-button>
              <el-button link type="primary" size="small" @click="openSourceDialog(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="removeSource(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

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

    <!-- 来源编辑弹窗 -->
    <el-dialog v-model="showSource" :title="sourceForm.id ? '编辑来源' : '新增来源'" width="640px">
      <el-form :model="sourceForm" label-width="100px">
        <el-form-item label="来源名称" required>
          <el-input v-model="sourceForm.name" placeholder="如:四川省公共资源交易中心" />
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="sourceForm.url" placeholder="列表页或种子页 URL" />
        </el-form-item>
        <el-form-item label="抓取模式">
          <el-radio-group v-model="sourceForm.scrape_mode">
            <el-radio value="crawl">整站抓取</el-radio>
            <el-radio value="scrape">单页抓取</el-radio>
            <el-radio value="query">查询式(验证码)</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="sourceForm.scrape_mode === 'query'">
          <el-alert type="warning" :closable="false" style="margin-bottom: 12px"
            title="查询式抓取: 适用于 JS 动态渲染 + 图形验证码的公告站点(如四川政府采购网)。系统自动 OCR 识别验证码并模拟点击查询。" />
          <el-form-item label="验证码框占位">
            <el-input v-model="queryCfg.captcha_placeholder" placeholder="验证码输入框 placeholder，默认: 验证码" />
          </el-form-item>
          <el-form-item label="查询按钮文本">
            <el-input v-model="queryCfg.query_button_text" placeholder="默认: 查询" />
          </el-form-item>
          <el-form-item label="验证码图关键字">
            <el-input v-model="queryCfg.captcha_img_keyword" placeholder="验证码 img src 含此关键字，默认: getVerify" />
          </el-form-item>
          <el-form-item label="列表接口关键字">
            <el-input v-model="queryCfg.api_url_keyword" placeholder="公告列表接口 URL 含此关键字，默认: selectInfoForIndex" />
          </el-form-item>
          <el-form-item label="结果路径">
            <el-input v-model="queryCfg.result_rows_jsonpath" placeholder="JSON 列表路径，默认: data.rows" />
          </el-form-item>
        </template>
        <el-form-item label="域名白名单">
          <el-input v-model="sourceForm.allow_domains" placeholder="逗号分隔, 如:ggzyjy.sc.gov.cn（空=不限）" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="sourceForm.keywords" placeholder="命中任一即通过, 逗号分隔" />
        </el-form-item>
        <el-form-item label="排除词">
          <el-input v-model="sourceForm.exclude_keywords" placeholder="命中即丢弃, 逗号分隔" />
        </el-form-item>
        <el-form-item label="地域限定">
          <el-input v-model="sourceForm.regions" placeholder="如:青川,广元,四川（空=不限）" />
        </el-form-item>
        <el-form-item label="AI 增强">
          <el-select v-model="sourceForm.llm_enhance" style="width: 200px">
            <el-option label="AI 语义筛选(默认)" value="filter" />
            <el-option label="筛选+总结" value="all" />
            <el-option label="仅总结" value="summary" />
            <el-option label="关闭" value="" />
          </el-select>
          <div class="form-tip">AI 筛选会剔除与生态修复/地质无关的公告(每条约 3-4 秒)</div>
        </el-form-item>
        <el-form-item label="最大深度/页数" v-if="sourceForm.scrape_mode === 'crawl'">
          <el-input-number v-model="sourceForm.max_depth" :min="0" :max="10" style="margin-right: 12px" />
          <el-input-number v-model="sourceForm.max_pages" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="sourceForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSource = false">取消</el-button>
        <el-button type="primary" @click="saveSource">保存</el-button>
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
import { ref, reactive, nextTick, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Link, Plus } from "@element-plus/icons-vue";
import api from "@/api";
import RegionCascader from "@/components/RegionCascader.vue";

const router = useRouter();

const activeTab = ref("clues");

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

function formatTime(t?: string) {
  if (!t) return "-";
  return t.replace("T", " ").slice(0, 19);
}

// ---------- 来源站点 ----------
const sources = ref<any[]>([]);
const sourceLoading = ref(false);

async function loadSources() {
  sourceLoading.value = true;
  try {
    const res: any = await api.get("/web-clues/sources", { params: { page: 1, page_size: 100 } });
    sources.value = res.items || [];
  } catch { /* 拦截器处理 */ }
  finally { sourceLoading.value = false; }
}

async function toggleSource(row: any, v: boolean) {
  try {
    await api.put(`/web-clues/sources/${row.id}`, { enabled: v });
    row.enabled = v;
    ElMessage.success(v ? "已启用" : "已禁用");
  } catch { /* 拦截器处理 */ }
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

async function crawlSource(row: any) {
  stopCrawlPolling();
  crawlLogs.value = [];
  crawlTaskId.value = "";
  crawlRunning.value = true;
  crawlDone.value = false;
  crawlLogTitle.value = `抓取日志 - ${row.name}`;
  showCrawlLog.value = true;

  // 续看已有任务: 若该来源正在抓取, 直接打开其任务日志
  async function resumeExisting(taskId: string) {
    crawlTaskId.value = taskId;
    crawlLogTitle.value = `抓取日志 - ${row.name}（进行中，续看）`;
    await loadCrawlLogs();
    crawlPollTimer = setTimeout(poll, 1000);
  }

  // 轮询日志, 检测完成标记
  async function poll() {
    if (!crawlTaskId.value) return;
    await loadCrawlLogs();
    const logs = crawlLogs.value;
    const last = logs[logs.length - 1];
    if (last && (/抓取完成/.test(last.msg) || /抓取失败/.test(last.msg) || /异常/.test(last.msg))) {
      stopCrawlPolling();
      crawlDone.value = true;
      crawlRunning.value = false;
      // 从日志解析结构化结果并弹出美观弹窗
      buildCrawlResult(logs);
      loadSources();
      loadClues();
    } else {
      crawlPollTimer = setTimeout(poll, 1500);
    }
  }

  try {
    const res: any = await api.post(`/web-clues/crawl-source/${row.id}`, null, { timeout: 30000 });
    if (res?.resumed && res?.task_id) {
      // 该来源正在抓取: 续看现有任务日志, 不重复提交
      ElMessage.info("该来源正在抓取中，已为您打开当前进度日志");
      await resumeExisting(res.task_id);
    } else if (res?.task_id) {
      crawlTaskId.value = res.task_id;
      crawlPollTimer = setTimeout(poll, 1000);
      // 也轮询抓取结果(从日志统计)
    }
  } catch (e: any) {
    crawlDone.value = true;
    crawlRunning.value = false;
    ElMessage.error(`提交抓取失败: ${e?.response?.data?.detail || e?.message || "未知错误"}`);
  }
}

async function removeSource(row: any) {
  await ElMessageBox.confirm(`确认删除来源「${row.name}」？`, "提示", { type: "warning" });
  try {
    await api.delete(`/web-clues/sources/${row.id}`);
    ElMessage.success("已删除");
    loadSources();
  } catch { /* 拦截器处理 */ }
}

// ---------- 来源编辑 ----------
const showSource = ref(false);
const sourceForm = ref<any>({
  id: null, name: "", url: "", description: "", allow_domains: "",
  keywords: "", exclude_keywords: "", regions: "", scrape_mode: "crawl",
  max_depth: 1, max_pages: 50, llm_enhance: "filter", enabled: true,
});

function modeLabel(mode?: string) {
  const m = mode ?? "";
  return ({ crawl: "整站", scrape: "单页", query: "查询式" } as Record<string, string>)[m] || m;
}

// 查询式抓取配置(独立编辑, 保存时并入 sourceForm)
const queryCfg = ref<any>({
  captcha_placeholder: "验证码",
  query_button_text: "查询",
  captcha_img_keyword: "getVerify",
  api_url_keyword: "selectInfoForIndex",
  result_rows_jsonpath: "data.rows",
  captcha_refresh_keyword: "换一张",
});

const defaultSourceForm = () => ({
  id: null, name: "", url: "", description: "", allow_domains: "",
  keywords: "", exclude_keywords: "", regions: "", scrape_mode: "crawl",
  max_depth: 1, max_pages: 50, llm_enhance: "filter", enabled: true,
});

function openSourceDialog(row?: any) {
  sourceForm.value = row ? { ...row } : defaultSourceForm();
  // 回填查询配置
  queryCfg.value = {
    captcha_placeholder: "验证码",
    query_button_text: "查询",
    captcha_img_keyword: "getVerify",
    api_url_keyword: "selectInfoForIndex",
    result_rows_jsonpath: "data.rows",
    captcha_refresh_keyword: "换一张",
    ...((row?.query_config as any) || {}),
  };
  showSource.value = true;
}

async function saveSource() {
  const f = sourceForm.value;
  if (!f.name || !f.url) { ElMessage.warning("请填写名称和 URL"); return; }
  const payload: any = {
    name: f.name, url: f.url, description: f.description,
    allow_domains: f.allow_domains || "", keywords: f.keywords || "",
    exclude_keywords: f.exclude_keywords || "", regions: f.regions || "",
    scrape_mode: f.scrape_mode, max_depth: f.max_depth, max_pages: f.max_pages,
    llm_enhance: f.llm_enhance ?? "filter",
    enabled: f.enabled,
  };
  if (f.scrape_mode === "query") {
    payload.query_config = { ...queryCfg.value };
  }
  try {
    if (f.id) await api.put(`/web-clues/sources/${f.id}`, payload);
    else await api.post("/web-clues/sources", payload);
    ElMessage.success("已保存");
    showSource.value = false;
    loadSources();
  } catch { /* 拦截器处理 */ }
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

onMounted(() => { loadClues(); loadSources(); });
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
