<template>
  <el-card>
    <template #header>
      <div class="card-hd"><span>选项集管理</span><el-button type="primary" size="small" @click="showCreate=true">新建</el-button></div>
    </template>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="点击选项集行，在其下方展开/收起该选项集的选项项管理"
      style="margin-bottom:12px"
    />

    <el-table
      :data="sets"
      stripe
      row-key="id"
      highlight-current-row
      :row-class-name="setRowClass"
      :expand-row-keys="expandedKeys"
      @row-click="toggleExpand"
      @expand-change="onExpandChange"
    >
      <!-- 展开列(手风琴: 点击行展开/收起该选项集的选项项) -->
      <el-table-column type="expand" width="44">
        <template #default="{ row }">
          <div class="expand-item">
            <div class="item-hd">
              <span>{{ row.name }} — 选项项（{{ items.length }}）</span>
              <el-button type="primary" size="small" @click.stop="showAddItem=true">添加选项</el-button>
            </div>
            <el-table :data="items" stripe style="margin-top:8px">
              <el-table-column prop="sort_order" label="排序" width="80" />
              <el-table-column prop="value" label="值" width="160" />
              <el-table-column prop="label" label="显示标签" min-width="140">
                <template #default="{row: it}">
                  <span class="tag-demo" :style="it.color ? { background: it.color, color: '#fff' } : {}">
                    {{ it.label }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="颜色" width="110">
                <template #default="{row: it}">
                  <span class="color-dot" :style="{ background: it.color || '#909399' }" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140">
                <template #default="{row: it}">
                  <el-button type="primary" size="small" @click.stop="openEditItem(it)">编辑</el-button>
                  <el-button text type="danger" size="small" @click.stop="delItem(it.value)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="编码" width="160">
        <template #default="{row}">
          <span class="link-text">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="160">
        <template #default="{row}">
          <span class="link-text strong">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="80">
        <template #default="{row}">
          <el-button text type="danger" size="small" @click.stop="delSet(row.code)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建选项集 -->
    <el-dialog v-model="showCreate" title="新建选项集" width="400px">
      <el-form ref="setFormRef" :model="newSet" :rules="setRules">
        <el-form-item label="编码" prop="code"><el-input v-model="newSet.code" /></el-form-item>
        <el-form-item label="名称" prop="name"><el-input v-model="newSet.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="newSet.description" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showCreate=false">取消</el-button><el-button type="primary" @click="createSet">确定</el-button></template>
    </el-dialog>

    <!-- 添加选项 -->
    <el-dialog v-model="showAddItem" title="添加选项" width="420px">
      <el-form ref="itemFormRef" :model="newItem" :rules="itemRules">
        <el-form-item label="值" prop="value"><el-input v-model="newItem.value" /></el-form-item>
        <el-form-item label="标签" prop="label"><el-input v-model="newItem.label" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="newItem.sort_order" :min="0" /></el-form-item>
        <el-form-item label="颜色">
          <div class="color-field">
            <el-color-picker v-model="newItem.color" size="small" />
            <span class="color-hint">（用于下拉框标签着色，可不填）</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showAddItem=false">取消</el-button><el-button type="primary" @click="addItem">确定</el-button></template>
    </el-dialog>

    <!-- 编辑选项 -->
    <el-dialog v-model="showEditItem" title="编辑选项" width="420px">
      <el-form ref="editItemFormRef" :model="editItemForm" :rules="itemRules">
        <el-form-item label="值"><el-input :model-value="editItemForm.value" disabled /></el-form-item>
        <el-form-item label="标签" prop="label"><el-input v-model="editItemForm.label" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="editItemForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="颜色">
          <div class="color-field">
            <el-color-picker v-model="editItemForm.color" size="small" />
            <span class="color-hint">（用于下拉框标签着色，可不填）</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showEditItem=false">取消</el-button><el-button type="primary" @click="saveEditItem">确定</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import api from "@/api";

const sets = ref<any[]>([]);
const items = ref<any[]>([]);
const curSet = ref<any>(null);
const expandedKeys = ref<any[]>([]);
const showCreate = ref(false);
const showAddItem = ref(false);
const showEditItem = ref(false);
const newSet = ref({ code: "", name: "", description: "" });
const newItem = ref({ value: "", label: "", sort_order: 0, color: undefined as string | undefined });
const editItemForm = ref({ value: "", label: "", sort_order: 0, color: undefined as string | undefined });
const editingValue = ref("");

function setRowClass({ row }: { row: any }) {
  return curSet.value && curSet.value.code === row.code ? "cur-set-row" : "";
}

async function loadSets() {
  const res: any = await api.get("/option-sets", { params: { page_size: 100 } });
  sets.value = res.items || [];
}

// 点击行: 手风琴切换 — 再次点击当前行收起, 点击其他行切换展开
function toggleExpand(row: any) {
  if (expandedKeys.value.length && expandedKeys.value[0] === row.id) {
    expandedKeys.value = [];
    curSet.value = null;
    items.value = [];
    return;
  }
  loadItems(row);
}

// el-table 展开变化回调: expandedRows 为当前展开行(单选受控)
function onExpandChange(_row: any, expandedRows: any[]) {
  if (expandedRows.length === 0) {
    curSet.value = null;
    items.value = [];
    return;
  }
  const current = expandedRows[0];
  if (curSet.value && curSet.value.code === current.code) return;
  loadItems(current);
}

async function loadItems(row: any) {
  const res: any = await api.get(`/option-sets/${row.code}/items`);
  items.value = res.items || [];
  curSet.value = row;
  expandedKeys.value = [row.id];
}
const setFormRef = ref<any>(null);
const itemFormRef = ref<any>(null);
const editItemFormRef = ref<any>(null);
const setRules = {
  code: [{ required: true, message: "编码为必填项", trigger: "blur" }],
  name: [{ required: true, message: "名称为必填项", trigger: "blur" }],
};
const itemRules = {
  value: [{ required: true, message: "值为必填项", trigger: "blur" }],
  label: [{ required: true, message: "标签为必填项", trigger: "blur" }],
};
async function createSet() {
  try { await setFormRef.value.validate(); } catch { return; }
  await api.post(`/option-sets`, newSet.value);
  ElMessage.success("已创建"); showCreate.value = false; loadSets();
}
async function addItem() {
  if (!curSet.value) return;
  try { await itemFormRef.value.validate(); } catch { return; }
  await api.post(`/option-sets/${curSet.value.code}/items`, newItem.value);
  ElMessage.success("已添加"); showAddItem.value = false;
  newItem.value = { value: "", label: "", sort_order: 0, color: undefined };
  loadItems(curSet.value);
}
async function openEditItem(row: any) {
  editingValue.value = row.value;
  editItemForm.value = { value: row.value, label: row.label, sort_order: row.sort_order, color: row.color };
  showEditItem.value = true;
}
async function saveEditItem() {
  if (!curSet.value) return;
  try { await editItemFormRef.value.validate(); } catch { return; }
  await api.put(`/option-sets/${curSet.value.code}/items/${editingValue.value}`, {
    label: editItemForm.value.label,
    sort_order: editItemForm.value.sort_order,
    color: editItemForm.value.color || null,
  });
  ElMessage.success("已保存"); showEditItem.value = false;
  loadItems(curSet.value);
}
async function delSet(code: string) {
  await api.delete(`/option-sets/${code}`); ElMessage.success("已删除");
  if (curSet.value && curSet.value.code === code) { curSet.value = null; items.value = []; expandedKeys.value = []; }
  loadSets();
}
async function delItem(val: string) {
  if (!curSet.value) return;
  await api.delete(`/option-sets/${curSet.value.code}/items/${val}`);
  ElMessage.success("已删除"); loadItems(curSet.value);
}
onMounted(loadSets);
</script>

<style scoped>
.card-hd { display: flex; justify-content: space-between; align-items: center; }
.item-hd { display: flex; justify-content: space-between; align-items: center; margin: 0; }
.link-text { color: #2979ff; cursor: pointer; }
.link-text.strong { font-weight: 600; }
.tag-demo { display: inline-block; padding: 0 8px; border-radius: 4px; line-height: 22px; font-size: 12px; }
.color-dot { display: inline-block; width: 16px; height: 16px; border-radius: 50%; vertical-align: middle; border: 1px solid #dcdfe6; }
.color-field { display: flex; align-items: center; gap: 8px; }
.color-hint { font-size: 12px; color: #909399; }
/* 展开区容器: 背景区分 + 内边距 */
.expand-item {
  padding: 8px 16px 8px 40px;
  background: #fafafa;
}
:deep(.cur-set-row) {
  background-color: #ecf5ff !important;
}
:deep(.cur-set-row:hover) {
  background-color: #ecf5ff !important;
}
:deep(.el-table__row) {
  cursor: pointer;
}
/* 展开箭头: 展开时向下旋转, 增强可展开提示 */
:deep(.el-table__expand-icon) {
  transition: transform 0.25s;
}
:deep(.el-table__expand-icon--expanded) {
  transform: rotate(90deg);
}
</style>
