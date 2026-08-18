<!-- 人员信息卡片(用于公司详情抽屉: 关联联系人 / 未竣工项目联系人) -->
<template>
  <div class="person-card">
    <!-- 头部: 头像 + 姓名职位 + 操作 -->
    <div class="pc-head">
      <el-avatar :size="44" class="pc-avatar">{{ person.name?.[0] || "?" }}</el-avatar>
      <div class="pc-head-info">
        <div class="pc-name-row">
          <span class="pc-name">{{ person.name || "-" }}</span>
          <el-tag v-if="person.position" type="info" effect="plain" size="small">{{ person.position }}</el-tag>
        </div>
        <div class="pc-company" v-if="companyName">
          <el-icon><OfficeBuilding /></el-icon>
          <span>{{ companyName }}</span>
        </div>
      </div>
      <div class="pc-actions">
        <el-button size="small" type="primary" @click="$emit('open')">详情</el-button>
        <el-button size="small" type="primary" @click="$emit('network')">查看人脉</el-button>
      </div>
    </div>

    <!-- 联系方式 -->
    <div class="pc-contacts" v-if="person.phone || person.email">
      <div class="pc-contact" v-if="person.phone">
        <el-icon><Phone /></el-icon><span>{{ person.phone }}</span>
      </div>
      <div class="pc-contact" v-if="person.email">
        <el-icon><Message /></el-icon><span>{{ person.email }}</span>
      </div>
    </div>

    <!-- 关联未竣工项目 -->
    <div class="pc-projects" v-if="person.projects?.length">
      <div class="pc-projects-title">
        <el-icon><Briefcase /></el-icon>
        <span>关联未竣工项目（{{ person.projects.length }}）</span>
      </div>
      <div
        v-for="pj in person.projects"
        :key="pj.id"
        class="pc-project-item"
        @click.stop="goProject(pj.id)"
      >
        <span class="pc-project-name" :title="pj.name">{{ pj.name }}</span>
        <span class="pc-project-meta">
          <span class="pc-project-role">{{ pj.role || "-" }}</span>
        </span>
        <el-icon class="pc-project-arrow"><ArrowRight /></el-icon>
      </div>
    </div>
    <div class="pc-projects pc-empty" v-else>
      <span class="pc-empty-text">暂无关联未竣工项目</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { Phone, Message, OfficeBuilding, Briefcase, ArrowRight } from "@element-plus/icons-vue";

const props = defineProps<{
  person: any;
  companyName?: string;
}>();

const router = useRouter();

function goProject(id: number) {
  router.push(`/workspace/projects/${id}`);
}

defineEmits<{
  (e: "open"): void;
  (e: "network"): void;
}>();
</script>

<style scoped>
.person-card {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 10px;
  padding: 14px 16px;
  transition: all 0.18s ease;
}
.person-card:hover {
  border-color: #b9d4ff;
  box-shadow: 0 2px 10px rgba(41, 121, 255, 0.08);
}

.pc-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.pc-avatar {
  background: linear-gradient(135deg, #2979ff 0%, #4f8aff 100%) !important;
  color: #fff !important;
  font-weight: 600;
  flex-shrink: 0;
}
.pc-head-info { flex: 1; min-width: 0; }
.pc-name-row { display: flex; align-items: center; gap: 8px; }
.pc-name { font-size: 15px; font-weight: 600; color: #1f2d3d; }
.pc-company {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: #909399;
  margin-top: 3px;
}
.pc-company :deep(.el-icon) { font-size: 13px; }
.pc-actions { flex-shrink: 0; display: flex; gap: 6px; }

/* 联系方式 */
.pc-contacts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #eef1f7;
}
.pc-contact {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: #4b5264;
}
.pc-contact :deep(.el-icon) { color: #2979ff; font-size: 13px; }

/* 关联未竣工项目 */
.pc-projects { margin-top: 12px; }
.pc-projects-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
}
.pc-projects-title :deep(.el-icon) { color: #2979ff; }
.pc-project-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  background: #f6f9ff;
  border: 1px solid #eef2fb;
  cursor: pointer;
  transition: all 0.15s ease;
  margin-bottom: 6px;
}
.pc-project-item:hover {
  background: #eef5ff;
  border-color: #b9d4ff;
}
.pc-project-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-project-meta { flex-shrink: 0; }
.pc-project-role {
  font-size: 12px;
  color: #2979ff;
  background: #e8f1ff;
  padding: 2px 8px;
  border-radius: 10px;
}
.pc-project-arrow { color: #c0c4cc; flex-shrink: 0; font-size: 13px; }
.pc-empty { padding-top: 0; }
.pc-empty-text { font-size: 12.5px; color: #c0c4cc; }
</style>