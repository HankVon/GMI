<!--
  情报中心 · 情报录入/编辑
  后端: POST/PUT /api/v1/admin/intelligence
-->
<template>
  <div class="intent-edit">
    <div class="page-head">
      <h2>{{ isEdit ? `编辑情报 #${id}` : "录入情报" }}</h2>
      <div class="head-actions">
        <el-button size="small" @click="router.back()">返回</el-button>
        <el-button size="small" :loading="saving" @click="save(false)">
          <el-icon><DocumentAdd /></el-icon>保存草稿
        </el-button>
        <el-button type="primary" size="small" :loading="saving" @click="save(true)">
          <el-icon><Promotion /></el-icon>保存并提交审核
        </el-button>
      </div>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-form :model="form" label-width="110px" class="edit-form">
        <el-row :gutter="16">
          <el-col :xs="24" :md="16">
            <el-form-item label="标题" required>
              <el-input v-model="form.title" placeholder="项目/意向标题" maxlength="512" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="项目阶段">
              <el-select v-model="form.stage" placeholder="选择阶段" clearable style="width: 100%">
                <el-option label="设计" value="设计" />
                <el-option label="动工" value="动工" />
                <el-option label="竣工" value="竣工" />
                <el-option label="竣工验收" value="竣工验收" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="行业">
              <el-select v-model="form.industry" placeholder="选择行业" clearable filterable style="width: 100%">
                <el-option v-for="c in catIndustry" :key="c.id" :label="c.label" :value="c.label" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="项目类型">
              <el-select v-model="form.project_type" placeholder="选择类型" clearable filterable style="width: 100%">
                <el-option v-for="c in catProjectType" :key="c.id" :label="c.label" :value="c.code" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="数据集">
              <el-select v-model="form.dataset_type" style="width: 100%">
                <el-option label="项目" value="project" />
                <el-option label="拟建" value="proposed" />
                <el-option label="土地交易" value="landTrade" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="发布部门">
              <el-input v-model="form.dept" placeholder="如: 四川省自然资源厅" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="预算金额(万)">
              <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="业务状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="最新" value="new" />
                <el-option label="合格" value="qualified" />
                <el-option label="跳过" value="skip" />
                <el-option label="过期" value="expired" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="省"><el-input v-model="form.province" /></el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="市"><el-input v-model="form.city" /></el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="县/区"><el-input v-model="form.county" /></el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="地域全称">
              <el-input v-model="form.region" placeholder="如: 四川省××县" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="拟开工时间">
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="发布时间">
              <el-date-picker v-model="form.published_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="原文链接">
          <el-input v-model="form.url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="联系人/电话">
          <el-input v-model="form.contact" placeholder="联系人/电话(仅后台可见)" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-select v-model="form.keywords" multiple filterable allow-create default-first-option placeholder="回车添加关键词" style="width: 100%">
            <el-option v-for="k in ['地质灾害','生态修复','地质勘察','矿山修复','监测预警']" :key="k" :label="k" :value="k" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">扩展展示字段(对应前台「项目概况」网格)</el-divider>
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="工程地址"><el-input v-model="ext.address" /></el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="招标类型">
              <el-select v-model="ext.tender_type" clearable style="width: 100%">
                <el-option label="公开招标" value="公开招标" />
                <el-option label="邀请招标" value="邀请招标" />
                <el-option label="竞争性磋商" value="竞争性磋商" />
                <el-option label="询价" value="询价" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="资金来源"><el-input v-model="ext.fund_source" /></el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="建筑规模(㎡)"><el-input v-model="ext.building_scale" /></el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="建筑层数"><el-input v-model="ext.floor_count" /></el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="建设性质">
              <el-select v-model="ext.nature" clearable style="width: 100%">
                <el-option label="新建" value="新建" />
                <el-option label="改扩建" value="改扩建" />
                <el-option label="重建" value="重建" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="项目代码"><el-input v-model="ext.project_code" /></el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="原文摘要">
          <el-input v-model="form.raw_text" type="textarea" :rows="8" placeholder="结构化原文" />
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { DocumentAdd, Promotion } from "@element-plus/icons-vue";
import api from "@/api";

const route = useRoute();
const router = useRouter();
const id = Number(route.params.id || 0);
const isEdit = computed(() => id > 0);

const loading = ref(false);
const saving = ref(false);
const catIndustry = ref<any[]>([]);
const catProjectType = ref<any[]>([]);

const form = reactive<Record<string, any>>({
  title: "", url: "", dept: "", industry: "", project_type: "",
  amount: null, region: "", province: "", city: "", county: "",
  contact: "", start_date: "", published_at: "", status: "new",
  keywords: [], raw_text: "", stage: "", dataset_type: "project",
});
const ext = reactive<Record<string, any>>({
  address: "", tender_type: "", fund_source: "",
  building_scale: "", floor_count: "", nature: "", project_code: "",
});

async function loadCategories() {
  try {
    const [ind, pt] = await Promise.all([
      api.get("/admin/intelligence/categories", { params: { category: "industry" } }),
      api.get("/admin/intelligence/categories", { params: { category: "project_type" } }),
    ]);
    catIndustry.value = ind?.success ? ind.items : [];
    catProjectType.value = pt?.success ? pt.items : [];
  } catch { /* 静默 */ }
}

async function loadDetail() {
  if (!isEdit.value) return;
  loading.value = true;
  try {
    const r: any = await api.get(`/admin/intelligence/${id}`);
    if (r?.success) {
      const d = r.data;
      Object.keys(form).forEach((k) => {
        if (k === "keywords") form[k] = d.keywords || [];
        else form[k] = d[k] ?? (k === "amount" ? null : "");
      });
      const attrs = d.ext_attrs || {};
      Object.keys(ext).forEach((k) => (ext[k] = attrs[k] ?? ""));
    }
  } finally {
    loading.value = false;
  }
}

function buildPayload() {
  return {
    title: form.title.trim(),
    url: form.url || null,
    dept: form.dept || null,
    industry: form.industry || null,
    project_type: form.project_type || null,
    amount: form.amount,
    region: form.region || null,
    province: form.province || null,
    city: form.city || null,
    county: form.county || null,
    contact: form.contact || null,
    start_date: form.start_date || null,
    published_at: form.published_at || null,
    status: form.status,
    keywords: form.keywords || [],
    raw_text: form.raw_text || null,
    stage: form.stage || null,
    dataset_type: form.dataset_type,
    ext_attrs: Object.values(ext).some((v) => v) ? { ...ext } : null,
  };
}

async function save(submit: boolean) {
  if (!form.title.trim()) {
    ElMessage.warning("请输入标题");
    return;
  }
  saving.value = true;
  try {
    const payload = buildPayload();
    let r: any;
    if (isEdit.value) {
      r = await api.put(`/admin/intelligence/${id}`, payload);
    } else {
      r = await api.post("/admin/intelligence", payload);
    }
    if (r?.success) {
      const nid = r.data?.id || id;
      ElMessage.success("已保存");
      if (submit) {
        const sr: any = await api.post(`/admin/intelligence/${nid}/submit`);
        if (sr?.success) {
          ElMessage.success("已提交审核");
          router.push("/workspace/intent-admin");
          return;
        }
      }
      if (!isEdit.value) {
        router.replace({ path: `/workspace/intent-admin/edit/${nid}` });
      }
    }
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadCategories();
  loadDetail();
});
</script>

<style scoped>
.intent-edit { padding: 4px 0 30px; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.page-head h2 { margin: 0; font-size: 16px; color: #1c2a3a; }
.head-actions { display: flex; gap: 8px; }
.edit-form { max-width: 1180px; }
</style>
