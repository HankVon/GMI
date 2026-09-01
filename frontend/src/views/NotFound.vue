<template>
  <div class="nf-page">
    <div class="nf-card">
      <div class="nf-code">404</div>
      <div class="nf-title">页面不存在</div>
      <div class="nf-desc">您访问的页面可能已被移动、删除或地址有误。</div>
      <el-button type="primary" @click="back">{{ isSite ? "返回数据中心" : "返回工作台" }}</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
const route = useRoute();
const router = useRouter();
// 数据中心/官网侧(site)不往后台(workbench)引, 保持站内闭环; 后台侧才回工作台
const isSite = computed(() => String(route.path).startsWith("/site"));
function back() {
  router.push(isSite.value ? "/site/data-center" : "/workspace/projects");
}
</script>

<style scoped>
.nf-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1200px 400px at 100% 0%, rgba(165, 28, 48, 0.05) 0%, transparent 60%),
    #f0f3f8;
}
.nf-card {
  text-align: center;
  padding: 48px 64px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(60, 30, 30, 0.08);
}
.nf-code {
  font-size: 64px;
  font-weight: 800;
  color: #a51c30;
  letter-spacing: 4px;
}
.nf-title {
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
  margin: 12px 0 8px;
}
.nf-desc {
  font-size: 13.5px;
  color: #8c8784;
  margin-bottom: 24px;
}
</style>
