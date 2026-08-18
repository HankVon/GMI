<!-- 数据流水线: 采集 → 筛选入库 → 实体识别/图谱 → 前端字段回填 -->
<template>
  <div class="pipe-page">
    <div class="page-head">
      <div>
        <h2>数据流水线</h2>
        <p class="page-desc">多源采集 → 质量筛选(川藏新/时效/主题) → 实体识别建图谱 → 前端字段回填</p>
      </div>
      <div class="head-actions">
        <el-button :loading="running" type="primary" @click="runFull">
          <el-icon style="margin-right: 4px"><VideoPlay /></el-icon>全链路执行
        </el-button>
        <el-button :loading="loading" @click="loadStats"><el-icon style="margin-right: 4px"><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <!-- 运行状态 -->
    <el-card v-if="running || statusMsg" class="status-card" shadow="never">
      <div class="status-line">
        <el-icon class="is-loading" color="#2979ff"><Loading /></el-icon>
        <span>{{ statusMsg || '流水线执行中…' }}</span>
        <el-tag v-if="statusData?.current_stage" size="small" type="warning">阶段: {{ stageLabel(statusData.current_stage) }}</el-tag>
        <el-tag v-if="control?.mode === 'paused'" size="small" type="danger" effect="dark">已暂停</el-tag>
        <el-tag v-if="control?.done_count" size="small" type="info">已处理 {{ control.done_count }} 条</el-tag>
        <span class="status-controls">
          <el-button size="small" type="warning" plain v-if="control?.mode !== 'paused'" @click="doControl('pause')">
            <el-icon style="margin-right: 4px"><VideoPause /></el-icon>暂停
          </el-button>
          <el-button size="small" type="success" plain v-else @click="doControl('resume')">
            <el-icon style="margin-right: 4px"><VideoPlay /></el-icon>继续
          </el-button>
          <el-button size="small" type="danger" plain @click="doControl('stop')">
            <el-icon style="margin-right: 4px"><SwitchButton /></el-icon>停止(断点续跑)
          </el-button>
        </span>
      </div>
      <div class="control-tip" v-if="control?.mode === 'paused'">已暂停 — 当前单位处理完成后进入等待, 点「继续」从暂停处继续</div>
      <div class="control-tip" v-else-if="control?.mode === 'stopping'">正在停止 — 当前单位处理完后停止, 断点已记录, 下次启动从断点继续</div>
    </el-card>

    <!-- 运行过程日志(实时) -->
    <el-card class="log-card" shadow="never">
      <template #header>
        <div class="section-header">
          <span class="section-title">运行过程日志</span>
          <span class="section-sub" v-if="pipeLogs.length">共 {{ pipeLogs.length }} 条</span>
          <div class="log-actions">
            <el-button size="small" plain type="primary" :loading="loadingLogs" @click="loadLogs">
              <el-icon style="margin-right: 4px"><Refresh /></el-icon>刷新
            </el-button>
            <el-button size="small" plain type="danger" @click="clearLogs">清空</el-button>
          </div>
        </div>
      </template>
      <div ref="logBoxRef" class="log-box">
        <div v-if="!pipeLogs.length" class="log-empty">
          暂无日志 — 点击右上角「全链路执行」即可实时查看采集 → 筛选 → 图谱 → 回填的每一步处理过程
        </div>
        <div v-for="(log, i) in pipeLogs" :key="i" class="log-line">
          <span class="log-ts">{{ log.ts }}</span>
          <el-tag size="small" effect="dark" class="log-tag"
                  :style="{ background: stageColor(log.stage), borderColor: stageColor(log.stage) }">
            {{ stageLabel(log.stage) }}
          </el-tag>
          <span class="log-msg" :class="log.level">{{ log.msg }}</span>
        </div>
      </div>
    </el-card>

    <!-- 四阶段卡片 -->
    <el-row :gutter="14">
      <el-col :span="6" v-for="s in stages" :key="s.key">
        <el-card class="stage-card" shadow="never">
          <div class="stage-head">
            <el-icon :color="s.color"><component :is="s.icon" /></el-icon>
            <span class="stage-name">{{ s.name }}</span>
          </div>
          <div class="stage-desc">{{ s.desc }}</div>
          <div class="stage-stats" v-if="s.stats && Object.keys(s.stats).length">
            <div class="stat-row" v-for="([lk, vv], i) in flattenStat(s.key, s.stats)" :key="`${s.key}-${i}`">
              <span>{{ lk }}</span>
              <b>{{ typeof vv === 'number' ? vv : JSON.stringify(vv) }}</b>
            </div>
          </div>
          <div class="stage-stats stage-idle" v-else>
            <span v-if="running && statusData?.current_stage === s.key" class="idle-running">
              <el-icon class="is-loading"><Loading /></el-icon>执行中…
            </span>
            <span v-else class="idle-txt">本次未运行</span>
          </div>
          <div class="stage-run-row">
            <el-button class="stage-run" size="small" plain :loading="stageRunning === s.key" @click="runStage(s.key)">
              仅执行此阶段
            </el-button>
            <el-input-number
              v-if="s.key === 'backfill'"
              v-model="enrichLimit"
              :min="1" :max="100" :step="5" size="small"
              class="enrich-limit-input"
              :title="'每轮深度补全单位数(默认 15)'"
              @change="saveEnrichLimit"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选规则 -->
    <el-card class="rules-card" shadow="never">
      <template #header>
        <div class="section-header">
          <span class="section-title">当前筛选规则</span>
          <span class="section-sub">质量门槛 — 全部满足才入库(可在运行请求中覆盖)</span>
        </div>
      </template>
      <el-descriptions :column="2" border size="small" v-if="rules">
        <el-descriptions-item label="目标省份">
          <el-tag v-for="p in rules.target_provinces" :key="p" size="small" type="success">{{ p }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="时效窗口">
          {{ rules.max_age_days }} 天内
        </el-descriptions-item>
        <el-descriptions-item label="最小正文长度">{{ rules.min_content_len }} 字符</el-descriptions-item>
        <el-descriptions-item label="主题关键词">
          <el-tag v-for="k in rules.topic_keywords" :key="k" size="small" effect="plain">{{ k }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="排除词" :span="2">
          <el-tag v-for="k in rules.exclude_keywords" :key="k" size="small" type="danger" effect="plain">{{ k }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 本次筛选拒绝样例(折叠) -->
    <el-collapse v-if="filterSamples.length" class="samples-collapse">
      <el-collapse-item>
        <template #title>
          <span class="samples-title">本次筛选拒绝样例({{ filterSamples.length }} 条, 点击展开查看原因)</span>
        </template>
        <div v-for="(s, i) in filterSamples" :key="i" class="sample-line">
          <span class="sample-reason">{{ s.reason }}</span>
          <a :href="s.url" target="_blank" class="sample-url">{{ s.url }}</a>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick, watch, computed } from "vue";
import { ElMessage } from "element-plus";
import { VideoPlay, VideoPause, SwitchButton, Refresh, Loading, Promotion, Filter, Share, Position } from "@element-plus/icons-vue";
import api from "@/api";

const loading = ref(false);
const loadingLogs = ref(false);
const running = ref(false);
const stageRunning = ref("");
// 每轮深度补全单位数上限(仅回填阶段生效); 记住上次设置
const enrichLimit = ref(Number(localStorage.getItem("ssm_pipeline_enrich_limit")) || 15);
function saveEnrichLimit(val: any) {
  const n = Number(val);
  if (n >= 1 && n <= 100) localStorage.setItem("ssm_pipeline_enrich_limit", String(n));
}
const stats = ref<any>({});
const rules = ref<any>(null);
const statusData = ref<any>({});
const control = ref<any>(null);   // 暂停/停止控制状态(来自 /pipeline/status.control)
const pipeLogs = ref<any[]>([]);
const logBoxRef = ref<HTMLElement>();
let logTimer: number | undefined = undefined;

const statusMsg = computed(() => {
  const d = statusData.value;
  if (!d?.running) return "";
  const s = d.current_stage;
  if (s === "init") return "正在初始化…";
  return `正在执行「${stageLabel(s)}」阶段…`;
});

// 阶段卡片数据 = 本次运行实时进度(非数据库存量): 来自 /pipeline/status 的 progress,
// 每阶段完成后由后端写入该阶段本次运行的结果; 未运行/未开始阶段为 undefined。
const stages = computed(() => {
  const prog = statusData.value?.progress || {};
  return [
    {
      key: "collect", name: "采集", color: "#2979ff", icon: Promotion,
      desc: "多源抓取意向/招标/中标信息", stats: prog.collect,
    },
    {
      key: "filter", name: "筛选入库", color: "#19be6b", icon: Filter,
      desc: "川藏新/时效/主题质量过滤", stats: prog.filter,
    },
    {
      key: "graph", name: "图谱构建", color: "#ff9900", icon: Share,
      desc: "实体识别+关系落Neo4j", stats: prog.graph,
    },
    {
      key: "backfill", name: "前端回填", color: "#9254de", icon: Position,
      desc: "单位/人员自动创建与补全", stats: prog.backfill,
    },
  ];
});

const statLabels: Record<string, Record<string, string>> = {
  collect: { intent: "意向入库", clues: "线索入库", bids: "中标解析", sources: "已采集源", intent_errors: "意向源失败" },
  filter: { checked: "已复检", passed: "通过", rejected: "拒绝", samples: "样例" },
  graph: { processed: "已处理线索", nodes: "节点", relations: "关系数", llm_relations: "LLM关系", errors: "错误" },
  backfill: { processed: "已处理线索", created_companies: "新建单位", updated_companies: "补全单位", created_persons: "新建人员", created_projects: "新建项目", rejected: "质量拒绝", enriched_companies: "本轮深度补全单位", enriched_pending: "待补单位(下轮继续)", errors: "错误" },
};
function statLabel(stage: string, key: string) {
  return statLabels[stage]?.[key] || key;
}
function stageLabel(key: string) {
  return ({ collect: "采集", filter: "筛选入库", graph: "图谱构建", backfill: "前端回填", general: "流水线" } as any)[key] || key;
}

// 阶段卡片展示字段: 过滤大对象(rules/样例)/空错误, 展开嵌套 nodes → 单位/人员/项目
function flattenStat(stage: string, st: any): Array<[string, any]> {
  if (!st) return [];
  const out: Array<[string, any]> = [];
  for (const [k, v] of Object.entries(st)) {
    if (k === "rules" || k === "samples") continue;                  // 规则在下方卡片, 样例单独折叠
    if (k === "errors" && Array.isArray(v) && !v.length) continue;   // 无错误不显示
    if (k === "nodes" && v && typeof v === "object") {
      out.push(["单位", v.companies ?? 0]);
      out.push(["人员", v.persons ?? 0]);
      out.push(["项目", v.projects ?? 0]);
      continue;
    }
    out.push([statLabel(stage, k), v]);
  }
  return out;
}

// 本次筛选拒绝样例(独立折叠展示, 不占卡片)
const filterSamples = computed(() => statusData.value?.progress?.filter?.samples || []);

const stageColors: Record<string, string> = {
  collect: "#2979ff", filter: "#19be6b", graph: "#ff9900", backfill: "#9254de", general: "#606266",
};
function stageColor(s: string) { return stageColors[s] || "#909399"; }

async function loadStats() {
  loading.value = true;
  try {
    const res: any = await api.get("/pipeline/stats");
    stats.value = res.data || {};
    rules.value = res.data?.rules || null;
  } catch { /* 拦截器 */ }
  finally { loading.value = false; }
}

async function loadLogs() {
  loadingLogs.value = true;
  try {
    const res: any = await api.get("/pipeline/logs", { params: { limit: 300 } });
    pipeLogs.value = res.data || [];
  } catch { /* 拦截器 */ }
  finally { loadingLogs.value = false; }
}

async function clearLogs() {
  try {
    await api.post("/pipeline/logs/clear");
    pipeLogs.value = [];
  } catch { /* 拦截器 */ }
}

function startLogPolling() {
  stopLogPolling();
  logTimer = window.setInterval(() => { loadLogs(); }, 1500);
}
function stopLogPolling() {
  if (logTimer !== undefined) {
    window.clearInterval(logTimer);
    logTimer = undefined;
  }
}

// 自动滚底
watch(pipeLogs, async () => {
  await nextTick();
  const box = logBoxRef.value;
  if (box) box.scrollTop = box.scrollHeight;
});

// 运行状态常驻轮询: 页面打开期间持续探测 /pipeline/status。
// 修复: 旧实现把轮询放在 runFull 的临时 setInterval 里, 一次请求异常即整体停摆 → 页面日志定格,
// 但后端其实仍在跑(观感像卡死)。现在不依赖启动按钮, 即使刷新页面, 只要后端有任务在跑也会自动续接日志。
let statusTimer: number | undefined = undefined;
let prevRunning = false;

async function pollStatus() {
  try {
    const res: any = await api.get("/pipeline/status");
    statusData.value = res.data || {};
    control.value = res.data?.control || null;
    const wasRunning = prevRunning;
    const nowRunning = !!statusData.value?.running;
    prevRunning = nowRunning;
    running.value = nowRunning;
    if (!nowRunning) stageRunning.value = "";   // 单阶段完成时解除按钮 loading
    // 运行完成边沿检测: true -> false
    if (wasRunning && !nowRunning) {
      ElMessage.success("流水线执行完成");
      loadStats();
      loadLogs();   // 拉取最终日志
    }
  } catch { /* 拦截器 */ }
}

function startStatusPolling() {
  stopStatusPolling();
  statusTimer = window.setInterval(async () => {
    await pollStatus();
    if (running.value) await loadLogs();   // 运行中持续拉日志, 空闲时不打扰
  }, 3000);
}
function stopStatusPolling() {
  if (statusTimer !== undefined) {
    window.clearInterval(statusTimer);
    statusTimer = undefined;
  }
}

async function runFull() {
  running.value = true;
  prevRunning = true;   // 避免启动瞬间误触发「完成」
  await clearLogs();            // 从干净起点开始看过程
  await loadLogs();
  try {
    const res: any = await api.post("/pipeline/run", { stages: null }, { timeout: 10000 });
    ElMessage.success(res.message || "流水线已启动");
  } catch {
    running.value = false;
    prevRunning = false;
  }
}

async function runStage(key: string) {
  stageRunning.value = key;
  try {
    // 后台线程执行, 立即返回; 进度由页面常驻轮询(pollStatus + running时拉日志)接管
    const body: any = {};
    if (key === "backfill") {
      body.deep_enrich = true;
      body.deep_enrich_limit = enrichLimit.value;
    }
    const res: any = await api.post(`/pipeline/stage/${key}`, body, { timeout: 10000 });
    ElMessage.success(res.message || `阶段「${stageLabel(key)}」已启动`);
  } catch {
    stageRunning.value = "";
  }
}

// 暂停/继续/停止 流水线(断点续跑)
async function doControl(action: string) {
  try {
    const res: any = await api.post("/pipeline/control", { action }, { timeout: 10000 });
    ElMessage.info(res.message || res.data?.message || { pause: "已暂停", resume: "已继续", stop: "已停止" }[action as string]);
    await pollStatus();
  } catch { /* 拦截器 */ }
}

onMounted(() => { loadStats(); pollStatus(); loadLogs(); startStatusPolling(); });
onUnmounted(() => { stopStatusPolling(); stopLogPolling(); });
</script>

<style scoped>
.pipe-page { max-width: 1440px; padding-bottom: 32px; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.page-head h2 { margin: 0; font-size: 20px; color: #1f2d3d; }
.page-desc { margin: 4px 0 0; font-size: 12.5px; color: #909399; }
.head-actions { display: flex; gap: 8px; }
.status-card { margin-bottom: 14px; border: 1px solid #e0eaff; background: #f6faff; }
.status-line { display: flex; align-items: center; gap: 10px; font-size: 14px; color: #1f2d3d; flex-wrap: wrap; }
.status-controls { display: inline-flex; gap: 6px; margin-left: auto; }
.control-tip { margin-top: 8px; font-size: 12.5px; color: #e6a23c; }
.stage-card { margin-bottom: 14px; }
.stage-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.stage-name { font-weight: 600; font-size: 15px; color: #1f2d3d; }
.stage-desc { font-size: 12px; color: #909399; margin-bottom: 10px; }
.stage-stats { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; min-height: 60px; }
.stage-idle { justify-content: center; align-items: center; min-height: 72px; }
.idle-txt { color: #a8abb2; font-size: 12.5px; }
.idle-running { display: inline-flex; align-items: center; gap: 6px; color: #2979ff; font-size: 12.5px; }
.stat-row { display: flex; justify-content: space-between; font-size: 12.5px; color: #606266; }
.stat-row b { color: #2979ff; }
.stage-run-row { display: flex; align-items: center; gap: 8px; }
.stage-run { flex: 1; }
.enrich-limit-input { width: 96px; }
.rules-card { margin-bottom: 14px; }
.section-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.section-title { font-weight: 600; font-size: 15px; color: #303133; }
.section-sub { font-size: 12px; color: #c0c4cc; }
.samples-collapse { margin-bottom: 14px; border: 1px solid #eef2f9; border-radius: 8px; background: #fff; }
.samples-title { font-size: 12.5px; color: #606266; }
.sample-line { display: flex; flex-direction: column; gap: 2px; padding: 5px 0; border-bottom: 1px dashed #eef2f9; }
.sample-line:last-child { border-bottom: none; }
.sample-reason { font-size: 12.5px; color: #e6a23c; }
.sample-url { font-size: 12px; color: #2979ff; word-break: break-all; }

/* 运行过程日志 */
.log-card { margin-bottom: 14px; }
.log-actions { display: flex; gap: 2px; margin-left: auto; }
.log-box {
  background: #1b2230; border-radius: 8px; padding: 10px 12px;
  max-height: 300px; overflow-y: auto;
  font-family: Consolas, Menlo, monospace; font-size: 12.5px; line-height: 1.8;
}
.log-line { display: flex; align-items: baseline; gap: 8px; padding: 1px 0; }
.log-ts { color: #7f8ea3; flex-shrink: 0; }
.log-tag { flex-shrink: 0; }
.log-msg { color: #d4dbe6; word-break: break-all; }
.log-msg.error { color: #f56c6c; }
.log-msg.warn { color: #e6a23c; }
.log-msg.success { color: #67c23a; }
.log-empty { color: #6b7a8f; font-family: inherit; }
.log-box::-webkit-scrollbar { width: 6px; }
.log-box::-webkit-scrollbar-thumb { background: #3a4557; border-radius: 3px; }
</style>
