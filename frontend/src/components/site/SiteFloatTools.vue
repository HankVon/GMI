<template>
  <aside class="site-float-tools" aria-label="快捷服务">
    <button title="在线咨询" @click="$emit('consult')"><el-icon><ChatDotRound /></el-icon><span>咨询</span></button>
    <button title="反馈" @click="$emit('feedback')"><el-icon><EditPen /></el-icon><span>反馈</span></button>
    <button title="回到顶部" @click="toTop"><el-icon><Top /></el-icon><span>顶部</span></button>
  </aside>
</template>
<script setup lang="ts">
import { ChatDotRound, EditPen, Top } from '@element-plus/icons-vue';
defineEmits<{ (event: 'consult'): void; (event: 'feedback'): void }>();
function toTop() { window.scrollTo({ top: 0, behavior: 'smooth' }); }
</script>
<style scoped>
.site-float-tools { position: fixed; right: 22px; top: 42%; z-index: 90; width: 48px; background: #fff; border: 1px solid #e5eaf2; box-shadow: 0 5px 20px rgba(34,54,82,.12); border-radius: 7px; overflow: hidden; }
.site-float-tools button { display: flex; flex-direction: column; align-items: center; gap: 3px; width: 100%; padding: 10px 2px; border: 0; border-bottom: 1px solid #edf0f5; background: #fff; color: #667085; cursor: pointer; font-size: 10px; }
.site-float-tools button:last-child { border-bottom: 0; }
.site-float-tools button:hover { color: #2876d1; background: #f5f9ff; }
.site-float-tools .el-icon { font-size: 17px; }
@media (max-width: 768px) { .site-float-tools { right: 8px; width: 42px; } }
</style>
