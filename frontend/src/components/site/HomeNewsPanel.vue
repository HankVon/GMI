<template>
  <section class="home-news-panel site-card">
    <div class="home-news-menu">
      <div class="home-module-title">最新信息</div>
      <button v-for="item in categories" :key="item.key" class="home-news-menu-item" :class="{ active: activeCategory === item.key }" @click="$emit('change-category', item.key)">
        <el-icon><component :is="item.icon" /></el-icon>{{ item.label }}
      </button>
      <button class="home-news-more" @click="$emit('more', activeCategory)">查看更多 <el-icon><ArrowRight /></el-icon></button>
    </div>
    <div class="home-news-content">
      <div class="home-news-head">
        <div>
          <span class="site-eyebrow">LIVE INFORMATION</span>
          <h2 class="site-h2">{{ currentCategory?.label || '最新信息' }}</h2>
        </div>
        <span class="home-news-update">{{ items.length }} 条实时更新</span>
      </div>
      <div v-if="items.length" class="home-company-matrix">
        <button v-for="item in items" :key="item.id" class="home-company-card" @click="$emit('select', item)">
          <span class="home-company-type">{{ item.type || currentCategory?.label || '动态' }}</span>
          <strong>{{ item.name || item.title }}</strong>
          <span class="home-company-meta">{{ item.province || item.region || '地域未披露' }} · {{ item.capital || item.amount || '信息待补充' }}</span>
          <span class="home-company-date">更新于 {{ item.updated_at || item.published_at || '—' }}</span>
        </button>
      </div>
      <el-empty v-else description="暂无该类更新" :image-size="70" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { ArrowRight, OfficeBuilding, Tickets, Files, User, Medal, Trophy, CircleCheck, DataAnalysis, Notification } from '@element-plus/icons-vue';

type Category = { key: string; label: string; icon: any };
const props = defineProps<{ activeCategory: string; items: any[] }>();
defineEmits<{ (event: 'change-category', value: string): void; (event: 'select', value: any): void; (event: 'more', value: string): void }>();
const categories: Category[] = [
  { key: 'companies', label: '企业更新', icon: OfficeBuilding },
  { key: 'intents', label: '最新意向', icon: Notification },
  { key: 'bids', label: '最新中标', icon: Trophy },
  { key: 'projects', label: '四库更新', icon: Files },
  { key: 'tenders', label: '最新招标', icon: Tickets },
  { key: 'persons', label: '人员更新', icon: User },
  { key: 'managers', label: '项目经理', icon: DataAnalysis },
  { key: 'qualifications', label: '资质更新', icon: Medal },
  { key: 'honors', label: '荣誉更新', icon: Trophy },
  { key: 'credit', label: '诚信更新', icon: CircleCheck },
];
const currentCategory = computed(() => categories.find((item) => item.key === props.activeCategory));
</script>

<style scoped>
.home-news-panel { display: grid; grid-template-columns: 190px 1fr; gap: 28px; padding: 26px; }
.home-news-menu { border-right: 1px solid var(--site-hairline); padding-right: 18px; }
.home-module-title { font-size: 18px; font-weight: 800; margin-bottom: 16px; }
.home-news-menu-item, .home-news-more { display: flex; align-items: center; gap: 8px; width: 100%; border: 0; background: transparent; color: var(--site-text-dim); padding: 10px 12px; border-radius: 6px; text-align: left; cursor: pointer; font-size: 13px; }
.home-news-menu-item:hover, .home-news-menu-item.active { background: var(--site-brand-soft); color: var(--site-brand); font-weight: 700; }
.home-news-more { margin-top: 12px; color: var(--site-brand); justify-content: center; }
.home-news-head { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid var(--site-hairline); padding-bottom: 12px; }
.home-news-head .site-h2 { font-size: 24px; margin: 0; }
.home-news-update { color: var(--site-text-mute); font-size: 12px; margin-top: 22px; }
.home-company-matrix { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding-top: 16px; }
.home-company-card { min-height: 118px; min-width: 0; text-align: left; background: #fff; border: 1px solid var(--site-hairline); border-radius: 6px; padding: 15px; cursor: pointer; display: flex; flex-direction: column; gap: 9px; transition: .2s; }
.home-company-card:hover { border-color: var(--site-brand); box-shadow: 0 12px 24px -12px rgba(200,16,46,0.35); transform: translateY(-2px); }
.home-company-type { color: var(--site-brand); font-size: 11px; }
.home-company-card strong {
  display: block;
  width: 100%;
  min-width: 0;
  color: var(--site-text);
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.home-company-meta, .home-company-date { color: var(--site-text-dim); font-size: 12px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.home-company-date { color: var(--site-text-mute); }
@media (max-width: 1100px) { .home-company-matrix { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) { .home-news-panel { grid-template-columns: 1fr; } .home-news-menu { border-right: 0; border-bottom: 1px solid var(--site-hairline); padding: 0 0 12px; display: flex; flex-wrap: wrap; gap: 4px; } .home-module-title { width: 100%; } .home-news-menu-item { width: auto; } .home-company-matrix { grid-template-columns: 1fr; } }
</style>
