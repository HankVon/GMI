<!-- 商机管理(后台): 列表 + 全字段筛选 + 建档/编辑(版本自动 bump) + 详情抽屉 + 版本时间线 + 标签维护 + 导出 -->
<template>
  <div class="opp-mgmt-page">
    <!-- 页面头 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">商机管理</h2>
        <p class="page-desc">人工策展的项目商机台账 · 编辑自动生成语义化版本 · 与前台「项目商机」页同源</p>
      </div>
      <div class="header-actions">
        <el-button :loading="syncLoading" @click="syncFromIntents">
          <el-icon style="margin-right: 4px"><Refresh /></el-icon>意向同步建档
        </el-button>
        <el-button :loading="exporting" @click="exportCsv">
          <el-icon style="margin-right: 4px"><Download /></el-icon>导出
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon style="margin-right: 4px"><Plus /></el-icon>新建商机
        </el-button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <el-card class="filter-card" shadow="never">
      <div class="filters">
        <el-select v-model="query.dataset_type" placeholder="数据集" clearable style="width: 140px" @change="loadList">
          <el-option label="项目" value="project" />
          <el-option label="拟建" value="proposed" />
          <el-option label="土地交易·招标" value="landtrade" />
        </el-select>
        <el-input
          v-model="query.project_name" placeholder="项目名称关键词" clearable style="width: 200px"
          @keyup.enter="loadList" @clear="loadList"
        />
        <el-input
          v-model="query.owner_name" placeholder="业主名称关键词" clearable style="width: 200px"
          @keyup.enter="loadList" @clear="loadList"
        />
        <el-select v-model="query.owner_type" placeholder="业主类型" clearable style="width: 140px" @change="loadList">
          <el-option v-for="t in OWNER_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
        <el-select v-model="query.stage" placeholder="项目阶段" clearable style="width: 140px" @change="loadList">
          <el-option v-for="s in STAGES" :key="s" :label="s" :value="s" />
        </el-select>
        <el-select v-model="query.region_province" placeholder="省份" clearable filterable style="width: 130px" @change="loadList">
          <el-option v-for="p in PROVINCES" :key="p" :label="p" :value="p" />
        </el-select>
        <el-select v-model="query.project_type" placeholder="项目类型" clearable style="width: 140px" @change="loadList">
          <el-option v-for="t in PROJECT_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
        <el-date-picker
          v-model="query.updateRange" type="daterange" range-separator="~"
          start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD"
          style="width: 240px" @change="loadList"
        />
        <el-button type="primary" :loading="loading" @click="loadList">
          <el-icon style="margin-right: 4px"><Search /></el-icon>查询
        </el-button>
        <el-button @click="resetQuery">
          <el-icon style="margin-right: 4px"><RefreshLeft /></el-icon>重置
        </el-button>
        <div style="flex: 1" />
        <span class="stat-total">共 <b>{{ total }}</b> 条商机</span>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card class="list-card" shadow="never" body-style="padding: 0">
      <el-table :data="items" v-loading="loading" stripe size="default" style="width: 100%">
        <el-table-column prop="projectName" label="项目名称" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="title-cell">
              <span class="proj-name" @click="openDetail(row)">{{ row.projectName }}</span>
              <el-tag v-if="row.currentVersion" size="small" type="warning" effect="plain" class="ver-tag">
                v{{ String(row.currentVersion).replace(/^V/i, '') }}
              </el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="ownerName" label="业主" min-width="180" show-overflow-tooltip />
        <el-table-column label="业主类型" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.ownerType" size="small" :color="ownerTypeColor(row.ownerType)" effect="dark" style="color:#fff;border:none">
              {{ row.ownerType }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="投资金额(万)" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.amountWan != null" class="amount-cell">{{ row.amountWan.toLocaleString() }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="阶段" width="100">
          <template #default="{ row }">{{ row.stage || '-' }}</template>
        </el-table-column>
        <el-table-column label="地区" width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ regionLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="项目类型" width="110">
          <template #default="{ row }">{{ row.projectType || '-' }}</template>
        </el-table-column>
        <el-table-column label="数据集" width="110">
          <template #default="{ row }">
            <el-tag :type="dsType(row.datasetType)" size="small" effect="light">{{ dsLabel(row.datasetType) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标签" width="150">
          <template #default="{ row }">
            <template v-if="row.tags && row.tags.length">
              <el-tag v-for="t in row.tags.slice(0, 2)" :key="t.code" size="small" class="tag-chip" effect="plain">
                {{ t.label }}
              </el-tag>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="收藏" width="130">
          <template #default="{ row }">
            <FavoriteButton entity-type="opportunity" :entity-id="row.id" />
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="150">
          <template #default="{ row }">{{ formatTime(row.updatedAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager" v-if="total > 0">
        <el-pagination
          v-model:current-page="page" :page-size="pageSize" :total="total"
          layout="prev, pager, next, total" background @current-change="loadList"
        />
      </div>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="formVisible" :title="editingId ? `编辑商机 #${editingId}` : '新建商机'"
      width="760px" top="6vh" destroy-on-close
    >
      <el-form :model="form" label-width="92px" class="opp-form">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目名称" required>
              <el-input v-model="form.project_name" placeholder="必填" maxlength="255" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="业主名称" required>
              <el-input v-model="form.owner_name" placeholder="必填" maxlength="255" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="业主类型">
              <el-select v-model="form.owner_type" placeholder="请选择" clearable style="width: 100%">
                <el-option v-for="t in OWNER_TYPES" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="业主规模">
              <el-select v-model="form.owner_scale" placeholder="请选择" clearable style="width: 100%">
                <el-option label="大型" value="大型" />
                <el-option label="中型" value="中型" />
                <el-option label="小型" value="小型" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="投资金额(万)">
              <el-input-number v-model="form.amount_wan" :min="0" :step="1000" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目阶段">
              <el-select v-model="form.stage" placeholder="请选择" clearable style="width: 100%">
                <el-option v-for="s in STAGES" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="省份">
              <el-select v-model="form.region_province" placeholder="请选择" clearable filterable style="width: 100%">
                <el-option v-for="p in PROVINCES" :key="p" :label="p" :value="p" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="城市">
              <el-input v-model="form.region_city" placeholder="如: 深圳市" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目类型">
              <el-select v-model="form.project_type" placeholder="请选择" clearable style="width: 100%">
                <el-option v-for="t in PROJECT_TYPES" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据集">
              <el-select v-model="form.dataset_type" style="width: 100%">
                <el-option label="项目" value="project" />
                <el-option label="拟建" value="proposed" />
                <el-option label="土地交易·招标" value="landtrade" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="我方角色">
              <el-input v-model="form.unit_role" placeholder="如: 施工总承包" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="我方单位">
              <el-input v-model="form.unit_name" placeholder="如: 中铁某局" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="项目摘要">
              <el-input v-model="form.body_excerpt" type="textarea" :rows="2" maxlength="2000" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="关键联系人">
              <el-input v-model="form.contact_summary" type="textarea" :rows="2" placeholder="仅 VIP 可见" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="跟进记录">
              <el-input v-model="form.followup_log" type="textarea" :rows="2" placeholder="仅 VIP 可见" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="策展标签">
              <el-checkbox-group v-model="form.tag_ids">
                <el-checkbox v-for="t in tagDefs" :key="t.id" :value="t.id">
                  {{ t.label }}
                  <span class="tag-kind">{{ t.kind === 'hot_field' ? '热点领域' : '热门项目' }}</span>
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="变更摘要">
              <el-input
                v-model="form.change_summary" type="textarea" :rows="1"
                :placeholder="editingId ? '留空则由系统根据字段差异自动生成' : '留空默认为首版立项信息录入'"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="商机详情" size="640px">
      <template v-if="detail">
        <div class="detail-head">
          <h3 class="detail-name">{{ detail.projectName }}</h3>
          <div class="detail-meta">
            <el-tag v-if="detail.currentVersion" size="small" type="warning" effect="plain">v{{ String(detail.currentVersion).replace(/^V/i, '') }}</el-tag>
            <el-tag v-if="detail.datasetType" size="small" effect="light" :type="dsType(detail.datasetType)">{{ dsLabel(detail.datasetType) }}</el-tag>
            <template v-if="detail.tags && detail.tags.length">
              <el-tag v-for="t in detail.tags" :key="t.code" size="small" class="tag-chip" effect="plain">{{ t.label }}</el-tag>
            </template>
          </div>
        </div>

        <el-descriptions :column="2" border size="small" class="detail-desc">
          <el-descriptions-item label="业主">{{ detail.ownerName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="业主类型">{{ detail.ownerType || '-' }}</el-descriptions-item>
          <el-descriptions-item label="业主规模">{{ detail.ownerScale || '-' }}</el-descriptions-item>
          <el-descriptions-item label="投资金额">{{ detail.amountWan != null ? `${detail.amountWan.toLocaleString()} 万元` : '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目阶段">{{ detail.stage || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目类型">{{ detail.projectType || '-' }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ regionLabel(detail) || '-' }}</el-descriptions-item>
          <el-descriptions-item label="我方角色">{{ detail.unitRole || '-' }}</el-descriptions-item>
          <el-descriptions-item label="我方单位" :span="2">{{ detail.unitName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="数据来源" :span="2">{{ detail.source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="首次发布" :span="2">{{ formatTime(detail.publishedAt) }}</el-descriptions-item>
          <el-descriptions-item label="最近更新" :span="2">{{ formatTime(detail.updatedAt) }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.bodyExcerpt" label="项目摘要" :span="2">
            <div class="excerpt">{{ detail.bodyExcerpt }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.vipOnly?.contactSummary" label="关键联系人" :span="2">
            <span class="vip-text"><el-icon style="margin-right:4px"><Lock /></el-icon>{{ detail.vipOnly.contactSummary }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.vipOnly?.followupLog" label="跟进记录" :span="2">
            <span class="vip-text"><el-icon style="margin-right:4px"><Lock /></el-icon>{{ detail.vipOnly.followupLog }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="versions-head">
          <span class="versions-title">版本历史</span>
          <el-button link type="primary" size="small" @click="loadVersions">刷新</el-button>
        </div>
        <el-timeline v-loading="versionsLoading" class="versions-timeline">
          <el-timeline-item
            v-for="v in versions" :key="v.id" :timestamp="formatTime(v.releasedAt)" placement="top" :type="timelineType(v)"
          >
            <div class="ver-item">
              <span class="ver-badge">v{{ String(v.version).replace(/^V/i, '') }}</span>
              <span class="ver-summary">{{ v.changeSummary || '更新' }}</span>
              <span v-if="v.operator" class="ver-operator">{{ v.operator }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
      </template>
      <el-empty v-else description="加载中…" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Search, Refresh, Download, RefreshLeft, Lock } from "@element-plus/icons-vue";
import {
  searchOpportunitiesAdmin,
  fetchOpportunityDetail,
  createOpportunity,
  updateOpportunity,
  deleteOpportunity,
  fetchOpportunityVersions,
  syncOpportunitiesFromIntents,
  exportOpportunities,
  listTagDefsAdmin,
  type OpportunityDetail,
  type OpportunityVersionItem,
  type OpportunityTagDefAdmin,
  type OpportunityAdminPayload,
} from "@/api/opportunityAdmin";
import FavoriteButton from "@/components/FavoriteButton.vue";

const OWNER_TYPES = ["国央企", "民企", "机关单位", "事业单位", "外资"];
const STAGES = ["意向征集", "已匹配", "已过期", "已跳过", "立项", "招标", "签订", "筹备阶段", "可研阶段", "设计阶段"];
const PROJECT_TYPES = ["房建", "市政交通", "产业园区", "科研", "新能源", "水利水电", "城市更新", "其他"];
const PROVINCES = [
  "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
  "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
  "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古",
  "广西", "西藏", "宁夏", "新疆", "台湾", "香港", "澳门",
];

const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const exporting = ref(false);
const syncLoading = ref(false);
const tagDefs = ref<OpportunityTagDefAdmin[]>([]);

const query = reactive<Record<string, any>>({
  dataset_type: "",
  project_name: "",
  owner_name: "",
  owner_type: "",
  stage: "",
  region_province: "",
  project_type: "",
  updateRange: null as [string, string] | null,
});

// 表单
const formVisible = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const form = reactive<Record<string, any>>({
  project_name: "",
  owner_name: "",
  owner_type: "",
  owner_scale: "",
  amount_wan: null,
  stage: "",
  region_province: "",
  region_city: "",
  project_type: "",
  dataset_type: "project",
  unit_role: "",
  unit_name: "",
  body_excerpt: "",
  contact_summary: "",
  followup_log: "",
  tag_ids: [] as number[],
  change_summary: "",
});

// 详情
const detailVisible = ref(false);
const detail = ref<OpportunityDetail | null>(null);
const versions = ref<OpportunityVersionItem[]>([]);
const versionsLoading = ref(false);

function formatTime(v?: string | null): string {
  if (!v) return "-";
  return v.replace("T", " ").slice(0, 16);
}
function regionLabel(row: any): string {
  const parts = [row.regionProvince, row.regionCity].filter((x) => x);
  return parts.join(" / ") || "-";
}
function dsLabel(ds?: string): string {
  if (ds === "proposed") return "拟建";
  if (ds === "landtrade") return "土地交易";
  return "项目";
}
function dsType(ds?: string): "success" | "primary" | "warning" {
  if (ds === "proposed") return "primary";
  if (ds === "landtrade") return "warning";
  return "success";
}
function ownerTypeColor(t: string): string {
  const map: Record<string, string> = {
    "国央企": "#ff7a45",
    "民企": "#36cbcb",
    "机关单位": "#7c4dff",
    "事业单位": "#ff85c0",
    "外资": "#faad14",
  };
  return map[t] || "#909399";
}
function timelineType(v: OpportunityVersionItem): "primary" | "success" {
  return versions.value[0]?.id === v.id ? "success" : "primary";
}

function buildParams() {
  const p: Record<string, unknown> = {
    page: page.value,
    page_size: pageSize,
  };
  if (query.dataset_type) p.dataset_type = query.dataset_type;
  if (query.project_name) p.project_name = query.project_name;
  if (query.owner_name) p.owner_name = query.owner_name;
  if (query.owner_type) p.owner_type = query.owner_type;
  if (query.stage) p.stage = query.stage;
  if (query.region_province) p.region_province = query.region_province;
  if (query.project_type) p.project_type = query.project_type;
  if (query.updateRange && query.updateRange.length === 2) {
    p.update_start = query.updateRange[0];
    p.update_end = query.updateRange[1];
  }
  return p;
}

async function loadList() {
  loading.value = true;
  try {
    const res: any = await searchOpportunitiesAdmin(buildParams());
    const d = res?.data || {};
    items.value = d.items || [];
    total.value = d.total || 0;
  } catch {
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function resetQuery() {
  Object.keys(query).forEach((k) => {
    if (k === "updateRange") query[k] = null;
    else query[k] = "";
  });
  page.value = 1;
  loadList();
}

async function loadTagDefs() {
  try {
    const res: any = await listTagDefsAdmin();
    tagDefs.value = res?.data || [];
  } catch { /* 忽略 */ }
}

// ── 新建 / 编辑 ──
function openCreate() {
  editingId.value = null;
  Object.assign(form, {
    project_name: "", owner_name: "", owner_type: "", owner_scale: "",
    amount_wan: null, stage: "", region_province: "", region_city: "",
    project_type: "", dataset_type: "project", unit_role: "", unit_name: "",
    body_excerpt: "", contact_summary: "", followup_log: "",
    tag_ids: [], change_summary: "",
  });
  formVisible.value = true;
}

function openEdit(row: any) {
  editingId.value = row.id;
  fetchOpportunityDetail(row.id).then((res: any) => {
    const d = res?.data || {};
    Object.assign(form, {
      project_name: d.projectName || "",
      owner_name: d.ownerName || "",
      owner_type: d.ownerType || "",
      owner_scale: d.ownerScale || "",
      amount_wan: d.amountWan ?? null,
      stage: d.stage || "",
      region_province: d.regionProvince || "",
      region_city: d.regionCity || "",
      project_type: d.projectType || "",
      dataset_type: d.datasetType || "project",
      unit_role: d.unitRole || "",
      unit_name: d.unitName || "",
      body_excerpt: d.bodyExcerpt || "",
      contact_summary: d.vipOnly?.contactSummary || "",
      followup_log: d.vipOnly?.followupLog || "",
      tag_ids: (d.tags || []).map((t: any) => tagDefs.value.find((td) => td.label === t.label)?.id).filter(Boolean),
      change_summary: "",
    });
    formVisible.value = true;
  }).catch(() => { /* 拦截器已提示 */ });
}

async function saveForm() {
  if (!form.project_name.trim() || !form.owner_name.trim()) {
    ElMessage.warning("项目名称与业主名称为必填项");
    return;
  }
  saving.value = true;
  try {
    const payload: OpportunityAdminPayload = {
      project_name: form.project_name.trim(),
      owner_name: form.owner_name.trim(),
      owner_type: form.owner_type || null,
      owner_scale: form.owner_scale || null,
      amount_wan: form.amount_wan ?? null,
      stage: form.stage || null,
      region_province: form.region_province || null,
      region_city: form.region_city || null,
      project_type: form.project_type || null,
      unit_role: form.unit_role || null,
      unit_name: form.unit_name || null,
      body_excerpt: form.body_excerpt || null,
      contact_summary: form.contact_summary || null,
      followup_log: form.followup_log || null,
      dataset_type: form.dataset_type || "project",
      change_summary: form.change_summary || null,
    };
    if (form.tag_ids?.length) payload.tag_ids = form.tag_ids;
    if (editingId.value) {
      const res: any = await updateOpportunity(editingId.value, payload);
      ElMessage.success(`已保存, 版本升级为 v${String(res?.data?.currentVersion || "").replace(/^V/i, "")}`);
    } else {
      await createOpportunity(payload);
      ElMessage.success("商机创建成功(初始版本 V1.0)");
    }
    formVisible.value = false;
    loadList();
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false;
  }
}

// ── 删除 ──
async function confirmDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除商机「${row.projectName}」? 删除后前台不再展示。`, "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
    await deleteOpportunity(row.id);
    ElMessage.success("已删除");
    loadList();
  } catch { /* 取消或失败 */ }
}

// ── 详情 + 版本 ──
async function openDetail(row: any) {
  detailVisible.value = true;
  detail.value = null;
  versions.value = [];
  try {
    const res: any = await fetchOpportunityDetail(row.id);
    detail.value = res?.data || null;
    await loadVersions();
  } catch { /* 拦截器已提示 */ }
}

async function loadVersions() {
  if (!detail.value?.id) return;
  versionsLoading.value = true;
  try {
    const res: any = await fetchOpportunityVersions(detail.value.id);
    versions.value = res?.data || [];
  } catch {
    versions.value = [];
  } finally {
    versionsLoading.value = false;
  }
}

// ── 同步意向 ──
async function syncFromIntents() {
  syncLoading.value = true;
  try {
    const res: any = await syncOpportunitiesFromIntents();
    const d = res?.data || {};
    ElMessage.success(`同步完成: 新增 ${d.created || 0} 条, 跳过 ${d.skipped || 0} 条`);
    loadList();
  } catch { /* 拦截器已提示 */ } finally {
    syncLoading.value = false;
  }
}

// ── 导出 ──
async function exportCsv() {
  exporting.value = true;
  try {
    const params: Record<string, unknown> = {};
    if (query.dataset_type) params.dataset_type = query.dataset_type;
    if (query.owner_type) params.owner_type = query.owner_type;
    if (query.owner_name) params.owner_name = query.owner_name;
    if (query.stage) params.stage = query.stage;
    if (query.region_province) params.region_province = query.region_province;
    if (query.project_name) params.project_name = query.project_name;
    const blob: any = await exportOpportunities(params);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `opportunity_${query.dataset_type || "project"}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success("导出成功, 已开始下载");
  } catch {
    ElMessage.error("导出失败, 请稍后重试");
  } finally {
    exporting.value = false;
  }
}

onMounted(() => {
  loadTagDefs();
  loadList();
});
</script>

<style scoped>
.opp-mgmt-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.page-title { font-size: 20px; font-weight: 700; color: var(--ssm-text-main); margin: 0; }
.page-desc { font-size: 13px; color: var(--ssm-text-secondary); margin: 4px 0 0; }
.header-actions { display: flex; gap: 10px; flex-wrap: wrap; }

.filter-card { border-radius: var(--ssm-radius); }
.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.stat-total { font-size: 13px; color: var(--ssm-text-secondary); }
.stat-total b { color: var(--ssm-primary); font-size: 16px; }

.list-card { border-radius: var(--ssm-radius); }
.title-cell { display: inline-flex; align-items: center; gap: 6px; }
.proj-name { color: var(--ssm-primary); font-weight: 600; cursor: pointer; }
.proj-name:hover { text-decoration: underline; }
.ver-tag { font-family: 'Consolas', monospace; }
.amount-cell { color: var(--ssm-warning); font-weight: 600; }
.muted { color: var(--ssm-text-secondary); }
.tag-chip { margin-right: 4px; }
.pager { display: flex; justify-content: flex-end; padding: 14px 16px; border-top: 1px solid var(--ssm-border); }

.detail-head { margin-bottom: 14px; }
.detail-name { font-size: 18px; font-weight: 700; color: var(--ssm-text-main); margin: 0 0 8px; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 6px; }
.detail-desc { margin-bottom: 6px; }
.excerpt { white-space: pre-wrap; line-height: 1.6; color: var(--ssm-text-regular); font-size: 13px; }
.vip-text { color: var(--ssm-warning); display: inline-flex; align-items: center; }

.versions-head { display: flex; align-items: center; justify-content: space-between; margin: 18px 0 10px; }
.versions-title { font-weight: 700; font-size: 15px; color: var(--ssm-text-main); }
.versions-timeline { padding-left: 4px; }
.ver-item { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ver-badge {
  font-family: 'Consolas', monospace; font-weight: 700; color: var(--ssm-primary);
  background: var(--ssm-primary-soft); border-radius: 4px; padding: 1px 6px; font-size: 12px;
}
.ver-summary { font-size: 13px; color: var(--ssm-text-regular); }
.ver-operator { font-size: 12px; color: var(--ssm-text-secondary); }

.tag-kind { font-size: 11px; color: var(--ssm-text-secondary); margin-left: 2px; }

@media (max-width: 640px) {
  .opp-mgmt-page .el-card { padding: 0; }
  .filters .el-input, .filters .el-select { width: 100% !important; }
}
</style>
