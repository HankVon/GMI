<!--
  人员关联图谱面板（P1-5 阶段二补全：人员/单位详情页关联图谱面板之"人员"侧）
  复用后端 /network/person-neighbors/{id}（知识图谱 1 跳邻居，按类型口径分组），
  以"本人"为中心展示：任职单位 / 参与项目 / 认识·共事的人。
  仅消费既有图谱数据，不新增孤儿节点；视觉风格对齐 CompanyGraph。
-->
<template>
  <div class="pg">
    <!-- 中心人员 -->
    <div class="pg-center">
      <div class="pg-center-card" @click="goSelf">
        <el-icon class="pg-center-icon"><User /></el-icon>
        <div class="pg-center-name">{{ personName || "人员" }}</div>
        <div class="pg-center-sub">关系中心</div>
      </div>
    </div>

    <!-- 分支: 任职单位 / 参与项目 / 认识·共事的人 -->
    <div class="pg-branches">
      <!-- 任职单位 -->
      <div class="pg-branch">
        <div class="pg-branch-title">
          <el-icon><OfficeBuilding /></el-icon>
          <span>任职单位</span>
          <el-tag size="small" type="primary" effect="plain">{{ companies.length }}</el-tag>
        </div>
        <div v-if="!loading" class="pg-list">
          <div v-for="c in companies" :key="'C' + c.company_id" class="pg-node">
            <el-icon class="pg-node-company"><OfficeBuilding /></el-icon>
            <span class="pg-node-name" @click="goCompany(c)">{{ c.name }}</span>
            <el-tag v-if="c.company_type" size="small" type="info" effect="plain">{{ c.company_type }}</el-tag>
            <el-tag v-if="c.grant" size="small" type="warning" effect="plain">系统授权</el-tag>
          </div>
          <div v-if="!companies.length" class="pg-empty">暂无任职单位</div>
        </div>
      </div>

      <!-- 参与项目 -->
      <div class="pg-branch">
        <div class="pg-branch-title">
          <el-icon><FolderOpened /></el-icon>
          <span>参与项目</span>
          <el-tag size="small" type="success" effect="plain">{{ projects.length }}</el-tag>
        </div>
        <div v-if="!loading" class="pg-list">
          <div v-for="p in projects" :key="'J' + p.project_id" class="pg-node">
            <el-icon class="pg-node-proj"><FolderOpened /></el-icon>
            <span class="pg-node-name" @click="goProject(p)">{{ p.name }}</span>
            <el-tag v-if="p.category" size="small" type="info" effect="plain">{{ p.category }}</el-tag>
            <el-tag v-if="p.grant" size="small" type="warning" effect="plain">系统授权</el-tag>
          </div>
          <div v-if="!projects.length" class="pg-empty">暂无参与项目</div>
        </div>
      </div>

      <!-- 认识 / 共事的人 -->
      <div class="pg-branch pg-branch-full">
        <div class="pg-branch-title">
          <el-icon><User /></el-icon>
          <span>认识 / 共事的人</span>
          <el-tag size="small" type="warning" effect="plain">{{ persons.length }}</el-tag>
        </div>
        <div v-if="!loading" class="pg-list pg-persons">
          <div v-for="p in persons" :key="'P' + p.person_id" class="pg-node">
            <el-avatar :size="24" class="pg-avatar">{{ p.name?.[0] || "?" }}</el-avatar>
            <span class="pg-node-name" @click="goPerson(p)">{{ p.name }}</span>
            <el-tag v-if="p.position" size="small" type="info" effect="plain">{{ p.position }}</el-tag>
            <span v-if="p.company_name" class="pg-sub">{{ p.company_name }}</span>
            <el-link
              type="primary" :underline="false" class="pg-rel"
              @click.stop="viewNetwork(p)"
            >人脉路径</el-link>
          </div>
          <div v-if="!persons.length" class="pg-empty">暂无关联人员</div>
        </div>
      </div>
    </div>

    <div v-if="loading" v-loading="true" class="pg-loading" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { User, OfficeBuilding, FolderOpened } from "@element-plus/icons-vue";
import api from "@/api";
import { useNavBase } from "@/utils/navBase";

const props = defineProps<{ personId: number; personName?: string }>();
const { navToNewTab } = useNavBase();

const loading = ref(true);
const companies = ref<any[]>([]);
const projects = ref<any[]>([]);
const persons = ref<any[]>([]);

async function load() {
  loading.value = true;
  try {
    const res: any = await api.get(`/network/person-neighbors/${props.personId}?limit=40`);
    const ns: any[] = res.neighbors || [];
    companies.value = ns.filter((n) => n.type === "Company");
    projects.value = ns.filter((n) => n.type === "Project");
    persons.value = ns.filter((n) => n.type === "Person");
  } catch {
    companies.value = [];
    projects.value = [];
    persons.value = [];
  } finally {
    loading.value = false;
  }
}

function goSelf() {
  navToNewTab(`/persons/${props.personId}`);
}
function goCompany(c: any) {
  if (c.company_id) navToNewTab(`/companies/${c.company_id}`);
}
function goProject(p: any) {
  if (p.project_id) navToNewTab(`/projects/${p.project_id}`);
}
function goPerson(p: any) {
  if (p.person_id) navToNewTab(`/persons/${p.person_id}`);
}
/** 查看从「我」到该关联人员的真实人脉路径 */
function viewNetwork(p: any) {
  if (p.person_id) navToNewTab(`/network/${p.person_id}`);
}

onMounted(load);
</script>

<style scoped>
.pg {
  position: relative;
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 16px 18px;
  margin-top: 16px;
}

/* 中心人员 */
.pg-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.pg-center-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 28px;
  border-radius: 12px;
  background: linear-gradient(135deg, #722ed1, #9254de);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(114, 46, 209, 0.28);
  transition: transform 0.15s;
}
.pg-center-card:hover { transform: translateY(-1px); }
.pg-center-icon { font-size: 22px; }
.pg-center-name { font-size: 17px; font-weight: 700; }
.pg-center-sub { font-size: 11px; opacity: 0.85; }

/* 三分支 */
.pg-branches {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.pg-branch-full { grid-column: 1 / -1; }
@media (max-width: 800px) {
  .pg-branches { grid-template-columns: 1fr; }
}
.pg-branch {
  background: #fafcff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 12px;
}
.pg-branch-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 10px;
}
.pg-branch-title :deep(.el-icon) { color: #722ed1; }
.pg-list { display: flex; flex-direction: column; gap: 6px; }

/* 节点行 */
.pg-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  transition: background 0.15s;
  flex-wrap: wrap;
}
.pg-node:hover { background: #f7f0ff; border-color: #e9d8ff; }
.pg-node-company { color: #909399; font-size: 18px; flex-shrink: 0; }
.pg-node-proj { color: #fa8c16; font-size: 16px; flex-shrink: 0; }
.pg-avatar {
  background: linear-gradient(135deg, #722ed1, #9254de);
  color: #fff;
  font-weight: 600;
  flex-shrink: 0;
}
.pg-node-name {
  color: #1f2d3d;
  font-weight: 500;
  cursor: pointer;
}
.pg-node-name:hover { color: #722ed1; text-decoration: underline; }
.pg-sub { color: #909399; font-size: 12px; }
/* 人脉路径(浅紫链接) */
.pg-rel {
  flex-shrink: 0;
  margin-left: auto;
  font-size: 12px !important;
  padding: 0 8px;
  height: 22px;
  line-height: 20px;
  border: 1px solid #efdbff;
  background: #f9f0ff;
  color: #722ed1 !important;
  border-radius: 4px;
}
.pg-rel:hover { background: #722ed1; color: #fff !important; }
.pg-empty { color: #b0b8c4; font-size: 12.5px; padding: 8px 0; }
.pg-loading { position: absolute; inset: 0; }
</style>
