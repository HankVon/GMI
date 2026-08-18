<template>
  <div class="login-page">
    <div class="login-bg-decor decor-1" />
    <div class="login-bg-decor decor-2" />
    <div class="login-card">
      <div class="login-logo">
        <div class="login-logo-icon">
          <el-icon :size="26"><DataAnalysis /></el-icon>
        </div>
        <div>
          <div class="login-title">GMI 数据平台</div>
          <div class="login-subtitle">统一商情数据中台</div>
        </div>
      </div>
      <el-form :model="form" label-width="0" class="login-form">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" @keyup.enter="handleLogin">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="handleLogin">
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" :loading="loading" size="large" style="width: 100%" @click="handleLogin">
          登 录
        </el-button>
      </el-form>
      <div class="login-footer">© 2026 GMI · 内部使用</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useUserStore } from "@/stores/user";
import { DataAnalysis, User, Lock } from "@element-plus/icons-vue";

const router = useRouter();
const userStore = useUserStore();
const loading = ref(false);
const form = ref({ username: "", password: "" });

async function handleLogin() {
  loading.value = true;
  try {
    await userStore.login(form.value.username, form.value.password);
    ElMessage.success("登录成功");
    router.push("/workspace/business");
  } catch {
    // 错误由拦截器处理
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(900px 500px at 80% -10%, rgba(41, 121, 255, 0.18) 0%, transparent 60%),
    radial-gradient(700px 400px at 10% 110%, rgba(79, 138, 255, 0.14) 0%, transparent 60%),
    linear-gradient(135deg, #f4f8ff 0%, #e8f0ff 50%, #f2f6ff 100%);
}
.login-bg-decor {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.5;
}
.decor-1 {
  width: 320px;
  height: 320px;
  top: -80px;
  right: -60px;
  background: rgba(41, 121, 255, 0.25);
}
.decor-2 {
  width: 260px;
  height: 260px;
  bottom: -60px;
  left: -40px;
  background: rgba(79, 138, 255, 0.2);
}
.login-card {
  width: 420px;
  padding: 36px 40px 28px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border: 1px solid #e8edf8;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(30, 60, 114, 0.12);
  position: relative;
  z-index: 1;
}
.login-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 28px;
}
.login-logo-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2979ff, #4f8aff);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 6px 16px rgba(41, 121, 255, 0.3);
}
.login-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2d3d;
  letter-spacing: 1px;
}
.login-subtitle {
  font-size: 12.5px;
  color: #909399;
  margin-top: 3px;
}
.login-form {
  margin-top: 8px;
}
.login-footer {
  text-align: center;
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 22px;
}
</style>
