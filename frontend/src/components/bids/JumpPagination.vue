<template>
  <div class="jump-pagination"><el-pagination background layout="prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="$emit('change', $event)" /><el-input-number v-model="jumpPage" :min="1" :max="Math.max(1, Math.ceil(total / pageSize))" controls-position="right" /><el-button @click="$emit('change', jumpPage)">转到</el-button></div>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue';
const props = defineProps<{ total: number; page: number; pageSize: number; lastSortValue?: unknown }>();
const jumpPage = ref(props.page);
watch(() => props.page, (value) => { jumpPage.value = value; });
defineEmits<{ (event: 'change', page: number, lastSortValue?: unknown): void }>();
</script>
<style scoped>.jump-pagination { display: flex; gap: 10px; align-items: center; justify-content: flex-end; flex-wrap: wrap; }.jump-pagination .el-input-number { width: 115px; }</style>
