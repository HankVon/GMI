<!--
  网页线索详情页 — 展示爬虫从公告接口抓取的结构化项目信息(完整)
  布局：顶部主信息卡(标题+来源/关键词) + 时间信息卡(截止/发布) + 结构化字段网格 + 公告全文
-->
<template>
  <div class="clue-detail">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>{{ clue?.title || "加载中..." }}</span>
      </template>
    </el-page-header>

    <div v-loading="loading">
      <!-- 顶部主信息卡 -->
      <div v-if="clue" class="fgbs-header">
        <div class="fgbs-head-main">
          <h2 class="fgbs-title">{{ clue.title || "-" }}</h2>
          <el-tag v-if="clue.source_name" type="primary" effect="dark" size="small">{{ clue.source_name }}</el-tag>
        </div>

        <!-- 信息小卡 -->
        <div class="fgbs-info-cards">
          <div class="fgbs-info-card">
            <div class="fgbs-info-icon"><el-icon><Timer /></el-icon></div>
            <div class="fgbs-info-body">
              <div class="fgbs-info-label">截止时间</div>
              <div class="fgbs-info-value" style="color:#e6a23c;font-weight:600">
                {{ formatTime(meta.expire_time) }}
              </div>
            </div>
          </div>
          <div class="fgbs-info-card">
            <div class="fgbs-info-icon"><el-icon><Calendar /></el-icon></div>
            <div class="fgbs-info-body">
              <div class="fgbs-info-label">发布时间</div>
              <div class="fgbs-info-value">{{ formatTime(meta.noticeTime || clue.published_at) }}</div>
            </div>
          </div>
          <div class="fgbs-info-card">
            <div class="fgbs-info-icon"><el-icon><Wallet /></el-icon></div>
            <div class="fgbs-info-body">
              <div class="fgbs-info-label">预算金额</div>
              <div class="fgbs-info-value">{{ budgetText }}</div>
            </div>
          </div>
        </div>

        <!-- 关键词/地域 tags -->
        <div class="fgbs-tags">
          <el-tag
            v-for="k in hitKeywords" :key="k" size="small" type="warning" effect="light"
            style="margin-right:6px"
          >{{ k }}</el-tag>
          <el-tag v-if="clue.region" size="small" type="info" effect="plain">{{ clue.region }}</el-tag>
        </div>
      </div>

      <!-- AI 分析 -->
      <el-row v-if="clue && aiSummary" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <el-card class="section-card ai-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title"><el-icon><MagicStick /></el-icon> AI 分析</span>
                <el-tag size="small" type="success" effect="light">Ollama 本地大模型</el-tag>
              </div>
            </template>
            <div class="ai-summary">{{ aiSummary }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 项目概况 -->
      <el-row v-if="clue && meta.overview" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title"><el-icon><Memo /></el-icon> 项目概况</span>
              </div>
            </template>
            <div class="overview-box">{{ cleanSection(meta.overview) }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 项目资质 -->
      <el-row v-if="clue && (meta.specific_qualification || meta.qualification)" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title"><el-icon><Files /></el-icon> 项目资质</span>
              </div>
            </template>
            <div v-if="cleanSection(meta.specific_qualification)" class="qual-block">
              <div class="qual-label">特定资格要求</div>
              <div class="qual-text">{{ cleanSection(meta.specific_qualification) }}</div>
            </div>
            <div v-if="cleanSection(meta.qualification)" class="qual-block">
              <div class="qual-label">资格要求</div>
              <div class="qual-text">{{ cleanSection(meta.qualification) }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 结构化信息 -->
      <el-row v-if="clue" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title"><el-icon><DataAnalysis /></el-icon> 项目结构化信息</span>
              </div>
            </template>

            <!-- 关键字段 -->
            <el-descriptions :column="2" border size="default" class="desc-grid">
              <el-descriptions-item v-if="meta.openTenderCode" label="项目编号">
                {{ meta.openTenderCode }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.purchaseManner" label="采购方式">
                {{ mannerLabel(meta.purchaseManner) }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.purchaser" label="采购人" :span="2">
                {{ meta.purchaser }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.agency" label="代理机构" :span="2">
                {{ meta.agency }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.regionName" label="地域">
                {{ meta.regionName }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.regionCode" label="行政区划码">
                {{ meta.regionCode }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.purchaseNature" label="采购性质">
                {{ natureLabel(meta.purchaseNature) }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.purchaseCategory" label="采购类别">
                {{ meta.purchaseCategory }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.projectTypeName" label="项目类型">
                {{ meta.projectTypeName }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.capitalProject" label="资金性质">
                {{ meta.capitalProject }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.platform" label="平台">
                {{ meta.platform }}
              </el-descriptions-item>
              <el-descriptions-item v-if="meta.purchaseModeName" label="采购模式">
                {{ meta.purchaseModeName }}
              </el-descriptions-item>
            </el-descriptions>

            <!-- 全部原始字段(中文标签) -->
            <template v-if="otherFields.length">
              <div class="sub-section-title">全部字段</div>
              <div class="all-fields">
                <div v-for="f in otherFields" :key="f.k" class="field-row">
                  <span class="field-k">{{ fieldLabel(f.k) }}</span>
                  <span class="field-v">{{ f.v }}</span>
                </div>
              </div>
            </template>
          </el-card>
        </el-col>
      </el-row>

      <!-- 关联实体(线索解析出的项目/单位/人员) -->
      <el-row v-if="clue" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title"><el-icon><Connection /></el-icon> 关联实体（已解析）</span>
                <el-tag v-if="derived.length" size="small" type="success" effect="light">
                  已解析 {{ derived.length }} 个实体
                </el-tag>
                <el-tag v-else size="small" type="info" effect="plain">未解析</el-tag>
              </div>
            </template>
            <template v-if="derived.length">
              <div class="derived-grid">
                <div
                  v-for="(d, i) in derived" :key="i"
                  class="derived-item" :class="`dv-${d.entity_type}`"
                  @click="goEntity(d)"
                >
                  <div class="dv-icon">
                    <el-icon>
                      <OfficeBuilding v-if="d.entity_type === 'company'" />
                      <User v-else-if="d.entity_type === 'person'" />
                      <FolderOpened v-else />
                    </el-icon>
                  </div>
                  <div class="dv-body">
                    <div class="dv-name">{{ d.name }}</div>
                    <div class="dv-meta">
                      {{ entityTypeLabel(d.entity_type) }}
                      <template v-if="d.code"> · {{ d.code }}</template>
                      <el-icon class="dv-arrow"><Right /></el-icon>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <div v-else class="derived-empty">
              该线索尚未解析出系统实体。可在「网页线索」页点击「补全解析关联」，或运行数据流水线 backfill 阶段自动识别公告中的单位/人员/项目。
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 标讯人脉匹配(P1-5 阶段一): 复用后端 /biz-network/tenders/* -->
      <el-row v-if="clue && clue.id" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <TenderMatchPanel :clue-id="Number(clue.id)" />
        </el-col>
      </el-row>

      <!-- 相关附件 -->
      <el-row v-if="clue && attachments.length" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title"><el-icon><Paperclip /></el-icon> 相关附件</span>
              </div>
            </template>
            <div class="attach-list">
              <div v-for="(a, i) in attachments" :key="i" class="attach-item">
                <el-icon class="attach-icon"><Document /></el-icon>
                <a :href="a.url" target="_blank" rel="noopener" class="attach-name">{{ a.name }}</a>
                <el-tag size="small" type="info" effect="plain">{{ fileExt(a.name) }}</el-tag>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 公告全文 -->
      <el-row v-if="clue" :gutter="16" style="margin-top: 16px">
        <el-col :span="24">
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title"><el-icon><Document /></el-icon> 公告全文</span>
                <el-link v-if="clue.url" type="primary" underline="never" :href="clue.url" target="_blank">
                  打开原网页 <el-icon><TopRight /></el-icon>
                </el-link>
              </div>
            </template>
            <div class="clue-content">{{ clue.content || clue.summary || "（无正文）" }}</div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { DataAnalysis, Document, Timer, Calendar, Wallet, TopRight, Memo, Files, Paperclip, MagicStick, Connection, OfficeBuilding, User, FolderOpened, Right } from "@element-plus/icons-vue";
import api from "@/api";
import TenderMatchPanel from "@/components/TenderMatchPanel.vue";

const route = useRoute();
const router = useRouter();
const clue = ref<any>(null);
const loading = ref(false);

// 线索解析出的系统实体(项目/单位/人员), 由后端 /web-clues/{id} 返回
const derived = computed<any[]>(() => {
  const list = clue.value?.derived;
  return Array.isArray(list) ? list : [];
});

const ENTITY_LABELS: Record<string, string> = {
  project: "项目", company: "单位", person: "人员",
};
function entityTypeLabel(t: string) {
  return ENTITY_LABELS[t] || t;
}

function goEntity(d: any) {
  const routes: Record<string, string> = {
    project: `/workspace/projects/${d.id}`,
    company: `/workspace/companies/${d.id}`,
    person: `/workspace/persons/${d.id}`,
  };
  const p = routes[d.entity_type];
  if (p) router.push(p);
}

// 兼容驼峰(原始接口字段)与下划线(解析映射)两种命名
const meta = computed<any>(() => {
  const m = (clue.value?.meta || {}) as Record<string, any>;
  const pick = (a?: string, b?: string) => m[a ?? ""] ?? m[b ?? ""];
  return {
    ...m,
    expire_time: pick("expire_time", "expireTime"),
    noticeTime: pick("noticeTime", "publishTime"),
    budget: pick("budget"),
    openTenderCode: pick("openTenderCode", "planCodes"),
    purchaseManner: pick("purchaseManner"),
    purchaser: pick("purchaser"),
    agency: pick("agency"),
    regionName: pick("regionName"),
    regionCode: pick("regionCode"),
    purchaseNature: pick("purchaseNature"),
    purchaseCategory: pick("purchaseCategory"),
    projectTypeName: pick("projectTypeName"),
    capitalProject: pick("capitalProject"),
    platform: pick("platform"),
    purchaseModeName: pick("purchaseModeName"),
    overview: pick("overview"),
    qualification: pick("qualification"),
    specific_qualification: pick("specific_qualification"),
  };
});

// 采购性质映射
function natureLabel(code?: string) {
  if (!code) return "-";
  const map: Record<string, string> = { "1": "政府采购", "2": "非政府采购" };
  return map[code] || code;
}

// 清理段落: 去掉开头冒号/空白/重复换行
function cleanSection(s?: string) {
  if (!s) return "";
  return s.replace(/^[：:\s]+/, "").split("\n").map((l) => l.trim()).filter(Boolean).join("\n");
}

const hitKeywords = computed(() => (clue.value?.hit_keywords || "").split(",").filter(Boolean));

const attachments = computed<any[]>(() => {
  const m = meta.value;
  const list = m.attachments || [];
  return Array.isArray(list) ? list : [];
});

// AI 分析: meta.llm.ai_summary.summary 或 ai_filter.reason
const aiSummary = computed(() => {
  const llm = meta.value.llm;
  if (!llm || typeof llm !== "object") return "";
  const s = llm.ai_summary?.summary;
  if (s) return s;
  const f = llm.ai_filter;
  if (f?.reason) return f.reason;
  return "";
});

function fileExt(name: string) {
  const m = /\.([a-zA-Z0-9]+)$/.exec(name || "");
  return m ? m[1].toUpperCase() : "文件";
}

const budgetText = computed(() => {
  const b = meta.value.budget;
  if (!b) return "-";
  const n = Number(b);
  return Number.isFinite(n) ? `${n.toLocaleString()} 元` : String(b);
});

const MANNER_MAP: Record<string, string> = {
  "1": "公开招标", "2": "邀请招标", "3": "竞争性谈判", "4": "询价",
  "5": "竞争性磋商", "6": "单一来源", "7": "框架协议",
};
function mannerLabel(code?: string) {
  if (!code) return "-";
  return MANNER_MAP[code] || code;
}

// 与项目无关的内部/系统字段(不在字段区展示)
const SYSTEM_KEYS = [
  "id", "noticeId", "planId", "contentId", "site", "siteId", "siteName",
  "channel", "channelId", "channelName", "dataSource", "editor", "source",
  "clickNum", "clicks", "status", "state", "isdel", "isDel", "htmlIndexnum",
  "orderNum", "isTop", "publisher", "creator", "ownerName", "userId",
  "username", "pageView", "viewCount", "readCount", "likes", "comments",
  "author", "title", "description", "createTime", "updateTime", "overview",
  "qualification", "specific_qualification",
];
// 已在顶部信息卡/概况/资质独立栏展示的
const EXCLUDED_KEYS = [
  "expire_time", "expireTime", "noticeTime", "publishTime", "budget",
  "openTenderCode", "purchaseManner", "purchaser", "agency", "regionName",
  "regionCode", "purchaseNature", "purchaseCategory", "projectTypeName",
  "capitalProject", "platform", "purchaseModeName",
  ...SYSTEM_KEYS,
];

// 其余字段(基于原始 meta, 排除已单独展示的)
const otherFields = computed(() => {
  const m = clue.value?.meta || {};
  return Object.keys(m)
    .filter((k) => !EXCLUDED_KEYS.includes(k))
    .filter((k) => {
      const v = m[k];
      if (v === null || v === undefined || v === "") return false;
      // 跳过复杂对象(数组/嵌套对象)
      if (typeof v === "object") return false;
      return true;
    })
    .map((k) => ({ k, v: String(m[k]) }));
});

const FIELD_LABELS: Record<string, string> = {
  id: "公告ID", noticeId: "公告编号", planId: "计划ID", planCodes: "项目编码",
  site: "站点ID", siteName: "站点名称", channel: "频道ID", channelName: "频道名称",
  openTenderCode: "项目编号", openTenderTime: "开标时间", projectCode: "项目代码",
  contentId: "内容ID", title: "标题", author: "发布单位", source: "来源",
  dataSource: "数据来源", editor: "编辑", clickNum: "点击量", clicks: "点击量",
  status: "状态", state: "状态", isdel: "删除标记", htmlIndexnum: "HTML序号",
  orderNum: "排序", isTop: "置顶", start_time: "开始时间", end_time: "结束时间",
  expire_time: "截止时间", expireTime: "截止时间", noticeEndTime: "公告结束时间",
  noticeTime: "发布时间", publishTime: "发布时间", createTime: "创建时间",
  updateTime: "更新时间", budget: "预算金额", regionName: "地域",
  regionCode: "行政区划码", purchaser: "采购人", purchaserCode: "采购人代码",
  purchaserAddr: "采购人地址", purchaserLinkPhone: "采购人电话",
  agency: "代理机构", agencyCode: "代理机构代码", purchaseManner: "采购方式",
  purchaseNature: "采购性质", purchaseCategory: "采购类别",
  purchaseModeName: "采购模式", projectTypeName: "项目类型",
  capitalProject: "资金性质", platform: "平台", description: "项目概况",
  catalogName: "品目名称", catalogueName: "品目", catalogueNameList: "品目列表",
  noticeType: "公告类型", workflowInstanceStepsVoList: "流程步骤",
  files: "附件", attchs: "附件列表", attchList: "附件列表",
  overview: "项目概况", qualification: "资格要求",
  specific_qualification: "特定资格要求",
};
function fieldLabel(k: string) {
  return FIELD_LABELS[k] || k;
}

function formatTime(t?: string) {
  if (!t) return "-";
  return t.replace("T", " ").slice(0, 19);
}

async function loadDetail() {
  loading.value = true;
  try {
    const id = route.params.id;
    const res: any = await api.get(`/web-clues/${id}`);
    clue.value = res;
  } catch { /* 拦截器处理 */ }
  finally { loading.value = false; }
}

onMounted(loadDetail);
</script>

<style scoped>
.clue-detail { padding: 4px; }
.fgbs-header {
  background: #fff; border-radius: 10px; padding: 20px 24px; margin-top: 14px;
  border-top: 4px solid #2979ff; box-shadow: 0 1px 4px rgba(31,39,51,.06);
}
.fgbs-head-main { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.fgbs-title { margin: 0; font-size: 20px; font-weight: 600; color: #1f2733; flex: 1; }
.fgbs-info-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 18px; }
.fgbs-info-card {
  display: flex; align-items: center; gap: 10px; background: #f7f9fc;
  border-radius: 8px; padding: 12px 14px;
}
.fgbs-info-icon { font-size: 22px; color: #2979ff; }
.fgbs-info-label { font-size: 12px; color: #8a94a6; }
.fgbs-info-value { font-size: 14px; color: #1f2733; margin-top: 2px; }
.fgbs-tags { margin-top: 14px; }
.section-card { border-radius: 10px; }
.section-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 15px; font-weight: 600; color: #1f2733; display: inline-flex; align-items: center; gap: 6px; }
.desc-grid { margin-top: 4px; }
.ai-card { border-top: 3px solid #13c2c2; }
.ai-summary {
  background: linear-gradient(135deg, #f0fbfb, #f7f9fc); border-radius: 6px;
  padding: 14px 16px; font-size: 13px; line-height: 1.9; color: #1f2733;
}
.overview-box {
  background: #f0f6ff; border-left: 3px solid #2979ff; border-radius: 6px;
  padding: 12px 16px; font-size: 13px; line-height: 1.8; color: #3c4a5d; white-space: pre-wrap;
}
.qual-block { margin-bottom: 12px; }
.qual-block:last-child { margin-bottom: 0; }
.qual-label { font-size: 13px; font-weight: 600; color: #1f2733; margin-bottom: 6px; }
.qual-text {
  background: #f7f9fc; border-radius: 6px; padding: 10px 14px;
  font-size: 13px; line-height: 1.8; color: #3c4a5d; white-space: pre-wrap;
}
.sub-section-title { margin: 18px 0 10px; font-size: 13px; font-weight: 600; color: #1f2733; }
.all-fields {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 0 20px;
  background: #f7f9fc; border-radius: 8px; padding: 12px 16px;
}
.field-row { display: flex; gap: 8px; padding: 5px 0; border-bottom: 1px dashed #e3e8ef; font-size: 13px; }
.field-k { color: #8a94a6; flex: 0 0 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.field-v { color: #3c4a5d; word-break: break-all; }
.clue-content {
  white-space: pre-wrap; font-size: 13px; color: #3c4a5d; line-height: 1.8;
  max-height: 600px; overflow-y: auto;
}
.attach-list { display: flex; flex-direction: column; gap: 8px; }
.attach-item {
  display: flex; align-items: center; gap: 8px;
  background: #f7f9fc; border-radius: 6px; padding: 8px 14px;
}
.attach-icon { color: #2979ff; font-size: 16px; }
.attach-name {
  font-size: 13px; color: #2979ff; text-decoration: none; flex: 1;
  word-break: break-all;
}
.attach-name:hover { text-decoration: underline; }
.derived-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px;
}
.derived-item {
  display: flex; align-items: center; gap: 12px;
  background: #f7f9fc; border: 1px solid #ebeef5; border-radius: 8px;
  padding: 12px 14px; cursor: pointer; transition: all .15s;
}
.derived-item:hover { border-color: #2979ff; background: #f0f6ff; box-shadow: 0 1px 4px rgba(41,121,255,.12); }
.dv-icon {
  width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
  font-size: 20px; flex-shrink: 0;
}
.dv-project .dv-icon { background: #eef4ff; color: #2979ff; }
.dv-company .dv-icon { background: #f0f9eb; color: #67c23a; }
.dv-person .dv-icon { background: #fdf6ec; color: #e6a23c; }
.dv-body { flex: 1; min-width: 0; }
.dv-name {
  font-size: 13px; font-weight: 600; color: #1f2733;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dv-meta {
  font-size: 12px; color: #8a94a6; margin-top: 3px;
  display: flex; align-items: center; gap: 4px;
}
.dv-arrow { margin-left: auto; color: #c0c4cc; }
.derived-empty {
  font-size: 13px; color: #8a94a6; background: #f7f9fc;
  border-radius: 6px; padding: 14px 16px; line-height: 1.8;
}
</style>
