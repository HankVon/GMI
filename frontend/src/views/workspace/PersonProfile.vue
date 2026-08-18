<!--
  人员主页 — 基础信息(可编辑) + 动态字段 + 参与项目轨迹(可退出)
-->
<template>
  <div class="person-profile">
    <el-page-header @back="$router.back()" title="返回列表">
      <template #content>
        <span>{{ person.name || "加载中..." }}</span>
      </template>
    </el-page-header>

    <!-- 顶部主信息卡(白底 + 蓝色顶边, 姓名 + 状态 + 所属单位 + 编辑) -->
    <div class="fgbs-header">
      <div class="fgbs-head-main">
        <h2 class="fgbs-title">
          {{ person.name || "-" }}
          <span v-if="companyName !== '-'" class="title-company">({{ companyName }})</span>
        </h2>
        <el-tag :type="person.status === 'active' ? 'success' : 'info'" effect="dark" size="small">
          {{ person.status === 'active' ? '在职' : '离职' }}
        </el-tag>
        <div class="fgbs-head-spacer" />
        <el-button v-if="!editing" type="primary" size="small" class="fgbs-print" @click="viewNetwork">
          <el-icon><Share /></el-icon><span>查看人脉</span>
        </el-button>
        <!-- <el-button v-if="!editing" type="primary" size="small" class="fgbs-print" @click="startEdit">
          <el-icon><Edit /></el-icon><span>编辑</span>
        </el-button> -->
      </div>

      <!-- 三张信息小卡: 人员编码 / 职位 / 联系电话 -->
      <div class="fgbs-info-cards">
        <div class="fgbs-info-card">
          <div class="fgbs-info-icon"><el-icon><Document /></el-icon></div>
          <div class="fgbs-info-body">
            <div class="fgbs-info-label">人员编码</div>
            <div class="fgbs-info-value">{{ person.code || "-" }}</div>
          </div>
        </div>
        <div class="fgbs-info-card">
          <div class="fgbs-info-icon"><el-icon><Briefcase /></el-icon></div>
          <div class="fgbs-info-body">
            <div class="fgbs-info-label">职位</div>
            <div class="fgbs-info-value">{{ person.position || "-" }}</div>
          </div>
        </div>
        <div class="fgbs-info-card">
          <div class="fgbs-info-icon"><el-icon><Phone /></el-icon></div>
          <div class="fgbs-info-body">
            <div class="fgbs-info-label">联系电话</div>
            <div class="fgbs-info-value">{{ person.phone || "-" }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI分析能力横幅 -->
    <div class="ai-banner">
      <div class="ai-banner-left">
        <span class="ai-banner-label"><el-icon><MagicStick /></el-icon><b>AI分析:</b></span>
        <span v-for="(c, i) in AI_CHIPS" :key="i" class="ai-chip" @click="openAiChat(c)">{{ c }}</span>
      </div>
      <el-link type="primary" :underline="false" class="ai-more" @click="openAiChat()">
        更多分析 <el-icon><ArrowRight /></el-icon>
      </el-link>
    </div>

    <!-- 统计卡片(数字可点击查看明细) -->
    <div class="fgbs-stats">
      <div class="fgbs-stat">
        <div class="stat-label">参与项目</div>
        <a class="stat-num stat-link" @click="openProjectDrawer('all')">{{ trajectory.length }}</a>
        <span class="stat-hint">个</span>
      </div>
      <div class="fgbs-stat">
        <div class="stat-label">参与中</div>
        <a class="stat-num stat-link" @click="openProjectDrawer('active')">{{ activeTrajectoryCount }}</a>
        <span class="stat-hint">个</span>
      </div>
      <div class="fgbs-stat">
        <div class="stat-label">负责项目</div>
        <a class="stat-num stat-link" @click="openProjectDrawer('manager')">{{ managerActiveCount }}</a>
        <span class="stat-hint">个</span>
      </div>
      <div class="fgbs-stat">
        <div class="stat-label">合作单位</div>
        <a class="stat-num stat-link" @click="openCompanyDrawer()">{{ companyCount }}</a>
        <span class="stat-hint">家</span>
      </div>
    </div>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>基本信息</span>
            <el-button
              v-if="!editing" type="primary" size="small" style="float: right"
              @click="startEdit">编辑</el-button>
            <div v-else style="float: right; display: flex; gap: 8px">
              <el-button size="small" @click="cancelEdit">取消</el-button>
              <el-button type="primary" size="small" :loading="saving" @click="saveEdit">保存</el-button>
            </div>
          </template>

          <!-- 查看模式 -->
          <template v-if="!editing">
            <div class="person-avatar">
              <el-avatar :size="80" class="avatar-pic avatar-pic-lg">{{ person.name?.charAt(0) }}</el-avatar>
              <h2>{{ person.name }}</h2>
              <div class="avatar-actions">
                <el-tag :type="person.status === 'active' ? 'success' : 'info'">
                  {{ person.status === 'active' ? '在职' : '离职' }}
                </el-tag>
                <el-link
                  type="primary" :underline="false" class="member-relation-link"
                  @click="viewNetwork"
                >查看人脉</el-link>
              </div>
            </div>
            <el-descriptions :column="1" border style="margin-top: 16px">
              <el-descriptions-item label="人员编码">{{ person.code }}</el-descriptions-item>
              <el-descriptions-item label="职位">{{ person.position || "-" }}</el-descriptions-item>
              <el-descriptions-item label="所属单位">
                <span v-if="person.company_id" class="company-link" @click="goCompany(person.company_id)">
                  {{ companyName }}
                </span>
                <span v-else>-</span>
              </el-descriptions-item>
              <!-- <el-descriptions-item label="邮箱">{{ person.email || "-" }}</el-descriptions-item> -->
              <el-descriptions-item label="电话">{{ person.phone || "-" }}</el-descriptions-item>
              <!-- <el-descriptions-item label="入职日期">{{ person.entry_date || "-" }}</el-descriptions-item> -->
              <!-- <el-descriptions-item v-if="person.resign_date" label="离职日期">{{ person.resign_date }}</el-descriptions-item> -->
              <el-descriptions-item
                v-for="df in dynamicFields"
                :key="df.field_key"
                :label="df.display_name"
              >
                {{ person.ext_attrs?.[df.field_key] ?? "-" }}
              </el-descriptions-item>
            </el-descriptions>
          </template>

          <!-- 编辑模式 -->
          <el-form ref="editFormRef" v-else :model="editForm" label-width="100px" :rules="builtinRules">
            <el-form-item label="编码"><el-input v-model="editForm.code" disabled /></el-form-item>
            <el-form-item label="姓名" prop="name"><el-input v-model="editForm.name" /></el-form-item>
            <el-form-item label="职位"><el-input v-model="editForm.position" /></el-form-item>
            <el-form-item label="所属单位">
              <el-select
                v-model="editForm.company_id"
                filterable remote clearable
                :remote-method="searchCompanies"
                placeholder="输入单位名称搜索"
                style="width: 100%"
              >
                <el-option
                  v-for="c in companyOptions"
                  :key="c.id"
                  :label="c.name"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
            <!-- <el-form-item label="邮箱"><el-input v-model="editForm.email" /></el-form-item> -->
            <el-form-item label="电话"><el-input v-model="editForm.phone" /></el-form-item>
            <!-- <el-form-item label="状态">
              <el-select v-model="editForm.status">
                <el-option label="在职" value="active" />
                <el-option label="离职" value="resigned" />
              </el-select>
            </el-form-item> -->
            <!-- <el-form-item label="入职日期">
              <el-date-picker v-model="editForm.entry_date" type="date" value-format="YYYY-MM-DD" />
            </el-form-item> -->
            <DynamicForm ref="dynamicFormRef" entity-type="person" v-model="editFormDynamic" mode="edit" />
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card>
          <template #header><span>参与项目轨迹 ({{ trajectory.length }})</span></template>
          <el-timeline v-if="trajectory.length > 0">
            <el-timeline-item
              v-for="t in trajectory"
              :key="t.member_id"
              :timestamp="formatDate(t.joined_at)"
              placement="top"
              :color="t.is_active ? '#409EFF' : '#909399'"
            >
              <el-card
                shadow="hover"
                class="trajectory-card"
                :class="{ 'trajectory-card-left': !t.is_active }"
                @click="goProject(t.project_id)"
              >
                <div class="trajectory-header">
                  <strong class="project-link">{{ t.project_name }}</strong>
                  <div>
                    <el-tag size="small" :type="t.role === 'manager' ? 'danger' : ''">{{ roleLabel(t.role) }}</el-tag>
                    <el-tag
                      v-if="t.stage"
                      size="small" type="primary" effect="plain" style="margin-left: 8px"
                    >{{ t.stage }}</el-tag>
                    <el-tag size="small" :type="t.is_active ? 'success' : 'info'" style="margin-left: 8px">
                      {{ t.is_active ? '参与中' : '已退出' }}
                    </el-tag>
                    <el-tag
                      v-if="t.is_active && t.role === 'manager'"
                      size="small" type="warning" effect="plain" style="margin-left: 8px"
                    >联系人不能退出</el-tag>
                    <el-button
                      v-else-if="t.is_active"
                      type="danger" text size="small" style="margin-left: 8px"
                      @click.stop="exitProject(t)">退出项目</el-button>
                  </div>
                </div>
                <div class="trajectory-dates">
                  加入 {{ formatDate(t.joined_at) }}
                  <template v-if="t.left_at"> → 退出 {{ formatDate(t.left_at) }}</template>
                  <template v-else> → 至今</template>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无参与项目" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 统计卡明细抽屉: 参与项目 / 参与中 / 负责项目(ProjectCard 质感) -->
    <el-drawer
      v-model="projectDrawerVisible"
      :size="680"
      direction="rtl"
      :title="`${projectDrawerTitle}（${projectDrawerList.length}）`"
    >
      <div v-if="projectDrawerList.length" class="drawer-list">
        <ProjectCard
          v-for="p in projectDrawerList"
          :key="p.member_id"
          :project="p"
          :role-label-map="personRoleLabelMap"
          :category-label-map="categoryLabelMap"
          @open="goProject(p.project_id)"
        />
      </div>
      <el-empty v-else :description="`暂无${projectDrawerTitle}`" :image-size="80" />
    </el-drawer>

    <!-- 统计卡明细抽屉: 合作单位 -->
    <el-drawer
      v-model="companyDrawerVisible"
      :size="620"
      direction="rtl"
      :title="`合作单位（${cooperatedCompanies.length}）`"
    >
      <div v-if="cooperatedCompanies.length" class="drawer-list">
        <div v-for="c in cooperatedCompanies" :key="c.company_id" class="coop-card">
          <div class="coop-head">
            <div class="coop-title-row">
              <el-icon class="coop-icon"><OfficeBuilding /></el-icon>
              <strong class="coop-name" @click="goCompany(c.company_id)">{{ c.name }}</strong>
            </div>
            <el-tag size="small" type="info">{{ c.projects.length }} 项目 · {{ c.persons.length }} 人</el-tag>
          </div>
          <div class="coop-sub" v-if="c.projects.length">
            <span class="coop-sub-label">合作项目</span>
            <el-tag
              v-for="p in c.projects"
              :key="p.id"
              size="small"
              type="primary"
              effect="plain"
              class="coop-tag"
              @click="goProject(p.id)"
            >{{ p.name }}</el-tag>
          </div>
          <div class="coop-sub" v-if="c.persons.length">
            <span class="coop-sub-label">对接人</span>
            <el-tag
              v-for="pp in c.persons"
              :key="pp.id"
              size="small"
              type="info"
              effect="plain"
              class="coop-tag"
              @click="goPerson(pp.id)"
            >{{ pp.name }}<template v-if="pp.position"> · {{ pp.position }}</template></el-tag>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无合作单位" :image-size="80" />
    </el-drawer>

    <!-- AI 分析师抽屉 -->
    <AiAnalystChat
      :key="aiChatKey"
      v-model="aiChatVisible"
      :me-name="aiPathMode ? '我' : ''"
      :target-name="person.name || '目标人员'"
      :steps="aiSteps"
      :is-path="aiPathMode"
      :fallback-result="aiFallback"
      :preset-question="aiPresetQuestion"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Document, Briefcase, Phone, MagicStick, ArrowRight, Share, OfficeBuilding,
} from "@element-plus/icons-vue";
import dayjs from "dayjs";
import api from "@/api";
import DynamicForm from "@/components/DynamicForm.vue";
import AiAnalystChat from "@/components/AiAnalystChat.vue";
import ProjectCard from "@/components/ProjectCard.vue";

const route = useRoute();
const router = useRouter();
const personId = Number(route.params.id);

const person = ref<any>({});
const trajectory = ref<any[]>([]);
const dynamicFields = ref<any[]>([]);
const editing = ref(false);
const saving = ref(false);
const editForm = ref<any>({});
const editFormDynamic = ref<any>({ ext_attrs: {} });
const dynamicFormRef = ref<any>(null);
const editFormRef = ref<any>(null);
const builtinRules = {
  name: [{ required: true, message: "姓名为必填项", trigger: "blur" }],
};
const companyName = ref<string>("-");
const companyOptions = ref<any[]>([]);

/* ─────────── 360° 看板: AI 分析 ─────────── */
const AI_CHIPS = [
  "分析此人的背景与专业能力",
  "分析此人的合作建议与沟通策略",
  "分析从「我」到「此人」的人脉路径",
];
const aiChatVisible = ref(false);
const aiChatKey = ref(0);
const aiPresetQuestion = ref<string | undefined>(undefined);
const aiFallback = ref<any>(null);

/** 统计卡: 参与中项目数 / 负责(经理角色且在途)项目数 / 合作单位数 */
const activeTrajectoryCount = computed(() => trajectory.value.filter((t: any) => t.is_active).length);
const managerActiveCount = computed(
  () => trajectory.value.filter((t: any) => t.role === "manager" && t.is_active).length
);
const companyCount = ref(0);
/** 合作单位明细(后端聚合: 单位 + 合作项目 + 联系人) */
const cooperatedCompanies = ref<any[]>([]);
/** 统计卡明细抽屉状态 */
const projectDrawerVisible = ref(false);
const projectDrawerTitle = ref("参与项目");
const projectDrawerList = ref<any[]>([]);
const companyDrawerVisible = ref(false);

/** 项目角色中文映射(ProjectCard 用) */
const personRoleLabelMap: Record<string, string> = {
  manager: "项目联系人", member: "成员", observer: "观察者",
};
/** 项目类别中文映射(从选项集直接加载, 独立于动态字段加载时序, 保证 ProjectCard 稳定显示中文) */
const categoryLabelMap = ref<Record<string, string>>({});
async function loadCategories() {
  try {
    const res: any = await api.get("/option-sets/project_category/items");
    const m: Record<string, string> = {};
    for (const i of (res.items || [])) m[i.value] = i.label;
    categoryLabelMap.value = m;
  } catch { categoryLabelMap.value = {}; }
}

function openProjectDrawer(kind: "all" | "active" | "manager") {
  const list = trajectory.value;
  if (kind === "active") {
    projectDrawerTitle.value = "参与中的项目";
    projectDrawerList.value = list.filter((t: any) => t.is_active);
  } else if (kind === "manager") {
    projectDrawerTitle.value = "负责的项目";
    projectDrawerList.value = list.filter((t: any) => t.role === "manager" && t.is_active);
  } else {
    projectDrawerTitle.value = "参与过的项目";
    projectDrawerList.value = list;
  }
  projectDrawerVisible.value = true;
}

function openCompanyDrawer() {
  companyDrawerVisible.value = true;
}

/** 当前 AI 会话是否为人脉路径模式(真实路径) */
const aiPathMode = ref(false);
/** 从「我」到此人 的真实人脉路径(Neo4j /network/path), 仅路径类问题加载 */
const realPathSteps = ref<any[]>([]);
const realPathLoading = ref(false);
async function loadRealPath() {
  if (realPathLoading.value) return;
  realPathLoading.value = true;
  try {
    const res: any = await api.get(`/network/path/${personId}`);
    realPathSteps.value = res.found && res.steps?.length ? res.steps : [];
  } catch {
    realPathSteps.value = [];
  } finally {
    realPathLoading.value = false;
  }
}

/** 该人在知识图谱中的直接邻居(1跳): 任职单位 / 参与项目 / 认识的人 / 同事 / 合作过的人。
 * 供上下文模式 AI 分析补充关联信息——即使 MySQL 无单位/无项目轨迹, 也能拿到真实图谱关联。 */
const graphNeighbors = ref<any[]>([]);
async function loadGraphNeighbors() {
  try {
    const res: any = await api.get(`/network/person-neighbors/${personId}`);
    graphNeighbors.value = res.neighbors || [];
  } catch { graphNeighbors.value = []; }
}

/** AI 分析步骤:
 *  - 路径模式: 使用从「我」到此人的真实知识图谱路径(首节点为我);
 *  - 上下文模式: 此人 → 所属单位 → 参与项目 → 知识图谱邻居(认识的人/同事/合作过的人),
 *    不含「我」、不伪造关系, 作为背景/合作等主题分析的参考资料。 */
const aiSteps = computed(() => {
  if (aiPathMode.value) return realPathSteps.value;
  const arr: any[] = [
    {
      type: "Person",
      name: person.value.name || "目标人员",
      position: person.value.position || "",
      company_name: companyName.value !== "-" ? companyName.value : "",
    },
  ];
  if (person.value.company_id) {
    arr.push({ type: "Company", name: companyName.value, relation_label: "任职于" });
  }
  for (const t of trajectory.value.slice(0, 10)) {
    arr.push({ type: "Project", name: t.project_name, relation_label: roleLabel(t.role) });
  }
  // 图谱邻居补充(去重); 上下文模式不携带「我」, 兜底过滤名为「我」的 Person 节点,
  // 防止 AI 把「我」误判为目标人员的合作者/共同参与人。
  const meTagNames = new Set(["我", "本人", "我自己"]);
  for (const g of graphNeighbors.value) {
    if (g.type === "Person" && meTagNames.has(String(g.name || "").trim())) continue;
    if (arr.some((x: any) => x.type === g.type && x.name === g.name)) continue;
    arr.push({ ...g });
  }
  return arr;
});

/** 预设问题是否为人脉路径类(路径问题才加载真实路径并走路径分析模板) */
function isPathQuestion(preset?: string): boolean {
  return !preset || preset.includes("人脉路径") || preset.includes("触达");
}

function buildAiFallback(preset?: string): any {
  const pname = person.value.name || "该人员";
  // 路径模式下优先用真实路径生成: 真实桥接人/步数, 与知识图谱保持一致
  if (aiPathMode.value && realPathSteps.value.length) {
    const path = realPathSteps.value;
    const target = path[path.length - 1];
    const midPersons = path.filter((s, i) => i > 0 && i < path.length - 1 && s.type === "Person");
    return {
      summary: `从你到「${target?.name || pname}」共 ${path.length - 1} 跳${midPersons.length ? `，经由 ${midPersons.map((p) => `「${p.name}」`).join("、")}` : ""}，为知识图谱中的真实人脉路径。`,
      bridges: midPersons.map((p) => ({
        name: p.name,
        position: p.position,
        company_name: p.company_name,
        tip: p.company_name
          ? `在「${p.company_name}」任职，是连接你与目标的关键桥接人，建议先联系建立引荐`
          : "是连接你与目标的关键人物，建议直接沟通请求引荐",
      })),
      companies: person.value.company_id
        ? [{ name: companyName.value, tip: "所属单位" }]
        : [],
      projects: trajectory.value.slice(0, 5).map((t) => ({
        name: t.project_name,
        tip: `角色：${roleLabel(t.role)}；状态：${t.is_active ? "参与中" : "已退出"}`,
      })),
      advice: [
        `通过桥接人「${midPersons[0]?.name || "相关熟人"}」引荐触达「${pname}」，比陌生拜访更高效`,
        "结合其职位与参与项目锁定共同话题, 降低沟通成本",
        "关注其所在单位的招投标动态, 把握合作时机",
      ],
      opportunities: [
        `当前参与 ${trajectory.value.length} 个项目，其中 ${activeTrajectoryCount.value} 个仍在推进`,
      ],
    };
  }
  const summary = preset
    ? `正在分析「${pname}」的${preset.replace(/^分析|此人|我方的|建议$/g, "").trim() || "整体"}情况…`
    : `正在分析「${pname}」的背景与人脉情况…`;
  return {
    summary,
    bridges: [],
    companies: person.value.company_id
      ? [{ name: companyName.value, tip: "所属单位" }]
      : [],
    projects: trajectory.value.slice(0, 5).map((t) => ({
      name: t.project_name,
      tip: `角色：${roleLabel(t.role)}；状态：${t.is_active ? "参与中" : "已退出"}`,
    })),
    advice: [
      `先通过「查看人脉」查看从你到「${pname}」的真实触达路径`,
      "结合其职位与参与项目锁定共同话题, 降低沟通成本",
      "关注其所在单位的招投标动态, 把握合作时机",
    ],
    opportunities: [
      `当前参与 ${trajectory.value.length} 个项目，其中 ${activeTrajectoryCount.value} 个仍在推进`,
    ],
  };
}

async function openAiChat(preset?: string) {
  const usePath = isPathQuestion(preset);
  if (usePath) {
    await loadRealPath();
    // 找不到真实路径时回退上下文模式, 避免把空 steps 当路径发送
    aiPathMode.value = realPathSteps.value.length > 0;
  } else {
    aiPathMode.value = false;
  }
  // 上下文模式: 确保图谱邻居已加载(补充关联信息, 避免 AI 拿到空节点)
  if (!usePath && !graphNeighbors.value.length) {
    await loadGraphNeighbors();
  }
  aiPresetQuestion.value = preset || undefined;
  // 两种模式的 SESSION_KEY 都清掉, 保证每次点击重建组件后都触发全新首轮分析
  const nm = person.value.name || "目标人员";
  try {
    sessionStorage.removeItem(`ssm_ai_chat_我_${nm}`);
    sessionStorage.removeItem(`ssm_ai_chat__${nm}`);
  } catch { /* ignore */ }
  aiChatKey.value++;
  aiFallback.value = buildAiFallback(preset);
  aiChatVisible.value = true;
}

function roleLabel(r: string): string {
  return { manager: "项目联系人", member: "成员", observer: "观察者" }[r] || r;
}
function formatDate(d: string): string {
  return d ? dayjs(d).format("YYYY-MM-DD") : "-";
}
function goProject(pid: number) {
  router.push(`/workspace/projects/${pid}`);
}
function goPerson(pid: number) {
  if (pid) router.push(`/workspace/persons/${pid}`);
}
function goCompany(cid: number) {
  if (cid) router.push(`/workspace/companies/${cid}`);
}
function viewNetwork() {
  // 以当前登录用户为源, 查通往本人员的人脉路径
  router.push(`/workspace/network/${personId}`);
}

async function loadPerson() {
  try {
    const res: any = await api.get(`/persons/${personId}`);
    person.value = res;
    if (res.company_id) await loadCompanyName(res.company_id);
  } catch { router.back(); }
}
async function loadCompanyName(cid: number) {
  try {
    const c: any = await api.get(`/companies/${cid}`);
    companyName.value = c.name || `ID ${cid}`;
  } catch { companyName.value = `ID ${cid}`; }
}
async function loadTrajectory() {
  try {
    const res: any = await api.get(`/project-members/person-trajectory/${personId}`);
    trajectory.value = res.trajectory || [];
    companyCount.value = res.company_count ?? 0;
    cooperatedCompanies.value = res.cooperated_companies || [];
  } catch { trajectory.value = []; }
}
async function loadDynamicFields() {
  try {
    const res: any = await api.get("/dynamic/person/form-config?mode=view");
    dynamicFields.value = res.fields || [];
  } catch { dynamicFields.value = []; }
}

// 编辑
function startEdit() {
  editForm.value = { ...person.value };
  editFormDynamic.value = { ext_attrs: { ...(person.value.ext_attrs || {}) } };
  companyOptions.value = person.value.company_id && companyName.value !== "-"
    ? [{ id: person.value.company_id, name: companyName.value }]
    : [];
  editing.value = true;
}
function cancelEdit() { editing.value = false; }

let companySearchSeq = 0;
async function searchCompanies(query: string) {
  if (!query) { companyOptions.value = []; return; }
  const seq = ++companySearchSeq;
  try {
    const res: any = await api.get("/companies", { params: { keyword: query, page_size: 20 } });
    if (seq !== companySearchSeq) return; // 丢弃过期响应, 避免竞态覆盖
    companyOptions.value = res.items || [];
  } catch { if (seq === companySearchSeq) companyOptions.value = []; }
}

async function saveEdit() {
  // 校验内置必填 + 动态字段必填，不通过则中断保存
  try {
    await editFormRef.value.validate();
  } catch { return; }
  if (dynamicFormRef.value) {
    const ok = await dynamicFormRef.value.validate();
    if (!ok) return;
  }
  saving.value = true;
  try {
    let dynamic = { ...(editFormDynamic.value.ext_attrs || {}) };
    if (dynamicFields.value.length > 0) {
      for (const f of dynamicFields.value) {
        const v = editFormDynamic.value[f.field_key];
        if (v !== undefined && v !== null && v !== "") dynamic[f.field_key] = v;
      }
    } else {
      const builtin = ["code","name","position","email","phone","status","entry_date","resign_date","company_id","department_id","ext_attrs","id","created_at","updated_at","is_deleted"];
      for (const [k, v] of Object.entries(editFormDynamic.value)) {
        if (!builtin.includes(k) && v !== undefined && v !== null && v !== "") dynamic[k] = v;
      }
    }
    if (dynamicFormRef.value) {
      const ok = await dynamicFormRef.value.validate();
      if (!ok) return;
    }
    await api.put(`/persons/${personId}`, {
      name: editForm.value.name,
      position: editForm.value.position,
      company_id: editForm.value.company_id,
      email: editForm.value.email,
      phone: editForm.value.phone,
      status: editForm.value.status,
      entry_date: editForm.value.entry_date,
      ext_attrs: dynamic,
    });
    ElMessage.success("保存成功");
    editing.value = false;
    await loadPerson();
  } catch { /* interceptor */ }
  finally { saving.value = false; }
}

// 退出项目(软退出: 保留参与记录, 仅标记 is_active=false + left_at, 在途人数相应减少)
async function exitProject(t: any) {
  try {
    await ElMessageBox.confirm(
      `确定将「${t.project_name}」标记为已退出？参与记录将保留（统计为已退出），仅「参与中」人数减少。`,
      "退出项目",
      { type: "warning" }
    );
  } catch { return; }
  try {
    await api.put(`/project-members/${t.member_id}`, {
      left_at: dayjs().format("YYYY-MM-DD"),
      is_active: false,
    });
    ElMessage.success("已退出项目");
    loadTrajectory();
  } catch (e: any) {
    // 负责人被后端拒绝时, 给出明确提示(interceptor 通常已 toast)
    if (e?.response?.status === 400) {
      ElMessage.error(e?.response?.data?.detail || "项目联系人人不能退出, 请先改派联系人");
    }
  }
}

onMounted(() => {
  loadPerson();
  loadTrajectory();
  loadGraphNeighbors();
  loadDynamicFields();
  loadCategories();
});
</script>

<style scoped>
.person-profile { max-width: 1200px; }
.person-avatar { text-align: center; padding: 16px 0; }
.person-avatar h2 { margin: 12px 0 8px; }
/* 人员头像统一品牌蓝渐变风格 */
.avatar-pic {
  background: linear-gradient(135deg, #4f8df9 0%, #2979ff 55%, #1d63e0 100%) !important;
  color: #fff !important;
  font-weight: 600;
  box-shadow: 0 3px 10px rgba(41, 121, 255, 0.28);
}
.avatar-pic-lg { font-size: 32px; }
.avatar-actions { display: flex; align-items: center; justify-content: center; gap: 8px; }
.member-relation-link {
  font-size: 12px !important;
  padding: 0 8px;
  height: 22px;
  line-height: 20px;
  border: 1px solid #d9ecff;
  background: #ecf5ff;
  color: #2979ff !important;
  border-radius: 4px;
}
.member-relation-link:hover {
  background: #2979ff;
  color: #fff !important;
  border-color: #2979ff;
}
.trajectory-card {
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid #ebeef5;
}
.trajectory-card:hover {
  border-color: #2979ff;
  box-shadow: 0 4px 14px rgba(64, 158, 255, 0.22) !important;
  transform: translateY(-2px);
  background: #f6faff;
}
/* 已退出轨迹卡片: 灰色 + 左侧条, 视觉上明显区分参与中 */
.trajectory-card.trajectory-card-left {
  background: #f5f5f7;
  opacity: 0.85;
  border-left: 3px solid #909399;
}
.trajectory-card.trajectory-card-left:hover {
  opacity: 1;
  border-color: #909399;
}
.trajectory-card:hover .project-link {
  color: #1d6fe0;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.trajectory-header { display: flex; justify-content: space-between; align-items: center; }
.trajectory-dates { font-size: 12px; color: #909399; margin-top: 4px; }
.project-link { color: #2979ff; }
.company-link { color: #2979ff; cursor: pointer; }
.company-link:hover { text-decoration: underline; }

/* ─── 360° 看板: 顶部主信息卡 ─── */
.fgbs-header {
  margin-top: 16px;
  background: #fff;
  border-top: 3px solid #2979ff;
  border-radius: 4px;
  padding: 18px 22px 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.fgbs-head-main {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.fgbs-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1f2d3d;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.fgbs-title .title-company {
  font-size: 15px;
  color: #909399;
  font-weight: normal;
}
.fgbs-head-spacer { flex: 1; }
.fgbs-print { border-radius: 14px; }
.fgbs-print :deep(.el-icon) { margin-right: 3px; }

/* 三张信息小卡 */
.fgbs-info-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.fgbs-info-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f5f8fc;
  border-radius: 6px;
  padding: 12px 14px;
  min-height: 56px;
}
.fgbs-info-icon {
  width: 32px; height: 32px;
  background: #fff;
  border: 1px solid #e6ebf5;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  color: #2979ff;
  font-size: 16px;
  flex-shrink: 0;
}
.fgbs-info-body { flex: 1; min-width: 0; }
.fgbs-info-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.fgbs-info-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* AI分析能力横幅 */
.ai-banner {
  margin-top: 14px;
  background: linear-gradient(90deg, #eef4ff 0%, #f7faff 100%);
  border: 1px solid #dde7fa;
  border-radius: 6px;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ai-banner-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.ai-banner-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #2979ff;
  font-size: 14px;
  flex-shrink: 0;
  margin-right: 4px;
}
.ai-banner-label :deep(.el-icon) { font-size: 14px; }
.ai-banner-label b { font-weight: 700; }
.ai-chip {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #dde7fa;
  color: #4b6cb7;
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.18s ease;
  user-select: none;
}
.ai-chip:hover {
  background: #2979ff;
  color: #fff;
  border-color: #2979ff;
}
.ai-more { flex-shrink: 0; }

/* 统计卡片条 */
.fgbs-stats {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.fgbs-stat {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.fgbs-stat .stat-num {
  font-size: 26px;
  font-weight: 700;
  color: #2979ff;
  line-height: 1;
}
.fgbs-stat .stat-label {
  font-size: 13px;
  color: #909399;
}

/* 统计卡数字(蓝色链接质感, 参考单位详情潜在商机) */
.stat-link {
  color: #2979ff;
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  text-decoration: none;
}
.stat-link:hover {
  text-decoration: underline;
  color: #1d63e0;
}
.stat-hint { font-size: 12px; color: #909399; }
.stat-label { font-size: 13px; color: #909399; }

/* 抽屉列表(对齐单位详情 drawer-list 质感) */
.drawer-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
/* 合作单位卡片 */
.coop-card {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 10px;
  padding: 14px 16px;
  transition: all 0.18s ease;
}
.coop-card:hover {
  border-color: #b9d4ff;
  box-shadow: 0 2px 10px rgba(41, 121, 255, 0.1);
}
.coop-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.coop-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.coop-icon {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: #eef4ff;
  color: #2979ff;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.coop-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.coop-name:hover { color: #2979ff; }
.coop-sub {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.coop-sub:last-child { margin-bottom: 0; }
.coop-sub-label {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
  width: 44px;
}
.coop-tag { cursor: pointer; }

@media (max-width: 900px) {
  .fgbs-info-cards { grid-template-columns: 1fr; }
  .fgbs-stats { grid-template-columns: 1fr 1fr; }
}</style>
