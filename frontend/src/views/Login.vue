<template>
  <div class="login-page">
    <!-- 背景: 网格 + 光晕 + 米白渐变(前台主题) -->
    <div class="login-bg">
      <div class="grid-overlay"></div>
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>
      <div class="glow glow-3"></div>
    </div>

    <div class="login-shell">
      <!-- 左侧品牌区 -->
      <div class="login-brand">
        <div class="brand-mark">
          <el-icon :size="30"><DataAnalysis /></el-icon>
        </div>
        <div class="brand-name">{{ mode === 'portal' ? 'GMI 数据平台' : 'GMI 管理后台' }}</div>
        <div class="brand-tag">统一商情数据中台</div>
        <div class="brand-line"></div>
        <p class="brand-desc">
          汇聚招投标、单位画像、人脉网络与 AI 情报分析，<br />
          将分散的公开数据转化为可决策的情报资产。
        </p>
        <div class="brand-tags">
          <span>地质</span><span>产业</span><span>情报</span><span>AI 研判</span>
        </div>
      </div>

      <!-- 右侧登录卡片 -->
      <div class="login-card">
        <div class="login-switch">
          <router-link :to="switchTo" class="switch-link">{{ switchText }}</router-link>
        </div>
        <div class="card-eyebrow">{{ mode === 'portal' ? 'WELCOME TO PORTAL' : 'ADMIN CONSOLE' }}</div>
        <h2 class="card-title">{{ mode === 'portal' ? '前台账号登录' : '管理后台登录' }}</h2>
        <p class="card-sub">{{ mode === 'portal' ? '登录后访问数据中心、情报动态等完整功能' : '登录后进入后台管理系统，进行数据与管理操作' }}</p>

        <el-form :model="form" label-width="0" class="login-form" @submit.prevent="handleLogin">
          <el-form-item>
            <el-input
              v-model="form.username"
              placeholder="用户名"
              size="large"
              class="login-input"
              @keyup.enter="handleLogin"
            >
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              size="large"
              class="login-input"
              show-password
              @keyup.enter="handleLogin"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-button type="primary" :loading="loading" size="large" class="login-btn" @click="handleLogin">
            {{ mode === 'portal' ? '登 录' : '登录后台' }}
          </el-button>
        </el-form>

        <div class="login-footer">© 2026 GMI · 内部使用</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useUserStore } from "@/stores/user";
import { DataAnalysis, User, Lock } from "@element-plus/icons-vue";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const loading = ref(false);
const form = ref({ username: "", password: "" });

// 区分前台/后台登录: redirect 指向后台工作区则为后台模式
const mode = computed<"portal" | "admin">(() => {
  const redirect = (route.query.redirect as string) || "";
  if (redirect.startsWith("/workspace") || redirect.startsWith("/admin") || redirect.startsWith("/me")) {
    return "admin";
  }
  return "portal";
});
const switchTo = computed(() => {
  return mode.value === "portal"
    ? "/login?redirect=/workspace/projects"
    : "/login";
});
const switchText = computed(() => {
  return mode.value === "portal" ? "前往管理后台 →" : "← 返回前台登录";
});

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }
  loading.value = true;
  try {
    await userStore.login(form.value.username, form.value.password);
    ElMessage.success("登录成功");
    // 支持从数据中心等受保护页跳转过来时回跳原页面
    const redirect = (route.query.redirect as string) || "";
    if (redirect && redirect.startsWith("/")) {
      router.push(redirect);
    } else {
      router.push(mode.value === "admin" ? "/workspace/projects" : "/site");
    }
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
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 24px;
  background:
    radial-gradient(1000px 600px at 85% -10%, rgba(192, 57, 77, 0.08) 0%, transparent 55%),
    radial-gradient(900px 500px at 5% 110%, rgba(165, 28, 48, 0.10) 0%, transparent 60%),
    linear-gradient(160deg, #fbfaf9 0%, #f1efec 100%);
}
/* 背景装饰 */
.login-bg { position: absolute; inset: 0; z-index: 0; }
.grid-overlay {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(165, 28, 48, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(165, 28, 48, 0.045) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: radial-gradient(ellipse at 70% 30%, #000 25%, transparent 78%);
}
.glow { position: absolute; border-radius: 50%; filter: blur(90px); }
.glow-1 { width: 380px; height: 380px; background: rgba(165, 28, 48, 0.18); top: -100px; left: 8%; }
.glow-2 { width: 420px; height: 420px; background: rgba(192, 57, 77, 0.14); bottom: -120px; right: 5%; }
.glow-3 { width: 260px; height: 260px; background: rgba(165, 28, 48, 0.10); top: 45%; left: 55%; }

/* 主体: 左品牌 + 右卡片 */
.login-shell {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: stretch;
  width: min(900px, 100%);
  border-radius: 20px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(236, 232, 228, 0.9);
  box-shadow: 0 24px 80px rgba(60, 20, 20, 0.14);
}
/* 左侧品牌区 */
.login-brand {
  flex: 1.1;
  padding: 52px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: var(--site-grad);
  color: #fff;
  position: relative;
  overflow: hidden;
}
.login-brand::before {
  content: "";
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.07) 1px, transparent 1px);
  background-size: 40px 40px;
}
.login-brand::after {
  content: "";
  position: absolute;
  width: 320px; height: 320px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.10);
  filter: blur(60px);
  bottom: -80px; right: -80px;
}
.login-brand > * { position: relative; z-index: 1; }
.brand-mark {
  width: 58px; height: 58px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(6px);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 22px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}
.brand-name { font-size: 26px; font-weight: 800; letter-spacing: 1px; }
.brand-tag { font-size: 13px; opacity: 0.85; margin-top: 6px; letter-spacing: 2px; }
.brand-line { width: 52px; height: 3px; border-radius: 2px; background: rgba(255, 255, 255, 0.85); margin: 24px 0 18px; }
.brand-desc { font-size: 14px; line-height: 1.9; opacity: 0.92; margin: 0; }
.brand-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 26px; }
.brand-tags span {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(4px);
  letter-spacing: 1px;
}

/* 右侧登录卡片 */
.login-card { flex: 1; padding: 52px 48px; display: flex; flex-direction: column; justify-content: center; position: relative; }
.login-switch { position: absolute; top: 22px; right: 26px; }
.switch-link {
  font-size: 12.5px;
  color: var(--site-text-mute);
  text-decoration: none;
  padding: 5px 12px;
  border: 1px solid #e7e2dc;
  border-radius: 18px;
  transition: all 0.2s ease;
  background: #fff;
}
.switch-link:hover { color: var(--site-brand); border-color: var(--site-brand); }
.card-eyebrow { font-size: 11px; letter-spacing: 3px; color: var(--site-brand); font-weight: 700; }
.card-title { font-size: 26px; font-weight: 800; color: var(--site-text); margin: 10px 0 6px; }
.card-sub { font-size: 13.5px; color: var(--site-text-mute); margin: 0 0 28px; }
.login-input :deep(.el-input__wrapper) {
  background: #faf9f8;
  box-shadow: 0 0 0 1px #e7e2dc inset;
  border-radius: 10px;
  height: 46px;
  transition: box-shadow 0.2s ease;
}
.login-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--site-brand) inset, 0 3px 10px rgba(165, 28, 48, 0.08);
  background: #fff;
}
.login-input :deep(.el-input__prefix) { color: var(--site-text-mute); }
.login-input :deep(.el-input__inner) { font-size: 14.5px; }
.login-btn {
  width: 100%;
  height: 46px;
  font-size: 15px;
  letter-spacing: 6px;
  border-radius: 10px;
  margin-top: 6px;
  background: var(--site-grad);
  border: none;
  font-weight: 700;
  box-shadow: 0 8px 20px rgba(165, 28, 48, 0.28);
  transition: all 0.2s ease;
}
.login-btn:hover { transform: translateY(-1px); box-shadow: 0 10px 26px rgba(165, 28, 48, 0.34); opacity: 0.97; }
.login-footer { text-align: center; font-size: 12px; color: var(--site-text-mute); margin-top: 26px; }

@media (max-width: 720px) {
  .login-brand { display: none; }
  .login-shell { border-radius: 16px; }
  .login-card { padding: 40px 30px; }
}
</style>
