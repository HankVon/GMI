<!--
  ★ FieldManager.vue ★
  字段管理页面 — 管理员在线增删改查字段元数据
  通过此组件新增的字段立即出现在 DynamicForm/DynamicTable 中
-->
<template>
  <div class="field-manager">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>字段元数据管理</span>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>新增字段
          </el-button>
        </div>
      </template>

      <!-- 实体类型切换 -->
      <el-tabs v-model="activeEntity" @tab-change="loadFields">
        <el-tab-pane label="项目字段" name="project" />
        <el-tab-pane label="人员字段" name="person" />
        <el-tab-pane label="单位字段" name="company" />
      </el-tabs>

      <!-- 字段列表 -->
      <el-table :data="fields" stripe>
        <el-table-column prop="field_key" label="字段标识" width="160" />
        <el-table-column prop="display_name" label="显示名" width="140" />
        <el-table-column prop="data_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ dataTypeLabel(row.data_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="group_name" label="分组" width="120" />

        <el-table-column label="列表" width="65" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_list_visible" color="#67c23a"><Check /></el-icon>
            <el-icon v-else color="#c0c4cc"><Close /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="搜索" width="65" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_searchable" color="#67c23a"><Check /></el-icon>
            <el-icon v-else color="#c0c4cc"><Close /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="导出" width="65" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_exportable" color="#67c23a"><Check /></el-icon>
            <el-icon v-else color="#c0c4cc"><Close /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'enabled' ? 'success' : 'info'" size="small">
              {{ row.status === 'enabled' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openEditDialog(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定删除此字段？历史数据将保留"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新增/编辑弹窗 -->
      <el-dialog
        v-model="dialogVisible"
        :title="editingField ? '编辑字段' : '新增字段'"
        width="640px"
        destroy-on-close
      >
        <el-form ref="formRef" :model="form" label-width="110px" :rules="formRules">
          <el-form-item label="字段标识" prop="field_key">
            <el-input
              v-model="form.field_key"
              placeholder="英文字段名,如 contract_amount"
              :disabled="!!editingField"
            />
          </el-form-item>
          <el-form-item label="显示名" prop="display_name">
            <el-input v-model="form.display_name" placeholder="如 合同金额" />
          </el-form-item>
          <el-form-item label="数据类型" prop="data_type">
            <el-select v-model="form.data_type" style="width: 100%">
              <el-option label="文本" value="text" />
              <el-option label="多行文本" value="textarea" />
              <el-option label="数字" value="number" />
              <el-option label="金额" value="money" />
              <el-option label="日期" value="date" />
              <el-option label="单选" value="select" />
              <el-option label="多选" value="multi_select" />
              <el-option label="开关" value="switch" />
            </el-select>
          </el-form-item>
          <el-form-item
            v-if="['select', 'multi_select'].includes(form.data_type)"
            label="选项集"
          >
            <el-select v-model="form.option_set_code" style="width: 100%" clearable>
              <el-option
                v-for="os in optionSets"
                :key="os.code"
                :label="os.name"
                :value="os.code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="分组">
            <el-input v-model="form.group_name" placeholder="如 合同信息" />
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="排序">
                <el-input-number v-model="form.sort_order" :min="0" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="必填">
                <el-switch v-model="form.is_required" />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="列表">
                <el-switch v-model="form.is_list_visible" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="6">
              <el-form-item label="可搜索">
                <el-switch v-model="form.is_searchable" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="可筛选">
                <el-switch v-model="form.is_filterable" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="可导出">
                <el-switch v-model="form.is_exportable" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="是否启用">
                <el-switch
                  v-model="form.status"
                  active-value="enabled"
                  inactive-value="disabled"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="字段级权限">
            <div class="perm-row">
              <span>可查看角色:</span>
              <el-select
                v-model="permViewRoles"
                multiple
                placeholder="不填=所有人可见"
                style="flex: 1"
              >
                <el-option label="管理员" value="admin" />
                <el-option label="项目经理" value="project_mgr" />
                <el-option label="项目成员" value="member" />
              </el-select>
            </div>
            <div class="perm-row" style="margin-top:8px">
              <span>可编辑角色:</span>
              <el-select
                v-model="permEditRoles"
                multiple
                placeholder="不填=所有人可编辑"
                style="flex: 1"
              >
                <el-option label="管理员" value="admin" />
                <el-option label="项目经理" value="project_mgr" />
                <el-option label="项目成员" value="member" />
              </el-select>
            </div>
          </el-form-item>
          <el-form-item label="校验规则(JSON)">
            <el-input
              v-model="validationRulesStr"
              type="textarea"
              :rows="3"
              placeholder='{"min": 0, "max": 999999999}'
            />
          </el-form-item>
        </el-form>

        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import api from "@/api";

interface FieldRecord {
  id: number;
  field_key: string;
  display_name: string;
  data_type: string;
  option_set_code?: string;
  sort_order: number;
  group_name?: string;
  is_required: boolean;
  is_list_visible: boolean;
  is_searchable: boolean;
  is_filterable: boolean;
  is_exportable: boolean;
  field_permissions?: Record<string, string[]>;
  status: string;
}

const activeEntity = ref("project");
const fields = ref<FieldRecord[]>([]);
const optionSets = ref<any[]>([]);
const dialogVisible = ref(false);
const editingField = ref<FieldRecord | null>(null);
const saving = ref(false);
const formRef = ref<any>(null);
const formRules = {
  field_key: [{ required: true, message: "字段标识为必填项", trigger: "blur" }],
  display_name: [{ required: true, message: "显示名为必填项", trigger: "blur" }],
  data_type: [{ required: true, message: "数据类型为必填项", trigger: "blur" }],
};

const form = ref({
  field_key: "",
  display_name: "",
  data_type: "text",
  option_set_code: "",
  group_name: "",
  sort_order: 0,
  is_required: false,
  is_list_visible: true,
  is_searchable: false,
  is_filterable: false,
  is_exportable: true,
  status: "enabled",
});

const permViewRoles = ref<string[]>([]);
const permEditRoles = ref<string[]>([]);
const validationRulesStr = ref("");

function dataTypeLabel(t: string): string {
  const map: Record<string, string> = {
    text: "文本", textarea: "多行", number: "数字", money: "金额",
    date: "日期", select: "单选", multi_select: "多选", switch: "开关",
  };
  return map[t] || t;
}

async function loadFields() {
  try {
    const res: any = await api.get("/field-metadata", {
      params: { entity_type: activeEntity.value, page_size: 200 },
    });
    fields.value = res.items || [];
  } catch {
    fields.value = [];
  }
}

async function loadOptionSets() {
  try {
    const res: any = await api.get("/option-sets", { params: { page_size: 200 } });
    optionSets.value = res.items || [];
  } catch { optionSets.value = []; }
}

function resetForm() {
  form.value = {
    field_key: "", display_name: "", data_type: "text",
    option_set_code: "", group_name: "", sort_order: 0,
    is_required: false, is_list_visible: true,
    is_searchable: false, is_filterable: false, is_exportable: true,
    status: "enabled",
  };
  permViewRoles.value = [];
  permEditRoles.value = [];
  validationRulesStr.value = "";
}

function openCreateDialog() {
  editingField.value = null;
  resetForm();
  dialogVisible.value = true;
}

function openEditDialog(row: FieldRecord) {
  editingField.value = row;
  form.value = {
    field_key: row.field_key,
    display_name: row.display_name,
    data_type: row.data_type,
    option_set_code: row.option_set_code || "",
    group_name: row.group_name || "",
    sort_order: row.sort_order,
    is_required: row.is_required,
    is_list_visible: row.is_list_visible,
    is_searchable: row.is_searchable,
    is_filterable: row.is_filterable,
    is_exportable: row.is_exportable,
    status: row.status || "enabled",
  };
  permViewRoles.value = row.field_permissions?.view || [];
  permEditRoles.value = row.field_permissions?.edit || [];
  dialogVisible.value = true;
}

async function handleSave() {
  // 校验必填核心字段，不通过则中断保存
  try {
    await formRef.value.validate();
  } catch { return; }
  saving.value = true;
  try {
    const payload: any = {
      ...form.value,
      entity_type: activeEntity.value,
      field_permissions: {
        view: permViewRoles.value,
        edit: permEditRoles.value,
      },
    };
    if (validationRulesStr.value) {
      try {
        payload.validation_rules = JSON.parse(validationRulesStr.value);
      } catch { ElMessage.error("校验规则JSON格式错误"); return; }
    }

    if (editingField.value) {
      await api.put(`/field-metadata/${editingField.value.id}`, payload);
      ElMessage.success("字段已更新");
    } else {
      await api.post("/field-metadata", payload);
      ElMessage.success("字段已创建，缓存已失效，表单将出现新字段");
    }
    dialogVisible.value = false;
    loadFields();
  } catch {
    // 错误由拦截器处理
  } finally {
    saving.value = false;
  }
}

async function handleDelete(id: number) {
  try {
    await api.delete(`/field-metadata/${id}`);
    ElMessage.success("字段已删除(软删除)，历史数据保留");
    loadFields();
  } catch { /* 错误由拦截器处理 */ }
}

onMounted(() => {
  loadFields();
  loadOptionSets();
});
</script>

<style scoped>
.field-manager {
  max-width: 1200px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.perm-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.perm-row span {
  width: 90px;
  flex-shrink: 0;
  font-size: 13px;
  color: #606266;
}
</style>
