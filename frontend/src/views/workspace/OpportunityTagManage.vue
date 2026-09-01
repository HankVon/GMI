<!-- 策展标签管理: 热点领域(HOT)/热门项目 字典维护, 前台筛选区与列表标签同源 -->
<template>
  <div class="tag-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">策展标签管理</h2>
        <p class="page-desc">维护前台「项目商机」页筛选区的热点领域/热门标签, 及商机列表自定义标签</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadTags">
          <el-icon style="margin-right: 4px"><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon style="margin-right: 4px"><Plus /></el-icon>新增标签
        </el-button>
      </div>
    </div>

    <el-card class="group-card" shadow="never">
      <template #header>
        <div class="group-head">
          <span class="group-title">热点领域 <span class="hot-badge">HOT</span></span>
          <span class="group-hint">前台筛选区·单选 pill</span>
        </div>
      </template>
      <el-table :data="fieldTags" v-loading="loading" size="default" style="width: 100%">
        <el-table-column prop="sortOrder" label="排序" width="80" align="center" />
        <el-table-column prop="code" label="编码" width="200">
          <template #default="{ row }"><code class="code-text">{{ row.code }}</code></template>
        </el-table-column>
        <el-table-column prop="label" label="标签名称" min-width="160" />
        <el-table-column label="NEW 角标" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.isNew" type="danger" size="small" effect="dark">NEW</el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="group-card" shadow="never">
      <template #header>
        <div class="group-head">
          <span class="group-title">热门项目标签</span>
          <span class="group-hint">前台筛选区·多选 checkbox + 列表紫色标签</span>
        </div>
      </template>
      <el-table :data="projectTags" v-loading="loading" size="default" style="width: 100%">
        <el-table-column prop="sortOrder" label="排序" width="80" align="center" />
        <el-table-column prop="code" label="编码" width="220">
          <template #default="{ row }"><code class="code-text">{{ row.code }}</code></template>
        </el-table-column>
        <el-table-column prop="label" label="标签名称" min-width="160" />
        <el-table-column label="NEW 角标" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.isNew" type="danger" size="small" effect="dark">NEW</el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="formVisible" :title="editingId ? `编辑标签 #${editingId}` : '新增标签'"
      width="480px" destroy-on-close
    >
      <el-form :model="form" label-width="88px">
        <el-form-item label="标签名称" required>
          <el-input v-model="form.label" placeholder="如: 城市更新 / 大型国企项目" maxlength="64" />
        </el-form-item>
        <el-form-item label="标签编码" required>
          <el-input v-model="form.code" placeholder="如: hot_field_urban / hot_proj_private" maxlength="64" :disabled="!!editingId" />
          <div class="field-hint">唯一编码, 建议前缀 hot_field_ / hot_proj_</div>
        </el-form-item>
        <el-form-item label="所属分组">
          <el-radio-group v-model="form.kind">
            <el-radio value="hot_field">热点领域(HOT)</el-radio>
            <el-radio value="hot_project">热门项目</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :step="10" />
        </el-form-item>
        <el-form-item label="NEW 角标">
          <el-switch v-model="form.is_new" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Refresh } from "@element-plus/icons-vue";
import {
  listTagDefsAdmin,
  createTagDef,
  updateTagDef,
  deleteTagDef,
  type OpportunityTagDefAdmin,
} from "@/api/opportunityAdmin";

const loading = ref(false);
const tags = ref<OpportunityTagDefAdmin[]>([]);

const fieldTags = computed(() => tags.value.filter((t) => t.kind === "hot_field"));
const projectTags = computed(() => tags.value.filter((t) => t.kind === "hot_project"));

const formVisible = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const form = reactive({
  label: "",
  code: "",
  kind: "hot_project",
  sort_order: 10,
  is_new: true,
});

async function loadTags() {
  loading.value = true;
  try {
    const res: any = await listTagDefsAdmin();
    tags.value = res?.data || [];
  } catch {
    tags.value = [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  Object.assign(form, { label: "", code: "", kind: "hot_project", sort_order: 10, is_new: true });
  formVisible.value = true;
}

function openEdit(row: OpportunityTagDefAdmin) {
  editingId.value = row.id;
  Object.assign(form, {
    label: row.label,
    code: row.code,
    kind: row.kind,
    sort_order: row.sortOrder ?? 0,
    is_new: row.isNew,
  });
  formVisible.value = true;
}

async function saveForm() {
  if (!form.label.trim() || !form.code.trim()) {
    ElMessage.warning("标签名称与编码为必填项");
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await updateTagDef(editingId.value, {
        label: form.label.trim(),
        kind: form.kind,
        is_new: form.is_new,
        sort_order: form.sort_order,
      });
      ElMessage.success("标签已更新");
    } else {
      await createTagDef({
        label: form.label.trim(),
        code: form.code.trim(),
        kind: form.kind,
        is_new: form.is_new,
        sort_order: form.sort_order,
      });
      ElMessage.success("标签已创建");
    }
    formVisible.value = false;
    loadTags();
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false;
  }
}

async function confirmDelete(row: OpportunityTagDefAdmin) {
  try {
    await ElMessageBox.confirm(
      `确认删除标签「${row.label}」? 其与商机的关联将一并解除。`,
      "删除确认",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
    await deleteTagDef(row.id);
    ElMessage.success("已删除");
    loadTags();
  } catch { /* 取消或失败 */ }
}

onMounted(loadTags);
</script>

<style scoped>
.tag-page { display: flex; flex-direction: column; gap: 14px; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.page-title { font-size: 20px; font-weight: 700; color: var(--ssm-text-main); margin: 0; }
.page-desc { font-size: 13px; color: var(--ssm-text-secondary); margin: 4px 0 0; }
.header-actions { display: flex; gap: 10px; }
.group-card { border-radius: var(--ssm-radius); }
.group-head { display: flex; align-items: center; gap: 10px; }
.group-title { font-weight: 700; color: var(--ssm-text-main); font-size: 15px; }
.hot-badge {
  display: inline-block; background: #ff4d4f; color: #fff; font-size: 10px; font-weight: 700;
  padding: 1px 5px; border-radius: 4px; letter-spacing: 0.5px;
}
.group-hint { font-size: 12px; color: var(--ssm-text-secondary); }
.code-text { font-family: 'Consolas', monospace; font-size: 12px; color: var(--ssm-text-regular); }
.muted { color: var(--ssm-text-secondary); }
.field-hint { font-size: 12px; color: var(--ssm-text-secondary); margin-top: 4px; line-height: 1.4; }
</style>
