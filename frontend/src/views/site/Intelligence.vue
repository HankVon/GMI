<!-- 项目商机列表页(原"情报动态"页改造版) - 紧凑表格 + 策展筛选 + 分页跳转 -->
<template>
  <SiteLayout>
    <!-- 顶部条: 项目商机 + 右侧说明 -->
    <!-- <div class="opp-topbar">
      <div class="site-container opp-topbar-inner">
        <h1 class="opp-topbar-title">项目商机</h1>
        <div class="opp-topbar-notice">
          <el-icon class="opp-notice-icon"><InfoFilled /></el-icon>
          <span>项目商机是基于人工智能的优质数据资源，包括全国各相关行业领域，矿产资源等项目</span>
        </div>
      </div>
    </div> -->

    <section class="opp-section">
      <div class="site-container">
        <!-- 筛选卡 -->
        <div class="opp-filter-card">
          <!-- 策展标签: 热点领域(可多选, 与热门标签同池 OR 并集生效) -->
          <div class="opp-row opp-row-tags" v-if="hotFieldTags.length">
            <div class="opp-row-label">
              热点领域
              <span class="opp-row-hint">HOT</span>
            </div>
            <div class="opp-row-content opp-pill-list">
              <span
                v-for="t in hotFieldTags"
                :key="t.id"
                :class="['opp-pill', { active: selectedTagIds.includes(t.id) }]"
                @click="toggleHotField(t.id)"
              >
                <span class="opp-pill-text">{{ t.label }}</span>
                <span v-if="t.isNew" class="opp-pill-new">NEW</span>
              </span>
            </div>
          </div>

          <!-- 策展标签: 热门标签(多选) -->
          <div class="opp-row opp-row-tags" v-if="hotProjectTags.length">
            <div class="opp-row-label">热门标签</div>
            <div class="opp-row-content opp-check-list">
              <el-checkbox-group v-model="selectedTagIds" @change="onQuery">
                <el-checkbox v-for="t in hotProjectTags" :key="t.id" :value="t.id">
                  <span class="opp-check-text">{{ t.label }}</span>
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>

          <!-- 表单字段网格(3 列布局) -->
          <div class="opp-form-grid">
            <div class="opp-form-cell">
              <label class="opp-cell-label">项目地区</label>
              <el-select
                v-model="form.regionProvince"
                placeholder="输入地区或选择地区"
                clearable filterable
                class="opp-cell-input"
                @change="onQuery"
              >
                <el-option v-for="p in PROVINCES" :key="p" :label="p" :value="p" />
              </el-select>
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">投资金额</label>
              <div class="opp-amount-range">
                <el-input v-model.number="form.amountMin" placeholder="最小金额" type="number" class="opp-amount-input" />
                <span class="opp-range-sep">-</span>
                <el-input v-model.number="form.amountMax" placeholder="最大金额" type="number" class="opp-amount-input" />
                <span class="opp-range-unit">万</span>
              </div>
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">项目阶段</label>
              <el-select
                v-model="form.stage"
                placeholder="立项、签订等"
                clearable
                class="opp-cell-input"
                @change="onQuery"
              >
                <el-option v-for="s in STAGE_OPTIONS" :key="s" :label="s" :value="s" />
              </el-select>
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">项目角色</label>
              <el-select
                v-model="form.unitRole"
                placeholder="请选择我方角色"
                clearable
                class="opp-cell-input"
                @change="onQuery"
              >
                <el-option v-for="r in ROLE_OPTIONS" :key="r" :label="r" :value="r" />
              </el-select>
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">项目名称</label>
              <el-input v-model="form.projectName" placeholder="请输入项目名称" class="opp-cell-input" clearable @keyup.enter="onQuery" />
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">业主类型</label>
              <el-select
                v-model="form.ownerType"
                placeholder="请选择甲方类型"
                clearable
                class="opp-cell-input"
                @change="onQuery"
              >
                <el-option v-for="o in OWNER_TYPE_OPTIONS" :key="o" :label="o" :value="o" />
              </el-select>
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">更新时间</label>
              <el-date-picker
                v-model="form.updateRange"
                type="daterange"
                range-separator="-"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                class="opp-cell-input opp-date-input"
                @change="onQuery"
              />
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">单位名称</label>
              <el-input v-model="form.unitName" placeholder="请输入单位关键字，多个关键词空格隔开，如：学校 医院" class="opp-cell-input" clearable @keyup.enter="onQuery" />
            </div>

            <div class="opp-form-cell">
              <label class="opp-cell-label">项目类型</label>
              <el-select
                v-model="form.projectType"
                placeholder="请选择"
                clearable
                class="opp-cell-input"
                @change="onQuery"
              >
                <el-option v-for="t in PROJECT_TYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </div>
          </div>

          <!-- 操作按钮组 -->
          <div class="opp-actions">
            <el-button type="primary" :icon="Search" @click="onQuery">查询</el-button>
            <el-button :icon="FolderAdd" @click="onSave">保存条件</el-button>
            <el-button :icon="RefreshLeft" @click="resetFilter">清空条件</el-button>
            <!-- <el-button text class="opp-more-btn">
              更多搜索条件
              <el-icon class="opp-more-icon"><ArrowDown /></el-icon>
            </el-button> -->
          </div>
        </div>

        <!-- 结果区 -->
        <div class="opp-result-card">
          <!-- 结果头: 命中数 + 数据集切换 + 订阅/导出 -->
          <div class="opp-result-head">
            <div class="opp-result-info">
              <span class="opp-total-text">
                共找到 <b class="opp-hit-num">{{ formatTotal(oppTotal) }}</b> 条项目商机
              </span>
              <div class="opp-dataset-switch" v-if="datasets.length > 1">
                <span
                  v-for="ds in datasets"
                  :key="ds.value"
                  :class="['opp-ds-btn', { active: datasetType === ds.value }]"
                  @click="switchDataset(ds.value)"
                >
                  <span v-if="ds.isNew" class="opp-ds-new">NEW</span>
                  <span class="opp-ds-tick">{{ datasetType === ds.value ? '✓' : '' }}</span>
                  {{ ds.label }}
                </span>
              </div>
            </div>
            <div class="opp-result-actions">
              <el-button type="warning" :icon="Bell" @click="onSubscribe">商机订阅</el-button>
              <el-button type="warning" :icon="Download" @click="onExport">导出项目</el-button>
            </div>
          </div>

          <!-- 列表 -->
          <div class="opp-list" v-loading="oppLoading" :element-loading-text="'加载中…'">
            <div
              v-for="(it, idx) in oppItems"
              :key="it.id"
              class="opp-item"
              @click="goDetail(it)"
            >
              <span class="opp-item-num">{{ (page - 1) * pageSize + idx + 1 }}</span>
              <div class="opp-item-main">
                <div class="opp-item-title-line">
                  <a class="opp-item-name" @click.stop="goDetail(it)">{{ it.projectName }}</a>
                  <span v-if="it.currentVersion" class="opp-item-version">v{{ formatVersion(it.currentVersion) }}</span>
                  <span v-if="it.ownerType" :class="['opp-item-tag', ownerTypeClass(it.ownerType)]">{{ it.ownerType }}</span>
                  <span
                    v-for="t in it.tags?.slice(0, 2)"
                    :key="t.code"
                    class="opp-item-tag opp-tag-project"
                  >{{ t.label }}</span>
                  <span class="opp-item-fav" @click.stop>
                    <FavoriteButton entity-type="opportunity" :entity-id="it.id" />
                  </span>
                </div>
                <div class="opp-item-meta">
                  <span class="opp-meta-item">
                    <span class="opp-meta-key">项目阶段:</span>
                    <span class="opp-meta-val">{{ it.stage || '—' }}</span>
                  </span>
                  <span class="opp-meta-item">
                    <span class="opp-meta-key">投资金额:</span>
                    <span class="opp-meta-val opp-amount">{{ formatAmount(it.amountWan) }}</span>
                  </span>
                  <span class="opp-meta-item">
                    <span class="opp-meta-key">业主:</span>
                    <span class="opp-meta-val">{{ it.ownerName || '—' }}</span>
                  </span>
                  <span class="opp-meta-item">
                    <span class="opp-meta-key">地区:</span>
                    <span class="opp-meta-val">{{ regionLabel(it) || '—' }}</span>
                  </span>
                </div>
              </div>
              <div class="opp-item-time">{{ formatDate(it.updatedAt) }}</div>
            </div>
            <div v-if="!oppLoading && !oppItems.length" class="opp-empty">暂无匹配的项目商机，请调整筛选条件</div>
          </div>

          <!-- 分页: 带跳转 -->
          <div class="opp-pagination" v-if="oppTotal > 0">
            <JumpPagination
              :total="oppTotal"
              :page="page"
              :page-size="pageSize"
              @change="onPageChange"
            />
          </div>
        </div>
      </div>
    </section>

    <!-- 商机订阅对话框 -->
    <el-dialog v-model="subDialogVisible" title="商机订阅" width="460px" destroy-on-close>
      <el-form label-width="88px" @submit.prevent="submitSubscribe">
        <el-form-item label="订阅名称" required>
          <el-input v-model="subName" placeholder="如: 广东新能源项目订阅" maxlength="128" />
        </el-form-item>
        <el-form-item label="筛选条件">
          <div class="sub-preview">
            <template v-if="subPreviewTags.length">
              <el-tag v-for="t in subPreviewTags" :key="t" size="small" effect="plain" class="sub-prev-tag">{{ t }}</el-tag>
            </template>
            <span v-else class="sub-preview-empty">未设置条件, 将订阅当前数据集全部新增商机</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="subSaving" @click="submitSubscribe">确认订阅</el-button>
      </template>
    </el-dialog>
  </SiteLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  Search,
  FolderAdd,
  RefreshLeft,
  ArrowDown,
  Bell,
  Download,
  InfoFilled,
} from "@element-plus/icons-vue";

import SiteLayout from "@/components/site/SiteLayout.vue";
import JumpPagination from "@/components/bids/JumpPagination.vue";
import {
  listOpportunityTags,
  searchOpportunities,
  type OpportunityItem,
  type OpportunityTagDef,
} from "@/api/opportunities";
import {
  createOpportunitySubscription,
  exportOpportunities,
} from "@/api/opportunityAdmin";
import FavoriteButton from "@/components/FavoriteButton.vue";

// 32 省级行政区(覆盖常用地区)
const PROVINCES = [
  "北京", "天津", "上海", "重庆",
  "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东",
  "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海",
  "内蒙古", "广西", "西藏", "宁夏", "新疆", "台湾", "香港", "澳门",
];

// 项目阶段可选项(与库内 stage 字段真实值对齐, 按业务流程排序)
const STAGE_OPTIONS = ["意向征集", "立项阶段", "可研阶段", "筹备阶段", "设计", "设计阶段", "动工"];
// 项目角色(我方角色)
const ROLE_OPTIONS = ["总包", "分包", "代理", "合作", "咨询", "业主", "其他"];
// 业主类型
const OWNER_TYPE_OPTIONS = ["国央企", "民企", "机关单位", "事业单位", "外资"];
// 项目类型(与库内 project_type 真实值对齐: 英文代码 + 少量自由文本)
const PROJECT_TYPE_OPTIONS = [
  { label: "矿业权交易", value: "mining_rights" },
  { label: "地质勘察", value: "geo_survey" },
  { label: "地质灾害治理", value: "geo_hazard" },
  { label: "生态修复/矿山修复", value: "eco_restoration" },
  { label: "水利水电", value: "water" },
  { label: "政策研究", value: "policy" },
  { label: "房建", value: "房建" },
  { label: "市政交通", value: "市政交通" },
  { label: "产业园区", value: "产业园区" },
  { label: "科研", value: "科研" },
];

const router = useRouter();

// ── 筛选条件 ──
const form = ref<{
  regionProvince: string;
  amountMin: number | null;
  amountMax: number | null;
  stage: string;
  unitName: string;
  unitRole: string;
  ownerType: string;
  updateRange: [string, string] | null;
  projectName: string;
  projectType: string;
}>({
  regionProvince: "",
  amountMin: null,
  amountMax: null,
  stage: "",
  unitName: "",
  unitRole: "",
  ownerType: "",
  updateRange: null,
  projectName: "",
  projectType: "",
});

// 策展标签
const tagDefs = ref<OpportunityTagDef[]>([]);
const selectedTagIds = ref<number[]>([]);
const hotFieldTags = computed(() => tagDefs.value.filter((t) => t.kind === "hot_field"));
const hotProjectTags = computed(() => tagDefs.value.filter((t) => t.kind === "hot_project"));

// 数据集切换(项目/拟建/土地交易)
const datasetType = ref<"project" | "proposed" | "landtrade">("project");
const datasets = [
  { value: "project" as const, label: "项目", isNew: false },
  { value: "proposed" as const, label: "拟建", isNew: false },
  { value: "landtrade" as const, label: "土地交易·招标", isNew: true },
];

// 列表状态
const oppItems = ref<OpportunityItem[]>([]);
const oppTotal = ref(0);
const oppLoading = ref(false);
const page = ref(1);
const pageSize = ref(20);

// ── 格式化工具 ──
function formatTotal(n: number): string {
  return (n || 0).toLocaleString();
}
function formatVersion(v: string): string {
  // 后端存储 "V3.6.3" → UI 显示 "3.6.3"
  return String(v || "").replace(/^V/i, "");
}
function formatAmount(w: number | null | undefined): string {
  if (w === null || w === undefined) return "未披露";
  return `${w.toLocaleString()}万元`;
}
function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return String(iso).slice(0, 10);
}
// 业主类型 → 配色 class
function ownerTypeClass(t: string): string {
  return `ot-${t}`;
}
// 地区显示(过滤脏数据)
const _REGION_NOISE = /^(拟建|筹建|未知|国土|n\/a|null|undefined)$/i;
function regionLabel(it: OpportunityItem): string {
  const parts: string[] = [];
  if (it.regionProvince && !_REGION_NOISE.test(it.regionProvince)) parts.push(it.regionProvince);
  if (it.regionCity && !_REGION_NOISE.test(it.regionCity)) parts.push(it.regionCity);
  return parts.join(" / ");
}

// ── 行为 ──
function toggleHotField(id: number) {
  const i = selectedTagIds.value.indexOf(id);
  if (i >= 0) selectedTagIds.value.splice(i, 1);
  else selectedTagIds.value.push(id);
  onQuery();
}

function buildPayload() {
  const f = form.value;
  const p: any = {
    dataset_type: datasetType.value,
    page: page.value,
    page_size: pageSize.value,
  };
  if (selectedTagIds.value.length) p.tags = [...selectedTagIds.value];
  if (f.regionProvince) p.region_province = f.regionProvince;
  if (f.amountMin != null && Number.isFinite(f.amountMin)) p.amount_min = f.amountMin;
  if (f.amountMax != null && Number.isFinite(f.amountMax)) p.amount_max = f.amountMax;
  if (f.stage) p.stage = f.stage;
  if (f.unitName) p.unit_name = f.unitName;
  if (f.unitRole) p.unit_role = f.unitRole;
  if (f.ownerType) p.owner_type = f.ownerType;
  if (f.updateRange && f.updateRange.length === 2) {
    p.update_start = f.updateRange[0];
    p.update_end = f.updateRange[1];
  }
  if (f.projectName) p.project_name = f.projectName;
  if (f.projectType) p.project_type = f.projectType;
  return p;
}

async function searchOpp() {
  oppLoading.value = true;
  try {
    const resp: any = await searchOpportunities(buildPayload());
    const d = resp?.data || { total: 0, items: [] };
    oppItems.value = d.items || [];
    oppTotal.value = d.total || 0;
  } catch {
    oppItems.value = [];
    oppTotal.value = 0;
    ElMessage.warning("商机数据加载失败,请稍后重试");
  } finally {
    oppLoading.value = false;
  }
}

function onQuery() {
  page.value = 1;
  searchOpp();
}
function onPageChange(p: number) {
  page.value = p;
  searchOpp();
}
function switchDataset(t: "project" | "proposed" | "landtrade") {
  datasetType.value = t;
  page.value = 1;
  searchOpp();
}
function resetFilter() {
  form.value = {
    regionProvince: "",
    amountMin: null,
    amountMax: null,
    stage: "",
    unitName: "",
    unitRole: "",
    ownerType: "",
    updateRange: null,
    projectName: "",
    projectType: "",
  };
  selectedTagIds.value = [];
  page.value = 1;
  searchOpp();
  ElMessage.success("已清空全部筛选条件");
}
function goDetail(it: OpportunityItem) {
  if (!it.intentId) {
    ElMessage.info("该商机暂无对应意向详情");
    return;
  }
  // 新标签页打开意向详情, 保留商机列表上下文
  const { href } = router.resolve(`/site/intelligence/${it.intentId}`);
  window.open(href, "_blank", "noopener");
}
function onSave() {
  // 暂存条件到 localStorage(订阅管理页「新建订阅」会读取该快照)
  const snap = { form: form.value, tagIds: selectedTagIds.value, dataset: datasetType.value };
  try {
    localStorage.setItem("gmi:opp:filter", JSON.stringify(snap));
    ElMessage.success("筛选条件已保存,可在后台「商机订阅」中一键创建订阅");
  } catch {
    ElMessage.warning("保存失败,请检查浏览器存储");
  }
}

// ── 商机订阅(登录态) ──
const subDialogVisible = ref(false);
const subName = ref("");
const subSaving = ref(false);
const subPreviewTags = computed(() => {
  const f = form.value;
  const tags: string[] = [];
  if (selectedTagIds.value.length) tags.push(`标签 ${selectedTagIds.value.length} 个`);
  if (f.regionProvince) tags.push(`地区:${f.regionProvince}`);
  if (f.stage) tags.push(`阶段:${f.stage}`);
  if (f.ownerType) tags.push(`业主:${f.ownerType}`);
  if (f.projectType) tags.push(`类型:${f.projectType}`);
  if (f.amountMin != null || f.amountMax != null) {
    tags.push(`金额:${f.amountMin || 0}~${f.amountMax || "∞"}万`);
  }
  if (f.projectName) tags.push(`项目:${f.projectName}`);
  return tags;
});
function onSubscribe() {
  subName.value = "";
  subDialogVisible.value = true;
}
async function submitSubscribe() {
  if (!subName.value.trim()) {
    ElMessage.warning("请输入订阅名称");
    return;
  }
  subSaving.value = true;
  try {
    const condition: Record<string, unknown> = buildPayload();
    delete condition.page;
    delete condition.page_size;
    await createOpportunitySubscription({ name: subName.value.trim(), condition });
    ElMessage.success("订阅成功,每日扫描新增商机并推送通知");
    subDialogVisible.value = false;
  } catch { /* 拦截器已提示 */ } finally {
    subSaving.value = false;
  }
}

// ── 导出项目(登录态, 当前筛选条件) ──
async function onExport() {
  try {
    const params: Record<string, unknown> = {
      dataset_type: datasetType.value,
    };
    const f = form.value;
    if (selectedTagIds.value.length) params.tags = selectedTagIds.value.join(",");
    if (f.regionProvince) params.region_province = f.regionProvince;
    if (f.amountMin != null && Number.isFinite(f.amountMin)) params.amount_min = f.amountMin;
    if (f.amountMax != null && Number.isFinite(f.amountMax)) params.amount_max = f.amountMax;
    if (f.stage) params.stage = f.stage;
    if (f.ownerType) params.owner_type = f.ownerType;
    if (f.projectType) params.project_type = f.projectType;
    if (f.projectName) params.project_name = f.projectName;
    if (f.unitName) params.unit_name = f.unitName;
    if (f.unitRole) params.unit_role = f.unitRole;
    if (f.updateRange && f.updateRange.length === 2) {
      params.update_start = f.updateRange[0];
      params.update_end = f.updateRange[1];
    }
    const blob: any = await exportOpportunities(params);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `project_opportunities_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success("导出成功,已开始下载");
  } catch {
    ElMessage.error("导出失败,请稍后重试");
  }
}

onMounted(async () => {
  try {
    const resp: any = await listOpportunityTags();
    tagDefs.value = resp?.data || [];
  } catch { /* 标签失败不影响主流程 */ }
  await searchOpp();
});
</script>

<style scoped>
/* =============================================================
   项目商机页(紧凑表格 + 多列筛选)
   设计: 浅色卡片 + 蓝色主题 + 紧凑行高 + 响应式断点
   ============================================================= */

/* 顶部条 */
.opp-topbar {
  background: #fff;
  border-bottom: 1px solid var(--site-panel-border);
  padding: 18px 0;
}
.opp-topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}
.opp-topbar-title {
  font-size: 20px;
  font-weight: 700;
  color: #c8102e;
  margin: 0;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.opp-topbar-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}
.opp-notice-icon {
  color: #c8102e;
  font-size: 14px;
  flex-shrink: 0;
}

.opp-section { padding: 16px 0 32px; background: var(--site-bg); }

/* 筛选卡 */
.opp-filter-card {
  background: #fff;
  border: 1px solid var(--site-panel-border);
  border-radius: 8px;
  padding: 18px 20px 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
  margin-bottom: 14px;
}
.opp-row { display: flex; align-items: flex-start; gap: 12px; padding: 8px 0; }
.opp-row + .opp-row { border-top: 1px dashed #ebeef5; }
.opp-row-label {
  flex-shrink: 0;
  width: 70px;
  font-size: 13px;
  color: #606266;
  font-weight: 500;
  padding-top: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.opp-row-hint {
  display: inline-block;
  background: #ff7a45;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 1px 4px;
  border-radius: 3px;
  line-height: 1.2;
}
.opp-row-content { flex: 1; min-width: 0; }

/* 热点领域 pill */
.opp-pill-list { display: flex; flex-wrap: wrap; gap: 8px; }
.opp-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 14px;
  font-size: 13px;
  color: #c8102e;
  background: #fceef0;
  border: 1px solid #f7c3cb;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}
.opp-pill:hover { background: #f7c3cb; }
.opp-pill.active {
  background: #c8102e;
  color: #fff;
  border-color: #c8102e;
}
.opp-pill-new {
  display: inline-block;
  background: #ff4d4f;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 0 4px;
  border-radius: 6px;
  line-height: 14px;
  margin-left: 2px;
}
.opp-pill.active .opp-pill-new { background: #fff; color: #ff4d4f; }

/* 热门标签 check */
.opp-check-list :deep(.el-checkbox-group) { display: flex; flex-wrap: wrap; gap: 6px 14px; }
.opp-check-list :deep(.el-checkbox) { margin-right: 0; }
.opp-check-text { font-size: 13px; color: #303133; }

/* 表单网格 */
.opp-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px 16px;
  padding: 12px 0 6px;
  border-top: 1px dashed #ebeef5;
  margin-top: 8px;
}
.opp-form-cell { display: flex; flex-direction: column; gap: 4px; }
.opp-cell-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}
.opp-cell-input { width: 100%; }
.opp-cell-input :deep(.el-input__wrapper) { background: #fafbfc; }

/* 金额范围 */
.opp-amount-range { display: flex; align-items: center; gap: 6px; }
.opp-amount-input { flex: 1; min-width: 0; }
.opp-amount-input :deep(.el-input__wrapper) { background: #fafbfc; }
.opp-range-sep { color: #c0c4cc; font-size: 13px; }
.opp-range-unit { color: #909399; font-size: 12px; flex-shrink: 0; }
.opp-date-input { width: 100%; }

/* 操作按钮 */
.opp-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px dashed #ebeef5;
  margin-top: 8px;
}
.opp-more-btn {
  margin-left: auto;
  color: #c8102e;
  font-size: 13px;
}
.opp-more-icon { font-size: 12px; margin-left: 2px; }

/* 结果区 */
.opp-result-card {
  background: #fff;
  border: 1px solid var(--site-panel-border);
  border-radius: 8px;
  padding: 14px 20px 18px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
}
.opp-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}
.opp-result-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #606266;
}
.opp-hit-num { color: #ff7a45; font-size: 16px; font-weight: 700; margin: 0 2px; }

/* 数据集切换 */
.opp-dataset-switch { display: inline-flex; gap: 6px; align-items: center; }
.opp-ds-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  font-size: 12.5px;
  color: #c8102e;
  background: #fceef0;
  border: 1px solid #f7c3cb;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}
.opp-ds-btn:hover { background: #f7c3cb; }
.opp-ds-btn.active {
  background: #c8102e;
  color: #fff;
  border-color: #c8102e;
  font-weight: 600;
}
.opp-ds-tick { font-weight: 700; font-size: 12px; }
.opp-ds-new {
  display: inline-block;
  background: #ff4d4f;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  padding: 0 3px;
  border-radius: 5px;
  line-height: 12px;
  margin-right: 2px;
}
.opp-ds-btn.active .opp-ds-new { background: #fff; color: #ff4d4f; }

.opp-result-actions { display: flex; gap: 8px; }
.opp-result-actions :deep(.el-button--warning) {
  --el-button-bg-color: #ff7a45;
  --el-button-border-color: #ff7a45;
  --el-button-hover-bg-color: #ff9c6e;
  --el-button-hover-border-color: #ff9c6e;
  --el-button-active-bg-color: #d9632f;
  --el-button-active-border-color: #d9632f;
}

/* 列表 */
.opp-list { padding: 4px 0; }
.opp-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 4px;
  border-bottom: 1px solid #f0f2f5;
  cursor: pointer;
  transition: background 0.15s ease;
}
.opp-item:hover { background: #fdf6f7; }
.opp-item:last-child { border-bottom: none; }
.opp-item-num {
  flex-shrink: 0;
  width: 28px;
  font-size: 13px;
  color: #909399;
  font-weight: 500;
  padding-top: 2px;
}
.opp-item-main { flex: 1; min-width: 0; }
.opp-item-title-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 8px;
  margin-bottom: 6px;
  min-width: 0;
}
.opp-item-fav { margin-left: auto; display: inline-flex; flex-shrink: 0; }
.opp-item-name {
  font-size: 14.5px;
  font-weight: 600;
  color: #c8102e;
  text-decoration: none;
  cursor: pointer;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  min-width: 0;
}
.opp-item-name:hover { color: #a40d26; text-decoration: underline; }
.opp-item-version {
  font-size: 11px;
  font-weight: 700;
  font-family: 'Consolas', 'Monaco', monospace;
  color: #ff7a45;
  background: #fff5ec;
  border: 1px solid #ffd5b3;
  border-radius: 3px;
  padding: 1px 5px;
  flex-shrink: 0;
}
.opp-item-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  color: #fff;
  font-weight: 500;
  flex-shrink: 0;
}
.opp-tag-project {
  background: #c456f0;
  color: #fff;
}
/* 业主类型配色 */
.ot-国央企    { background: #ff7a45; }
.ot-民企      { background: #36cbcb; }
.ot-机关单位  { background: #ff85c0; }
.ot-事业单位  { background: #7c4dff; }
.ot-外资      { background: #faad14; }

.opp-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-size: 12.5px;
  color: #909399;
  line-height: 1.6;
}
.opp-meta-item { min-width: 0; }
.opp-meta-key { color: #909399; margin-right: 2px; }
.opp-meta-val { color: #303133; word-break: break-word; overflow-wrap: break-word; }
.opp-amount { color: #ff7a45; font-weight: 600; }
.opp-item-time {
  flex-shrink: 0;
  font-size: 12.5px;
  color: #909399;
  padding-top: 2px;
  min-width: 80px;
  text-align: right;
}
.opp-empty {
  text-align: center;
  color: #909399;
  padding: 50px 0;
  font-size: 14px;
}

/* 分页 */
.opp-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 14px 0 4px;
  border-top: 1px solid #ebeef5;
  margin-top: 4px;
}

/* 订阅对话框 */
.sub-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 0;
}
.sub-prev-tag { margin-right: 0; }
.sub-preview-empty { font-size: 12.5px; color: #909399; }

/* ============================================================
   响应式
   ============================================================ */
@media (max-width: 1100px) {
  .opp-form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
  .opp-result-head { flex-direction: column; align-items: flex-start; }
  .opp-result-actions { width: 100%; }
  .opp-result-actions > * { flex: 1; }
  .opp-item { flex-wrap: wrap; }
  .opp-item-time { width: 100%; text-align: left; min-width: 0; padding-left: 40px; padding-top: 4px; }
}
@media (max-width: 768px) {
  .opp-topbar-inner { flex-direction: column; align-items: flex-start; gap: 8px; }
  .opp-topbar-notice { font-size: 12.5px; }
  .opp-form-grid { grid-template-columns: 1fr; gap: 10px; }
  .opp-row { flex-direction: column; gap: 8px; }
  .opp-row-label { width: auto; padding-top: 0; }
  .opp-actions { flex-wrap: wrap; }
  .opp-more-btn { margin-left: 0; }
  .opp-item-meta { gap: 2px 12px; }
  .opp-pagination { justify-content: center; }
  .opp-pagination :deep(.jump-pagination) { justify-content: center; }
}
@media (max-width: 480px) {
  .opp-filter-card { padding: 14px 12px 10px; }
  .opp-result-card { padding: 12px 12px 14px; }
  .opp-item-name { font-size: 13.5px; }
  .opp-amount-range { flex-wrap: wrap; }
  .opp-amount-input { flex: 1 1 calc(50% - 16px); min-width: 90px; }
}
</style>
