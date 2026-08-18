<template>
  <el-card>
    <template #header><span>日志</span></template>
    <el-tabs v-model="activeTab">
      <!-- 操作日志 -->
      <el-tab-pane label="操作日志" name="operations">
        <el-row :gutter="12" style="margin-bottom:12px">
          <el-col :span="6"><el-input v-model="filters.username" placeholder="用户名" clearable @change="reload" /></el-col>
          <el-col :span="4">
            <el-select v-model="filters.action" placeholder="操作类型" clearable @change="reload" style="width:100%">
              <el-option v-for="a in actions" :key="a" :label="a" :value="a" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select v-model="filters.resource_type" placeholder="资源类型" clearable @change="reload" style="width:100%">
              <el-option v-for="r in resources" :key="r" :label="r" :value="r" />
            </el-select>
          </el-col>
          <el-col :span="6"><el-date-picker v-model="filters.dateRange" type="daterange" range-separator="~" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" @change="reload" style="width:100%" /></el-col>
        </el-row>
        <el-table :data="logs" stripe>
          <el-table-column prop="created_at" label="时间" width="160" />
          <el-table-column prop="username" label="用户" width="100" />
          <el-table-column prop="action" label="操作" width="80"><template #default="{row}"><el-tag size="small" :type="actionTag(row.action)">{{row.action}}</el-tag></template></el-table-column>
          <el-table-column prop="resource_type" label="资源" width="100" />
          <el-table-column prop="resource_name" label="资源名" show-overflow-tooltip />
          <el-table-column prop="ip_address" label="IP" width="130" />
        </el-table>
        <el-pagination style="margin-top:12px;justify-content:flex-end" v-model:current-page="page" :page-size="pageSize" :total="total" layout="total,prev,next" @update:current-page="reload" />
      </el-tab-pane>

      <!-- 字段变更历史 -->
      <el-tab-pane label="字段变更历史" name="fieldChanges">
        <el-row :gutter="12" style="margin-bottom:12px">
          <el-col :span="6">
            <el-input v-model="fcFilters.resource_name" placeholder="按项目/人员/单位名称搜索" clearable @change="reloadFieldChanges">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </el-col>
          <el-col :span="4">
            <el-select v-model="fcFilters.entity_type" placeholder="实体类型" clearable @change="reloadFieldChanges" style="width:100%">
              <el-option label="项目" value="project" />
              <el-option label="人员" value="person" />
              <el-option label="单位" value="company" />
            </el-select>
          </el-col>
        </el-row>
        <el-table :data="fieldChanges" stripe>
          <el-table-column prop="changed_at" label="变更时间" width="160" />
          <el-table-column label="所属实体" width="220" show-overflow-tooltip>
            <template #default="{row}">
              <span v-if="row.entity_name">{{ row.entity_name }}</span>
              <span v-else>{{ entityTypeLabel(row.entity_type) }} #{{ row.entity_id }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="entity_type" label="类型" width="80">
            <template #default="{row}"><el-tag size="small">{{ entityTypeLabel(row.entity_type) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="field_label" label="字段" width="140" />
          <el-table-column label="变更内容" min-width="260">
            <template #default="{row}">
              <span class="old-val">{{ row.old_value || "(空)" }}</span> →
              <span class="new-val">{{ row.new_value || "(空)" }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="changed_by" label="变更人" width="90" />
        </el-table>
        <el-pagination style="margin-top:12px;justify-content:flex-end" v-model:current-page="fcPage" :page-size="pageSize" :total="fcTotal" layout="total,prev,next" @update:current-page="reloadFieldChanges" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Search } from "@element-plus/icons-vue";
import api from "@/api";

const activeTab = ref("operations");
const logs = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const filters = ref({ username: "", action: "", resource_type: "", dateRange: null as any });
const actions = ["create","update","delete","export","import","login","logout"];
const resources = ["project","person","project_member","field_metadata","option_set","excel"];

const fieldChanges = ref<any[]>([]);
const fcTotal = ref(0);
const fcPage = ref(1);
const fcFilters = ref({ resource_name: "", entity_type: "" });

function actionTag(a: string) { const m: any = {create:"success",update:"primary",delete:"danger"}; return m[a]||"info"; }
function entityTypeLabel(t: string): string {
  const m: any = { project: "项目", person: "人员", company: "单位", persons: "人员", companies: "单位" };
  return m[t] || t;
}
async function reload() {
  const p: any = { page: page.value, page_size: pageSize };
  if (filters.value.action) p.action = filters.value.action;
  if (filters.value.resource_type) p.resource_type = filters.value.resource_type;
  if (filters.value.username) p.user_id = filters.value.username;
  if (filters.value.dateRange) { p.date_from = filters.value.dateRange[0]; p.date_to = filters.value.dateRange[1]; }
  const res: any = await api.get("/audit/operations", { params: p });
  logs.value = res.items || []; total.value = res.total || 0;
}
async function reloadFieldChanges() {
  const p: any = { page: fcPage.value, page_size: pageSize };
  if (fcFilters.value.resource_name) p.resource_name = fcFilters.value.resource_name;
  if (fcFilters.value.entity_type) p.entity_type = fcFilters.value.entity_type;
  const res: any = await api.get("/audit/field-changes", { params: p });
  fieldChanges.value = res.items || []; fcTotal.value = res.total || 0;
}
onMounted(() => { reload(); reloadFieldChanges(); });
</script>

<style scoped>
.old-val { color: #f56c6c; text-decoration: line-through; margin-right: 4px; }
.new-val { color: #67c23a; margin-left: 4px; }
</style>
