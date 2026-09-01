<template>
  <div class="me-page">
    <el-card shadow="never" style="max-width: 720px">
      <template #header>
        <div class="me-header">
          <span class="me-title">账号设置</span>
          <el-tag v-for="r in me.roles" :key="r" size="small" style="margin:0 4px">{{ r }}</el-tag>
        </div>
      </template>

      <!-- 基本信息 -->
      <el-descriptions :column="2" border size="small" style="margin-bottom:24px">
        <el-descriptions-item label="用户名">{{ me.username }}</el-descriptions-item>
        <el-descriptions-item label="显示名">{{ me.display_name }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag v-for="r in me.roles" :key="r" size="small" style="margin:2px">{{ r }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="权限数">{{ me.permissions?.length ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="人脉节点">
          <el-tag v-if="me.person_id" type="success" size="small" effect="light">已关联</el-tag>
          <el-tag v-else type="info" size="small" effect="light">未关联</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 资料编辑 -->
      <h3 class="me-section-title">个人资料</h3>
      <el-form :model="profileForm" label-width="90px">
        <el-form-item label="显示名">
          <el-input v-model="profileForm.display_name" maxlength="32" placeholder="你的姓名/昵称" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="profileForm.email" maxlength="64" placeholder="选填" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="profileForm.phone" maxlength="32" placeholder="选填" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
        </el-form-item>
      </el-form>

      <!-- 修改密码 -->
      <h3 class="me-section-title">修改密码</h3>
      <el-form :model="pwdForm" label-width="90px">
        <el-form-item label="原密码" required>
          <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="8-64位，须含字母和数字" />
        </el-form-item>
        <el-form-item label="确认新密码" required>
          <el-input v-model="pwdForm.confirm" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingPwd" @click="savePassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import api from "@/api";

const me = ref<any>({ username: "", display_name: "", roles: [], permissions: [], person_id: null });
const profileForm = ref({ display_name: "", email: "", phone: "" });
const pwdForm = ref({ old_password: "", new_password: "", confirm: "" });
const savingProfile = ref(false);
const savingPwd = ref(false);

async function loadMe() {
  try {
    const res: any = await api.get("/auth/me");
    me.value = res;
    profileForm.value = {
      display_name: res.display_name || "",
      email: res.email || "",
      phone: res.phone || "",
    };
  } catch { /* 拦截器提示 */ }
}

async function saveProfile() {
  savingProfile.value = true;
  try {
    await api.put("/me/profile", {
      display_name: profileForm.value.display_name,
      email: profileForm.value.email,
      phone: profileForm.value.phone,
    });
    ElMessage.success("资料已保存");
    // ★ P0-1: 账号尚未关联人员节点时, 保存资料后自动调 POST /network/me 创建并绑定「我」节点(一次完成录入+绑定)
    if (!me.value.person_id) {
      try {
        const r: any = await api.post("/network/me", {
          name: (profileForm.value.display_name || "").trim() || me.value.username,
          email: profileForm.value.email,
          phone: profileForm.value.phone,
        });
        if (r && r.person_id) me.value.person_id = r.person_id;
      } catch {
        ElMessage.warning("资料已保存, 但关联人脉节点失败, 可稍后在「我的信息」重试");
      }
    }
    loadMe();
  } catch { /* 拦截器提示 */ }
  finally { savingProfile.value = false; }
}

async function savePassword() {
  if (!pwdForm.value.old_password) return ElMessage.warning("请输入原密码");
  if (pwdForm.value.new_password.length < 8) return ElMessage.warning("新密码至少 8 位");
  if (pwdForm.value.new_password !== pwdForm.value.confirm) return ElMessage.warning("两次输入的新密码不一致");
  savingPwd.value = true;
  try {
    await api.put("/me/password", {
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    });
    ElMessage.success("密码修改成功，下次登录请使用新密码");
    pwdForm.value = { old_password: "", new_password: "", confirm: "" };
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "修改失败";
    ElMessage.error(typeof detail === "string" ? detail : "修改失败");
  } finally { savingPwd.value = false; }
}

onMounted(loadMe);
</script>

<style scoped>
.me-page { max-width: 760px; }
.me-header { display: flex; align-items: center; gap: 12px; }
.me-title { font-weight: 600; font-size: 16px; }
.me-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
  border-left: 3px solid var(--ssm-primary, #a51c30);
  padding-left: 10px;
  margin: 22px 0 16px;
}
</style>
