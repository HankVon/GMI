<template>
  <SiteLayout>
    <!-- portal-page: 前台数据中心页面容器, 负责子路由内容水平居中(详情页等带 max-width 的根元素) -->
    <div class="portal-page">
      <router-view v-slot="{ Component, route }">
        <transition name="fade-slide" mode="out-in">
          <!-- 缓存数据中心页(保持 tab/分页状态) + 三个详情页(返回时秒开, 避免重新挂载加载数据慢);
               :key 按完整路径区分不同 id 的详情实例, 返回已看过的详情直接命中缓存 -->
          <keep-alive :include="['DataCenter', 'CompanyDetail', 'PersonProfile', 'ProjectDetail', 'BidDetail']">
            <component :is="Component" :key="route.fullPath" />
          </keep-alive>
        </transition>
      </router-view>
    </div>
  </SiteLayout>
</template>

<script setup lang="ts">
import SiteLayout from "@/components/site/SiteLayout.vue";
</script>

<style scoped>
/* 让子路由根元素(详情页/列表页等带 max-width 的块级元素)在容器内水平居中 */
.portal-page {
  width: 100%;
}
.portal-page :deep(> *) {
  margin-left: auto;
  margin-right: auto;
}
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
