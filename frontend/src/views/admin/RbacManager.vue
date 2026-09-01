<template>
  <div class="rbac-page">
    <el-card>
      <template #header>
        <div class="rbac-head">
          <span>角色权限管理</span>
          <div class="rbac-head-actions">
            <el-input
              v-model="keyword" placeholder="搜索用户名/显示名" clearable style="width: 220px"
              @keyup.enter="loadUsers(1)" @clear="loadUsers(1)"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="activeFilter" placeholder="状态" clearable style="width: 110px" @change="loadUsers(1)">
              <el-option label="启用" :value="true" />
              <el-option label="禁用" :value="false" />
            </el-select>
            <el-button type="primary" @click="openCreateDialog">
              <el-icon style="margin-right:4px"><Plus /></el-icon>新建账号
            </el-button>
            <el-button
              v-if="selectedUsers.length"
              type="primary" plain @click="openBatchRoleDialog"
            >
              批量分配角色({{ selectedUsers.length }})
            </el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="tab" type="card">
        <!-- ===== 用户 ===== -->
        <el-tab-pane label="用户" name="users">
          <el-table :data="users" stripe v-loading="loading" @selection-change="onUsersSelect">
            <el-table-column type="selection" width="42" />
            <el-table-column prop="username" label="用户名" width="130" />
            <el-table-column prop="display_name" label="显示名" width="130" />
            <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
            <el-table-column label="状态" width="80">
              <template #default="{row}">
                <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="角色" min-width="140">
              <template #default="{row}">
                <el-tag v-for="r in row.roles" :key="r" size="small" style="margin:2px">{{ roleName(r) }}</el-tag>
                <span v-if="!row.roles?.length" class="muted">无角色</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="165">
              <template #default="{row}">{{ fmtTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="390" fixed="right">
              <template #default="{row}">
                <el-button link type="primary" size="small" @click="openRoleDialog(row)">分配角色</el-button>
                <el-button link type="primary" size="small" @click="openDirectPermDialog(row)">直授权限</el-button>
                <el-button link type="primary" size="small" @click="openScopeDialog(row)">数据范围</el-button>
                <el-button link type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
                <el-dropdown trigger="click" @command="(c:string)=>onMoreCommand(c,row)">
                  <el-button link type="info" size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="resetpwd">重置密码</el-dropdown-item>
                      <el-dropdown-item :command="row.is_active ? 'disable' : 'enable'">
                        {{ row.is_active ? '禁用账号' : '启用账号' }}
                      </el-dropdown-item>
                      <el-dropdown-item divided command="delete">删除账号</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            style="margin-top:12px;justify-content:flex-end" v-model:current-page="userPage"
            :page-size="userPageSize" :total="userTotal" layout="total,prev,pager,next"
            @current-change="(p:number)=>loadUsers(p)"
          />
        </el-tab-pane>

        <!-- ===== 角色 ===== -->
        <el-tab-pane label="角色" name="roles">
          <div style="margin-bottom:12px;display:flex;justify-content:flex-end">
            <el-button type="primary" size="small" @click="openRoleCreate">
              <el-icon style="margin-right:4px"><Plus /></el-icon>新建角色
            </el-button>
          </div>
          <el-table :data="roles" stripe>
            <el-table-column prop="code" label="编码" width="130" />
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
            <el-table-column prop="user_count" label="用户数" width="80" />
            <el-table-column label="操作" width="240">
              <template #default="{row}">
                <el-button type="primary" size="small" @click="openPermDialog(row)">配置页面</el-button>
                <el-button size="small" @click="openRoleEdit(row)">编辑</el-button>
                <el-button type="danger" size="small" @click="deleteRole(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建账号 -->
    <el-dialog v-model="createDialog" title="新建账号" width="560px" :close-on-click-modal="false">
      <el-form :model="createForm" label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="createForm.username" placeholder="登录账号，如 zhangsan" maxlength="32" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="createForm.display_name" placeholder="展示名称，留空默认同用户名" maxlength="32" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="createForm.password" type="password" show-password placeholder="8-64位，须含字母和数字" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="createForm.email" placeholder="选填" maxlength="64" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="createForm.phone" placeholder="选填" maxlength="32" />
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="createForm.department_id" clearable placeholder="选填" style="width:100%">
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始角色">
          <el-checkbox-group v-model="createRoles">
            <el-checkbox v-for="r in allRoles" :key="r.id" :label="r.id" :value="r.id">{{ r.name }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="数据范围">
          <el-select v-model="createForm.data_scope_rule" clearable style="width:100%" placeholder="不选=继承角色">
            <el-option label="全部数据" value="ALL" />
            <el-option label="本部门及子部门" value="DEPT_TREE" />
            <el-option label="仅本部门" value="DEPT_ONLY" />
            <el-option label="仅本人负责" value="OWN" />
            <el-option label="自定义" value="CUSTOM" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="showCreateDept" label="部门">
          <el-select v-model="createForm.scope_dept_ids" multiple clearable style="width:100%" placeholder="选择部门(含子部门)">
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog=false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建账号</el-button>
      </template>
    </el-dialog>

    <!-- 编辑账号 -->
    <el-dialog v-model="editDialog" title="编辑账号" width="440px" :close-on-click-modal="false">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名"><el-input :model-value="editForm.username" disabled /></el-form-item>
        <el-form-item label="显示名"><el-input v-model="editForm.display_name" maxlength="32" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="editForm.email" maxlength="64" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="editForm.phone" maxlength="32" /></el-form-item>
        <el-form-item label="部门">
          <el-select v-model="editForm.department_id" clearable style="width:100%">
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog=false">取消</el-button>
        <el-button type="primary" :loading="savingEdit" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分配角色 -->
    <el-dialog v-model="roleDialog" title="分配角色" width="400px">
      <el-checkbox-group v-model="selectedRoles">
        <el-checkbox v-for="r in allRoles" :key="r.id" :label="r.id" :value="r.id">{{ r.name }}</el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="roleDialog=false">取消</el-button>
        <el-button type="primary" @click="saveRoles">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量分配角色 -->
    <el-dialog v-model="batchRoleDialog" title="批量分配角色" width="440px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px"
        :title="`将角色应用到选中的 ${selectedUsers.length} 个账号(覆盖其原角色)`" />
      <el-checkbox-group v-model="batchRoleIds">
        <el-checkbox v-for="r in allRoles" :key="r.id" :label="r.id" :value="r.id">{{ r.name }}</el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="batchRoleDialog=false">取消</el-button>
        <el-button type="primary" :loading="savingBatchRoles" @click="saveBatchRoles">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="pwdDialog" title="重置密码" width="420px" :close-on-click-modal="false">
      <el-form :model="pwdForm" label-width="90px">
        <el-form-item label="目标账号">
          <el-input :model-value="pwdForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="8-64位，须含字母和数字" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialog=false">取消</el-button>
        <el-button type="primary" :loading="savingPwd" @click="submitPwd">确认重置</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑角色 -->
    <el-dialog v-model="roleFormDialog" :title="roleForm.id ? '编辑角色' : '新建角色'" width="420px" :close-on-click-modal="false">
      <el-form :model="roleForm" label-width="80px">
        <el-form-item label="编码" required>
          <el-input v-model="roleForm.code" placeholder="如 analyst" :disabled="!!roleForm.id" maxlength="64" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="roleForm.name" placeholder="如 情报分析师" maxlength="128" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" maxlength="512" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleFormDialog=false">取消</el-button>
        <el-button type="primary" :loading="savingRole" @click="submitRoleForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 配置页面(页面级权限: 只勾选可见页面, 功能权限自动保留) -->
    <el-dialog v-model="permDialog" title="配置页面" width="440px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px"
        title="勾选该角色可见的页面；保存后前端菜单自动隐藏/显示，未勾选页面将无法访问。" />
      <el-tree :data="pageTree" show-checkbox node-key="id" ref="permTreeRef" default-expand-all :props="{label:'label'}" />
      <template #footer>
        <el-button @click="permDialog=false">取消</el-button>
        <el-button type="primary" @click="savePerms">保存</el-button>
      </template>
    </el-dialog>

    <!-- 直授权限(用户级, 绕过角色) -->
    <el-dialog v-model="directPermDialog" title="直授权限（例外授权）" width="460px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px"
        title="直授权限对指定用户单独生效，与角色权限取并集；用于临时放行或例外授权。" />
      <el-tree :data="permTree" show-checkbox node-key="id" ref="directPermTreeRef" default-expand-all :props="{label:'label'}" />
      <template #footer>
        <el-button @click="directPermDialog=false">取消</el-button>
        <el-button type="primary" @click="saveDirectPerms">保存</el-button>
      </template>
    </el-dialog>

    <!-- 数据范围 -->
    <el-dialog v-model="scopeDialog" title="数据范围" width="620px" :close-on-click-modal="false">
      <el-alert
        v-if="scopeInherit" type="info" :closable="false" style="margin-bottom:12px"
        :title="`角色继承: ${scopeInherit}`"
      />
      <el-form label-width="90px">
        <el-form-item label="范围规则">
          <el-radio-group v-model="scopeForm.rule">
            <el-radio value="">继承角色</el-radio>
            <el-radio value="ALL">全部数据</el-radio>
            <el-radio value="DEPT_TREE">本部门及子部门</el-radio>
            <el-radio value="DEPT_ONLY">仅本部门</el-radio>
            <el-radio value="OWN">仅本人负责</el-radio>
            <el-radio value="CUSTOM">自定义</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="showDeptSelect" label="部门">
          <el-select v-model="scopeForm.dept_ids" multiple clearable style="width:100%" placeholder="选择部门(含子部门)">
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象授权">
          <div style="width:100%">
            <el-table :data="grants" size="small" border max-height="220">
              <el-table-column prop="entity_type" label="类型" width="76">
                <template #default="{row}">{{ entityTypeLabel(row.entity_type) }}</template>
              </el-table-column>
              <el-table-column prop="entity_name" label="对象" min-width="120" show-overflow-tooltip>
                <template #default="{row}">{{ row.entity_name || ('#' + row.entity_id) }}</template>
              </el-table-column>
              <el-table-column prop="grant_type" label="授权" width="64">
                <template #default="{row}">{{ row.grant_type === 'own' ? '负责' : '查看' }}</template>
              </el-table-column>
              <el-table-column label="过期" width="120">
                <template #default="{row}">{{ row.expire_at ? row.expire_at.slice(0, 10) : '永久' }}</template>
              </el-table-column>
              <el-table-column label="操作" width="56">
                <template #default="{row}">
                  <el-button link type="danger" size="small" @click="removeGrant(row)">删</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div style="margin-top:8px;display:flex;gap:6px;align-items:center">
              <el-select v-model="grantForm.entity_type" style="width:96px">
                <el-option label="项目" value="project" />
                <el-option label="公司" value="company" />
                <el-option label="投标" value="bid" />
              </el-select>
              <el-input v-model.number="grantForm.entity_id" style="width:96px" placeholder="对象ID" />
              <el-select v-model="grantForm.grant_type" style="width:82px">
                <el-option label="查看" value="view" />
                <el-option label="负责" value="own" />
              </el-select>
              <el-button type="primary" size="small" @click="addGrant">添加授权</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scopeDialog=false">关闭</el-button>
        <el-button type="primary" :loading="savingScope" @click="saveScope">保存数据范围</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Search, ArrowDown } from "@element-plus/icons-vue";
import api from "@/api";

const tab = ref("users");
const loading = ref(false);

// ── 用户列表 ──
const users = ref<any[]>([]);
const userPage = ref(1);
const userPageSize = 20;
const userTotal = ref(0);
const keyword = ref("");
const activeFilter = ref<"" | boolean>("");

async function loadUsers(page = userPage.value) {
  loading.value = true;
  try {
    const res: any = await api.get("/rbac/users", {
      params: {
        page, page_size: userPageSize,
        keyword: keyword.value || undefined,
        is_active: activeFilter.value === "" ? undefined : activeFilter.value,
      },
    });
    users.value = res.items || [];
    userTotal.value = res.total || 0;
  } finally { loading.value = false; }
}

// ── 角色 ──
const roles = ref<any[]>([]);
const allRoles = ref<any[]>([]);
async function loadRoles() {
  const res: any = await api.get("/rbac/roles");
  roles.value = res.data || [];
  allRoles.value = res.data || [];
}
function roleName(code: string) {
  const r = allRoles.value.find((x) => x.code === code);
  return r ? r.name : code;
}

// ── 部门 ──
const departments = ref<any[]>([]);
async function loadDepartments() {
  const res: any = await api.get("/rbac/departments");
  departments.value = res.data || [];
}

// ── 权限树 ──
const permTree = ref<any[]>([]);
const pageTree = ref<any[]>([]);
const allPerms = ref<any[]>([]);
const permTreeRef = ref();
async function loadPerms() {
  const res: any = await api.get("/rbac/permissions");
  const perms = res.data || [];
  allPerms.value = perms;
  permTree.value = buildTree(perms);      // 全量树(直授权限用)
  pageTree.value = buildPageTree(perms);  // 页面树(仅 menu, 配置页面用)
}
function buildTree(perms: any[], parentId: number | null = null): any[] {
  return perms.filter((p) => p.parent_id === parentId).map((p) => ({
    id: p.id, label: p.name, children: buildTree(perms, p.id),
  }));
}
/** 页面树: 只保留 menu 类型权限, 按顶层菜单分组展示 */
function buildPageTree(perms: any[]): any[] {
  const menuOf = (parentId: number | null) =>
    perms
      .filter((p) => p.resource_type === "menu" && p.parent_id === parentId && !p.is_deleted)
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      .map((p) => ({ id: p.id, label: p.name, children: menuOf(p.id) }));
  return menuOf(null);
}

// ── 新建账号 ──
const createDialog = ref(false);
const creating = ref(false);
const createForm = ref({
  username: "", display_name: "", password: "", email: "", phone: "",
  department_id: null as number | null,
  data_scope_rule: "", scope_dept_ids: [] as number[],
});
const createRoles = ref<number[]>([]);
const showCreateDept = computed(() => ["DEPT_TREE", "DEPT_ONLY", "CUSTOM"].includes(createForm.value.data_scope_rule));

function openCreateDialog() {
  createForm.value = {
    username: "", display_name: "", password: "", email: "", phone: "",
    department_id: null, data_scope_rule: "", scope_dept_ids: [],
  };
  createRoles.value = [];
  createDialog.value = true;
}
async function submitCreate() {
  const u = createForm.value.username.trim();
  if (!u) return ElMessage.warning("请输入用户名");
  if (!createForm.value.password) return ElMessage.warning("请输入初始密码");
  if (createForm.value.password.length < 8) return ElMessage.warning("密码至少 8 位");
  creating.value = true;
  try {
    await api.post("/auth/register", {
      username: u,
      password: createForm.value.password,
      display_name: createForm.value.display_name.trim(),
      email: createForm.value.email.trim(),
      phone: createForm.value.phone.trim(),
      department_id: createForm.value.department_id,
      role_ids: createRoles.value,
      data_scope_rule: createForm.value.data_scope_rule || null,
      scope_dept_ids: createForm.value.scope_dept_ids,
    });
    ElMessage.success("账号创建成功");
    createDialog.value = false;
    loadUsers(1);
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || "创建失败";
    ElMessage.error(typeof detail === "string" ? detail : "创建失败");
  } finally { creating.value = false; }
}

// ── 编辑账号 ──
const editDialog = ref(false);
const savingEdit = ref(false);
const editForm = ref<any>({});
function openEditDialog(row: any) {
  editForm.value = {
    id: row.id, username: row.username,
    display_name: row.display_name || "",
    email: row.email || "", phone: row.phone || "",
    department_id: row.department_id ?? null,
  };
  editDialog.value = true;
}
async function submitEdit() {
  savingEdit.value = true;
  try {
    await api.put(`/rbac/users/${editForm.value.id}`, {
      display_name: editForm.value.display_name,
      email: editForm.value.email,
      phone: editForm.value.phone,
      department_id: editForm.value.department_id,
    });
    ElMessage.success("已保存");
    editDialog.value = false;
    loadUsers();
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || "保存失败";
    ElMessage.error(typeof detail === "string" ? detail : "保存失败");
  } finally { savingEdit.value = false; }
}

// ── 分配角色 ──
const roleDialog = ref(false);
const curUser = ref<any>({});
const selectedRoles = ref<number[]>([]);
function openRoleDialog(user: any) {
  curUser.value = user;
  // 列表只返回角色 code, 需要反查 id
  selectedRoles.value = (user.roles || [])
    .map((code: string) => allRoles.value.find((r) => r.code === code)?.id)
    .filter(Boolean);
  roleDialog.value = true;
}
async function saveRoles() {
  await api.put(`/rbac/users/${curUser.value.id}/roles`, { role_ids: selectedRoles.value });
  ElMessage.success("已保存");
  roleDialog.value = false;
  loadUsers();
}

// ── 批量分配角色 ──
const selectedUsers = ref<any[]>([]);
const batchRoleDialog = ref(false);
const batchRoleIds = ref<number[]>([]);
const savingBatchRoles = ref(false);
function onUsersSelect(rows: any[]) {
  selectedUsers.value = rows;
}
function openBatchRoleDialog() {
  batchRoleIds.value = [];
  batchRoleDialog.value = true;
}
async function saveBatchRoles() {
  if (!selectedUsers.value.length) return;
  savingBatchRoles.value = true;
  let ok = 0, fail = 0;
  for (const u of selectedUsers.value) {
    try {
      await api.put(`/rbac/users/${u.id}/roles`, { role_ids: batchRoleIds.value });
      ok++;
    } catch { fail++; }
  }
  savingBatchRoles.value = false;
  batchRoleDialog.value = false;
  ElMessage.success(`批量分配角色完成: 成功 ${ok} 条, 失败 ${fail} 条`);
  loadUsers();
}

// ── 更多操作 ──
async function onMoreCommand(cmd: string, row: any) {
  if (cmd === "resetpwd") {
    pwdForm.value = { id: row.id, username: row.username, new_password: "" };
    pwdDialog.value = true;
  } else if (cmd === "enable" || cmd === "disable") {
    const active = cmd === "enable";
    try {
      await api.put(`/rbac/users/${row.id}/active`, { is_active: active });
      ElMessage.success(active ? "已启用" : "已禁用");
      loadUsers();
    } catch (e: any) {
      const detail = e?.response?.data?.detail || "操作失败";
      ElMessage.error(typeof detail === "string" ? detail : "操作失败");
    }
  } else if (cmd === "delete") {
    await ElMessageBox.confirm(`确定删除账号「${row.username}」吗？该操作不可恢复。`, "删除账号", {
      type: "warning", confirmButtonText: "删除", cancelButtonText: "取消",
    });
    try {
      await api.delete(`/rbac/users/${row.id}`);
      ElMessage.success("已删除");
      loadUsers();
    } catch (e: any) {
      const detail = e?.response?.data?.detail || "删除失败";
      ElMessage.error(typeof detail === "string" ? detail : "删除失败");
    }
  }
}

// ── 重置密码 ──
const pwdDialog = ref(false);
const savingPwd = ref(false);
const pwdForm = ref({ id: 0, username: "", new_password: "" });
async function submitPwd() {
  if (pwdForm.value.new_password.length < 8) return ElMessage.warning("密码至少 8 位");
  savingPwd.value = true;
  try {
    await api.put(`/rbac/users/${pwdForm.value.id}/password`, { new_password: pwdForm.value.new_password });
    ElMessage.success("密码已重置");
    pwdDialog.value = false;
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "重置失败";
    ElMessage.error(typeof detail === "string" ? detail : "重置失败");
  } finally { savingPwd.value = false; }
}

// ── 角色新建/编辑/删除 ──
const roleFormDialog = ref(false);
const savingRole = ref(false);
const roleForm = ref<any>({});
function openRoleCreate() {
  roleForm.value = { id: 0, code: "", name: "", description: "" };
  roleFormDialog.value = true;
}
function openRoleEdit(row: any) {
  roleForm.value = { id: row.id, code: row.code, name: row.name, description: row.description || "" };
  roleFormDialog.value = true;
}
async function submitRoleForm() {
  if (!roleForm.value.code.trim()) return ElMessage.warning("请输入角色编码");
  if (!roleForm.value.name.trim()) return ElMessage.warning("请输入角色名称");
  savingRole.value = true;
  try {
    if (roleForm.value.id) {
      await api.put(`/rbac/roles/${roleForm.value.id}`, {
        code: roleForm.value.code, name: roleForm.value.name, description: roleForm.value.description,
      });
    } else {
      await api.post("/rbac/roles", {
        code: roleForm.value.code, name: roleForm.value.name, description: roleForm.value.description,
      });
    }
    ElMessage.success("已保存");
    roleFormDialog.value = false;
    loadRoles();
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "保存失败";
    ElMessage.error(typeof detail === "string" ? detail : "保存失败");
  } finally { savingRole.value = false; }
}
async function deleteRole(row: any) {
  await ElMessageBox.confirm(`确定删除角色「${row.name}」吗？`, "删除角色", {
    type: "warning", confirmButtonText: "删除", cancelButtonText: "取消",
  });
  try {
    await api.delete(`/rbac/roles/${row.id}`);
    ElMessage.success("已删除");
    loadRoles();
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "删除失败";
    ElMessage.error(typeof detail === "string" ? detail : "删除失败");
  }
}

// ── 配置页面(页面级权限; 功能权限自动保留) ──
const permDialog = ref(false);
const curRole = ref<any>({});
const rolePermIds = ref<number[]>([]);
async function openPermDialog(role: any) {
  curRole.value = role;
  permDialog.value = true;
  // 先清空再异步加载已有权限回显(只回显 menu 页面节点)
  nextTick(() => permTreeRef.value?.setCheckedKeys([]));
  try {
    const res: any = await api.get(`/rbac/roles/${role.id}/permissions`);
    const ids = res?.data || [];
    rolePermIds.value = ids;
    const menuIds = ids.filter((id: number) => {
      const p = allPerms.value.find((x) => x.id === id);
      return p && p.resource_type === "menu";
    });
    nextTick(() => permTreeRef.value?.setCheckedKeys(menuIds));
  } catch { /* 回显失败不阻塞 */ }
}
async function savePerms() {
  const ids = permTreeRef.value?.getCheckedKeys() || [];
  const half = permTreeRef.value?.getHalfCheckedKeys() || [];
  // 保留角色原有非菜单权限(api/button 功能权限), 避免全量替换把它们清掉
  const keepIds = (rolePermIds.value || []).filter((id: number) => {
    const p = allPerms.value.find((x) => x.id === id);
    return p && p.resource_type !== "menu";
  });
  await api.put(`/rbac/roles/${curRole.value.id}/permissions`, {
    permission_ids: [...ids, ...half, ...keepIds],
  });
  ElMessage.success("已保存");
  permDialog.value = false;
  loadRoles();
}

// ── 用户级直授权限(绕过角色) ──
const directPermDialog = ref(false);
const directPermUser = ref<any>({});
const directPermTreeRef = ref();
async function openDirectPermDialog(user: any) {
  directPermUser.value = user;
  directPermDialog.value = true;
  nextTick(() => directPermTreeRef.value?.setCheckedKeys([]));
  try {
    const res: any = await api.get(`/rbac/users/${user.id}/permissions`);
    nextTick(() => directPermTreeRef.value?.setCheckedKeys(res?.data || []));
  } catch { /* 回显失败不阻塞 */ }
}
async function saveDirectPerms() {
  const ids = directPermTreeRef.value?.getCheckedKeys() || [];
  const half = directPermTreeRef.value?.getHalfCheckedKeys() || [];
  try {
    await api.put(`/rbac/users/${directPermUser.value.id}/permissions`, {
      permission_ids: [...ids, ...half],
    });
    ElMessage.success("直授权限已保存");
    directPermDialog.value = false;
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "保存失败";
    ElMessage.error(typeof detail === "string" ? detail : "保存失败");
  }
}

// ── 数据范围(分发权限的数据维度) ──
const scopeDialog = ref(false);
const savingScope = ref(false);
const scopeInherit = ref("");
const scopeForm = ref<{ id: number; rule: string; dept_ids: number[] }>({ id: 0, rule: "", dept_ids: [] });
const grants = ref<any[]>([]);
const grantForm = ref<{ entity_type: string; entity_id: number | null; grant_type: string }>({
  entity_type: "project", entity_id: null, grant_type: "view",
});
const showDeptSelect = computed(() => ["DEPT_TREE", "DEPT_ONLY", "CUSTOM"].includes(scopeForm.value.rule));

function entityTypeLabel(t: string) {
  return { project: "项目", company: "公司", bid: "投标" }[t] || t;
}

async function openScopeDialog(user: any) {
  scopeForm.value = { id: user.id, rule: "", dept_ids: [] };
  scopeInherit.value = "";
  grants.value = [];
  scopeDialog.value = true;
  try {
    const res: any = await api.get(`/rbac/users/${user.id}/data-scope`);
    const d = res?.data || {};
    scopeForm.value.rule = d.user_rule || "";
    scopeForm.value.dept_ids = d.user_dept_ids || [];
    const inherits = (d.roles || []).filter((r: any) => r.data_scope_rule);
    scopeInherit.value = inherits.map((r: any) => `${r.name}(${r.data_scope_rule})`).join("、") || "";
  } catch { /* 回显失败不阻塞 */ }
  loadGrants(user.id);
}

async function loadGrants(uid: number) {
  try {
    const res: any = await api.get(`/rbac/users/${uid}/grants`);
    grants.value = res?.data || [];
  } catch { /* 忽略 */ }
}

async function saveScope() {
  if (!scopeForm.value.id) return;
  savingScope.value = true;
  try {
    await api.put(`/rbac/users/${scopeForm.value.id}/data-scope`, {
      rule: scopeForm.value.rule || null,
      dept_ids: scopeForm.value.dept_ids,
    });
    ElMessage.success("数据范围已保存");
    scopeDialog.value = false;
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "保存失败";
    ElMessage.error(typeof detail === "string" ? detail : "保存失败");
  } finally { savingScope.value = false; }
}

async function addGrant() {
  if (!grantForm.value.entity_id) return ElMessage.warning("请输入对象ID");
  try {
    await api.post(`/rbac/users/${scopeForm.value.id}/grants`, {
      items: [{
        entity_type: grantForm.value.entity_type,
        entity_id: grantForm.value.entity_id,
        grant_type: grantForm.value.grant_type,
      }],
    });
    ElMessage.success("已授权");
    grantForm.value.entity_id = null;
    loadGrants(scopeForm.value.id);
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "授权失败";
    ElMessage.error(typeof detail === "string" ? detail : "授权失败");
  }
}

async function removeGrant(row: any) {
  try {
    await api.delete(`/rbac/users/${scopeForm.value.id}/grants/${row.id}`);
    ElMessage.success("已撤销");
    loadGrants(scopeForm.value.id);
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "撤销失败";
    ElMessage.error(typeof detail === "string" ? detail : "撤销失败");
  }
}

function fmtTime(v?: string) {
  if (!v) return "—";
  return v.replace("T", " ").slice(0, 19);
}

onMounted(() => { loadUsers(1); loadRoles(); loadPerms(); loadDepartments(); });
</script>

<style scoped>
.rbac-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.rbac-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.muted { color: #909399; font-size: 12px; }
</style>
