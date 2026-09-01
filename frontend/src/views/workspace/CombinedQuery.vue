<template>
  <div class="combined-query-page">
    <el-page-header title="返回" @back="$router.back()">
      <template #content>
        <span>组合查询</span>
      </template>
    </el-page-header>

    <!-- 条件构建器 -->
    <el-card class="builder-card" shadow="never">
      <template #header>
        <div class="section-header">
          <span class="section-title">条件构建器</span>
          <span class="section-desc">多维度「加入筛选」，条件间为 AND 关系</span>
        </div>
      </template>

      <div class="builder-row">
        <el-select v-model="dimension" placeholder="选择条件维度" style="width: 180px" @change="onDimChange">
          <el-option label="单位名称（模糊）" value="company_name" />
          <el-option label="省份" value="province" />
          <el-option label="城市" value="city" />
          <el-option label="单位类型" value="company_type" />
          <el-option label="资质大类" value="qual_category" />
          <el-option label="资质等级" value="qual_level" />
          <el-option label="有中标记录" value="bid_exists" />
          <el-option label="有诚信记录" value="credit_exists" />
          <el-option label="人员姓名" value="person_name" />
        </el-select>

        <el-input
          v-if="isTextDim"
          v-model="dimValue"
          placeholder="输入关键词"
          clearable
          style="width: 260px"
          @keyup.enter="addCondition"
        />
        <el-select
          v-else-if="isSelectDim"
          v-model="dimValue"
          placeholder="选择"
          clearable
          filterable
          style="width: 240px"
        >
          <el-option v-for="o in dimOptions" :key="o" :label="o" :value="o" />
        </el-select>

        <el-button type="primary" @click="addCondition">加入筛选</el-button>
        <el-button v-if="conditions.length" @click="clearConditions">一键清除</el-button>
      </div>

      <!-- 已加入条件 -->
      <div v-if="conditions.length" class="conditions-bar">
        <el-tag
          v-for="(c, i) in conditions"
          :key="i"
          closable
          type="info"
          effect="plain"
          class="condition-tag"
          @close="removeCondition(i)"
        >{{ c.label }}: {{ c.value }}</el-tag>
        <el-button size="small" type="primary" :loading="loading" @click="doSearch">查看检索结果</el-button>
      </div>
    </el-card>

    <!-- 结果 -->
    <el-card class="result-card" shadow="never">
      <template #header>
        <div class="section-header">
          <span class="section-title">检索结果</span>
          <span v-if="searched" class="section-desc">共 {{ total }} 家单位</span>
        </div>
      </template>

      <el-table v-if="items.length" :data="items" size="small" border @row-click="goCompany">
        <el-table-column prop="name" label="单位名称" min-width="240">
          <template #default="{ row }">
            <span class="link-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="province" label="省份" width="90" />
        <el-table-column prop="city" label="城市" width="100" />
        <el-table-column prop="company_type" label="类型" width="120" />
        <el-table-column prop="qual_count" label="资质数" width="80" />
        <el-table-column prop="bid_count" label="中标数" width="80" />
        <el-table-column prop="credit_count" label="诚信记录" width="90" />
        <el-table-column prop="person_count" label="人员数" width="80" />
        <el-table-column width="36" align="right">
          <template #default><el-icon class="row-arrow"><ArrowRight /></el-icon></template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="searched" description="无符合条件的结果" :image-size="80" />
      <el-empty v-else description="选择条件并点击「查看检索结果」" :image-size="80" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "CombinedQuery" });
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowRight } from "@element-plus/icons-vue";
import api from "@/api";

const router = useRouter();
const dimension = ref("");
const dimValue = ref("");
const conditions = ref<any[]>([]);
const optionsData = ref<Record<string, string[]>>({});
const items = ref<any[]>([]);
const total = ref(0);
const searched = ref(false);
const loading = ref(false);

const DIM_LABELS: Record<string, string> = {
  company_name: "单位名称", province: "省份", city: "城市", company_type: "单位类型",
  qual_category: "资质大类", qual_level: "资质等级", bid_exists: "有中标记录",
  credit_exists: "有诚信记录", person_name: "人员姓名",
};
const TEXT_DIMS = new Set(["company_name", "person_name"]);
const SELECT_DIMS = new Set(["province", "city", "company_type", "qual_category", "qual_level"]);

const isTextDim = computed(() => TEXT_DIMS.has(dimension.value));
const isSelectDim = computed(() => SELECT_DIMS.has(dimension.value));
const dimOptions = computed(() => optionsData.value[dimension.value] || []);

function onDimChange() {
  dimValue.value = "";
}

async function loadOptions() {
  try {
    const res: any = await api.get("/combined-query/options");
    optionsData.value = res?.data || {};
  } catch { /* ignore */ }
}

function addCondition() {
  if (!dimension.value) {
    ElMessage.warning("请先选择条件维度");
    return;
  }
  // 布尔维度直接加入
  if (dimension.value === "bid_exists" || dimension.value === "credit_exists") {
    if (conditions.value.some((c) => c.key === dimension.value)) {
      ElMessage.info("该条件已加入");
      return;
    }
    conditions.value.push({ key: dimension.value, label: DIM_LABELS[dimension.value], value: "是" });
    dimension.value = "";
    return;
  }
  if (!dimValue.value) {
    ElMessage.warning("请输入/选择条件值");
    return;
  }
  conditions.value.push({ key: dimension.value, label: DIM_LABELS[dimension.value], value: dimValue.value });
  dimension.value = "";
  dimValue.value = "";
}

function removeCondition(i: number) {
  conditions.value.splice(i, 1);
}

function clearConditions() {
  conditions.value = [];
  searched.value = false;
  items.value = [];
}

async function doSearch() {
  if (!conditions.value.length) {
    ElMessage.warning("请先加入至少一个条件");
    return;
  }
  loading.value = true;
  try {
    const cond: Record<string, any> = {};
    for (const c of conditions.value) {
      if (c.key === "bid_exists" || c.key === "credit_exists") {
        cond[c.key] = true;
      } else {
        cond[c.key] = c.value;
      }
    }
    const res: any = await api.get("/combined-query/search", {
      params: { conditions: JSON.stringify(cond), page_size: 100 },
    });
    items.value = res?.data?.items || [];
    total.value = res?.data?.total || 0;
    searched.value = true;
  } finally {
    loading.value = false;
  }
}

function goCompany(row: any) {
  router.push(`/workspace/companies/${row.id}`);
}

loadOptions();
</script>

<style scoped>
.combined-query-page {
  padding: 18px;
  max-width: 1280px;
}
.builder-card { margin-top: 16px; }
.result-card { margin-top: 16px; }
.section-header { display: flex; align-items: baseline; gap: 10px; }
.section-title { font-size: 15px; font-weight: 600; }
.section-desc { font-size: 12px; color: #909399; }
.builder-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.conditions-bar {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: #f7f9fc;
  border: 1px dashed #c9d4e4;
  border-radius: 6px;
}
.condition-tag { font-size: 12px; }
.link-name { color: #2979ff; cursor: pointer; }
.row-arrow { color: #c0c4cc; }
</style>
