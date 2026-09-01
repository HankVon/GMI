<template>
  <div class="psq">
    <!-- 筛选区 -->
    <div class="sq-filters">
      <div class="sq-row">
        <span class="sq-label">{{ mode === "manager" ? "项目经理姓名" : "人员姓名" }}：</span>
        <input
          v-model="filter.keyword"
          class="sq-text"
          :placeholder="mode === 'manager' ? '如 张 / 王' : '输入人员姓名关键词'"
          @keyup.enter="search(1)"
        />
        <span class="sq-label sq-label-inline">地区：</span>
        <el-select
          v-model="filter.province"
          placeholder="选择省份"
          clearable
          style="width: 200px"
          @change="search(1)"
        >
          <el-option v-for="p in provinces" :key="p" :value="p" :label="p" />
        </el-select>
        <button class="sq-go" :disabled="loading" @click="search(1)">查询</button>
      </div>
      <div class="sq-row">
        <span class="sq-label">职位：</span>
        <input
          v-model="filter.position"
          class="sq-text"
          :placeholder="mode === 'manager' ? '默认：项目经理' : '如 总工 / 工程师 / 注册'"
          @keyup.enter="search(1)"
        />
        <span class="sq-label sq-label-inline">所属单位：</span>
        <input
          v-model="filter.company"
          class="sq-text"
          placeholder="单位名称关键字，如 地质"
          @keyup.enter="search(1)"
        />
      </div>
    </div>

    <!-- 结果摘要 -->
    <div class="sq-summary">
      <span class="sq-summary-left">
        共找到 <b>{{ total }}</b> 位符合条件的 <b class="text-brand">{{ typeLabel }}</b>。
      </span>
    </div>

    <!-- 结果列表 -->
    <div v-loading="loading" class="sq-list">
      <div
        v-for="(row, idx) in list"
        :key="row.id"
        class="sq-result"
        @click="open(row)"
      >
        <div class="sq-idx">{{ idx + 1 + (page - 1) * pageSize }}</div>
        <div class="sq-main">
          <div class="sq-name-row">
            <span class="sq-name" v-html="highlight(row.name)"></span>
            <el-tag v-if="row.company_name" size="small" effect="plain">{{ row.company_name }}</el-tag>
            <el-tag
              v-if="row.status"
              size="small"
              :type="row.status === 'active' ? 'success' : 'info'"
              effect="dark"
            >{{ row.status === "active" ? "在职" : "离职" }}</el-tag>
          </div>
          <div class="sq-stats">
            <span class="sq-stat"><span class="sq-stat-label">职位：</span><b>{{ row.position || "—" }}</b></span>
            <span class="sq-stat"><span class="sq-stat-label">地区：</span><b>{{ regionOf(row) || "—" }}</b></span>
            <span class="sq-stat"><span class="sq-stat-label">参与项目：</span>{{ row.related_projects || "—" }}</span>
            <span class="sq-stat"><span class="sq-stat-label">最近项目：</span>{{ row.latest_project_time ? fmtDate(row.latest_project_time) : "—" }}</span>
          </div>
        </div>
        <div class="sq-row-actions">
          <el-button class="sq-act-btn" @click.stop="open(row)">人员主页</el-button>
        </div>
      </div>
      <div v-if="!loading && list.length === 0 && searched" class="sq-empty">
        没有找到匹配的人员，请调整筛选条件后重试。
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="sq-pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, jumper"
        background
        @current-change="search"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import api from "@/api";
import { useNavBase } from "@/utils/navBase";

const props = defineProps<{ mode?: "person" | "manager" }>();
const router = useRouter();
const { navTo } = useNavBase();

const typeLabel = computed(() => (props.mode === "manager" ? "项目经理" : "人员"));

const provinces = [
  "北京", "天津", "上海", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
  "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
  "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
];

const filter = reactive({
  keyword: "",
  province: "",
  position: props.mode === "manager" ? "项目经理" : "",
  company: "",
});

const list = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const searched = ref(false);
const lastKeyword = ref("");

async function search(p: number = page.value) {
  page.value = p;
  loading.value = true;
  lastKeyword.value = filter.keyword || "";
  try {
    const params: Record<string, any> = {
      page: p,
      page_size: pageSize,
      keyword: filter.keyword || undefined,
      province: filter.province || undefined,
      position: filter.position || undefined,
      company_keyword: filter.company || undefined,
    };
    Object.keys(params).forEach((k) => params[k] === undefined && delete params[k]);
    const res: any = await api.get("/persons", { params });
    list.value = res.items || [];
    total.value = res.total || 0;
    searched.value = true;
  } catch {
    list.value = [];
    total.value = 0;
    ElMessage.error("查询失败，请稍后重试");
  } finally {
    loading.value = false;
  }
}

function regionOf(row: any): string {
  return [row.company_province, row.company_city].filter(Boolean).join("·") || "";
}

function fmtDate(s: string): string {
  return String(s || "").slice(0, 10);
}

function open(row: any) {
  if (!row?.id) return;
  // navTo 会按当前上下文(base)自动拼接前缀, 这里传相对路径即可
  router.push(navTo(`/persons/${row.id}`));
}

/* 关键词高亮(姓名) */
function escapeHtml(s: string): string {
  return String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" } as any)[c]
  );
}
function highlight(raw: string): string {
  const kw = String(lastKeyword.value || "").trim();
  const safe = escapeHtml(raw);
  if (!kw) return safe;
  try {
    const re = new RegExp(escapeHtml(kw).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    return safe.replace(re, (m) => `<span class="sq-hlkw">${m}</span>`);
  } catch {
    return safe;
  }
}

onMounted(() => search(1));
</script>

<style scoped>
.psq { padding: 0; }
.sq-filters {
  background: #fff;
  border: 1px solid var(--site-panel-border);
  border-top: none;
  padding: 14px 18px 4px;
}
.sq-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  padding: 10px 0;
  border-bottom: 1px dashed var(--site-hairline);
  gap: 10px;
}
.sq-row:last-child { border-bottom: none; }
.sq-label {
  flex: 0 0 80px;
  font-size: 14px;
  color: var(--site-text-dim);
  text-align: right;
  padding-right: 8px;
  font-weight: 500;
}
.sq-label-inline { margin-left: 18px; }
.sq-text {
  flex: 1 1 220px;
  max-width: 320px;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 14px;
}
.sq-text:focus { outline: none; border-color: var(--site-brand); }
.sq-go {
  background: var(--site-brand);
  color: #fff;
  border: none;
  padding: 7px 36px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-left: 6px;
}
.sq-go:hover:not(:disabled) { background: var(--site-brand-dark); }
.sq-go:disabled { opacity: 0.6; cursor: not-allowed; }

.sq-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20px 6px 14px;
  font-size: 14px;
  color: var(--site-text-dim);
  flex-wrap: wrap;
  gap: 12px;
}
.sq-summary b { color: var(--site-brand); font-size: 16px; padding: 0 3px; }
.text-brand { color: var(--site-brand); }

.sq-list { display: flex; flex-direction: column; gap: 8px; }
.sq-result {
  display: flex;
  align-items: stretch;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 8px;
  padding: 14px 20px 14px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.sq-result:hover {
  border-color: var(--site-brand);
  background: linear-gradient(135deg, #fff 0%, #fdf6f7 100%);
  box-shadow: 0 4px 14px rgba(165, 28, 48, 0.08);
}
.sq-idx {
  flex: 0 0 36px;
  color: var(--site-text-mute);
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  padding-top: 4px;
}
.sq-main { flex: 1; min-width: 0; }
.sq-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.sq-name {
  font-size: 15.5px;
  font-weight: 700;
  color: var(--site-text);
}
:deep(.sq-hlkw) {
  color: var(--site-brand);
  font-weight: 700;
}
.sq-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 22px;
  font-size: 13px;
  color: var(--site-text-dim);
  margin-top: 4px;
}
.sq-stat b {
  color: var(--site-brand);
  font-weight: 700;
  margin-right: 4px;
}
.sq-stat-label { color: var(--site-text-mute); margin-right: 2px; }
.sq-row-actions {
  flex: 0 0 140px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  gap: 6px;
  border-left: 1px dashed var(--site-hairline);
  padding-left: 16px;
}
.sq-act-btn {
  border: 1px solid var(--site-panel-border);
  background: #fff;
  border-radius: 4px;
  font-size: 13px;
  color: var(--site-text-dim);
  padding: 5px 0;
  height: 32px;
}
.sq-act-btn:hover { border-color: var(--site-brand); color: var(--site-brand); background: var(--site-brand-soft); }
.sq-empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--site-text-mute);
  font-size: 14px;
  background: #fff;
  border-radius: 8px;
  border: 1px dashed var(--site-hairline);
}
.sq-pagination {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .sq-label { flex: 0 0 70px; font-size: 13px; }
  .sq-row-actions { flex: 0 0 100px; padding-left: 10px; }
}
</style>
