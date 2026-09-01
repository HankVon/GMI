<!-- GEO 监测: 把 AI 引擎(豆包/DeepSeek/秘塔等)对行业关键词的回答与引用变成数据源 -->
<template>
  <div class="geo-page">
    <div class="page-head">
      <div>
        <h2>GEO 监测</h2>
        <p class="page-desc">
          采集 AI 引擎对行业关键词的回答 → 解析引用来源/提及实体/品牌可见性，反馈内容生产
        </p>
      </div>
      <div class="head-actions">
        <el-button type="primary" plain @click="manualVisible = true">
          <el-icon style="margin-right: 4px"><EditPen /></el-icon>手动录入回答
        </el-button>
        <el-button type="primary" :loading="fetching" @click="fetchAll">
          <el-icon style="margin-right: 4px"><VideoPlay /></el-icon>触发自动采集
        </el-button>
        <el-button @click="openConfig">
          <el-icon style="margin-right: 4px"><Setting /></el-icon>品牌词/行业词
        </el-button>
        <el-button :loading="loading" @click="loadAll"><el-icon style="margin-right: 4px"><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <el-tabs v-model="tab" type="border-card" class="geo-tabs">
      <!-- ── 概览 ── -->
      <el-tab-pane label="概览" name="overview">
        <el-row :gutter="14">
          <el-col :span="6" v-for="c in statCards" :key="c.label">
            <el-card shadow="never" class="stat-card">
              <div class="stat-num" :style="{ color: c.color }">{{ c.value }}</div>
              <div class="stat-label">{{ c.label }}</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="14" style="margin-top: 14px">
          <el-col :span="8">
            <el-card shadow="never" class="panel-card">
              <template #header><span class="section-title">引擎可见性对比</span></template>
              <el-table :data="dash.engines || []" size="small">
                <el-table-column prop="name" label="引擎" />
                <el-table-column prop="mentions" label="监测次数" width="90" align="center" />
                <el-table-column label="提及本公司" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.visible > 0 ? 'success' : 'info'">{{ row.visible }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="适配器" width="100">
                  <template #default="{ row }">{{ adapterLabel(row.adapter) }}</template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="never" class="panel-card">
              <template #header><span class="section-title">高频引用来源 TOP</span></template>
              <div v-if="!(dash.cited_sources || []).length" class="empty-tip">暂无数据</div>
              <div v-for="(s, i) in (dash.cited_sources || []).slice(0, 8)" :key="s.domain" class="rank-row">
                <span class="rank-no">{{ i + 1 }}</span>
                <span class="rank-name" :title="s.title">{{ s.title }}</span>
                <el-tag size="small" type="info">{{ s.count }} 次</el-tag>
              </div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="never" class="panel-card">
              <template #header><span class="section-title">被提及公司 TOP</span></template>
              <div v-if="!(dash.mentioned_top || []).length" class="empty-tip">暂无数据</div>
              <div v-for="(e, i) in (dash.mentioned_top || []).slice(0, 8)" :key="e.name" class="rank-row">
                <span class="rank-no">{{ i + 1 }}</span>
                <span class="rank-name" :title="e.name">{{ e.name }}</span>
                <el-tag size="small" type="warning">{{ e.count }} 次</el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-card shadow="never" class="panel-card" style="margin-top: 14px">
          <template #header><span class="section-title">可见性趋势（近30天）</span></template>
          <div v-if="!(dash.trend || []).length" class="empty-tip">暂无数据</div>
          <div v-else class="trend-wrap">
            <div v-for="t in dash.trend" :key="t.date" class="trend-col">
              <div class="trend-bar-wrap">
                <div class="trend-bar" :style="{ height: trendHeight(t) + 'px' }" :title="`${t.date}: 共${t.total}次 提及${t.visible}次`"></div>
              </div>
              <div class="trend-label">{{ t.date }}</div>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ── 监测记录 ── -->
      <el-tab-pane label="监测记录" name="records">
        <div class="filter-bar">
          <el-input v-model="filters.keyword" placeholder="搜索关键词" clearable style="width: 200px" @change="loadMentions" />
          <el-select v-model="filters.engine_id" placeholder="引擎" clearable style="width: 160px" @change="loadMentions">
            <el-option v-for="e in engines" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
          <el-select v-model="filters.self_visible" placeholder="品牌可见性" clearable style="width: 140px" @change="loadMentions">
            <el-option label="已提及本公司" :value="true" />
            <el-option label="未提及" :value="false" />
          </el-select>
          <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px" @change="loadMentions">
            <el-option label="已解析" value="parsed" />
            <el-option label="待解析" value="pending" />
            <el-option label="失败" value="error" />
          </el-select>
          <span class="filter-total">共 {{ mentionTotal }} 条</span>
        </div>
        <el-table :data="mentions" size="small" :loading="loadingMentions">
          <el-table-column prop="asked_at" label="时间" width="130" />
          <el-table-column prop="keyword" label="查询词" min-width="180" show-overflow-tooltip />
          <el-table-column prop="engine_name" label="引擎" width="110" />
          <el-table-column label="品牌可见" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.self_visible ? 'success' : 'info'" effect="plain">
                {{ row.self_visible ? `第${row.self_rank}位` : "未提及" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === 'parsed' ? 'success' : row.status === 'error' ? 'danger' : 'warning'">
                {{ { parsed: "已解析", pending: "待解析", error: "失败" }[row.status] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="summary" label="AI 回答摘要" min-width="220" show-overflow-tooltip />
          <el-table-column label="操作" width="170" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openMention(row)">查看</el-button>
              <el-button v-if="row.status !== 'parsed'" size="small" text type="warning" @click="reparse(row)">解析</el-button>
              <el-button size="small" text type="danger" @click="delMention(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="page" :page-size="pageSize" :total="mentionTotal"
          layout="prev, pager, next" small style="margin-top: 10px; justify-content: flex-end"
          @current-change="loadMentions"
        />
      </el-tab-pane>

      <!-- ── 关键词任务 ── -->
      <el-tab-pane label="关键词任务" name="keywords">
        <div class="filter-bar">
          <el-button type="primary" size="small" @click="openNewKeyword">
            <el-icon style="margin-right: 4px"><Plus /></el-icon>新增关键词
          </el-button>
        </div>
        <el-table :data="keywords" size="small">
          <el-table-column prop="keyword" label="监测关键词" min-width="220" />
          <el-table-column prop="category" label="分类" width="110" />
          <el-table-column label="绑定引擎" min-width="160">
            <template #default="{ row }">
              <template v-if="row.engines">
                <el-tag size="small" v-for="code in JSON.parse(row.engines)" :key="code" style="margin-right: 4px">
                  {{ engineName(code) }}
                </el-tag>
              </template>
              <el-tag v-else size="small" type="info" effect="plain">全部引擎</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="priority" label="优先级" width="80" align="center" />
          <el-table-column label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_run_at" label="上次执行" width="130" />
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openKwEdit(row)">编辑</el-button>
              <el-button size="small" text type="danger" @click="delKw(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ── 引擎配置 ── -->
      <el-tab-pane label="引擎配置" name="engines">
        <div class="filter-bar">
          <el-button type="primary" size="small" @click="openNewEngine">
            <el-icon style="margin-right: 4px"><Plus /></el-icon>新增引擎
          </el-button>
          <span class="filter-total">适配器: manual=手动粘贴 / crawl4ai=网页抓取 / openai_api=兼容API</span>
        </div>
        <el-table :data="engines" size="small">
          <el-table-column prop="name" label="引擎" width="140" />
          <el-table-column prop="code" label="编码" width="110" />
          <el-table-column label="适配器" width="110">
            <template #default="{ row }">{{ adapterLabel(row.adapter) }}</template>
          </el-table-column>
          <el-table-column prop="url" label="访问地址" min-width="200" show-overflow-tooltip />
          <el-table-column label="API" min-width="120">
            <template #default="{ row }">
              <span v-if="row.api_endpoint">{{ row.api_model || row.api_endpoint }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170">
            <template #default="{ row }">
              <el-button size="small" text type="success" :loading="testingEng === row.id" @click="testEngine(row)">测试</el-button>
              <el-button size="small" text type="primary" @click="openEngEdit(row)">编辑</el-button>
              <el-button size="small" text type="danger" @click="delEng(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 手动录入回答 -->
    <el-dialog v-model="manualVisible" title="手动录入 AI 回答" width="640px">
      <el-form label-width="90px">
        <el-form-item label="查询词" required>
          <el-input v-model="manualForm.keyword" placeholder="例如: 生态修复工程 招标 公司 推荐" />
        </el-form-item>
        <el-form-item label="引擎">
          <el-select v-model="manualForm.engine_id" clearable placeholder="选择引擎(可空=手动)">
            <el-option v-for="e in engines" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="AI 回答" required>
          <el-input v-model="manualForm.answer_text" type="textarea" :rows="10" placeholder="粘贴 AI 引擎的回答全文(含推荐的单位、引用链接等)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingManual" @click="saveManual">保存并解析</el-button>
      </template>
    </el-dialog>

    <!-- 记录详情 -->
    <el-drawer v-model="detailVisible" title="GEO 监测记录详情" size="640px">
      <template v-if="current">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="查询词">{{ current.keyword }}</el-descriptions-item>
          <el-descriptions-item label="引擎">{{ current.engine_name }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ current.asked_at }}</el-descriptions-item>
          <el-descriptions-item label="品牌可见">
            <el-tag size="small" :type="current.self_visible ? 'success' : 'info'">
              {{ current.self_visible ? `已提及(第${current.self_rank}位)` : "未提及" }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <h4>品牌命中</h4>
        <div v-if="current.brand_hits.length">
          <el-tag v-for="b in current.brand_hits" :key="b.name" type="success" effect="plain" style="margin-right: 6px">{{ b.name }}</el-tag>
        </div>
        <div v-else class="empty-tip">未命中品牌词</div>
        <h4>提及实体</h4>
        <div v-if="current.mentioned_entities.length">
          <el-tag v-for="e in current.mentioned_entities" :key="e.name" effect="plain" style="margin-right: 6px">{{ e.name }}</el-tag>
        </div>
        <div v-else class="empty-tip">未抽取到实体</div>
        <h4>引用来源</h4>
        <div v-if="current.cited_sources.length">
          <div v-for="s in current.cited_sources" :key="s.url || s.title" class="cite-item">
            <el-link v-if="s.url" :href="s.url" target="_blank" type="primary" :underline="false">{{ s.title }}</el-link>
            <span v-else>{{ s.title }}</span>
          </div>
        </div>
        <div v-else class="empty-tip">无引用来源</div>
        <h4>AI 回答全文</h4>
        <pre class="answer-pre">{{ current.answer_text }}</pre>
      </template>
    </el-drawer>

    <!-- 品牌词/行业词配置 -->
    <el-dialog v-model="configVisible" title="品牌词 / 行业词 / 模型配置" width="580px">
      <p class="config-tip">品牌词 = 本公司名称/简称，用于识别 AI 回答中是否提及本公司（GEO 可见性核心）</p>
      <el-form label-width="110px">
        <el-form-item label="品牌词">
          <el-select v-model="brandNames" multiple filterable allow-create default-first-option placeholder="输入公司名后回车" style="width: 100%">
            <el-option v-for="b in brandNames" :key="b" :label="b" :value="b" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业关键词">
          <el-select v-model="industryKeywords" multiple filterable allow-create default-first-option placeholder="输入行业词后回车" style="width: 100%">
            <el-option v-for="k in industryKeywords" :key="k" :label="k" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="智能体模型">
          <el-select v-model="llmModel" filterable allow-create default-first-option placeholder="选择 Ollama 模型" style="width: 100%">
            <el-option v-for="m in ollamaModels" :key="m" :label="m" :value="m" />
          </el-select>
          <div class="config-tip" style="margin-top: 6px">
            内容生成/GEO 解析使用的本地 Ollama 模型（默认 {{ defaultLlmModel }}，可在 AI 模型配置中管理）
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingConfig" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>

    <!-- 关键词编辑 -->
    <el-dialog v-model="kwEditVisible" :title="kwForm.id ? '编辑关键词任务' : '新增关键词任务'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="关键词" required>
          <el-input v-model="kwForm.keyword" placeholder="监测问题, 例如: 地质灾害治理 勘察设计 单位" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="kwForm.category" placeholder="行业分类(可选)" />
        </el-form-item>
        <el-form-item label="绑定引擎">
          <el-select v-model="kwEngineCodes" multiple clearable placeholder="空=全部启用引擎" style="width: 100%">
            <el-option v-for="e in engines" :key="e.code" :label="e.name" :value="e.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="kwForm.priority" :min="1" :max="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kwEditVisible = false">取消</el-button>
        <el-button type="primary" @click="saveKw">保存</el-button>
      </template>
    </el-dialog>

    <!-- 引擎编辑 -->
    <el-dialog v-model="engEditVisible" :title="engForm.id ? '编辑引擎' : '新增引擎'" width="560px">
      <el-form label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="engForm.name" placeholder="豆包/DeepSeek/秘塔..." />
        </el-form-item>
        <el-form-item label="编码" required>
          <el-input v-model="engForm.code" placeholder="doubao/deepseek/metaso..." :disabled="!!engForm.id" />
        </el-form-item>
        <el-form-item label="适配器">
          <el-select v-model="engForm.adapter" style="width: 100%">
            <el-option v-for="a in adapters" :key="a.value" :label="a.label" :value="a.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="访问地址">
          <el-input v-model="engForm.url" placeholder="网页地址(crawl4ai 时支持 {kw} 占位)" />
        </el-form-item>
        <template v-if="engForm.adapter === 'openai_api'">
          <el-form-item label="API 端点">
            <el-input v-model="engForm.api_endpoint" placeholder="https://api.deepseek.com/chat/completions" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="engForm.api_key" type="password" show-password placeholder="模型服务 API Key" />
          </el-form-item>
          <el-form-item label="模型名">
            <el-input v-model="engForm.api_model" placeholder="deepseek-chat" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="engEditVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEng">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "@/api";
import { Refresh, VideoPlay, EditPen, Setting, Plus } from "@element-plus/icons-vue";

const tab = ref("overview");
const loading = ref(false);
const dash = ref<any>({});
const engines = ref<any[]>([]);
const adapters = ref<any[]>([]);

const statCards = computed(() => [
  { label: "AI 回答监测(30天)", value: dash.value.total_mentions ?? 0, color: "#4d6bfe" },
  { label: "提及本公司", value: dash.value.visible_count ?? 0, color: "#00b894" },
  { label: "可见率", value: `${Math.round((dash.value.visible_ratio ?? 0) * 100)}%`, color: "#ff9f43" },
  { label: "引用来源数", value: (dash.value.cited_sources || []).length, color: "#6c5ce7" },
]);

async function loadAll() {
  loading.value = true;
  await Promise.all([loadDash(), loadEngines(), loadKeywords(), loadMentions(), loadAdapters()]);
  loading.value = false;
}
async function loadDash() {
  const r: any = await api.get("/geo/dashboard?days=30");
  dash.value = r;
}
async function loadEngines() {
  const r: any = await api.get("/geo/engines");
  engines.value = r.items || [];
}
async function loadAdapters() {
  const r: any = await api.get("/geo/adapters");
  adapters.value = r.items || [];
}

// ── 监测记录 ──
const mentions = ref<any[]>([]);
const mentionTotal = ref(0);
const page = ref(1);
const pageSize = 15;
const loadingMentions = ref(false);
const filters = reactive<any>({ keyword: "", engine_id: undefined, self_visible: undefined, status: "" });
async function loadMentions() {
  loadingMentions.value = true;
  try {
    const params: any = { page: page.value, page_size: pageSize };
    if (filters.keyword) params.keyword = filters.keyword;
    if (filters.engine_id) params.engine_id = filters.engine_id;
    if (filters.self_visible !== undefined && filters.self_visible !== null) params.self_visible = filters.self_visible;
    if (filters.status) params.status = filters.status;
    const r: any = await api.get("/geo/mentions", { params });
    mentions.value = r.items || [];
    mentionTotal.value = r.total || 0;
  } finally { loadingMentions.value = false; }
}

const detailVisible = ref(false);
const current = ref<any>(null);
function openMention(row: any) { current.value = row; detailVisible.value = true; }
async function reparse(row: any) {
  await api.post(`/geo/mentions/${row.id}/reparse`);
  ElMessage.success("解析完成");
  loadMentions(); loadDash();
}
async function delMention(row: any) {
  await ElMessageBox.confirm(`删除记录《${row.keyword}》?`, "确认", { type: "warning" });
  await api.delete(`/geo/mentions/${row.id}`);
  loadMentions(); loadDash();
}

// ── 手动录入 ──
const manualVisible = ref(false);
const savingManual = ref(false);
const manualForm = reactive({ keyword: "", engine_id: undefined as any, answer_text: "" });
async function saveManual() {
  if (!manualForm.keyword.trim() || !manualForm.answer_text.trim()) {
    ElMessage.warning("查询词与回答必填");
    return;
  }
  savingManual.value = true;
  try {
    await api.post("/geo/mentions/manual", {
      keyword: manualForm.keyword.trim(),
      engine_id: manualForm.engine_id || undefined,
      answer_text: manualForm.answer_text,
    });
    ElMessage.success("已保存并解析");
    manualVisible.value = false;
    manualForm.keyword = ""; manualForm.answer_text = ""; manualForm.engine_id = undefined;
    loadMentions(); loadDash();
  } finally { savingManual.value = false; }
}

// ── 自动采集 ──
const fetching = ref(false);
async function fetchAll() {
  fetching.value = true;
  try {
    const r: any = await api.post("/geo/mentions/fetch", {});
    const msg = `采集完成: 成功 ${r.ok ?? 0}, 失败 ${r.failed ?? 0}, 跳过(手动) ${r.skipped ?? 0}`;
    ElMessage.success(msg);
    loadMentions(); loadDash();
  } catch { /* 拦截器已提示 */ }
  fetching.value = false;
}

// ── 配置 ──
const configVisible = ref(false);
const savingConfig = ref(false);
const brandNames = ref<string[]>([]);
const industryKeywords = ref<string[]>([]);
const llmModel = ref("");
const defaultLlmModel = ref("");
const ollamaModels = ref<string[]>([]);
async function openConfig() {
  const r: any = await api.get("/geo/config");
  brandNames.value = r.brand_names || [];
  industryKeywords.value = r.industry_keywords || [];
  llmModel.value = r.llm_model || "";
  defaultLlmModel.value = r.default_llm_model || "";
  const m: any = await api.get("/ai/ollama/models").catch(() => ({ models: [] }));
  ollamaModels.value = m.models || [];
  configVisible.value = true;
}
async function saveConfig() {
  savingConfig.value = true;
  try {
    await api.put("/geo/config", {
      brand_names: brandNames.value,
      industry_keywords: industryKeywords.value,
      llm_model: llmModel.value || undefined,
    });
    ElMessage.success("配置已保存");
    configVisible.value = false;
  } finally { savingConfig.value = false; }
}

// ── 关键词 ──
const keywords = ref<any[]>([]);
const kwEditVisible = ref(false);
const kwForm = reactive<any>({});
const kwEngineCodes = ref<string[]>([]);
async function loadKeywords() {
  const r: any = await api.get("/geo/keywords");
  keywords.value = r.items || [];
}
function openNewKeyword() {
  Object.keys(kwForm).forEach((key) => delete kwForm[key]);
  kwEngineCodes.value = [];
  kwEditVisible.value = true;
}
function openKwEdit(row: any) {
  Object.keys(kwForm).forEach((key) => delete kwForm[key]);
  Object.assign(kwForm, row);
  kwEngineCodes.value = row.engines ? JSON.parse(row.engines) : [];
  kwEditVisible.value = true;
}
async function saveKw() {
  if (!kwForm.keyword?.trim()) { ElMessage.warning("关键词必填"); return; }
  const payload: any = {
    keyword: kwForm.keyword.trim(), category: kwForm.category || "",
    priority: kwForm.priority || 5, enabled: kwForm.enabled !== false,
  };
  if (kwEngineCodes.value.length) payload.engines = kwEngineCodes.value;
  if (kwForm.id) await api.put(`/geo/keywords/${kwForm.id}`, payload);
  else await api.post("/geo/keywords", payload);
  ElMessage.success("已保存");
  kwEditVisible.value = false;
  loadKeywords();
}
async function delKw(row: any) {
  await ElMessageBox.confirm(`删除关键词《${row.keyword}》?`, "确认", { type: "warning" });
  await api.delete(`/geo/keywords/${row.id}`);
  loadKeywords();
}
function engineName(code: string) {
  return engines.value.find((e) => e.code === code)?.name || code;
}

// ── 引擎 ──
const engEditVisible = ref(false);
const engForm = reactive<any>({});
function openNewEngine() {
  Object.keys(engForm).forEach((key) => delete engForm[key]);
  engForm.adapter = "manual";
  engEditVisible.value = true;
}
function openEngEdit(row: any) {
  Object.keys(engForm).forEach((key) => delete engForm[key]);
  Object.assign(engForm, row);
  engEditVisible.value = true;
}
async function saveEng() {
  if (!engForm.name?.trim() || !engForm.code?.trim()) { ElMessage.warning("名称与编码必填"); return; }
  const payload: any = { name: engForm.name, code: engForm.code, adapter: engForm.adapter || "manual", enabled: engForm.enabled !== false };
  if (engForm.url) payload.url = engForm.url;
  if (engForm.api_endpoint) payload.api_endpoint = engForm.api_endpoint;
  if (engForm.api_key) payload.api_key = engForm.api_key;
  if (engForm.api_model) payload.api_model = engForm.api_model;
  if (engForm.id) await api.put(`/geo/engines/${engForm.id}`, payload);
  else await api.post("/geo/engines", payload);
  ElMessage.success("已保存");
  engEditVisible.value = false;
  loadEngines();
}
async function delEng(row: any) {
  await ElMessageBox.confirm(`删除引擎《${row.name}》?`, "确认", { type: "warning" });
  await api.delete(`/geo/engines/${row.id}`);
  loadEngines();
}
const testingEng = ref<number | null>(null);
async function testEngine(row: any) {
  testingEng.value = row.id;
  try {
    const r: any = await api.post(`/geo/engines/${row.id}/test`);
    if (r.ok) ElMessage.success(r.detail || "连接正常");
    else ElMessage.error(r.detail || "连接失败");
  } catch { /* 拦截器已提示 */ }
  testingEng.value = null;
}

function adapterLabel(a: string) {
  return ({ manual: "手动粘贴", crawl4ai: "网页抓取", openai_api: "兼容API" } as any)[a] || a;
}
function trendHeight(t: any) {
  const max = Math.max(...(dash.value.trend || []).map((x: any) => x.total), 1);
  return Math.max(4, Math.round((t.total / max) * 120));
}

onMounted(loadAll);
</script>

<style scoped>
.geo-page { display: flex; flex-direction: column; gap: 14px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; }
.page-head h2 { margin: 0; font-size: 20px; color: #111827; }
.page-desc { margin: 6px 0 0; color: #8a94a6; font-size: 13px; }
.geo-tabs { border-radius: 12px; border: 1px solid #eef1f8; }
.stat-card { border-radius: 12px; border: 1px solid #eef1f8; text-align: center; padding: 6px 0; }
.stat-num { font-size: 28px; font-weight: 700; }
.stat-label { color: #909399; font-size: 12.5px; margin-top: 4px; }
.panel-card { border-radius: 12px; border: 1px solid #eef1f8; }
.section-title { font-weight: 600; color: #111827; font-size: 14px; }
.rank-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px dashed #f0f2f6; }
.rank-no { width: 20px; height: 20px; border-radius: 50%; background: #ecefff; color: #4d6bfe; font-size: 11px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rank-name { flex: 1; font-size: 13px; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.trend-wrap { display: flex; align-items: flex-end; gap: 6px; height: 150px; padding: 8px 4px 0; }
.trend-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.trend-bar-wrap { height: 130px; display: flex; align-items: flex-end; }
.trend-bar { width: 18px; border-radius: 4px 4px 0 0; background: linear-gradient(180deg, #6b83fe, #4d6bfe); }
.trend-label { font-size: 10px; color: #909399; }
.filter-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.filter-total { color: #909399; font-size: 12.5px; }
.empty-tip { color: #a3adc0; font-size: 13px; padding: 14px 0; text-align: center; }
.cite-item { padding: 4px 0; font-size: 13px; }
.answer-pre { background: #f6f8fc; border-radius: 8px; padding: 12px; font-size: 12.5px; white-space: pre-wrap; word-break: break-all; max-height: 320px; overflow-y: auto; color: #4b5563; }
.config-tip { color: #909399; font-size: 12.5px; margin: 0 0 12px; }
h4 { margin: 14px 0 8px; color: #111827; font-size: 13.5px; }
</style>
