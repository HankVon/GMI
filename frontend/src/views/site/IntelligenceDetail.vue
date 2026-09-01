<!--
  情报动态详情页 - 政企机构风重构版
  视觉特征:
   - 蓝色顶部状态条 + 收藏/打印/原文
   - 绿底立项标签 + 横向项目阶段时间线(设计→动工→竣工→竣工验收)
   - 黄色提示条 (高级会员升级提示)
   - 字段网格化项目概况
   - 智能分析 Tab 模块(AI 摘要)
   - 信息来源 + 联系人分组(甲方/设计师/建造商/分包) + 二维码
  保留原有功能: AI 研判 / 人脉触达路径 / 项目概况结构化解析 / 收藏 / 重新生成研判 / 附件
-->
<template>
  <SiteLayout>
    <section class="ib-body">
      <div class="site-container">
        <!-- 顶部蓝色状态条 -->
        <div class="ib-topbar">
          <div class="ib-topbar-left">
            <span class="ib-badge-cyan">最新信息</span>
            <h1 class="ib-title">
              {{ item?.title || "意向信息详情" }}
              <span v-if="item?.opp_version" class="ib-version">{{ item.opp_version }}</span>
            </h1>
            <div class="ib-tags">
              <span v-if="item" :class="['ib-tag', `tag-${item.status || 'info'}`]">{{ statusText(item.status) }}</span>
              <span v-if="item?.industry" class="ib-tag tag-warn">{{ item.industry }}</span>
              <span v-if="item?.region" class="ib-tag tag-blue">{{ item.region }}</span>
            </div>
          </div>
          <div class="ib-topbar-right">
            <button v-if="item?.url" class="ib-mini-btn" @click="openOriginal">
              <el-icon><Link /></el-icon><span>原始信息</span>
            </button>
            <button class="ib-mini-btn" @click="printPage">
              <el-icon><Printer /></el-icon><span>打印</span>
            </button>
            <button :class="['ib-mini-btn', isSaved && 'active']" :disabled="favSaving" @click="toggleSaved">
              <el-icon><Star /></el-icon><span>{{ favSaving ? "处理中" : isSaved ? "已收藏" : "加入收藏" }}</span>
            </button>
          </div>
        </div>

        <!-- 加载/空/不存在 状态 -->
        <div v-if="loading" v-loading="loading" class="ib-loading"></div>
        <el-empty v-else-if="!item" description="情报不存在或已删除" :image-size="120" />
        <div v-else>

          <!-- 黄色提示条 -->
          <!-- <div class="ib-tip">
            <div class="ib-tip-left">
              升级<strong>金牌会员</strong>的特权会员，对查看信息内容
              <button class="ib-tip-btn">立即咨询</button>
            </div>
            <div class="ib-tip-right">
              <el-icon><Phone /></el-icon>
              <span>客服热线：400-800-3367</span>
              <button class="ib-tip-link">在线客服</button>
            </div>
          </div> -->

          <!-- 项目阶段(可配置里程碑: 阶段定义来自选项集 project_progress_stage, 达成状态来自真实 ProjectProgress) -->
          <div v-if="progressList.length" class="ib-card ib-ms-card">
            <header class="ib-card-head">
              <span class="ib-card-title">项目阶段</span>
              <span class="ib-card-sub">{{ milestones.length ? "按配置阶段自动标记" : `${progressList.length} 条进展记录` }}</span>
            </header>
            <div class="ib-card-body">
              <!-- 已配置阶段: 横向里程碑 -->
              <ol v-if="milestones.length" class="ib-ms-track">
                <li
                  v-for="(m, mi) in milestones"
                  :key="m.key"
                  :class="['ib-ms-step', m.reached && 'reached']"
                >
                  <el-tooltip
                    :disabled="!m.reached"
                    :content="`${m.date || '已达成'}${m.content ? ' · ' + m.content : ''}`"
                    placement="top"
                  >
                    <span
                      class="ib-ms-num"
                      :style="m.reached && m.color ? { background: m.color, boxShadow: `0 0 0 2px ${m.color}` } : {}"
                    >{{ m.reached ? "✓" : mi + 1 }}</span>
                  </el-tooltip>
                  <span class="ib-ms-label">{{ m.label }}</span>
                  <span class="ib-ms-date">{{ m.date || "—" }}</span>
                </li>
              </ol>
              <!-- 未配置阶段(选项集为空): 回退为按进展记录渲染的纵向时间线 -->
              <ul v-else class="ib-progress">
                <li v-for="p in progressList" :key="p.id" class="ib-progress-item">
                  <span class="ib-progress-dot"></span>
                  <div class="ib-progress-body">
                    <div class="ib-progress-head">
                      <span class="ib-progress-title">{{ p.title }}</span>
                      <span class="ib-progress-date">{{ p.progress_date }}</span>
                    </div>
                    <div v-if="p.content" class="ib-progress-content">{{ p.content }}</div>
                  </div>
                </li>
              </ul>
            </div>
          </div>

          <el-row :gutter="20" class="ib-main-row">
            <!-- 左主栏 -->
            <el-col :xs="24" :md="16" class="ib-main-col">
              <!-- 项目概况(字段网格化) -->
              <div class="ib-card">
                <header class="ib-card-head">
                  <span class="ib-card-title">项目概况</span>
                </header>
                <div class="ib-card-body">
                  <div class="ib-fields">
                    <div v-for="f in projectFields" :key="f.label" class="ib-field">
                      <div class="ib-field-label">{{ f.label }}</div>
                      <div class="ib-field-value" :class="f.cls">{{ f.value }}</div>
                    </div>
                  </div>
                  <div class="ib-addr">
                    <div class="ib-field-label">项目地址</div>
                    <div class="ib-field-value">{{ item?.region || "暂无" }}</div>
                  </div>
                </div>
              </div>

              <!-- 项目跟踪(真实归整线索, 按阶段分组) -->
              <div class="ib-card">
                <header class="ib-card-head">
                  <span class="ib-card-title">项目跟踪</span>
                  <span v-if="trackerFallback" class="ib-card-sub">同类候选 · 尚未正式归整</span>
                </header>
                <div class="ib-card-body">
                  <div v-if="trackedLoading" v-loading="trackedLoading" class="ib-trace-loading"></div>
                  <div v-else-if="!trackedGroups.length" class="ib-empty-tip">
                    暂无跟踪线索 — 该意向尚未归整到项目或暂未匹配到后续进展
                  </div>
                  <template v-else>
                    <div class="ib-trace-group" v-for="g in trackedGroups" :key="g.stage">
                      <div class="ib-trace-group-head">
                        <el-tag size="small" :type="stageTagType(g.stage)" effect="plain">{{ g.stage_label }}</el-tag>
                        <span class="ib-trace-count">{{ g.items.length }} 条</span>
                      </div>
                      <ul class="ib-trace-list">
                        <li
                          v-for="it in g.items"
                          :key="it.id"
                          class="ib-trace-item"
                          @click="it.url && openUrl(it.url)"
                        >
                          <span class="ib-trace-dot" :class="{ read: it.is_read }"></span>
                          <a
                            class="ib-trace-title"
                            :href="it.url"
                            target="_blank"
                            rel="noopener"
                            @click.stop
                          >{{ it.title }}</a>
                          <span class="ib-trace-time">{{ it.published_at || "—" }}</span>
                          <el-button
                            v-if="!it.is_read && it.id"
                            size="small" type="primary" link
                            :loading="readLoading[it.id]"
                            @click.stop="markClueRead(it)"
                          >标记已读</el-button>
                          <el-tag v-else-if="it.is_read" size="small" type="info" effect="plain">已读</el-tag>
                        </li>
                      </ul>
                    </div>
                  </template>
                </div>
              </div>

              <!-- 智能分析 Tab 模块 (蓝色块) -->
              <div class="ib-card ib-card-ai">
                <header class="ib-card-head ib-card-head-ai">
                  <div class="ib-head-left">
                    <span class="ib-card-title">智能分析</span>
                    <el-tag type="info" effect="dark" size="small" class="ib-tag-llm">LLM</el-tag>
                    <span class="ib-ai-sub">本次于AI智能助手深度分析，研判参考</span>
                  </div>
                  <button v-if="!aiLoading" class="ib-ai-regen" @click="regenAi">
                    <el-icon class="reload-icon"><Refresh /></el-icon>
                    重新生成研判
                  </button>
                </header>

                <!-- Tab 切换 -->
                <div class="ib-tabs-bar">
                  <span
                    v-for="t in aiTabs"
                    :key="t.key"
                    :class="['ib-tab', aiTab === t.key && 'active']"
                    @click="aiTab = t.key"
                  >{{ t.label }}</span>
                </div>

                <div class="ib-card-body">
                  <!-- AI 摘要 Tab -->
                  <div v-if="aiTab === 'summary'">
                    <div v-if="aiLoading" class="ib-ai-loading">
                      <el-icon class="spin"><Loading /></el-icon>
                      <span>正在调用本地大模型进行深度研判，弱算力下约需 1–2 分钟，请稍候…</span>
                    </div>
                    <template v-else-if="showAi">
                      <p v-if="showAi.summary" class="ib-ai-summary">{{ showAi.summary }}</p>

                      <div v-if="aiOrgs.length" class="ib-ai-block">
                        <div class="ib-ai-m-label">涉及单位 / 角色</div>
                        <div class="chips">
                          <span v-for="o in aiOrgs" :key="o" class="chip">{{ o }}</span>
                        </div>
                      </div>

                      <div v-if="showAi.persons_hint" class="ib-ai-block">
                        <div class="ib-ai-m-label">关键人员触达</div>
                        <p class="ib-ai-text">{{ showAi.persons_hint }}</p>
                      </div>

                      <div v-if="reachPath.paths.length || reachPath.note" class="ib-ai-block">
                        <div class="ib-ai-m-label">
                          人脉触达路径
                          <el-tooltip content="根据项目协作、任职、参与项目等真实图谱关系计算的最短触达链">
                            <el-icon class="ib-help"><InfoFilled /></el-icon>
                          </el-tooltip>
                        </div>
                        <p class="ib-ai-text path-note">{{ reachPath.note }}</p>
                        <div v-for="(p, pi) in reachPath.paths.slice(0, 3)" :key="pi" class="ib-path-chain">
                          <div class="ib-path-target">
                            <span class="pt-role">{{ p.target_role }}</span>
                            <span class="pt-name">{{ p.target }}</span>
                          </div>
                          <div class="ib-path-hops">
                            <template v-for="(nd, ni) in (p.nodes as any[])" :key="ni">
                              <span class="ib-path-node" :class="String(nd.type || '').toLowerCase()">{{ nd.name }}</span>
                              <span v-if="ni < (p.nodes as any[]).length - 1" class="ib-path-arrow">→</span>
                            </template>
                          </div>
                          <div v-if="p.kind === 'via_unit'" class="ib-path-tip">经关联单位内部人员触达</div>
                          <div v-else-if="p.kind === 'weak_region'" class="ib-path-tip weak">同地域弱关联，建议线下建立业务联系</div>
                        </div>
                        <div v-if="reachPath.bridges.length" class="ib-bridge-row">
                          <span class="ib-bridge-label">可作桥接人：</span>
                          <span v-for="b in reachPath.bridges" :key="b.name" class="ib-bridge-name">{{ b.name }}</span>
                        </div>
                      </div>
                      <div v-else-if="showAi.network_path" class="ib-ai-block">
                        <div class="ib-ai-m-label">人脉路径建议</div>
                        <p class="ib-ai-text">{{ showAi.network_path }}</p>
                      </div>

                      <div class="ib-ai-block">
                        <div class="ib-ai-m-label">推荐行动建议</div>
                        <ul class="ib-ai-list">
                          <li v-for="(a, i) in aiAdviceList" :key="i">{{ a }}</li>
                        </ul>
                      </div>

                      <div v-if="aiNote" class="ib-ai-note">{{ aiNote }}</div>
                    </template>
                    <div v-else-if="aiError" class="ib-ai-loading">{{ aiError }}</div>
                    <div v-else class="ib-ai-loading">暂无 AI 研判结果，请点击右上角「重新生成研判」。</div>
                  </div>

                  <!-- 信息来源 Tab: 仅呈现真实来源 -->
                  <div v-else-if="aiTab === 'source'" class="ib-ai-block">
                    <div class="ib-ai-m-label">信息来源</div>
                    <p class="ib-ai-text">
                      本条情报由「{{ sourceOrgText }}」发布，原文发布于 {{ item?.published_at || "时间未标注" }}。
                      页面仅呈现公告原文与附件中实际存在的内容，未作任何推断或补全；完整信息以
                      <a v-if="item?.url" :href="item.url" class="ib-src-link" target="_blank" rel="noopener">原文链接</a>
                      <span v-else>原文链接</span>为准。
                    </p>
                  </div>

                  <!-- 项目规模(展平展示) -->
                  <div v-if="overviewBlocks.length" class="ib-overview">
                    <div v-if="attachmentBlocks.length" class="ib-attach">
                      <div class="ib-ai-m-label">附件清单</div>
                      <ul class="ib-attach-list">
                        <li v-for="(a, i) in attachmentBlocks" :key="i">{{ a }}</li>
                      </ul>
                    </div>
                    <template v-for="(p, i) in overviewBlocks" :key="i">
                      <div v-if="p.kind === 'table' && p.rows?.length" class="ib-ov-table-wrap">
                        <table class="ib-ov-table">
                          <thead>
                            <tr><th v-for="(h, hi) in p.headers" :key="hi">{{ h }}</th></tr>
                          </thead>
                          <tbody>
                            <tr v-for="(r, ri) in p.rows" :key="ri">
                              <td v-for="(c, ci) in r" :key="ci">{{ c }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div v-else-if="p.kind === 'meta'" class="ib-ov-meta">
                        <el-icon><InfoFilled /></el-icon>{{ p.text }}
                      </div>
                      <div v-else-if="p.kind === 'attach'" class="ib-ov-title-bold">
                        <el-icon><Document /></el-icon>{{ p.text }}
                      </div>
                      <div v-else-if="p.kind === 'foot'" class="ib-ov-foot">{{ p.text }}</div>
                      <div v-else class="ib-ov-para">{{ p.text }}</div>
                    </template>
                  </div>
                </div>

                <footer class="ib-card-foot">
                  <el-button v-if="item?.url" size="small" plain @click="openOriginal">
                    <el-icon><Link /></el-icon>查看原文公告
                  </el-button>
                  <div class="ib-foot-info">
                    <span v-if="attachments.length">{{ attachments.length }} 个公告附件</span>
                    <span v-if="item?.published_at">发布时间：{{ item.published_at }}</span>
                  </div>
                </footer>
              </div>

              <!-- 公告附件 -->
              <div v-if="attachments.length" class="ib-card">
                <header class="ib-card-head">
                  <span class="ib-card-title">公告附件</span>
                  <span class="ib-foot-count">{{ attachments.length }} 个</span>
                </header>
                <div class="ib-card-body">
                  <div v-for="a in attachments" :key="a.id" class="ib-att-item">
                    <el-icon class="ib-att-icon"><Document /></el-icon>
                    <a :href="a.preview_url" class="ib-att-link" :title="a.remote_url || a.file_name" target="_blank" rel="noopener">{{ a.file_name }}</a>
                    <span class="ib-att-size">{{ fmtSize(a.file_size) }}</span>
                  </div>
                  <!-- 附件内的表格内容: 原样渲染解析结果, 无数据则不展示 -->
                  <el-table
                    v-if="attTableRows.length"
                    :data="attTableRows"
                    border
                    size="small"
                    max-height="420"
                    class="ib-att-table"
                  >
                    <el-table-column
                      v-for="h in attTable!.headers"
                      :key="h"
                      :prop="h"
                      :label="h"
                      min-width="160"
                      show-overflow-tooltip
                    />
                  </el-table>
                </div>
              </div>
            </el-col>

            <!-- 右主栏: 联系人(动态脱敏) / 二维码 -->
            <el-col :xs="24" :md="8" class="ib-side-col">
              <div v-for="g in contactGroups" :key="g" class="ib-side-card">
                <header class="ib-side-head">
                  <span class="ib-side-title">{{ g }}联系人</span>
                </header>
                <template v-if="contactsByGroup[g]?.length">
                  <ul class="ib-contact-list">
                    <li v-for="c in contactsByGroup[g]" :key="c.id">
                      <span class="ck">姓名：</span><span class="cv">{{ c.name || '***' }}</span>
                    </li>
                    <li v-for="(v, k) in contactDetailRows(contactsByGroup[g][0])" :key="k">
                      <span class="ck">{{ k }}：</span><span class="cv">{{ v || '***' }}</span>
                    </li>
                  </ul>
                </template>
                <p v-else class="ib-side-empty">暂无联系人信息</p>
                <button class="ib-mask-btn"><el-icon><View /></el-icon>查看联系人</button>
              </div>
            </el-col>
          </el-row>
        </div>
      </div>
    </section>
  </SiteLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import SiteLayout from "@/components/site/SiteLayout.vue";
import api from "@/api";
import { ElMessage } from "element-plus";
import { fetchIntelligence, fetchPublicIntent, fetchCachedIntentAi, submitIntentAi, pollIntentAi, fetchIntentAttachments, fetchIntentAttachmentTable, type IntentItem, type IntentAttachment, type AttachmentTable } from "@/api/siteApi";
import { Loading, Refresh, Document, Link, InfoFilled, Phone, Printer, Star, View } from "@element-plus/icons-vue";

const route = useRoute();
const router = useRouter();
const id = Number(route.params.id);

const loading = ref(true);
const item = ref<IntentItem | null>(null);
const favSaving = ref(false);

// 项目跟踪(真实归整线索, 按阶段分组)
const trackedGroups = ref<any[]>([]);
const readLoading = ref<Record<number, boolean>>({});
const trackedLoading = ref(false);
const trackerFallback = ref(false);
async function loadTracked() {
  trackedLoading.value = true;
  try {
    const r: any = await api.get(`/intent/${id}/tracker`);
    if (r?.success) {
      trackedGroups.value = r.groups || [];
      trackerFallback.value = !!r.fallback;
    }
  } catch {
    trackedGroups.value = [];
  } finally {
    trackedLoading.value = false;
  }
}

async function markClueRead(it: any) {
  readLoading.value[it.id] = true;
  try {
    await api.post(`/projects/tracker/mark-read/${it.id}`);
    it.is_read = true;
    ElMessage.success("已标记为已读");
  } catch {
    ElMessage.error("操作失败");
  } finally {
    readLoading.value[it.id] = false;
  }
}
function openUrl(u: string) {
  if (u) window.open(u, "_blank", "noopener");
}
function stageTagType(s: string) {
  return s === "investment" ? "success" : s === "bidding" ? "primary" : "warning";
}

// 项目进展(真实 ProjectProgress, 按日期倒序) + 可配置里程碑阶段(选项集 project_progress_stage)
const progressList = ref<any[]>([]);
const progressStages = ref<any[]>([]);
async function loadProgress() {
  try {
    const r: any = await api.get(`/intent/${id}/progress`);
    if (r?.success) {
      progressList.value = r.items || [];
      progressStages.value = r.stages || [];
    }
  } catch {
    progressList.value = [];
    progressStages.value = [];
  }
}
// 里程碑: 配置阶段 × 真实进展(记录 title 匹配阶段名/值, 同一阶段取最新一条)
const milestones = computed(() => {
  if (!progressStages.value.length) return [];
  const latest = new Map<string, any>();
  for (const it of progressList.value) {
    const t = String(it.title || "");
    const prev = latest.get(t);
    if (!prev || (it.progress_date || "") > (prev.progress_date || "")) latest.set(t, it);
  }
  return progressStages.value.map((s: any, idx: number) => {
    const hit = latest.get(String(s.label || "")) || latest.get(String(s.value || ""));
    return {
      key: String(s.value || idx),
      label: String(s.label || s.value || `阶段${idx + 1}`),
      color: s.color || "",
      reached: !!hit,
      date: hit?.progress_date || "",
      content: hit?.content || "",
    };
  });
});

// 联系卡(公开脱敏数据)
const contactGroups = ["甲方", "设计师", "建造商", "分包"];
const contacts = ref<any[]>([]);
const contactsByGroup = computed(() => {
  const m: Record<string, any[]> = {};
  for (const g of contactGroups) m[g] = [];
  for (const c of contacts.value) {
    (m[c.group] ||= []).push(c);
  }
  return m;
});
function contactDetailRows(c: any): Record<string, string> {
  if (!c) return {};
  const rows: Record<string, string> = {};
  const fields: Array<[string, string]> = [
    ["职务", c.role], ["部门", c.department], ["电话", c.phone], ["手机", c.mobile],
  ];
  for (const [label, v] of fields) {
    if (v) rows[label] = v;
  }
  return rows;
}
async function loadContacts() {
  try {
    const r: any = await api.get(`/public/intent/${id}/contacts`);
    if (r?.success) contacts.value = r.data || [];
  } catch { /* 接口失败静默, 保持空态 */ }
}
const isSaved = ref(false);
const note = ref("");
const attachments = ref<IntentAttachment[]>([]);

// 公告附件中的表格(xlsx 解析结果): 原样渲染, 不做任何推断补全, 无数据则不展示
const attTable = ref<AttachmentTable | null>(null);
const attTableRows = computed(() => {
  const t = attTable.value;
  if (!t) return [];
  return t.rows.map((r) => Object.fromEntries(r.map((v, i) => [t.headers[i] || `列${i + 1}`, v])));
});
// 多项目公告(如水土保持报备清单): 建设单位按实际家数汇总, 不臆造单一主体
const attOwnerSummary = computed(() => {
  const rows = attTableRows.value;
  const key = "建设单位";
  if (!rows.length || !(key in rows[0])) return "";
  const names = rows.map((r) => r[key]).filter((v) => v && v !== "/");
  return names.length ? `共 ${names.length} 家（详见下方报备清单）` : "";
});

// AI 研判
const aiLoading = ref(false);
const aiResult = ref<any>(null);
const aiError = ref("");
const aiCachedAt = ref("");
const aiSource = ref("");
const aiNote = ref("");
const aiTab = ref("summary");
let pollTimer: number | null = null;
let pollCount = 0;

// 「项目阶段/项目规模」Tab 已移除: 其展示的工程款/时间安排均为无数据源的写死值
const aiTabs = [
  { key: "summary", label: "摘要信息" },
  { key: "source", label: "信息来源" },
];

const showAi = computed(() => aiResult.value?.analysis ?? null);
const aiAdviceList = computed(() =>
  showAi.value?.advice?.length ? showAi.value.advice : (item.value ? [item.value.ai.advice] : [])
);
const aiOrgs = computed(() => {
  const fromAi = showAi.value?.parties ?? showAi.value?.orgs ?? [];
  const fromGraph = graphData.value.nodes
    .filter((n: any) => n.id !== "intent_center")
    .map((n: any) => n.name)
    .filter(Boolean);
  return Array.from(new Set([...fromAi, ...fromGraph]));
});

function statusText(s: string | null) {
  return { new: "最新", expired: "已过期", matched: "已匹配" }[s || ""] || s || "—";
}
function goBack() {
  if (window.history.length > 1) router.back();
  else router.push("/site/intelligence");
}
function openOriginal() {
  if (item.value?.url) window.open(item.value.url, "_blank", "noopener");
}
function printPage() {
  window.print();
}
async function loadFavState() {
  if (!item.value?.opp_id) return;
  try {
    const res: any = await api.get("/favorites/state", {
      params: { entity_type: "opportunity", entity_id: item.value.opp_id },
      silent: true,
    } as any);
    isSaved.value = !!res?.data?.active;
  } catch {
    isSaved.value = false;
  }
}
async function toggleSaved() {
  if (!item.value) return;
  if (!item.value.opp_id) {
    ElMessage.warning("该意向暂未关联项目商机，无法收藏");
    return;
  }
  favSaving.value = true;
  try {
    const res: any = await api.post("/favorites/toggle", {
      entity_type: "opportunity",
      entity_id: item.value.opp_id,
    });
    isSaved.value = !!res?.data?.active;
    ElMessage.success(isSaved.value ? "已收藏" : "已取消收藏");
  } catch {
    ElMessage.error("操作失败，请稍后重试");
  } finally {
    favSaving.value = false;
  }
}
function fmtSize(n: number) {
  if (!n) return "";
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / 1024 / 1024).toFixed(1) + " MB";
}

function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}
function startAiTask(taskId: string) {
  stopPoll();
  pollCount = 0;
  pollTimer = window.setInterval(async () => {
    pollCount++;
    const res = await pollIntentAi(taskId);
    if (!res) { if (pollCount > 30) { stopPoll(); aiLoading.value = false; aiError.value = "研判生成超时"; } return; }
    if (res.status === "done" && res.data) {
      stopPoll();
      aiResult.value = res.data;
      aiLoading.value = false;
      aiCachedAt.value = "";
    } else if (res.status === "failed") {
      stopPoll();
      aiLoading.value = false;
      aiError.value = res.error || "研判失败";
    } else if (pollCount > 30) {
      stopPoll();
      aiLoading.value = false;
      aiError.value = "研判生成超时（模型推理较慢）";
    }
  }, 3000);
}
async function runAi() {
  if (!item.value) return;
  aiError.value = "";
  aiLoading.value = true;
  aiResult.value = null;
  const taskId = await submitIntentAi(item.value.id);
  if (!taskId) { aiLoading.value = false; aiError.value = "研判服务暂不可用"; return; }
  startAiTask(taskId);
}
function regenAi() {
  runAi();
}
async function loadAiFromCache() {
  const cached = await fetchCachedIntentAi(id);
  if (cached?.found && cached.data) {
    aiResult.value = {
      source: cached.data.source,
      model: cached.data.model,
      analysis: cached.data.analysis,
      note: cached.data.note,
    };
    aiSource.value = cached.data.source;
    aiNote.value = cached.data.note;
    aiCachedAt.value = cached.data.updated_at || "";
    return true;
  }
  return false;
}
onUnmounted(stopPoll);

const graphData = ref<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] });
const reachPath = ref<{ targets: any[]; paths: any[]; bridges: any[]; note: string }>({
  targets: [], paths: [], bridges: [], note: "",
});
async function loadReachPath() {
  try {
    const r: any = await api.get(`/intent/path/${id}`);
    if (r?.success) {
      reachPath.value = {
        targets: r.targets || [],
        paths: r.paths || [],
        bridges: r.bridges || [],
        note: r.note || "",
      };
    }
  } catch { /* 接口失败静默, 回退 LLM 文案 */ }
}

// ===== 项目概况字段 =====
// 仅展示接口/附件中真实存在的字段; 无数据源的字段(建筑规模/建筑层数/资金来源/建设性质等)一律不展示,
// 避免用写死的占位值冒充脱敏数据。
const projectFields = computed(() => {
  const it = item.value;
  return [
    { label: "工程地址", value: it?.region || "—", cls: "" },
    { label: "招标类型", value: it?.industry || "—", cls: "" },
    { label: "项目类型", value: it?.project_type || "—", cls: "" },
    { label: "发布处室", value: it?.dept || "—", cls: "" },
    { label: "投资金额(万元)", value: it?.amount_level || "原文未披露", cls: "v-amount" },
    { label: "建设单位", value: attOwnerSummary.value || "原文未披露", cls: "" },
    {
      label: "关联商机",
      value: it?.opp_id ? `#${it.opp_id}${it.opp_version ? " " + it.opp_version : ""}` : "—",
      cls: "",
    },
    { label: "AI 热度 / 合作概率", value: it ? `${it.ai.heat} / ${it.ai.coop_prob}` : "—", cls: "v-em" },
  ];
});

// ===== 信息来源(真实发布处室, 不使用任何写死的机构名) =====
const sourceOrgText = computed(() => item.value?.dept || "原文未标注发布处室");

// ===== 项目概况正文解析 (沿用原逻辑) =====
const _NOISE_LINE_RE = /(【(信息发布主体|发布时间|字号|打印|关闭|扫一扫|编辑|字体|分享)|信息发布主体|此件公开发布|打印本页|关闭窗口|分享到|返回顶部|\b大中小\b|^\s*大\s*$|^\s*第[一二三四五六七八九十\d]+页\s*$|^\s*共\d+页\s*$)/;
const _ATTACH_LINE_RE = /^附件\s*[:：]?\s*\d*\.?[^\s]/;
const _SENT_END_RE = /[。；!?！？:]$/;
const _TITLE_START_RE = /^(一|二|三|四|五|六|七|八|九|十|附件|[（(]?[一二三四五六七八九十\d]+[、.])/;
const _PURE_NOISE_RE = /^(字号|字体)[:：]?\s*[大中小](\s*[大中小])*\s*$|^分享到[:：]?\s*$|^打印本页\s*$|^关闭窗口\s*$|^此件公开发布\s*$|^返回顶部\s*$|^大\s*$|^中\s*$|^小\s*$|^第[一二三四五六七八九十\d]+页\s*$|^共\d+页\s*$|【字号\s*[大中小]】?$/;
function _cleanLineTail(l: string): string {
  return l
    .replace(/\s*分享到[:：]?\s*$/, "")
    .replace(/\s*字体\s*[:：]?\s*[大中小](\s*[大中小])*\s*$/, "")
    .replace(/\s*字号\s*[:：]?\s*[大中小](\s*[大中小])*\s*$/, "")
    .trim();
}
function _cleanAnnouncementLines(raw: string): string[] {
  const out: string[] = [];
  const blocks = raw.replace(/\r\n/g, "\n").split(/\n\s*\n+/).map((b) => b.trim()).filter(Boolean);
  for (const block of blocks) {
    const lines = block.split(/\n/)
      .map((l) => l.trim())
      .filter(Boolean)
      .map(_cleanLineTail)
      .filter(Boolean)
      .filter((l) => !_PURE_NOISE_RE.test(l) && l !== "附件");
    if (!lines.length) continue;
    const merged = [lines[0]];
    for (let i = 1; i < lines.length; i++) {
      const prev = merged[merged.length - 1];
      const cur = lines[i];
      if (_SENT_END_RE.test(prev) || _TITLE_START_RE.test(cur) || cur.includes("\t")) {
        merged.push(cur);
      } else {
        merged[merged.length - 1] = prev + cur;
      }
    }
    out.push(...merged);
  }
  return out;
}
function _classifyLine(line: string): "meta" | "title" | "text" | "foot" | "attach" {
  if (/^(附件\d+|附件\s*[:：]?\s*\d+[\.、])/.test(line)) return "attach";
  if (/^(责任编辑|相关链接|主办单位|承办单位)/.test(line) || /^\d{4}年\d{1,2}月\d{1,2}日$/.test(line)) return "foot";
  if (/^(关于.*?(公告|通知|通报|公示|函|意见)$|.+?(人民政府|人民政府$))/u.test(line)) return "title";
  if (/^(发布(时间|日期)|来源[:：]|发文机关[:：]|文号[:：]|字号[:：])/.test(line)) return "meta";
  if (/^[\u4e00-\u9fa5]{2,15}(厅|局|委|部|政府|办公室|中心|局办公室|省.*?厅|自然资源厅)$/.test(line)) return "foot";
  if (/^202\d|^\d{4}年\d/.test(line) && line.length < 25) return "foot";
  return "text";
}
const overviewBlocks = computed(() => {
  const raw = item.value?.body_excerpt || "";
  if (!raw) return [];
  const lines = _cleanAnnouncementLines(raw);
  const seen = new Set<string>();
  const out: Array<{ kind: "meta" | "title" | "table" | "text" | "foot" | "attach"; text: string; headers?: string[]; rows?: string[][] }> = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.includes("\t")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("\t")) {
        rows.push(lines[i].split("\t").map((c) => c.trim()));
        i++;
      }
      const sig = JSON.stringify(rows);
      if (seen.has(sig)) continue;
      seen.add(sig);
      out.push({ kind: "table", text: "", headers: rows[0] || [], rows: rows.slice(1) });
      continue;
    }
    if (seen.has(line)) { i++; continue; }
    seen.add(line);
    if (line.length > 160 && line.includes("。")) {
      const parts = line.split(/(?<=。)/).map((s) => s.trim()).filter((s) => s);
      for (const part of parts) {
        if (seen.has(part)) continue;
        seen.add(part);
        out.push({ kind: "text", text: part });
      }
    } else {
      out.push({ kind: _classifyLine(line), text: line });
    }
    i++;
  }
  return out;
});

const attachmentBlocks = computed(() => {
  const raw = item.value?.body_excerpt || "";
  if (!raw) return [];
  const lines = _cleanAnnouncementLines(raw);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const l of lines) {
    if (_ATTACH_LINE_RE.test(l) && !seen.has(l)) {
      seen.add(l);
      const title = l.replace(/^附件\s*[:：]?\s*/, "").trim();
      if (!title || title.length < 4 || /^\d+$/.test(title)) continue;
      out.push(title);
    }
    if (out.length >= 8) break;
  }
  return out;
});

function fixContactNoise(s: string): string {
  return s
    .replace(/四\s*；\s*川/g, "四川省")
    .replace(/四\s+川/g, "四川省")
    .replace(/四\s*\n\s*川/g, "四川省");
}
const contactLines = computed(() => {
  const blocks = overviewBlocks.value;
  const hit = /(联系单位|联系人|联系电话|联系方式|地址|邮箱|邮编|电话：|电话:)/;
  const raw = blocks
    .filter((b) => b.kind !== "table" && hit.test(b.text))
    .map((b) => b.text.trim())
    .filter(Boolean)
    .join("\n");
  const merged = fixContactNoise(raw);
  const lines = merged
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  return lines.length ? lines : [];
});
const contactDisplay = computed(() => {
  if (contactLines.value.length) return contactLines.value;
  const c = item.value?.contact;
  return c ? [fixContactNoise(c)] : ["暂无公开联系方式"];
});

onMounted(async () => {
  // 优先按 id 直取单条: 不受列表 limit 上限限制, 发布时间较早的情报也能正常打开
  const one = await fetchPublicIntent(id);
  if (one) {
    item.value = one;
  } else {
    // 兜底: 直取失败(未发布/接口异常)时回退列表查找, 保持原有行为
    const all = await fetchIntelligence();
    note.value = all?.note || "";
    item.value = all?.intents.find((i) => i.id === id) ?? null;
  }
  loading.value = false;
  if (!item.value) return;
  loadFavState();
  attachments.value = await fetchIntentAttachments(id);
  // 表格类附件解析为结构化清单(解析失败则静默降级为仅展示附件链接)
  const xls = attachments.value.find((a) => /\.xlsx?$/i.test(a.file_name));
  if (xls) attTable.value = await fetchIntentAttachmentTable(id, xls.id);
  loadContacts();
  try {
    const g: any = await api.get(`/intent/graph/${id}`);
    if (g?.success && (g.nodes?.length || g.center)) {
      const nodes = [{ id: "intent_center", name: g.center?.name || item.value.title, type: "intent", degree: 1 }, ...(g.nodes || [])];
      graphData.value = { nodes, links: g.links || [] };
    }
  } catch { /* 子图加载失败则不展示图谱 */ }
  loadReachPath();
  loadTracked();
  loadProgress();
  const cached = await loadAiFromCache();
  if (!cached) runAi();
});
</script>

<style scoped>
/* ============================================================
   情报动态详情页 - 政企机构风
   主色: 蓝色 #c8102e 系列
   辅色: 黄色提示 / 绿底立项 / 灰底字段
   ============================================================ */
.ib-body {
  padding: 18px 0 60px;
  background: #f5f7fa;
  min-height: 70vh;
}
.ib-loading { min-height: 480px; }
.ib-empty-tip { font-size: 13px; color: #8a8e99; padding: 16px 0; text-align: center; }

/* 项目跟踪 */
.ib-card-sub { font-size: 12px; color: #c0c4cc; font-weight: normal; margin-left: 8px; }
.ib-trace-loading { min-height: 80px; }
.ib-trace-group { margin-bottom: 16px; }
.ib-trace-group:last-child { margin-bottom: 0; }
.ib-trace-group-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ib-trace-count { font-size: 12px; color: #909399; }
.ib-trace-list { list-style: none; margin: 0; padding: 0; }
.ib-trace-item {
  display: flex; align-items: center; gap: 10px;
  padding: 7px 0; border-bottom: 1px dashed #eef0f3; cursor: pointer;
}
.ib-trace-item:last-child { border-bottom: none; }
.ib-trace-dot {
  flex: none; width: 7px; height: 7px; border-radius: 50%;
  background: #c8102e; margin-left: 2px;
}
.ib-trace-title {
  flex: 1; min-width: 0; color: #303133; font-size: 13px;
  text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ib-trace-title:hover { color: #c8102e; text-decoration: underline; }
.ib-trace-time { flex: none; font-size: 12px; color: #a8adb8; }

/* 项目阶段里程碑(阶段定义来自选项集, 可后台配置) */
.ib-ms-card { margin-bottom: 20px; }
.ib-ms-track {
  list-style: none; margin: 0; padding: 0 0 4px;
  display: flex; align-items: flex-start;
  overflow-x: auto;
}
.ib-ms-step {
  flex: 1 1 0; min-width: 110px; position: relative;
  display: flex; flex-direction: column; align-items: center; gap: 5px;
  padding: 0 8px; text-align: center;
}
.ib-ms-step:not(:last-child)::after {
  content: ""; position: absolute;
  left: calc(50% + 18px); right: calc(-50% + 18px); top: 13px;
  height: 2px; background: #e6ebf1;
}
.ib-ms-step.reached:not(:last-child)::after { background: #18ac4f; }
.ib-ms-num {
  position: relative; z-index: 1;
  width: 28px; height: 28px; border-radius: 50%;
  background: #eef1f5; color: #8a8e99;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
  border: 2px solid #fff; box-shadow: 0 0 0 2px #e6ebf1;
  cursor: default;
}
.ib-ms-step.reached .ib-ms-num {
  background: #18ac4f; color: #fff; box-shadow: 0 0 0 2px #18ac4f;
}
.ib-ms-label { font-size: 13px; color: #4a5260; font-weight: 500; }
.ib-ms-step.reached .ib-ms-label { color: #18ac4f; font-weight: 700; }
.ib-ms-date { font-size: 11.5px; color: #a8adb8; }

/* 项目进展时间线(未配置阶段时的回退样式) */
.ib-progress-card { margin-bottom: 20px; }
.ib-progress { list-style: none; margin: 0; padding: 0; }
.ib-progress-item { position: relative; padding: 0 0 16px 20px; }
.ib-progress-item:last-child { padding-bottom: 0; }
.ib-progress-item::before {
  content: ""; position: absolute; left: 4px; top: 9px; bottom: -4px;
  width: 2px; background: #e6e9ef;
}
.ib-progress-item:last-child::before { display: none; }
.ib-progress-dot {
  position: absolute; left: 0; top: 3px; width: 10px; height: 10px;
  border-radius: 50%; background: #c8102e; border: 2px solid #fff;
  box-shadow: 0 0 0 2px #f3c6cf;
}
.ib-progress-head { display: flex; align-items: baseline; gap: 10px; }
.ib-progress-title { font-size: 13.5px; color: #303133; font-weight: 600; }
.ib-progress-date { font-size: 12px; color: #a8adb8; }
.ib-progress-content { font-size: 13px; color: #5a6270; margin-top: 3px; line-height: 1.6; }

/* 顶部蓝色状态条 */
.ib-topbar {
  background: linear-gradient(95deg, #e01a3c 0%, #c8102e 100%);
  color: #fff;
  border-radius: 6px;
  padding: 14px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  box-shadow: 0 4px 10px rgba(47, 123, 224, 0.18);
}
.ib-topbar-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
.ib-badge-cyan {
  background: #fff;
  color: #c8102e;
  font-size: 12px;
  font-weight: 700;
  border-radius: 3px;
  padding: 4px 12px;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.ib-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.4;
  color: #fff;
  word-break: break-word;
}
.ib-version {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  font-family: Consolas, monospace;
  color: #fa8c16;
  background: #fff7e6;
  border-radius: 3px;
  padding: 1px 7px;
  margin-left: 8px;
  vertical-align: middle;
}
.ib-tags { display: inline-flex; gap: 6px; flex-wrap: wrap; }
.ib-tag {
  font-size: 12px;
  background: rgba(255,255,255,0.22);
  color: #fff;
  border-radius: 3px;
  padding: 2px 9px;
  font-weight: 500;
}
.ib-tag.tag-success { background: #4cb24c; }
.ib-tag.tag-info { background: rgba(255,255,255,0.22); }
.ib-tag.tag-warn { background: #f5a623; }
.ib-tag.tag-blue { background: #c8102e; }

.ib-topbar-right { display: flex; gap: 10px; flex-wrap: wrap; flex-shrink: 0; }
.ib-mini-btn {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(255,255,255,0.18);
  color: #fff;
  border: 1px solid rgba(255,255,255,0.36);
  border-radius: 3px;
  padding: 6px 12px;
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.ib-mini-btn:hover { background: rgba(255,255,255,0.3); }
.ib-mini-btn.active { background: #f5a623; border-color: #f5a623; color: #fff; }



/* 黄色提示条 */
.ib-tip {
  margin-top: 14px;
  background: #fff8d6;
  border: 1px solid #f7e0a3;
  border-radius: 4px;
  padding: 10px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #664d00;
}
.ib-tip-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ib-tip strong { color: #b07b00; }
.ib-tip-btn {
  background: #f5a623;
  color: #fff;
  border: none;
  border-radius: 3px;
  padding: 5px 16px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
}
.ib-tip-btn:hover { background: #e09512; }
.ib-tip-right { display: inline-flex; align-items: center; gap: 10px; flex-wrap: wrap; color: #664d00; }
.ib-tip-link { color: #c8102e; background: none; border: none; cursor: pointer; font-size: 12.5px; padding: 0; }

/* 主行 */
.ib-main-row { margin-top: 16px !important; }
.ib-main-col, .ib-side-col { display: flex; flex-direction: column; gap: 14px; }

/* 通用卡片 */
.ib-card {
  background: #fff;
  border: 1px solid #e6ebf1;
  border-radius: 6px;
}
.ib-card-head {
  background: #fdf6f7;
  border-bottom: 1px solid #e6ebf1;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.ib-card-title {
  font-size: 14px; font-weight: 700; color: #1c2a3a;
  padding-left: 10px;
  border-left: 3px solid #c8102e;
  line-height: 1;
}
.ib-card-body { padding: 16px 18px; }
.ib-card-foot {
  border-top: 1px dashed #e6ebf1;
  padding: 10px 16px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
}
.ib-foot-info { font-size: 12.5px; color: #8a8e99; display: flex; gap: 14px; flex-wrap: wrap; }
.ib-foot-count {
  margin-left: auto;
  font-size: 11.5px; color: #b07b00;
  background: #fff8e1; border-radius: 20px; padding: 2px 10px;
}

/* 项目概况: 字段网格 */
.ib-fields {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px 18px;
}
.ib-field {
  display: flex; flex-direction: column; gap: 4px;
  border-bottom: 1px dashed #e6ebf1;
  padding-bottom: 8px;
}
.ib-field-label { font-size: 12.5px; color: #8a8e99; }
.ib-field-value {
  font-size: 13.5px;
  color: #1c2a3a;
  font-weight: 600;
  word-break: break-all;
}
.ib-field-value.v-em { color: #c8102e; }
.ib-field-value.v-amount { color: #f56c00; font-weight: 700; }
.ib-field-value.v-ok { color: #18ac4f; }

.ib-addr {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed #e6ebf1;
}
.ib-addr .ib-field-value { font-size: 13px; color: #4a5260; }

/* 项目跟踪 */
.ib-trace { list-style: none; margin: 0; padding: 0; }
.ib-trace li {
  display: flex; gap: 14px;
  padding: 10px 0;
  border-bottom: 1px dashed #e6ebf1;
  position: relative;
}
.ib-trace li:last-child { border-bottom: none; }
.ib-trace-dot {
  width: 12px; height: 12px;
  border-radius: 50%;
  background: #c7d2e0;
  margin-top: 4px;
  flex-shrink: 0;
  position: relative;
}
.ib-trace-dot.ok { background: #18ac4f; }
.ib-trace-dot.warn { background: #f5a623; }
.ib-trace-body { flex: 1; min-width: 0; }
.ib-trace-time { font-size: 12px; color: #8a8e99; }
.ib-trace-text { font-size: 13.5px; color: #1c2a3a; margin-top: 2px; }

/* 智能分析 Tab 模块 (蓝色块) */
.ib-card-ai { border-color: #f0cdd2; }
.ib-card-head-ai {
  background: linear-gradient(90deg, #c8102e 0%, #e01a3c 100%);
  border-bottom-color: #c8102e;
  padding: 12px 16px;
  color: #fff;
}
.ib-card-head-ai .ib-card-title {
  color: #fff;
  border-left-color: #fff;
}
.ib-head-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1; min-width: 0; }
.ib-tag-llm { background: #fff !important; color: #c8102e !important; border: none !important; font-weight: 700; }
.ib-ai-sub { font-size: 12.5px; color: rgba(255,255,255,0.92); }
.ib-ai-regen {
  display: inline-flex; align-items: center; gap: 4px;
  background: #fff;
  color: #c8102e;
  border: none;
  border-radius: 3px;
  padding: 5px 12px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
}
.ib-ai-regen:hover { background: #f4f7fb; }
.reload-icon { margin-right: 4px; }

.ib-tabs-bar {
  display: flex; gap: 0;
  background: #fdf6f7;
  border-bottom: 1px solid #e6ebf1;
  padding: 0 12px;
}
.ib-tab {
  position: relative;
  padding: 10px 18px;
  font-size: 13px;
  color: #4a5260;
  cursor: pointer;
  transition: color 0.2s ease;
}
.ib-tab:hover { color: #c8102e; }
.ib-tab.active {
  color: #c8102e;
  font-weight: 700;
}
.ib-tab.active::after {
  content: "";
  position: absolute;
  left: 12px; right: 12px; bottom: 0;
  height: 2px;
  background: #c8102e;
  border-radius: 2px 2px 0 0;
}

/* AI 摘要 Tab 内容 */
.ib-ai-loading {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: #4a5260;
  background: #fdf6f7;
  padding: 16px;
  border-radius: 4px;
}
.ib-ai-loading .spin { font-size: 18px; color: #c8102e; animation: spin 1.1s linear infinite; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
.ib-ai-summary {
  font-size: 13.5px; line-height: 1.8; color: #1c2a3a;
  background: #fdf6f7;
  border-left: 3px solid #c8102e;
  padding: 12px 14px;
  border-radius: 4px;
  margin: 0 0 14px;
}
.ib-ai-block { margin-top: 14px; }
.ib-ai-m-label {
  font-size: 13px;
  color: #c8102e;
  font-weight: 700;
  margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px;
}
.ib-help { color: #8a8e99; cursor: help; vertical-align: -2px; }
.ib-ai-text { font-size: 13.5px; line-height: 1.85; color: #4a5260; margin: 6px 0 0; }
.path-note { color: #8a8e99; font-size: 12.5px; margin-top: 2px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  font-size: 12px;
  padding: 3px 11px;
  border-radius: 20px;
  background: #eef3fb;
  color: #c8102e;
  border: 1px solid #f0cdd2;
}
.ib-ai-list {
  margin: 6px 0 0; padding-left: 22px;
}
.ib-ai-list li {
  font-size: 13.5px; line-height: 1.9; color: #4a5260;
}

.ib-path-chain {
  margin-top: 8px;
  padding: 10px 12px;
  border: 1px dashed #f0cdd2;
  border-radius: 4px;
  background: #fdf6f7;
}
.ib-path-target { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.pt-role {
  font-size: 11px; color: #fff;
  background: #c8102e;
  border-radius: 3px;
  padding: 1px 7px;
  flex-shrink: 0;
}
.pt-name { font-size: 13px; font-weight: 700; color: #1c2a3a; }
.ib-path-hops { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; font-size: 12px; line-height: 1.7; }
.ib-path-node {
  background: #fff; border: 1px solid #f0cdd2; border-radius: 3px;
  padding: 2px 7px; color: #4a5260;
  max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ib-path-node.person { border-color: #bcd3ea; color: #3b6fb6; }
.ib-path-node.company { border-color: #e3b7c0; color: #a51c30; }
.ib-path-node.project { border-color: #e5d9bd; color: #b08d57; }
.ib-path-node.region { border-color: #d9d6d0; color: #8a8e99; }
.ib-path-arrow { color: #8a8e99; flex-shrink: 0; }
.ib-path-tip { margin-top: 6px; font-size: 11.5px; color: #c8102e; }
.ib-path-tip.weak { color: #f5a623; }
.ib-bridge-row {
  margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px;
  align-items: center; font-size: 12.5px;
}
.ib-bridge-label { color: #8a8e99; }
.ib-bridge-name {
  background: #eef3fb; color: #c8102e; border-radius: 20px;
  padding: 2px 10px; font-size: 12px; border: 1px solid #f0cdd2;
}
.ib-ai-note {
  margin-top: 14px; font-size: 12px; color: #8a8e99;
  background: #fdf6f7;
  padding: 10px 12px; border-radius: 4px; line-height: 1.65;
}

/* 项目正文(展平展示) */
.ib-overview { margin-top: 14px; border-top: 1px dashed #e6ebf1; padding-top: 14px; }
.ib-attach { background: #fff8e1; border-radius: 4px; padding: 10px 12px; margin-bottom: 12px; border: 1px solid #f7e0a3; }
.ib-attach-list { margin: 0; padding-left: 20px; }
.ib-attach-list li { font-size: 13px; line-height: 1.9; color: #4a5260; }
.ib-ov-table-wrap { overflow-x: auto; margin: 10px 0; }
.ib-ov-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ib-ov-table th, .ib-ov-table td { border: 1px solid #e6ebf1; padding: 7px 10px; text-align: left; }
.ib-ov-table th { background: #f4f7fb; color: #1c2a3a; font-weight: 600; white-space: nowrap; }
.ib-ov-table td { color: #4a5260; }
.ib-ov-para { margin: 5px 0; text-indent: 2em; font-size: 13px; line-height: 1.85; color: #4a5260; }
.ib-ov-meta { margin: 4px 0; font-size: 12.5px; color: #8a8e99; }
.ib-ov-title-bold { font-weight: 700; color: #c8102e; margin: 10px 0 2px; font-size: 13.5px; }
.ib-ov-foot { margin: 6px 0 0; font-size: 12px; color: #8a8e99; border-top: 1px dashed #e6ebf1; padding-top: 6px; }

/* 公告附件 */
.ib-att-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 0;
  border-bottom: 1px dashed #e6ebf1;
}
.ib-att-item:last-child { border-bottom: none; }
.ib-att-icon { color: #c8102e; font-size: 16px; flex-shrink: 0; }
.ib-att-link { font-size: 13px; color: #c8102e; text-decoration: none; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ib-att-link:hover { text-decoration: underline; }
.ib-att-size { font-size: 11.5px; color: #8a8e99; flex-shrink: 0; }
/* 附件内表格(由 xlsx 解析后原样渲染) */
.ib-att-table { margin-top: 12px; font-size: 12.5px; }
.ib-src-link { color: #c8102e; text-decoration: none; }
.ib-src-link:hover { text-decoration: underline; }

/* 右栏: 联系人卡片 */
.ib-side-card {
  background: #fff;
  border: 1px solid #e6ebf1;
  border-radius: 6px;
  overflow: hidden;
}
.ib-side-head {
  background: #fdf6f7;
  border-bottom: 1px solid #e6ebf1;
  padding: 10px 16px;
  display: flex; align-items: center; justify-content: space-between;
}
.ib-side-title {
  font-size: 14px; font-weight: 700; color: #1c2a3a;
  padding-left: 10px;
  border-left: 3px solid #c8102e;
  line-height: 1;
}
.ib-contact-list { list-style: none; margin: 0; padding: 14px 16px; }
.ib-contact-list li {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 0;
  border-bottom: 1px dashed #e6ebf1;
  font-size: 13px; color: #4a5260;
}
.ib-contact-list li:last-child { border-bottom: none; }
.ib-contact-list .ck { color: #8a8e99; flex-shrink: 0; min-width: 50px; }
.ib-contact-list .cv {
  color: #1c2a3a;
  font-weight: 600;
  flex: 1;
  word-break: break-all;
}
.ib-c-tag { background: #f4f7fb !important; color: #c8102e !important; border-color: #f0cdd2 !important; font-size: 10px !important; flex-shrink: 0; }
.ib-side-empty {
  font-size: 12.5px; color: #b5b9c2;
  padding: 16px; text-align: center;
  background: repeating-linear-gradient(
    -45deg,
    transparent, transparent 4px,
    #f4f7fb 4px, #f4f7fb 8px
  );
  margin: 14px;
  border-radius: 4px;
}
.ib-mask-btn {
  display: flex; align-items: center; justify-content: center; gap: 5px;
  width: calc(100% - 28px);
  margin: 0 14px 14px;
  background: #c8102e;
  color: #fff;
  border: none;
  border-radius: 3px;
  padding: 8px 0;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}
.ib-mask-btn:hover { background: #1f6bd0; }

/* 响应式 */
@media (max-width: 992px) {
  .ib-fields { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .ib-topbar { padding: 12px 14px; }
  .ib-title { font-size: 14.5px; }
  .ib-topbar-right { width: 100%; }
  .ib-tip { font-size: 12px; padding: 10px 12px; }
  .ib-tip-right { width: 100%; }
  .ib-fields { grid-template-columns: 1fr; }
  .ib-card-head { flex-wrap: wrap; }
  .ib-tabs-bar { overflow-x: auto; }
  .ib-qr-row { flex-wrap: wrap; }
  .ib-qr-img { width: 84px; height: 84px; }
}
@media (max-width: 560px) {
  .ib-mini-btn span { display: none; }
  .ib-mini-btn { padding: 6px 10px; }
  .ib-side-card { padding: 0; }
}
</style>
