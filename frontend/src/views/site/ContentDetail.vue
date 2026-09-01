<template>
  <SiteLayout>
    <main class="content-detail site-container">
      <el-page-header content="行业内容详情" @back="router.back" />
      <div v-loading="loading" class="content-shell site-card">
        <el-empty v-if="!loading && !item" description="内容不存在或尚未发布" />
        <template v-else-if="item">
          <span class="site-eyebrow">{{ item.kind || '行业分析' }}</span>
          <h1>{{ item.title }}</h1>
          <div class="content-meta">发布时间：{{ item.published_at || '—' }}</div>
          <p v-if="item.summary" class="summary">{{ item.summary }}</p>
          <article class="markdown-body">{{ item.content || '暂无正文内容' }}</article>
        </template>
      </div>
    </main>
  </SiteLayout>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import SiteLayout from '@/components/site/SiteLayout.vue';
import api from '@/api';
const route = useRoute(); const router = useRouter();
const loading = ref(true); const item = ref<any>(null);
onMounted(async () => { try { const result: any = await api.get(`/public/home/content/${route.params.id}`); item.value = result?.item || result?.data || null; } finally { loading.value = false; } });
</script>
<style scoped>
.content-detail { min-height: 70vh; padding-top: 108px; padding-bottom: 60px; }
.content-shell { max-width: 900px; margin: 24px auto 0; padding: 38px 46px; }
h1 { margin: 16px 0 10px; font-size: 30px; color: var(--site-text); }
.content-meta { color: var(--site-text-mute); font-size: 12px; }
.summary { margin: 28px 0; padding: 16px; background: var(--site-bg); color: var(--site-text-dim); line-height: 1.8; }
.markdown-body { white-space: pre-wrap; line-height: 2; color: var(--site-text-dim); margin-top: 28px; }
@media (max-width: 768px) { .content-shell { padding: 24px 18px; } h1 { font-size: 24px; } }
</style>
