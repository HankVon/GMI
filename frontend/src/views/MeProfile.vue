<template>
  <div class="me-page">
    <el-card shadow="never" style="max-width: 680px">
      <template #header>
        <div class="me-header">
          <span class="me-title">我的信息</span>
          <el-tag v-if="saved" type="success" size="small" effect="light">
            <el-icon style="vertical-align: -2px; margin-right: 4px"><CircleCheck /></el-icon>已保存并关联为人脉源节点
          </el-tag>
          <el-tag v-else type="danger" size="small" effect="light">
            <el-icon style="vertical-align: -2px; margin-right: 4px"><CircleClose /></el-icon>未录入
          </el-tag>
        </div>
      </template>

      <el-alert
        type="info" show-icon :closable="false" style="margin-bottom: 16px"
        title="这里的「我」是人脉查询的源节点。录入后，点击任意人员的「查看人脉」即可从你出发，展示经过哪些项目/单位/合作找到对方。"
      />

      <el-form ref="formRef" :model="form" label-width="90px" :rules="rules">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入你的姓名" />
        </el-form-item>
        <el-form-item label="职位" prop="position">
          <el-input v-model="form.position" placeholder="如：项目经理 / 高级地质工程师" />
        </el-form-item>
        <el-form-item label="所属单位">
          <el-select
            v-model="form.company_id"
            filterable remote clearable
            placeholder="输入单位名搜索(如: 第五地质大队)"
            style="width: 100%"
            :remote-method="loadCompanies"
            :loading="companyLoading"
          >
            <el-option v-for="c in companyOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="选填" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="在职" value="active" />
            <el-option label="离职" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>

      <div class="me-actions">
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { CircleCheck, CircleClose } from "@element-plus/icons-vue";
import api from "@/api";

const form = ref<any>({
  name: "", position: "", company_id: null, email: "", phone: "", status: "active",
});
const companyOptions = ref<any[]>([]);
const companyLoading = ref(false);
const saving = ref(false);
const saved = ref(false);
const formRef = ref<any>(null);
const rules = {
  name: [{ required: true, message: "姓名为必填项", trigger: "blur" }],
  position: [{ required: false }],
};

async function loadMe() {
  try {
    const res: any = await api.get("/network/me");
    saved.value = !!res.linked;
    if (res.linked) {
      form.value = {
        name: res.name || "",
        position: res.position || "",
        company_id: res.company_id ?? null,
        email: res.email || "",
        phone: res.phone || "",
        status: res.status || "active",
      };
    }
  } catch (e: any) {
    // 拦截器已 ElMessage 提示过, 这里只把状态置为未录入, 不再额外弹窗
    saved.value = false;
  }
}

async function loadCompanies(q: string) {
  companyLoading.value = true;
  try {
    const res: any = await api.get("/companies", {
      params: { page_size: 50, keyword: q || undefined },
    });
    companyOptions.value = res.items || [];
  } catch { companyOptions.value = []; }
  finally { companyLoading.value = false; }
}

async function save() {
  try { await formRef.value.validate(); } catch { return; }
  saving.value = true;
  try {
    await api.post("/network/me", {
      name: form.value.name,
      position: form.value.position,
      company_id: form.value.company_id || null,
      email: form.value.email,
      phone: form.value.phone,
      status: form.value.status,
    });
    ElMessage.success("已保存");
    saved.value = true;
    loadMe();
  } catch { /* 拦截器处理 */ }
  finally { saving.value = false; }
}

onMounted(() => { loadMe(); loadCompanies(); });
</script>

<style scoped>
.me-page { max-width: 760px; }
.me-header { display: flex; align-items: center; gap: 12px; }
.me-title { font-weight: 600; font-size: 16px; }
.me-actions { display: flex; justify-content: flex-end; padding-top: 8px; }
</style>
