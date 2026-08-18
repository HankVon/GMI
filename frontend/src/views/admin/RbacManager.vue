<template>
  <el-card>
    <template #header><span>角色权限管理</span></template>
    <el-tabs v-model="tab" type="card">
      <el-tab-pane label="用户" name="users">
        <el-table :data="users" stripe><el-table-column prop="username" label="用户名" width="120" />
          <el-table-column prop="display_name" label="显示名" width="120" />
          <el-table-column prop="email" label="邮箱" />
          <el-table-column label="角色"><template #default="{row}"><el-tag v-for="r in row.roles" :key="r" size="small" style="margin:2px">{{r}}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="120"><template #default="{row}"><el-button type="primary" size="small" @click="openRoleDialog(row)">分配角色</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="角色" name="roles">
        <el-table :data="roles" stripe><el-table-column prop="code" label="编码" width="120" />
          <el-table-column prop="name" label="名称" /><el-table-column prop="user_count" label="用户数" width="80" />
          <el-table-column label="操作" width="120"><template #default="{row}"><el-button type="primary" size="small" @click="openPermDialog(row)">配置权限</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="roleDialog" title="分配角色" width="400px">
      <el-checkbox-group v-model="selectedRoles"><el-checkbox v-for="r in allRoles" :key="r.code" :label="r.code" :value="r.code">{{r.name}}</el-checkbox></el-checkbox-group>
      <template #footer><el-button @click="roleDialog=false">取消</el-button><el-button type="primary" @click="saveRoles">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="permDialog" title="配置权限" width="400px">
      <el-tree :data="permTree" show-checkbox node-key="id" ref="permTreeRef" default-expand-all />
      <template #footer><el-button @click="permDialog=false">取消</el-button><el-button type="primary" @click="savePerms">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import { ElMessage } from "element-plus";
import api from "@/api";

const tab = ref("users");
const users = ref<any[]>([]);
const roles = ref<any[]>([]);
const allRoles = ref<any[]>([]);
const permTree = ref<any[]>([]);
const permTreeRef = ref();
const roleDialog = ref(false);
const permDialog = ref(false);
const curUser = ref<any>({});
const curRole = ref<any>({});
const selectedRoles = ref<string[]>([]);

let rolePermMap: Record<number, number[]> = {}; // role_id → permission_ids cache

async function loadUsers() {
  const res: any = await api.get("/rbac/users", { params: { page_size: 100 } });
  users.value = res.items || [];
}
async function loadRoles() {
  const res: any = await api.get("/rbac/roles");
  roles.value = res.data || [];
  allRoles.value = res.data || [];
}
async function loadPerms() {
  const res: any = await api.get("/rbac/permissions");
  permTree.value = buildTree(res.data || []);
}
async function loadRolePerms(roleId: number): Promise<number[]> {
  if (rolePermMap[roleId]) return rolePermMap[roleId];
  const res: any = await api.get("/rbac/permissions");
  rolePermMap[roleId] = []; // load from server maybe in next version
  return [];
}
function buildTree(perms: any[], parentId: number | null = null): any[] {
  return perms.filter(p => p.parent_id === parentId).map(p => ({
    id: p.id, label: p.name, children: buildTree(perms, p.id),
  }));
}
function openRoleDialog(user: any) {
  curUser.value = user;
  selectedRoles.value = (user.roles || []);
  roleDialog.value = true;
}
async function saveRoles() {
  await api.put(`/rbac/users/${curUser.value.id}/roles`, { role_ids: selectedRoles.value });
  ElMessage.success("已保存"); roleDialog.value = false; loadUsers();
}
function openPermDialog(role: any) {
  curRole.value = role;
  permDialog.value = true;
  // load existing permissions from a separate endpoint or simulate
  nextTick(() => permTreeRef.value?.setCheckedKeys([]));
}
async function savePerms() {
  const ids = permTreeRef.value?.getCheckedKeys() || [];
  await api.put(`/rbac/roles/${curRole.value.id}/permissions`, { permission_ids: ids });
  ElMessage.success("已保存"); permDialog.value = false;
}
onMounted(() => { loadUsers(); loadRoles(); loadPerms(); });
</script>
