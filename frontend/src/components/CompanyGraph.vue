<template>
  <div class="cg">
    <!-- 头部: 中心单位 -->
    <div class="cg-center">
      <div class="cg-center-card" @click="goCompany">
        <el-icon class="cg-center-icon"><OfficeBuilding /></el-icon>
        <div class="cg-center-name">{{ companyName || "目标单位" }}</div>
        <div class="cg-center-sub">中心单位</div>
      </div>
      <div class="cg-center-line" />
    </div>

    <!-- 分支: 内部联系人(左) / 合作方(右) -->
    <div class="cg-branches">
      <!-- 内部联系人 -->
      <div class="cg-branch">
        <div class="cg-branch-title">
          <el-icon><User /></el-icon>
          <span>内部联系人</span>
          <el-tag size="small" type="primary" effect="plain">{{ persons.length }}</el-tag>
        </div>
        <div v-if="!loading" class="cg-list">
          <div
            v-for="p in persons"
            :key="p.id"
            class="cg-node"
          >
            <el-avatar :size="26" class="cg-avatar">{{ p.name?.[0] || "?" }}</el-avatar>
            <span class="cg-node-name" @click="goPerson(p)">{{ p.name }}</span>
            <el-tag v-if="p.position" size="small" type="info" effect="plain" class="cg-pos">{{ p.position }}</el-tag>
            <el-link
              type="primary" :underline="false" class="member-relation-link"
              @click.stop="viewNetwork(p.id)"
            >查看人脉</el-link>
          </div>
          <div v-if="!persons.length" class="cg-empty">暂无内部联系人</div>
        </div>
      </div>

      <!-- 合作方(合作单位) -->
      <div class="cg-branch">
        <div class="cg-branch-title">
          <el-icon><OfficeBuilding /></el-icon>
          <span>合作单位</span>
          <el-tag size="small" type="warning" effect="plain">{{ partners.length }}</el-tag>
        </div>
        <div v-if="!loading" class="cg-list">
          <div
            v-for="c in partners"
            :key="c.id"
            class="cg-node"
            :class="{ expanded: c.expanded || c.projectsOpen }"
          >
            <button class="cg-toggle" :class="{ open: c.expanded }" @click="togglePartner(c)">
              <el-icon><Plus /></el-icon>
            </button>
            <el-icon class="cg-node-company"><OfficeBuilding /></el-icon>
            <span class="cg-node-name" @click="goCompanyById(c.id, c.name)">{{ c.name }}</span>
            <!-- 合作项目数: 可点击展开项目列表(像潜在商机点数字) -->
            <el-tag
              v-if="c.projects?.length"
              size="small" type="warning" effect="plain"
              class="cg-pos cg-projects-tag"
              :class="{ open: c.projectsOpen }"
              @click="toggleProjects(c)"
            >
              <el-icon><FolderOpened /></el-icon>{{ c.projects.length }} 个合作项目
            </el-tag>
            <!-- 展开: 该单位的相关联系人 -->
            <div v-if="c.expanded" class="cg-sub" v-loading="c.loading">
              <div class="cg-sub-title">相关联系人</div>
              <template v-if="c.persons.length">
                <div v-for="pp in c.persons" :key="pp.id" class="cg-sub-person" @click="goPerson(pp)">
                  <el-avatar :size="20" class="cg-avatar-sm">{{ pp.name?.[0] || "?" }}</el-avatar>
                  <span class="cg-sub-person-name">{{ pp.name }}</span>
                  <span v-if="pp.position" class="cg-sub-person-pos">{{ pp.position }}</span>
                </div>
              </template>
              <div v-else class="cg-empty">{{ c.loading ? "加载中…" : "暂无联系人" }}</div>
            </div>
            <!-- 展开: 合作项目列表 -->
            <div v-if="c.projectsOpen" class="cg-sub">
              <div class="cg-sub-title">合作项目</div>
              <div
                v-for="proj in c.projects"
                :key="proj.id"
                class="cg-sub-person"
                @click="goProject(proj)"
              >
                <el-icon class="cg-proj-icon"><FolderOpened /></el-icon>
                <span class="cg-sub-person-name">{{ proj.name }}</span>
              </div>
              <div v-if="!c.projects.length" class="cg-empty">暂无项目</div>
            </div>
          </div>
          <div v-if="!partners.length" class="cg-empty">暂无合作单位</div>
        </div>
      </div>
    </div>
    <div v-if="loading" v-loading="true" class="cg-loading" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { OfficeBuilding, User, Plus } from "@element-plus/icons-vue";
import api from "@/api";

const props = defineProps<{ companyId: number; companyName?: string }>();
const router = useRouter();

const loading = ref(true);
const persons = ref<any[]>([]); // 内部联系人
const partners = ref<any[]>([]); // 合作单位

const ID_PREFIX = { Person: "P", Company: "C", Project: "J" } as const;
const nodeId = (label: string, id: any) => `${ID_PREFIX[label as keyof typeof ID_PREFIX] || "X"}${id}`;

async function load() {
  loading.value = true;
  try {
    const res: any = await api.get(`/network/graph/company/${props.companyId}?max_depth=2&limit=150`);
    const nodes: any[] = res.nodes || [];
    const links: any[] = res.links || [];
    const centerId = nodeId("Company", props.companyId);

    const byId = new Map(nodes.map((n) => [n.id, n]));

    // 内部联系人: 与中心单位有 WORKS_AT 关系的 Person
    const personSet = new Set<string>();
    const pList: any[] = [];
    for (const l of links) {
      if (l.type !== "WORKS_AT") continue;
      const other = l.source === centerId ? l.target : l.target === centerId ? l.source : null;
      if (!other) continue;
      const n = byId.get(other);
      if (n && n.label === "Person" && !personSet.has(other)) {
        personSet.add(other);
        pList.push({ ...n, expanded: false });
      }
    }
    pList.sort((a, b) => (a.name || "").localeCompare(b.name || "", "zh"));
    persons.value = pList;

    // 合作单位: 由后端按「单位口径」聚合(参与项目者的任职公司), 含该单位内部联系人
    const partnerRows: any[] = res.partner_companies || [];
    partners.value = partnerRows.map((pc: any) => ({
      id: String(pc.id || `C${pc.company_id}`),
      company_id: pc.company_id,
      name: pc.name,
      projects: (pc.projects || []).map((pj: any) => ({ id: pj.id, name: pj.name })),
      persons: (pc.persons || []).map((pp: any) => ({ ...pp })),
      expanded: false,
      projectsOpen: false,
      loading: false,
      _loaded: true, // 后端已带回联系人, 无需再次请求
    }));
  } catch {
    persons.value = [];
    partners.value = [];
  } finally {
    loading.value = false;
  }
}

/** 展开合作单位时动态加载其内部联系人(后端已带回则直接展示) */
async function togglePartner(c: any) {
  c.expanded = !c.expanded;
  if (!c.expanded || c.persons.length || c.loading) return;
  if (c._loaded) return; // 后端已返回该单位联系人
  c.loading = true;
  try {
    const res: any = await api.get(`/network/graph/company/${c.raw_id ?? c.id.replace(/^C/, "")}?max_depth=1&limit=80`);
    const nodes: any[] = res.nodes || [];
    const links: any[] = res.links || [];
    const centerId = nodeId("Company", c.raw_id ?? c.id.replace(/^C/, ""));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const set = new Set<string>();
    const list: any[] = [];
    for (const l of links) {
      if (l.type !== "WORKS_AT") continue;
      const other = l.source === centerId ? l.target : l.target === centerId ? l.source : null;
      if (!other) continue;
      const n = byId.get(other);
      if (n && n.label === "Person" && !set.has(other)) {
        set.add(other);
        list.push({ ...n });
      }
    }
    list.sort((a, b) => (a.name || "").localeCompare(b.name || "", "zh"));
    c.persons = list;
  } catch {
    c.persons = [];
  } finally {
    c.loading = false;
  }
}

function goPerson(p: any) {
  const id = Number(String(p.id).replace(/^P/, ""));
  if (id) router.push(`/workspace/persons/${id}`);
}
/** 查看人脉: 入参为人员节点 id(如 'P1'), 不是对象 */
function viewNetwork(id: any) {
  const pid = Number(String(id).replace(/^P/, ""));
  if (pid) router.push(`/workspace/network/${pid}`);
}
/** 点击合作项目数: 展开/收起项目列表 */
function toggleProjects(c: any) {
  c.projectsOpen = !c.projectsOpen;
}
/** 点击项目 → 项目详情 */
function goProject(proj: any) {
  const pid = Number(proj.id);
  if (pid) router.push(`/workspace/projects/${pid}`);
}
function goCompany() {
  router.push(`/workspace/companies/${props.companyId}`);
}
function goCompanyById(id: string, name?: string) {
  const raw = Number(String(id).replace(/^C/, ""));
  if (raw) router.push(`/workspace/companies/${raw}`);
}

onMounted(load);
</script>

<style scoped>
.cg {
  position: relative;
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 16px 18px;
  margin-bottom: 12px;
}

/* 中心单位 */
.cg-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.cg-center-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 28px;
  border-radius: 12px;
  background: linear-gradient(135deg, #1d63e0, #2979ff);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(41, 121, 255, 0.28);
  transition: transform 0.15s;
}
.cg-center-card:hover { transform: translateY(-1px); }
.cg-center-icon { font-size: 22px; }
.cg-center-name { font-size: 17px; font-weight: 700; }
.cg-center-sub { font-size: 11px; opacity: 0.85; }
.cg-center-line {
  width: 2px;
  height: 18px;
  background: linear-gradient(#2979ff, #b9d4ff);
}

/* 左右分支 */
.cg-branches {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 800px) {
  .cg-branches { grid-template-columns: 1fr; }
}
.cg-branch {
  background: #fafcff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 12px;
}
.cg-branch-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 10px;
}
.cg-branch-title :deep(.el-icon) { color: #2979ff; }
.cg-list { display: flex; flex-direction: column; gap: 6px; }

/* 节点行 */
.cg-node {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  transition: background 0.15s;
  flex-wrap: wrap;
}
.cg-node:hover { background: #f0f5ff; border-color: #d9e6ff; }
.cg-node.expanded { background: #f0f5ff; border-color: #cfe0ff; }

/* 收放按钮 */
.cg-toggle {
  width: 18px; height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #c0ccdd;
  border-radius: 4px;
  background: #fff;
  color: #5b6b7e;
  cursor: pointer;
  padding: 0;
  font-size: 12px;
  flex-shrink: 0;
  transition: transform 0.15s;
}
.cg-toggle :deep(.el-icon) { font-size: 12px; }
.cg-toggle.open { transform: rotate(45deg); background: #2979ff; border-color: #2979ff; color: #fff; }

.cg-avatar {
  background: linear-gradient(135deg, #2979ff, #4f8aff);
  color: #fff;
  font-weight: 600;
  flex-shrink: 0;
}
.cg-node-name {
  color: #1f2d3d;
  font-weight: 500;
  cursor: pointer;
}
.cg-node-name:hover { color: #2979ff; text-decoration: underline; }
/* 查看人脉(与全项目一致的浅蓝链接样式) */
.member-relation-link {
  flex-shrink: 0;
  margin-left: auto;
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
}
.cg-node-company { color: #909399; font-size: 18px; flex-shrink: 0; }
.cg-pos { flex-shrink: 0; }
/* 合作项目数 tag: 可点击展开 */
.cg-projects-tag {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  transition: all 0.15s;
}
.cg-projects-tag :deep(.el-icon) { font-size: 12px; }
.cg-projects-tag:hover {
  background: #ffd591;
  border-color: #ffb347;
}
.cg-projects-tag.open {
  background: #fa8c16;
  border-color: #fa8c16;
  color: #fff;
}
.cg-proj-icon { color: #fa8c16; font-size: 14px; }

/* 子节点(展开) */
.cg-sub {
  flex-basis: 100%;
  margin-top: 4px;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid #e4edfc;
  border-radius: 6px;
}
.cg-sub-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.cg-sub-row {
  font-size: 12.5px;
  color: #4b5264;
  display: flex;
  gap: 8px;
  padding: 2px 0;
}
.cg-sub-label { color: #909399; width: 40px; flex-shrink: 0; }
.cg-sub-person {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  cursor: pointer;
  font-size: 12.5px;
}
.cg-sub-person:hover .cg-sub-person-name { color: #2979ff; }
.cg-avatar-sm {
  background: #eef4ff;
  color: #2979ff;
  font-size: 11px;
  flex-shrink: 0;
}
.cg-sub-person-name { color: #303133; }
.cg-sub-person-pos { color: #909399; font-size: 11.5px; margin-left: auto; }
.cg-empty { color: #b0b8c4; font-size: 12.5px; padding: 8px 0; }
.cg-loading { position: absolute; inset: 0; }
</style>