<template>
  <section class="home-ranking">
    <div class="section-head ranking-head">
      <div><span class="site-eyebrow">COMPANY RANKING</span><h2 class="site-h2">建企竞争力排行榜</h2><p class="site-sub">综合实力、中标数量和中标金额三个维度联动分析。</p></div>
      <el-select v-model="province" placeholder="选择地区" style="width: 140px" @change="load">
        <el-option v-for="item in provinces" :key="item" :label="item" :value="item" />
      </el-select>
    </div>
    <div class="ranking-grid">
      <div v-for="board in boards" :key="board.key" class="ranking-board site-card">
        <div class="ranking-board-title">{{ board.title }}<span>{{ board.unit }}</span></div>
        <button v-for="(row, index) in board.items" :key="row.company_id || row.name" class="ranking-row" @click="$emit('select-company', row.company_id)">
          <i :class="{ medal: index < 3 }">{{ index + 1 }}</i><strong>{{ row.name }}</strong><b>{{ row.value }}{{ board.unit }}</b>
        </button>
        <el-empty v-if="!board.items.length" description="暂无该地区排行" :image-size="55" />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import siteApi from '@/api/siteApi';
const emit = defineEmits<{ (event: 'select-company', id?: number): void }>();
const province = ref('四川');
const provinces = ['四川', '西藏', '新疆', '云南', '贵州', '重庆', '陕西'];
const data = ref<any>({ strength: [], count: [], amount: [] });
const boards = computed(() => [
  { key: 'strength', title: `${province.value}企业综合实力榜`, unit: '分', items: data.value.strength || [] },
  { key: 'count', title: `${province.value}项目中标数量榜`, unit: '个', items: data.value.count || [] },
  { key: 'amount', title: `${province.value}项目中标金额榜`, unit: '万', items: data.value.amount || [] },
]);
async function load() { try { const result: any = await siteApi.get('/public/home/rankings', { params: { province: province.value, limit: 10 } }); data.value = result?.data || result || {}; } catch { data.value = { strength: [], count: [], amount: [] }; } }
onMounted(load);
</script>

<style scoped>
.home-ranking { padding: 78px 0; }
.ranking-head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 28px; }
.ranking-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.ranking-board { padding: 20px; }
.ranking-board-title { font-weight: 800; padding-bottom: 15px; border-bottom: 1px solid var(--site-hairline); }
.ranking-board-title span { float: right; font-weight: 400; color: var(--site-text-mute); font-size: 12px; }
.ranking-row { display: flex; align-items: center; gap: 10px; width: 100%; border: 0; border-bottom: 1px dashed var(--site-hairline); background: transparent; padding: 12px 0; cursor: pointer; text-align: left; }
.ranking-row i { width: 24px; height: 24px; border-radius: 4px; display: grid; place-items: center; background: #f1f3f6; color: var(--site-text-dim); font-style: normal; font-size: 12px; }
.ranking-row i.medal { background: var(--site-brand-soft); color: var(--site-brand); font-weight: 800; }
.ranking-row strong { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; color: var(--site-text); font-size: 13px; }
.ranking-row b { color: var(--site-brand); font-size: 12px; flex-shrink: 0; }
@media (max-width: 1100px) { .ranking-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) { .ranking-head { align-items: flex-start; gap: 16px; flex-direction: column; } .ranking-grid { grid-template-columns: 1fr; } }
</style>
