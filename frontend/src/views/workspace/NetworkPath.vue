<template>
  <div class="network-page">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span class="page-title">人脉路径 — 从「{{ me.name || '我' }}」到「{{ targetName || '目标人员' }}」</span>
      </template>
    </el-page-header>

    <el-card style="margin-top: 16px" shadow="never">
      <!-- 顶部: 概览 + AI 分析 -->
      <template #header>
        <div class="np-header">
          <div class="np-header-left">
            <span class="np-title">人脉路径</span>
            <el-tag v-if="found && steps.length > 0" type="primary" size="small" effect="dark">
              {{ steps.length - 1 }} 步可达
            </el-tag>
            <el-tag v-if="me.person_id" type="success" size="small" effect="plain">我：{{ me.name }}</el-tag>
            <el-tag v-else type="warning" size="small">当前用户未关联人员</el-tag>
          </div>
          <div class="np-header-right">
            <el-tooltip
              :content="aiModel ? `使用 ${aiModel} 对话分析` : '未配置 AI 模型，将使用内置规则分析（可在右上角头像菜单配置）'"
              placement="bottom-end"
            >
              <el-button
                type="primary" :icon="MagicStick"
                :disabled="!found || steps.length === 0"
                @click="openAiChat"
              >
                AI 分析
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>

      <!-- 未关联人员提示 -->
      <el-alert
        v-if="!me.person_id"
        type="warning" show-icon :closable="false"
        :title="me.message || '当前用户未关联人员，请先在「我的信息」中录入'"
        style="margin-bottom: 12px"
      />

      <!-- 加载动画 -->
      <div v-else-if="loading" class="path-loading">
        <el-skeleton animated :rows="3" style="max-width: 560px; margin: 0 auto" />
        <div class="path-loading-tip">
          <el-icon class="is-loading" :size="18"><Loading /></el-icon>
          <span>正在知识图谱中检索从「{{ me.name }}」到「{{ targetName || '目标人员' }}」的最短人脉路径…</span>
        </div>
      </div>

      <!-- 未找到路径 -->
      <el-empty
        v-else-if="!found && steps.length === 0"
        :description="message || '未找到人脉路径'"
        :image-size="80"
      />

      <!-- 找到路径 -->
      <template v-else-if="steps.length > 0">
        <!-- 紧凑横向链路 -->
        <div class="path-chain-bar">
          <template v-for="(step, idx) in steps" :key="idx">
            <div class="chain-node" :class="chainNodeClass(idx)">
              <div class="chain-avatar" :style="{ background: avatarBg(idx, step) }">
                <span v-if="step.type === 'Person'" class="avatar-text">{{ avatarChar(step.name) }}</span>
                <el-icon v-else-if="step.type === 'Company'" :size="16"><OfficeBuilding /></el-icon>
                <el-icon v-else :size="16"><FolderOpened /></el-icon>
              </div>
              <div class="chain-info">
                <div class="chain-name">{{ step.name }}</div>
                <div class="chain-sub">
                  <el-tag v-if="idx === steps.length - 1" size="small" type="primary">目标</el-tag>
                  <span v-else-if="idx > 0" class="chain-type">{{ nodeTypeLabel(step.type) }}</span>
                </div>
              </div>
            </div>
            <div v-if="idx < steps.length - 1" class="chain-arrow" :class="relBadgeType(steps[idx + 1].relation)">
              <el-icon :size="14"><Right /></el-icon>
              <span class="chain-rel-label">{{ steps[idx + 1].relation_label }}</span>
            </div>
          </template>
        </div>

        <!-- 时间线展开详情 -->
        <div class="path-timeline">
          <div class="timeline-title">路径详情</div>
          <el-timeline>
            <template v-for="(step, idx) in steps" :key="idx">
              <el-timeline-item
                :timestamp="`第 ${idx + 1} 站`"
                :type="timelineType(idx)"
                placement="top"
                size="large"
              >
                <div class="tl-card" :class="{ 'is-me': idx === 0, 'is-target': idx === steps.length - 1 }">
                  <div class="tl-head">
                    <span class="tl-name">{{ step.name }}</span>
                    <el-tag size="small" :type="nodeTagType(step.type)">{{ nodeTypeLabel(step.type) }}</el-tag>
                    <el-tag v-if="idx === 0" size="small" type="danger" effect="dark">起点 · 我</el-tag>
                    <el-tag v-if="idx === steps.length - 1" size="small" type="primary" effect="dark">终点 · 目标</el-tag>
                  </div>
                  <div class="tl-meta">
                    <span v-if="step.position"><el-icon><Briefcase /></el-icon>{{ step.position }}</span>
                    <span v-if="step.company_name"><el-icon><OfficeBuilding /></el-icon>{{ step.company_name }}</span>
                    <span v-if="step.company_type"><el-icon><CollectionTag /></el-icon>{{ step.company_type }}</span>
                    <span v-if="step.category"><el-icon><FolderOpened /></el-icon>类别：{{ catLabel(step.category) }}</span>
                    <span v-if="step.status && step.type === 'Project'">
                      <el-icon><CircleCheck /></el-icon>状态：{{ statusLabel(step.status) }}
                    </span>
                  </div>
                  <div v-if="idx < steps.length - 1" class="tl-rel">
                    通过
                    <el-tag size="small" :type="relBadgeTagType(steps[idx + 1].relation)">
                      {{ steps[idx + 1].relation_label }}
                    </el-tag>
                    连接到下一站
                    <span v-if="steps[idx + 1].rel_via_project" class="tl-rel-ctx">
                      （合作项目：<el-link type="primary" :underline="false" size="small"
                        @click="goNode('project', steps[idx + 1].via_project_id)">
                        {{ steps[idx + 1].rel_via_project }}
                      </el-link>）
                    </span>
                    <span v-else-if="steps[idx + 1].rel_company" class="tl-rel-ctx">
                      （所属单位：{{ steps[idx + 1].rel_company }}）
                    </span>
                    <span v-else-if="steps[idx + 1].rel_role" class="tl-rel-ctx">
                      （参与角色：{{ steps[idx + 1].rel_role }}）
                    </span>
                  </div>
                  <el-link
                    v-if="step.type === 'Person' && step.id && idx !== 0"
                    type="primary" :underline="false" size="small"
                    @click="goNode('person', step.id)"
                  >查看人员</el-link>
                  <el-link
                    v-else-if="step.type === 'Company' && step.id"
                    type="primary" :underline="false" size="small"
                    @click="goNode('company', step.id)"
                  >查看单位</el-link>
                  <el-link
                    v-else-if="step.type === 'Project' && step.id"
                    type="primary" :underline="false" size="small"
                    @click="goNode('project', step.id)"
                  >查看项目</el-link>
                </div>
              </el-timeline-item>
            </template>
          </el-timeline>
        </div>
      </template>
    </el-card>

    <!-- AI 人脉分析师: 右侧聊天抽屉(SSE 流式 + 多轮互动) -->
    <AiAnalystChat
      v-model="aiChatVisible"
      :me-name="'我'"
      :target-name="targetName"
      :steps="steps"
      :fallback-result="fallbackResult"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  OfficeBuilding, FolderOpened, Right, Loading,
  Briefcase, CollectionTag, CircleCheck, MagicStick,
} from "@element-plus/icons-vue";
import api from "@/api";
import AiAnalystChat from "@/components/AiAnalystChat.vue";

const route = useRoute();
const router = useRouter();
const targetPersonId = ref(Number(route.params.id));

const me = ref<any>({});
const targetName = ref("");
const found = ref(false);
const steps = ref<any[]>([]);
const message = ref("");
const loading = ref(true);

/** 项目类别中文映射(从 option-set 动态加载) */
const catLabelMap = ref<Record<string, string>>({});
function catLabel(v: string): string {
  if (!v) return "";
  return catLabelMap.value[v] || v;
}
async function loadCatLabels() {
  try {
    const res: any = await api.get("/option-sets/project_category/items");
    const m: Record<string, string> = {};
    for (const i of (res.items || [])) m[i.value] = i.label;
    catLabelMap.value = m;
  } catch { catLabelMap.value = {}; }
}

const aiModel = ref("");
const aiChatVisible = ref(false);
const fallbackResult = ref<any>(null);

const AVATAR_GRADIENTS = [
  "linear-gradient(135deg, #667eea, #764ba2)",
  "linear-gradient(135deg, #f093fb, #f5576c)",
  "linear-gradient(135deg, #4facfe, #00f2fe)",
  "linear-gradient(135deg, #43e97b, #38f9d7)",
  "linear-gradient(135deg, #fa709a, #fee140)",
  "linear-gradient(135deg, #30cfd0, #330867)",
];

function nodeTypeLabel(t: string): string {
  const m: Record<string, string> = { Person: "人员", Company: "单位", Project: "项目" };
  return m[t] || t;
}

/** 跳转图谱节点详情: 仅对合法数字 id 跳转, 避免 /workspace/xxx/NaN */
function goNode(type: "person" | "company" | "project", id: any) {
  const pid = Number(id);
  if (!Number.isFinite(pid) || pid <= 0) return;
  router.push(`/workspace/${type}s/${pid}`);
}
function nodeTagType(t: string): string {
  const m: Record<string, string> = { Person: "primary", Company: "success", Project: "warning" };
  return m[t] || "info";
}
function avatarChar(name: string): string {
  return (name || "?").trim().charAt(0).toUpperCase();
}
function avatarBg(idx: number, step: any): string {
  if (idx === 0) return "linear-gradient(135deg, #f56c6c, #ff9d6c)";
  if (step.type === "Company") return "linear-gradient(135deg, #36cfc9, #597ef7)";
  if (step.type === "Project") return "linear-gradient(135deg, #ffa940, #ffc53d)";
  return AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length];
}
function statusLabel(s: string): string {
  const m: Record<string, string> = { active: "进行中", done: "已完成", finished: "已完成", paused: "暂停", closed: "已结束" };
  return m[s] || s;
}
function relBadgeType(rel: string): string {
  const m: Record<string, string> = {
    COLLEAGUE: "rel-colleague", COLLABORATED_WITH: "rel-collab",
    WORKS_AT: "rel-works", PARTICIPATES_IN: "rel-participate",
  };
  return m[rel] || "";
}
function relBadgeTagType(rel: string): string {
  const m: Record<string, string> = {
    COLLEAGUE: "success", COLLABORATED_WITH: "primary",
    WORKS_AT: "warning", PARTICIPATES_IN: "info",
  };
  return m[rel] || "info";
}
function chainNodeClass(idx: number): string {
  if (idx === 0) return "is-me";
  if (idx === steps.value.length - 1) return "is-target";
  return "";
}
function timelineType(idx: number): string {
  if (idx === 0) return "danger";
  if (idx === steps.value.length - 1) return "primary";
  return "success";
}

async function load() {
  loading.value = true;
  try { me.value = await api.get("/network/me"); } catch { me.value = {}; }
  if (!me.value?.person_id) { steps.value = []; loading.value = false; return; }
  const minDelay = new Promise((r) => setTimeout(r, 500));
  try {
    const [res] = await Promise.all([
      api.get(`/network/path/${targetPersonId.value}`) as Promise<any>,
      minDelay,
    ]);
    found.value = res.found;
    steps.value = res.steps || [];
    targetName.value = res.target?.name || "";
    message.value = res.message || "";
  } catch {
    found.value = false; steps.value = [];
  } finally {
    loading.value = false;
  }
}

/**
 * 内置规则分析: 基于路径信息生成结构化公关建议。
 * 用于未配置 AI 模型时的回退(在聊天窗口中以首条消息展示)。
 */
function buildAiAnalysis(): any {
  if (!steps.value.length) return null;
  const list = steps.value;

  // 节点集合
  const persons = list.filter((s) => s.type === "Person");
  const companies = list.filter((s) => s.type === "Company");
  const projectsInPath = list.filter((s) => s.type === "Project");

  // 关系集合 (i=1..)
  const rels = list.slice(1).map((s, i) => ({
    type: s.relation,
    label: s.relation_label,
    viaProject: s.rel_via_project,
    viaProjectId: s.rel_via_project ? findViaProjectId(i) : null,
    company: s.rel_company,
    role: s.rel_role,
  }));
  const collabRels = rels.filter((r) => r.type === "COLLABORATED_WITH" && r.viaProject);
  const colleagueRels = rels.filter((r) => r.type === "COLLEAGUE");

  const distance = list.length - 1;
  const targetStep = list[list.length - 1];

  // 摘要
  const projCount = collabRels.length + projectsInPath.length;
  const compCount = companies.length + colleagueRels.length;
  let summary = `通过 ${distance} 步可从「${me.value.name}」触达「${targetStep.name}」`;
  if (projCount > 0) summary += `，路径中涉及 ${projCount} 个合作项目`;
  if (compCount > 0) summary += `，${compCount} 个关联单位`;
  summary += "。";

  // 关键桥接人: 路径中间 Person(非起终点)
  const bridges = list.slice(1, -1).filter((s) => s.type === "Person").map((s) => ({
    id: s.id, name: s.name,
    position: s.position, company_name: s.company_name,
    tip: s.company_name
      ? `在「${s.company_name}」${s.position ? "任职" + s.position : "任职"}，是你们之间的关键节点，可主动联系以获取引荐`
      : "是连接你与目标的关键人物，建议直接沟通请求引荐",
  }));

  // 关键单位
  const companyItems = companies.map((c) => {
    const sameCoCount = list.filter(
      (s) => s.type === "Person" && s.company_name === c.name
    ).length;
    return {
      id: c.id, name: c.name,
      tip: sameCoCount >= 2
        ? `路径上 ${sameCoCount} 人与此单位相关，可基于单位背景切入`
        : `路径上的关联单位，可考虑以业务合作为切入点`,
    };
  });
  colleagueRels.forEach((r) => {
    if (r.company && !companyItems.find((x) => x.name === r.company)) {
      companyItems.push({
        id: null, name: r.company,
        tip: "同单位关系，可作为快速引荐依据",
      });
    }
  });

  // 合作项目
  const projectItems = projectsInPath.map((p) => ({
    id: p.id, name: p.name,
    category: p.category, status: p.status,
    tip: p.category
      ? `类别：${catLabel(p.category)}${p.status ? "，" + statusLabel(p.status) : ""}，可作为共同话题`
      : "可作为共同话题切入",
  }));
  collabRels.forEach((r) => {
    if (r.viaProject && !projectItems.find((x) => x.name === r.viaProject)) {
      projectItems.push({
        id: null, name: r.viaProject,
        category: "", status: "",
        tip: "你与目标通过此项目产生关联，是最佳破冰话题",
      });
    }
  });

  // 公关建议
  const advice: string[] = [];
  if (distance === 1) {
    advice.push("一步可达，关系最直接，可直接联系对方本人。");
  } else if (distance === 2) {
    advice.push("两步可达，建议优先通过中间人引荐，比冷启动成功率更高。");
    const mid = list[1];
    if (mid?.type === "Person") {
      advice.push(`中间人「${mid.name}」${mid.company_name ? "（" + mid.company_name + "）" : ""}是突破关键，建议先与其建立沟通。`);
    }
  } else if (distance >= 3) {
    advice.push(`路径较长（${distance} 步），建议通过项目或单位关系作为切入话题，再请中间人引荐。`);
  }
  if (collabRels.length > 0) {
    advice.push(`你与目标在「${collabRels[0].viaProject}」等项目上有过交集，可基于项目复盘或后续合作展开对话。`);
  }
  if (colleagueRels.length > 0) {
    const co = colleagueRels[0].company;
    advice.push(`存在同单位关系（${co}），可通过单位内部渠道或同事圈获取推荐。`);
  }
  if (companies.length > 0) {
    advice.push(`路径中涉及单位「${companies[0].name}」，可考虑以单位间的业务往来作为切入点。`);
  }
  if (advice.length === 0) {
    advice.push("建议先建立初步联系，再逐步深化关系。");
  }

  // 潜在合作机会
  const opportunities: string[] = [];
  if (projectItems.length > 0) {
    opportunities.push(`基于共同项目「${projectItems[0].name}」可探讨后续合作或经验复用。`);
  }
  const sameCompanyPersons = persons.filter((p) => p.company_name && p.company_name === targetStep.company_name);
  if (sameCompanyPersons.length > 0) {
    opportunities.push(`目标所在单位「${targetStep.company_name}」已有熟人资源，可挖掘新的合作场景。`);
  }
  if (bridges.length > 0) {
    opportunities.push(`通过桥接人「${bridges[0].name}」可拓展你与目标所在圈层的资源。`);
  }
  if (opportunities.length === 0) {
    opportunities.push("建议先建立个人层面的信任，再探索业务合作。");
  }

  return { summary, bridges, companies: companyItems, projects: projectItems, advice, opportunities };
}

function loadAiModel() {
  try {
    const cfg = JSON.parse(localStorage.getItem("ssm_ai_config") || "null");
    aiModel.value = cfg?.model || "";
  } catch { aiModel.value = ""; }
}

function findViaProjectId(relIdx: number): number | null {
  // 从 steps[i+1] 的 rel_via_project 名字反查项目 id(不直接存, 通过名字匹配)
  const target = steps.value[relIdx + 1]?.rel_via_project;
  if (!target) return null;
  const p = steps.value.find((s) => s.type === "Project" && s.name === target);
  return p?.id || null;
}

function openAiChat() {
  if (!steps.value.length) return;
  fallbackResult.value = buildAiAnalysis();
  aiChatVisible.value = true;
}

onMounted(() => { load(); loadAiModel(); loadCatLabels(); });

// 同一路由参数变化(如张三→孙七)时 Vue Router 复用组件实例, 必须监听参数重新加载,
// 否则页面与 AI 对话框会停留在旧目标。
watch(
  () => route.params.id,
  (nv) => {
    targetPersonId.value = Number(nv);
    me.value = {};
    targetName.value = "";
    found.value = false;
    steps.value = [];
    message.value = "";
    fallbackResult.value = null;
    aiChatVisible.value = false; // 关闭旧目标的 AI 抽屉
    load();
    loadAiModel();
  }
);
</script>

<style scoped>
.network-page { max-width: 920px; margin: 0 auto; }
.page-title { font-weight: 600; }
.np-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.np-header-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.np-title { font-weight: 600; font-size: 16px; }

/* 加载 */
.path-loading { padding: 24px 8px; }
.path-loading-tip { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 18px; color: #909399; font-size: 13px; }
.path-loading-tip .is-loading { animation: rotating 1.2s linear infinite; color: #2979ff; }
@keyframes rotating { from { transform: rotate(0); } to { transform: rotate(360deg); } }

/* 紧凑横向链路 */
.path-chain-bar {
  display: flex; align-items: center; justify-content: center;
  gap: 8px; flex-wrap: wrap;
  padding: 14px 8px; margin-bottom: 8px;
  background: linear-gradient(90deg, #fff5f5, #ecf5ff);
  border-radius: 10px;
  border: 1px solid #f0f0f0;
}
.chain-node {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px;
  border-radius: 20px;
  background: #fff;
  border: 1px solid #e4e7ed;
  transition: all 0.2s ease;
}
.chain-node:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,0.06); }
.chain-node.is-me { border-color: #f56c6c; background: #fff5f5; }
.chain-node.is-target { border-color: #2979ff; background: #ecf5ff; }
.chain-avatar {
  width: 30px; height: 30px; flex-shrink: 0;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 600; font-size: 14px;
}
.avatar-text { font-size: 14px; }
.chain-info { display: flex; flex-direction: column; line-height: 1.2; }
.chain-name { font-size: 13.5px; font-weight: 600; color: #303133; }
.chain-sub { font-size: 11.5px; color: #909399; margin-top: 2px; }
.chain-type { color: #909399; }

.chain-arrow {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  background: #f5f7fa; color: #606266;
}
.chain-arrow.rel-colleague { background: #f0f9eb; color: #67c23a; }
.chain-arrow.rel-collab { background: #ecf5ff; color: #2979ff; }
.chain-arrow.rel-works { background: #fdf6ec; color: #e6a23c; }
.chain-arrow.rel-participate { background: #f4f4f5; color: #909399; }
.chain-rel-label { font-weight: 600; }

/* 时间线 */
.path-timeline { margin-top: 12px; }
.timeline-title {
  font-weight: 600; font-size: 14px;
  color: #303133; margin-bottom: 12px;
  padding-left: 4px;
  border-left: 3px solid #2979ff;
}
.tl-card {
  background: #fff; padding: 12px 14px;
  border-radius: 8px; border: 1px solid #ebeef5;
}
.tl-card.is-me { border-color: #f56c6c; background: #fff8f8; }
.tl-card.is-target { border-color: #2979ff; background: #f0f7ff; }
.tl-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.tl-name { font-weight: 600; font-size: 15px; color: #303133; }
.tl-meta { display: flex; flex-wrap: wrap; gap: 4px 14px; color: #606266; font-size: 12.5px; margin: 4px 0 8px; }
.tl-meta > span { display: inline-flex; align-items: center; gap: 4px; }
.tl-meta .el-icon { color: #909399; }
.tl-rel { font-size: 13px; color: #606266; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tl-rel-ctx { color: #909399; font-size: 12.5px; }
</style>
