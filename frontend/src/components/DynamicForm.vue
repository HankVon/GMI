<!--
  ★ DynamicForm.vue ★
  动态表单组件 — 按服务端元数据渲染表单，前端即时校验 + 服务端权威校验

  使用方式：
    <DynamicForm
      entity-type="project"
      :model-value="formData"
      @update:model-value="handleUpdate"
      mode="edit"
    />
-->
<template>
  <el-form ref="formRef" :model="localModel" label-width="140px" label-position="right">
    <!-- 按 group_name 分组 -->
    <template v-for="group in groupedFields" :key="group.name">
      <el-divider v-if="group.name" content-position="left">
        {{ group.name }}
      </el-divider>

      <template v-for="field in group.fields" :key="field.field_key">
        <!-- 文本 -->
        <el-form-item
          v-if="field.data_type === 'text' || field.data_type === 'textarea'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-input
            v-if="field.data_type === 'text'"
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: string) => setFieldValue(field.field_key, v)"
            :placeholder="field.placeholder || `请输入${field.display_name}`"
            :disabled="!canEdit(field)"
            maxlength="512"
          />
          <el-input
            v-else
            type="textarea"
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: string) => setFieldValue(field.field_key, v)"
            :placeholder="field.placeholder || `请输入${field.display_name}`"
            :disabled="!canEdit(field)"
            :rows="4"
          />
          <template v-if="field.help_text" #extra>
            <span class="help-text">{{ field.help_text }}</span>
          </template>
        </el-form-item>

        <!-- 数字 -->
        <el-form-item
          v-else-if="field.data_type === 'number'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-input-number
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: number) => setFieldValue(field.field_key, v)"
            :placeholder="field.placeholder"
            :disabled="!canEdit(field)"
            :min="field.validation_rules?.min"
            :max="field.validation_rules?.max"
            style="width: 100%"
          />
        </el-form-item>

        <!-- 金额 -->
        <el-form-item
          v-else-if="field.data_type === 'money'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-input-number
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: number) => setFieldValue(field.field_key, v)"
            :placeholder="field.placeholder"
            :disabled="!canEdit(field)"
            :min="0"
            :precision="2"
            :step="10000"
            style="width: 100%"
          >
            <template #prefix>¥</template>
          </el-input-number>
        </el-form-item>

        <!-- 日期 -->
        <el-form-item
          v-else-if="field.data_type === 'date'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-date-picker
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: string) => setFieldValue(field.field_key, v)"
            type="date"
            value-format="YYYY-MM-DD"
            :placeholder="field.placeholder || '选择日期'"
            :disabled="!canEdit(field)"
            style="width: 100%"
          />
        </el-form-item>

        <!-- 单选 -->
        <el-form-item
          v-else-if="field.data_type === 'select'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-select
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: string) => setFieldValue(field.field_key, v)"
            :placeholder="field.placeholder || '请选择'"
            :disabled="!canEdit(field)"
            style="width: 100%"
            clearable
          >
            <el-option
              v-for="opt in field.options || []"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            >
              <el-tag v-if="opt.color" :color="opt.color" size="small" effect="dark">
                {{ opt.label }}
              </el-tag>
              <span v-else>{{ opt.label }}</span>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- 多选 -->
        <el-form-item
          v-else-if="field.data_type === 'multi_select'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-select
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: string[]) => setFieldValue(field.field_key, v)"
            multiple
            :placeholder="field.placeholder || '请选择'"
            :disabled="!canEdit(field)"
            style="width: 100%"
            clearable
          >
            <el-option
              v-for="opt in field.options || []"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            >
              <el-tag v-if="opt.color" :color="opt.color" size="small" effect="dark">
                {{ opt.label }}
              </el-tag>
              <span v-else>{{ opt.label }}</span>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- 开关 -->
        <el-form-item
          v-else-if="field.data_type === 'switch'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-switch
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: boolean) => setFieldValue(field.field_key, v)"
            :disabled="!canEdit(field)"
          />
        </el-form-item>

        <!-- 关联实体 -->
        <el-form-item
          v-else-if="field.data_type === 'entity_ref'"
          :label="field.display_name"
          :prop="field.field_key"
          :rules="canEdit(field) && field.is_required ? requiredRule(field.display_name) : []"
        >
          <el-select
            :model-value="getFieldValue(field.field_key)"
            @update:model-value="(v: any) => setFieldValue(field.field_key, v)"
            :placeholder="field.placeholder || '请选择'"
            :disabled="!canEdit(field)"
            style="width: 100%"
            filterable
            clearable
          >
            <el-option
              v-for="opt in field.options || []"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
      </template>
    </template>
  </el-form>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { useUserStore } from "@/stores/user";
import api from "@/api";

interface FieldMeta {
  field_key: string;
  display_name: string;
  data_type: string;
  is_required: boolean;
  validation_rules?: Record<string, any>;
  field_permissions?: Record<string, string[]>;
  sort_order: number;
  group_name?: string;
  placeholder?: string;
  help_text?: string;
  options?: Array<{ value: string; label: string; color?: string }>;
}

const props = defineProps<{
  entityType: string;          // 实体类型: project/person/project_member
  modelValue: Record<string, any>;  // 包含 ext_attrs 的实体数据
  mode?: "view" | "edit";       // 视图/编辑模式
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: Record<string, any>): void;
}>();

const userStore = useUserStore();
const fields = ref<FieldMeta[]>([]);
const localModel = ref<Record<string, any>>({});
const formRef = ref<any>(null);

const requiredRule = (label: string) => [
  { required: true, message: `「${label}」为必填项`, trigger: "blur" },
];

// 按 group 分组
const groupedFields = computed(() => {
  const groups: Record<string, FieldMeta[]> = {};
  for (const f of fields.value) {
    const g = f.group_name || "";
    if (!groups[g]) groups[g] = [];
    groups[g].push(f);
  }
  return Object.entries(groups)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([name, fds]) => ({
      name,
      fields: fds.sort((a, b) => a.sort_order - b.sort_order),
    }));
});

function getFieldValue(key: string): any {
  return localModel.value[key] ?? undefined;
}

let internalUpdating = false;
function setFieldValue(key: string, val: any): void {
  // 直接修改本地值，避免每次输入重建对象触发 watch 覆盖导致无法输入/回退
  internalUpdating = true;
  localModel.value = {
    ...localModel.value,
    [key]: val,
  };
  emit("update:modelValue", { ...localModel.value });
  // 稍后重置标志，避免吞掉下一次外部赋值
  setTimeout(() => { internalUpdating = false; }, 0);
}

function canEdit(field: FieldMeta): boolean {
  if (props.mode === "view") return false;
  const perms = field.field_permissions || {};
  const editRoles = perms.edit || [];
  if (editRoles.length === 0) return true;
  return userStore.hasAnyRole(...editRoles);
}

function isEmptyValue(v: any): boolean {
  return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
}

// 必填校验：供父组件保存前调用，拦截未填写的必填项。
// 优先走 el-form 原生校验(精确标红)，不可用时回退手动校验。
async function validate(): Promise<boolean> {
  if (formRef.value) {
    try {
      await formRef.value.validate();
      return true;
    } catch {
      return false; // el-form 已自动显示字段级错误提示
    }
  }
  // 兜底：formRef 未就绪时手动校验
  const missing: string[] = [];
  for (const f of fields.value) {
    if (!f.is_required) continue;
    if (!canEdit(f)) continue;
    if (isEmptyValue(localModel.value[f.field_key])) {
      missing.push(f.display_name);
    }
  }
  if (missing.length) {
    ElMessage.error(`以下必填项未填写：${missing.join("、")}`);
    return false;
  }
  return true;
}

defineExpose({ validate, formRef });

async function loadFormConfig() {
  try {
    const res: any = await api.get(
      `/dynamic/${props.entityType}/form-config?mode=${props.mode || "edit"}`
    );
    fields.value = res.fields || [];
  } catch {
    fields.value = [];
  }
}

// 初始化
onMounted(() => {
  loadFormConfig();
  localModel.value = { ...props.modelValue };
  if (props.modelValue.ext_attrs) {
    Object.assign(localModel.value, props.modelValue.ext_attrs);
  }
});

watch(
  () => props.modelValue,
  (val) => {
    // 由内部输入引起的变化跳过，避免把输入内容回滚，导致无法修改/回退字符
    if (internalUpdating) return;
    localModel.value = { ...val };
    if (val.ext_attrs) {
      Object.assign(localModel.value, val.ext_attrs);
    }
  },
  { deep: true }
);
</script>

<style scoped>
.help-text {
  font-size: 12px;
  color: #909399;
}
</style>
