<template>
  <div class="site-page">
    <!-- 顶部主导航（编辑式学院风：白色 + 地质红 + 衬线 Logo） -->
    <header class="site-nav" :class="{ 'nav-scrolled': scrolled, 'nav-open': menuOpen }">
      <div class="site-container nav-inner">
        <router-link to="/site" class="nav-logo">
          <span class="logo-mark">地</span>
          <span class="logo-text">地质与产业情报平台<em>GEO · INTELLIGENCE</em></span>
        </router-link>

        <nav class="nav-links" :class="{ open: menuOpen }">
          <router-link to="/site" @click="menuOpen = false">首页</router-link>
          <router-link to="/site/intelligence" @click="menuOpen = false">项目商机</router-link>
          <router-link to="/site/data-center/overview" @click="menuOpen = false">标讯中心</router-link>
          <router-link to="/site/data-center/companies" @click="menuOpen = false">分项查询</router-link>
          <router-link to="/site/solutions" @click="menuOpen = false">解决方案</router-link>
          <router-link to="/site/about" @click="menuOpen = false">关于我们</router-link>
          <router-link to="/site/contact" @click="menuOpen = false">联系我们</router-link>
        </nav>

        <div class="nav-user">
          <!-- <router-link v-if="isLoggedIn" to="/site/account" class="nav-account-btn">
            <el-icon><UserFilled /></el-icon>
            <span>个人中心</span>
          </router-link> -->
          <template v-if="isLoggedIn">
            <el-dropdown trigger="click" @command="onUserCommand">
              <button class="nav-user-btn">
                <span class="nav-user-avatar">{{ avatarChar }}</span>
                <span class="nav-user-name">{{ displayName || username }}</span>
                <el-icon class="nav-user-arrow"><ArrowDown /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu class="nav-user-menu">
                  <el-dropdown-item command="account"><el-icon><UserFilled /></el-icon>个人中心</el-dropdown-item>
                  <el-dropdown-item command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <router-link v-else to="/login" class="nav-register-btn">登录</router-link>
        </div>

        <button class="nav-toggle" @click="menuOpen = !menuOpen" aria-label="菜单">
          <span></span><span></span><span></span>
        </button>
      </div>
    </header>

    <!-- 页面主体 -->
    <main class="site-main">
      <slot />
    </main>

    <SiteFloatTools @consult="router.push('/site/contact')" @feedback="router.push('/site/contact?type=feedback')" />

    <!-- 页脚（编辑式：多列 + 衬线标题 + 品牌红点缀） -->
    <footer class="site-footer">
      <div class="site-container footer-top">
        <div class="footer-brand">
          <div class="nav-logo">
            <span class="logo-mark">地</span>
            <span class="logo-text">地质与产业情报平台</span>
          </div>
          <p class="footer-desc">将分散在公开采购、招投标、工商与行业资讯中的海量数据，转化为可供政企单位直接使用的决策情报资产。</p>
        </div>
        <div class="footer-col">
          <h4>产品</h4>
          <a href="/site/intelligence">项目商机</a>
          <a href="/site/data-center/overview">标讯中心</a>
          <a href="/site/data-center/companies">单位画像</a>
          <a href="/site/solutions">解决方案</a>
        </div>
        <div class="footer-col">
          <h4>关于</h4>
          <a href="/site/about">关于我们</a>
          <a href="/site/about">发展历程</a>
          <a href="/site/solutions">核心能力</a>
          <a href="/site/contact">合作联系</a>
        </div>
        <div class="footer-col">
          <h4>联系</h4>
          <span class="footer-line">400-000-0000</span>
          <a href="mailto:contact@gmi.example">contact@gmi.example</a>
          <span class="footer-line">成都市 · 高新区</span>
          <span class="footer-line">工作日 9:00 - 18:00</span>
        </div>
      </div>
      <div class="site-container footer-bottom">
        <span>© 2026 地质与产业情报平台 · 保留所有权利</span>
        <div class="footer-bottom-right">
          <span class="footer-icp">数据来源均来自公开渠道 · 仅供行业研究参考</span>
          <router-link v-if="canEnterAdmin" to="/workspace/projects" class="footer-admin-link">
            <el-icon><Grid /></el-icon>
            <span>管理后台</span>
          </router-link>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { SwitchButton, ArrowDown, UserFilled, Grid } from "@element-plus/icons-vue";
import { useUserStore } from "@/stores/user";
import SiteFloatTools from "@/components/site/SiteFloatTools.vue";

const router = useRouter();
const userStore = useUserStore();

const scrolled = ref(false);
const menuOpen = ref(false);

const isLoggedIn = computed(() => !!userStore.token);
const username = computed(() => userStore.username || "");
const displayName = computed(() => userStore.displayName || "");
const avatarChar = computed(() => {
  const s = (displayName.value || username.value || "G").trim();
  return s.charAt(0).toUpperCase();
});
/** 具备任一后台菜单权限的内部账号, 才在页脚展示「管理后台」入口 */
const canEnterAdmin = computed(() => userStore.permissions.some((p) => p.startsWith("menu_")));

function onUserCommand(cmd: string) {
  if (cmd === "logout") {
    userStore.logout();
    router.push("/login");
  } else if (cmd === "account") {
    router.push("/site/account");
  }
}

function onScroll() {
  scrolled.value = window.scrollY > 30;
}
onMounted(() => {
  window.addEventListener("scroll", onScroll);
  onScroll();
});
onUnmounted(() => window.removeEventListener("scroll", onScroll));
</script>

<style scoped>
.site-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding: 18px 0;
  transition: all 0.3s ease;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--site-panel-border);
}
.site-nav.nav-scrolled {
  padding: 10px 0;
  box-shadow: 0 1px 12px rgba(20, 20, 20, 0.06);
}
.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.nav-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
}
.logo-mark {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--site-brand);
  color: #fff;
  font-weight: 800;
  font-size: 20px;
  font-family: var(--site-font-display);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px -8px rgba(200, 16, 46, 0.6);
}
.logo-text {
  display: flex;
  flex-direction: column;
  color: var(--site-text);
  font-size: 18px;
  font-weight: var(--fw-bold);
  font-family: var(--site-font-display);
  letter-spacing: 0.06em;
  line-height: 1.2;
}
.logo-text em {
  font-style: normal;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: var(--site-text-mute);
  margin-top: 2px;
}
.nav-links {
  display: flex;
  align-items: center;
  gap: 26px;
}
.nav-links a {
  color: var(--site-text-dim);
  text-decoration: none;
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
  letter-spacing: 0.03em;
  padding: 6px 2px;
  transition: color 0.2s ease;
  position: relative;
}
.nav-links a:hover {
  color: var(--site-brand);
}
.nav-links a.router-link-exact-active {
  color: var(--site-brand);
  font-weight: var(--fw-semibold);
}
.nav-links a.router-link-exact-active::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 2px;
  background: var(--site-brand);
  border-radius: 2px;
}
.nav-toggle {
  display: none;
  flex-direction: column;
  gap: 5px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
}
.nav-user {
  display: flex;
  align-items: center;
}
.nav-user-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--site-panel-border);
  background: #fff;
  border-radius: 999px;
  padding: 4px 12px 4px 5px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.nav-user-btn:hover {
  border-color: var(--site-brand);
  box-shadow: 0 4px 12px -6px rgba(200, 16, 46, 0.35);
}
.nav-account-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--site-text, #141414);
  text-decoration: none;
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #f0f2f5;
  transition: all 0.2s ease;
}
.nav-account-btn:hover {
  background: var(--site-brand);
  color: #fff;
}
.nav-user-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--site-brand);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-user-name {
  font-size: 13px;
  color: var(--site-text);
  font-weight: 500;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav-user-arrow {
  color: var(--site-text-mute);
  font-size: 12px;
}
.nav-register-btn {
  color: #fff !important;
  background: var(--site-brand);
  border-radius: 999px;
  padding: 8px 22px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  text-decoration: none;
  transition: background 0.2s ease;
}
.nav-register-btn:hover {
  background: var(--site-brand-dark);
}
.nav-register-btn::after {
  display: none !important;
}
.nav-toggle span {
  width: 24px;
  height: 2px;
  background: var(--site-text);
  border-radius: 2px;
  transition: all 0.3s ease;
}
.site-main {
  padding-top: 80px;
}

.site-footer {
  margin-top: 60px;
  background: #141414;
  color: rgba(255, 255, 255, 0.62);
  padding: 60px 0 24px;
}
.footer-top {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1.2fr;
  gap: 40px;
  padding-bottom: 40px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.footer-brand .logo-mark {
  background: var(--site-brand);
}
.footer-brand .logo-text {
  color: #fff;
}
.footer-desc {
  margin: 18px 0 0;
  font-size: 13.5px;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.55);
  max-width: 340px;
}
.footer-col h4 {
  font-size: 14px;
  color: #fff;
  margin: 0 0 18px;
  font-weight: var(--fw-semibold);
  font-family: var(--site-font-display);
  letter-spacing: 0.12em;
}
.footer-col a,
.footer-line {
  display: block;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.58);
  text-decoration: none;
  margin-bottom: 12px;
  transition: color 0.2s ease;
}
.footer-col a:hover {
  color: var(--site-brand-bright);
}
.footer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 22px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
.footer-icp {
  font-size: 11.5px;
}
.footer-bottom-right {
  display: flex;
  align-items: center;
  gap: 20px;
}
.footer-admin-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.62);
  text-decoration: none;
  padding: 5px 14px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.footer-admin-link:hover {
  color: #fff;
  border-color: var(--site-brand-bright);
  background: rgba(200, 16, 46, 0.2);
}

@media (max-width: 768px) {
  .nav-toggle {
    display: flex;
  }
  .nav-links {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    background: #fff;
    border-bottom: 1px solid var(--site-panel-border);
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease;
    box-shadow: 0 16px 30px -20px rgba(20, 20, 20, 0.2);
  }
  .nav-links.open {
    max-height: 480px;
  }
  .nav-links a {
    padding: 15px 24px;
    border-bottom: 1px solid var(--site-hairline);
  }
  .nav-links a.router-link-active::after {
    display: none;
  }
  .nav-user-name {
    display: none;
  }
  .logo-text {
    font-size: 15px;
  }
  .footer-top {
    grid-template-columns: 1fr 1fr;
    gap: 28px 20px;
  }
  .footer-bottom {
    flex-direction: column;
    gap: 10px;
    text-align: center;
  }
  .footer-bottom-right {
    flex-direction: column;
    gap: 10px;
  }
}
</style>
