<!-- 省-市-县三级地域级联选择器(仅四川/西藏/新疆) -->
<template>
  <div class="cascader-root" :style="{ width: width, minWidth: width }">
    <el-cascader
      v-model="value"
      :options="options"
      :props="cascaderProps"
      :placeholder="placeholder"
      clearable
      style="width: 100%"
      @change="onChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import api from "@/api";

const props = withDefaults(defineProps<{ modelValue?: string[]; width?: string; placeholder?: string }>(),
  { width: "220px", placeholder: "省 / 市 / 县" });
const emit = defineEmits<{ (e: "update:modelValue", v: string[]): void; (e: "change", v: { province: string; city: string; county: string }): void }>();

const value = ref<string[]>(props.modelValue || []);
const options = ref<any[]>([]);

// checkStrictly=true: 允许只选省/市(不强制到县)
const cascaderProps = { value: "value", label: "label", children: "children", checkStrictly: true };

async function loadTree() {
  try {
    const res: any = await api.get("/intent/region-tree");
    options.value = res.items || [];
  } catch {
    // 降级: 内置三级树(仅川藏新, 与后端 target_region_tree 对齐)
    options.value = [
      { value: "四川", label: "四川省", children: [
        { value: "成都", label: "成都市", children: [
          { value: "锦江", label: "锦江" }, { value: "青羊", label: "青羊" },
          { value: "金牛", label: "金牛" }, { value: "武侯", label: "武侯" },
          { value: "成华", label: "成华" }, { value: "双流", label: "双流" },
        ]},
        { value: "凉山", label: "凉山彝族自治州", children: [
          { value: "西昌", label: "西昌" }, { value: "喜德", label: "喜德" },
          { value: "雷波", label: "雷波" }, { value: "冕宁", label: "冕宁" },
        ]},
        { value: "阿坝", label: "阿坝藏族羌族自治州", children: [
          { value: "茂县", label: "茂县" }, { value: "汶川", label: "汶川" },
        ]},
      ]},
      { value: "西藏", label: "西藏自治区", children: [
        { value: "日喀则", label: "日喀则市", children: [
          { value: "定日", label: "定日" }, { value: "南木林", label: "南木林" },
        ]},
        { value: "阿里", label: "阿里地区", children: [
          { value: "普兰", label: "普兰" }, { value: "噶尔", label: "噶尔" },
        ]},
        { value: "山南", label: "山南市", children: [
          { value: "洛扎", label: "洛扎" }, { value: "隆子", label: "隆子" },
        ]},
      ]},
      { value: "新疆", label: "新疆维吾尔自治区", children: [
        { value: "喀什", label: "喀什地区", children: [
          { value: "疏附", label: "疏附" }, { value: "疏勒", label: "疏勒" },
        ]},
        { value: "昌吉", label: "昌吉回族自治州", children: [
          { value: "昌吉", label: "昌吉" }, { value: "阜康", label: "阜康" },
        ]},
      ]},
    ];
  }
}

function onChange(v: any) {
  const arr = Array.isArray(v) ? v : [];
  emit("update:modelValue", arr);
  emit("change", {
    province: arr[0] || "",
    city: arr[1] || "",
    county: arr[2] || "",
  });
}

onMounted(loadTree);
</script>

<style scoped>
/* 宽度由外层 .cascader-root 承载(遵循 width prop), 内部 el-cascader 撑满 100% */
.cascader-root {
  display: inline-block;
  vertical-align: middle;
}
/* 强制 el-cascader 宽度与 prop 一致, 避免 Element Plus 默认 300px 干扰 */
::deep(.el-cascader) {
  width: 100% !important;
}
::deep(.el-cascader .el-cascader__wrapper),
::deep(.el-cascader .el-input) {
  width: 100% !important;
}
::deep(.el-cascader .el-input__wrapper) {
  width: 100% !important;
}
/* 高度/字体与同页 el-select/el-input(default 尺寸)保持一致 */
::deep(.el-cascader) {
  height: 32px !important;
  line-height: 32px;
  font-size: var(--el-font-size-base, 14px);
}
::deep(.el-cascader .el-input__inner) {
  font-size: var(--el-font-size-base, 14px);
  height: 30px;
  line-height: 30px;
}
</style>
