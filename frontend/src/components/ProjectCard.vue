<!-- 项目信息卡片(用于公司详情抽屉: 项目商机 / 未竣工项目) -->
<template>
  <div class="project-card" @click="$emit('open')">
    <!-- 头部: 项目名称 + 状态 -->
    <div class="pc-head">
      <div class="pc-title-row">
        <span class="pc-name" :title="project.name">{{ project.name || "-" }}</span>
        <el-tag :type="statusTagType(project.status)" size="small" effect="light">{{ statusLabel(project.status) }}</el-tag>
      </div>
      <div class="pc-code">{{ project.code }}</div>
    </div>

    <!-- 核心信息行: 角色 / 类别 / 投资额 -->
    <div class="pc-meta-row" v-if="roleLabel || categoryLabel || formattedAmount">
      <div class="pc-meta-item" v-if="roleLabel">
        <span class="pc-meta-icon role"><el-icon><UserFilled /></el-icon></span>
        <span class="pc-meta-text">{{ roleLabel }}</span>
      </div>
      <div class="pc-meta-item" v-if="categoryLabel">
        <span class="pc-meta-icon"><el-icon><FolderOpened /></el-icon></span>
        <span class="pc-meta-text">{{ categoryLabel }}</span>
      </div>
      <div class="pc-meta-item" v-if="formattedAmount">
        <span class="pc-meta-icon amount"><el-icon><Coin /></el-icon></span>
        <span class="pc-meta-text amount">{{ formattedAmount }}</span>
      </div>
    </div>

    <!-- 项目阶段 -->
    <div class="pc-stage-row" v-if="project.stage">
      <span class="pc-stage-label">阶段</span>
      <el-progress
        :percentage="stagePercent"
        :stroke-width="8"
        :show-text="false"
        :color="'#2979ff'"
      />
      <span class="pc-stage-value">{{ project.stage }}</span>
    </div>

    <!-- 地点 + 时间 -->
    <div class="pc-info-row">
      <div class="pc-info-item" v-if="locationText">
        <el-icon><Location /></el-icon><span>{{ locationText }}</span>
      </div>
      <div class="pc-info-item" v-if="dateText">
        <el-icon><Calendar /></el-icon><span>{{ dateText }}</span>
      </div>
      <div class="pc-info-item" v-if="managerText">
        <el-icon><Avatar /></el-icon><span>{{ managerText }}</span>
      </div>
    </div>

    <!-- 描述 -->
    <div class="pc-desc" v-if="project.description">
      <span>{{ project.description }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { UserFilled, FolderOpened, Coin, Location, Calendar, Avatar } from "@element-plus/icons-vue";

const props = defineProps<{
  project: any;
  roleLabelMap?: Record<string, string>;
  categoryLabelMap?: Record<string, string>;
}>();

defineEmits<{
  (e: "open"): void;
}>();

const roleLabel = computed(() => {
  if (!props.project?.role) return "";
  return props.roleLabelMap?.[props.project.role] || props.project.role;
});

const categoryLabel = computed(() => {
  const c = props.project?.category;
  if (!c) return "";
  return props.categoryLabelMap?.[c] || c;
});

function formatAmount(v: any): string {
  if (v === null || v === undefined || v === "") return "";
  const num = Number(v);
  if (Number.isNaN(num) || num === 0) return "";
  if (num >= 100000000) return (num / 100000000).toFixed(2).replace(/\.?0+$/, "") + " 亿元";
  if (num >= 10000) return (num / 10000).toFixed(2).replace(/\.?0+$/, "") + " 万元";
  return num + " 元";
}
const formattedAmount = computed(() => formatAmount(props.project?.amount));

const locationText = computed(() => {
  const p = props.project;
  if (!p) return "";
  return [p.province, p.city].filter(Boolean).join("");
});

const dateText = computed(() => {
  const p = props.project;
  if (!p) return "";
  if (p.start_date && p.end_date) return `${p.start_date} ~ ${p.end_date}`;
  if (p.start_date) return `起 ${p.start_date}`;
  return p.end_date ? `止 ${p.end_date}` : "";
});

const managerText = computed(() => {
  const m = props.project?.manager;
  return m ? `负责人: ${m}` : "";
});

function statusLabel(s: string): string {
  return { active: "进行中", suspended: "挂起", completed: "已完成", cancelled: "已取消" }[s] || s || "-";
}
function statusTagType(s: string): string {
  return { active: "primary", suspended: "warning", completed: "success", cancelled: "danger" }[s] || "info";
}

/** 阶段进度百分比: 粗略按进度文本映射(无则均分) */
const stagePercent = computed(() => {
  const s = props.project?.stage;
  const map: Record<string, number> = {
    "前期": 15, "立项": 20, "勘察": 35, "设计": 45, "招标": 55,
    "施工": 70, "验收": 90, "竣工": 100, "投产": 100,
  };
  if (s && map[s]) return map[s];
  return 50;
});
</script>

<style scoped>
.project-card {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.project-card:hover {
  border-color: #b9d4ff;
  box-shadow: 0 2px 10px rgba(41, 121, 255, 0.1);
  transform: translateY(-1px);
}

.pc-head { margin-bottom: 10px; }
.pc-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.pc-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-code {
  font-size: 12px;
  color: #909399;
  margin-top: 3px;
}

/* 核心信息行 */
.pc-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 10px;
}
.pc-meta-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: #4b5264;
}
.pc-meta-icon {
  width: 20px;
  height: 20px;
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2979ff;
  background: #eef4ff;
  font-size: 12px;
}
.pc-meta-icon.role { color: #2979ff; background: #eef4ff; }
.pc-meta-icon.amount { color: #b7791f; background: #fdf3e2; }
.pc-meta-text.amount { color: #b7791f; font-weight: 600; }

/* 阶段进度 */
.pc-stage-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f8faff;
  border-radius: 6px;
}
.pc-stage-label {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}
.pc-stage-row :deep(.el-progress) { flex: 1; }
.pc-stage-value {
  font-size: 12px;
  color: #2979ff;
  font-weight: 600;
  flex-shrink: 0;
}

/* 信息行 */
.pc-info-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 8px;
}
.pc-info-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: #606266;
}
.pc-info-item :deep(.el-icon) { color: #2979ff; font-size: 13px; }

/* 描述 */
.pc-desc {
  font-size: 12.5px;
  color: #909399;
  line-height: 1.6;
  padding-top: 8px;
  border-top: 1px dashed #eef1f7;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>