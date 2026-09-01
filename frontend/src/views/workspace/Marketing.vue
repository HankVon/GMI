<!-- 营销智能体: 感知 → 决策 → 执行 → 反馈 闭环驾驶舱 -->
<template>
  <div class="mk-page">
    <div class="page-head">
      <div>
        <h2>营销智能体</h2>
        <p class="page-desc">
          感知(GEO监测) → 决策(商机评分/选题) → 执行(内容工厂) → 反馈(引用回流) 全链路闭环
        </p>
      </div>
      <div class="head-actions">
        <el-button :loading="loading" @click="load"><el-icon style="margin-right: 4px"><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <!-- 品牌配置提示 -->
    <el-alert v-if="!brandNames.length" type="warning" :closable="false" style="margin-bottom: 14px">
      <template #title>
        尚未配置品牌词 — 请到 <el-link type="primary" @click="goGeo">GEO 监测</el-link> 页配置「本公司名称/简称」，
        才能识别 AI 回答中是否提及本公司
      </template>
    </el-alert>

    <!-- 四环卡片 -->
    <el-row :gutter="14" class="cycle-row">
      <el-col :span="6" v-for="c in cycleCards" :key="c.key">
        <el-card class="cycle-card" shadow="never" :body-style="{ padding: '16px 18px' }">
          <div class="cycle-head">
            <div class="cycle-icon" :style="{ background: c.color }">
              <el-icon :size="20"><component :is="c.icon" /></el-icon>
            </div>
            <div>
              <div class="cycle-name">{{ c.name }}</div>
              <div class="cycle-desc">{{ c.desc }}</div>
            </div>
          </div>
          <div class="cycle-stats">
            <div v-for="s in c.stats" :key="s.label" class="cycle-stat">
              <b :style="{ color: c.color }">{{ s.value }}</b>
              <span>{{ s.label }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 商机与选题 -->
    <el-row :gutter="14">
      <el-col :span="12">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="section-header">
              <span class="section-title">🎯 高价值商机（{{ opportunities.length }}）</span>
              <el-button size="small" text type="primary" @click="goOpportunities">查看全部</el-button>
            </div>
          </template>
          <el-table :data="opportunities" size="small" max-height="360">
            <el-table-column label="阶段" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="stageType(row.source)">{{ row.source_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" show-overflow-tooltip min-width="220">
              <template #default="{ row }">
                <el-link v-if="row.url" :href="row.url" target="_blank" type="primary" :underline="false">
                  {{ row.title }}
                </el-link>
                <span v-else>{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column label="地域" width="90">
              <template #default="{ row }">{{ row.region || '-' }}</template>
            </el-table-column>
            <el-table-column label="评分" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.score >= 6 ? 'danger' : row.score >= 3 ? 'warning' : 'info'">
                  {{ row.score }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="section-header">
              <span class="section-title">💡 内容选题推荐（{{ topics.length }}）</span>
              <el-button size="small" text type="primary" @click="goContent">去内容工厂</el-button>
            </div>
          </template>
          <div v-if="!topics.length" class="empty-tip">暂无选题 — 先到 GEO 监测页录入几条 AI 回答</div>
          <div v-for="t in topics" :key="t.title" class="topic-item">
            <div class="topic-main">
              <el-tag size="small" :type="topicSourceType(t.source)" effect="plain">{{ sourceLabel(t.source) }}</el-tag>
              <span class="topic-title">{{ t.title }}</span>
            </div>
            <div class="topic-rationale">{{ t.rationale }}</div>
            <div class="topic-actions">
              <el-button size="small" type="primary" plain @click="generateFromTopic(t)">
                <el-icon style="margin-right: 4px"><MagicStick /></el-icon>生成内容
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- GEO 引用源 -->
    <el-card class="panel-card" shadow="never" style="margin-top: 14px">
      <template #header>
        <div class="section-header">
          <span class="section-title">📗 AI 高频引用源（GEO 监测反馈）</span>
          <span class="section-sub">AI 在回答中引用了哪些来源 → 反向指导内容生产</span>
        </div>
      </template>
      <div v-if="!citedSources.length" class="empty-tip">暂无引用数据</div>
      <el-row :gutter="12" v-else>
        <el-col :span="6" v-for="s in citedSources.slice(0, 8)" :key="s.domain" style="margin-bottom: 12px">
          <div class="cited-box">
            <div class="cited-title">{{ s.title }}</div>
            <div class="cited-meta">{{ s.count }} 次被引用</div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import api from "@/api";
import { Refresh, Search, Aim, EditPen, DataLine, MagicStick } from "@element-plus/icons-vue";

const router = useRouter();
const loading = ref(false);
const dashboard = ref<any>({});
const brandNames = computed(() => dashboard.value.brand_names || []);
const opportunities = computed(() => dashboard.value.opportunities || []);
const topics = computed(() => dashboard.value.topics || []);
const citedSources = computed(() => dashboard.value.geo?.cited_sources || []);
const cycle = computed(() => dashboard.value.cycle || {});

const cycleCards = computed(() => [
  {
    key: "perceive", name: "感知层", desc: "GEO 监测 + 情报采集",
    color: "linear-gradient(135deg,#4d6bfe,#6b83fe)", icon: Search,
    stats: [
      { label: "AI 回答监测", value: cycle.value.perceive?.geo_mentions ?? 0 },
      { label: "提及本公司", value: cycle.value.perceive?.self_visible ?? 0 },
    ],
  },
  {
    key: "decide", name: "决策层", desc: "商机评分 + 选题推荐",
    color: "linear-gradient(135deg,#ff9f43,#ffbe76)", icon: Aim,
    stats: [
      { label: "高价值商机", value: cycle.value.decide?.opportunities ?? 0 },
      { label: "内容选题", value: cycle.value.decide?.topics ?? 0 },
    ],
  },
  {
    key: "execute", name: "执行层", desc: "数据内容工厂",
    color: "linear-gradient(135deg,#00b894,#55efc4)", icon: EditPen,
    stats: [
      { label: "内容资产", value: cycle.value.execute?.content_total ?? 0 },
      { label: "已发布", value: cycle.value.execute?.published ?? 0 },
    ],
  },
  {
    key: "feedback", name: "反馈层", desc: "引用回流迭代",
    color: "linear-gradient(135deg,#6c5ce7,#a29bfe)", icon: DataLine,
    stats: [
      { label: "引用来源", value: cycle.value.feedback?.cited_sources ?? 0 },
      { label: "内容被AI引用", value: cycle.value.feedback?.content_cited ?? 0 },
    ],
  },
]);

async function load() {
  loading.value = true;
  try {
    const r: any = await api.get("/marketing/dashboard?days=30");
    dashboard.value = r;
  } catch { /* 拦截器已提示 */ }
  loading.value = false;
}

function stageType(s: string) {
  return s === "意向" ? "warning" : s === "招标" ? "danger" : "success";
}
function topicSourceType(s: string) {
  return s === "data_hot" ? "success" : s === "geo_gap" ? "danger" : "primary";
}
function sourceLabel(s: string) {
  return { data_hot: "数据热点", geo_gap: "可见度缺口", cite_gap: "引用源缺口" }[s] || s;
}
async function generateFromTopic(t: any) {
  const params: any = {};
  if (t.kind === "industry_report") params.days = 90;
  if (t.kind === "faq" || t.kind === "article") params.topic = t.title.replace(/^《?|》?$/, "").replace(/^「?|」?$/, "").trim();
  try {
    await api.post("/content/generate", { kind: t.kind, params });
    ElMessage.success(`已生成草稿：《${t.title}》`);
    goContent();
  } catch { /* 拦截器已提示 */ }
}
function goGeo() { router.push("/workspace/geo"); }
function goContent() { router.push("/workspace/content"); }
function goOpportunities() { router.push("/workspace/geo"); }

onMounted(load);
</script>

<style scoped>
.mk-page { display: flex; flex-direction: column; gap: 14px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; }
.page-head h2 { margin: 0; font-size: 20px; color: #111827; }
.page-desc { margin: 6px 0 0; color: #8a94a6; font-size: 13px; }
.cycle-card { border-radius: 12px; border: 1px solid #eef1f8; }
.cycle-head { display: flex; align-items: center; gap: 10px; }
.cycle-icon {
  width: 40px; height: 40px; border-radius: 10px; color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}
.cycle-name { font-weight: 700; color: #111827; font-size: 15px; }
.cycle-desc { font-size: 12px; color: #a3adc0; margin-top: 2px; }
.cycle-stats { display: flex; gap: 26px; margin-top: 14px; }
.cycle-stat { display: flex; flex-direction: column; }
.cycle-stat b { font-size: 22px; }
.cycle-stat span { font-size: 12px; color: #909399; margin-top: 2px; }
.panel-card { border-radius: 12px; border: 1px solid #eef1f8; }
.section-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-weight: 600; color: #111827; }
.section-sub { font-size: 12px; color: #a3adc0; margin-left: 10px; }
.topic-item {
  padding: 10px 12px; border: 1px solid #eef1f8; border-radius: 8px;
  margin-bottom: 8px; background: #fafcff;
}
.topic-main { display: flex; align-items: center; gap: 8px; }
.topic-title { font-weight: 600; color: #303133; font-size: 13.5px; }
.topic-rationale { color: #8a94a6; font-size: 12px; margin: 6px 0; line-height: 1.5; }
.topic-actions { display: flex; justify-content: flex-end; }
.cited-box { border: 1px solid #eef1f8; border-radius: 8px; padding: 10px 12px; background: #fafcff; }
.cited-title { font-size: 13px; color: #303133; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cited-meta { font-size: 12px; color: #4d6bfe; margin-top: 4px; }
.empty-tip { color: #a3adc0; font-size: 13px; padding: 20px 0; text-align: center; }
</style>
