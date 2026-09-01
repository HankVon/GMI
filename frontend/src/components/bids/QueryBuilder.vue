<template>
  <section class="query-builder">
    <div class="quick-row">
      <span class="filter-label">标讯类型</span>
      <el-radio-group v-model="store.state.noticeType"><el-radio-button label="">不限</el-radio-button><el-radio-button label="招标">招标</el-radio-button><el-radio-button label="中标">中标</el-radio-button><el-radio-button label="成交">成交</el-radio-button></el-radio-group>
    </div>
    <div class="form-grid">
      <el-input v-model="store.state.keyword" placeholder="标题、项目编号或关键词" clearable />
      <el-select v-model="store.state.province" placeholder="地区" clearable><el-option v-for="item in provinces" :key="item" :label="item" :value="item" /></el-select>
      <el-input v-model="store.state.purchaserKeyword" placeholder="招标单位" clearable />
      <el-input v-model="store.state.supplierKeyword" placeholder="中标单位" clearable />
      <el-input v-model="store.state.amountMin" placeholder="最低金额（万）" clearable />
      <el-input v-model="store.state.amountMax" placeholder="最高金额（万）" clearable />
    </div>
    <el-collapse-transition><div v-show="store.moreExpanded" class="advanced-panel">
      <div class="keyword-title"><span>动态关键词</span><el-button link type="primary" @click="store.addKeyword">+ 添加条件</el-button></div>
      <div v-for="(condition, index) in store.state.keywords" :key="index" class="keyword-row">
        <el-select v-if="index > 0" v-model="condition.operator" style="width: 90px"><el-option label="AND" value="AND" /><el-option label="OR" value="OR" /></el-select><span v-else class="keyword-where">条件</span>
        <el-input v-model="condition.value" placeholder="输入关键词" clearable /><el-button link type="danger" :disabled="store.state.keywords.length === 1" @click="store.removeKeyword(index)">删除</el-button>
      </div>
      <el-checkbox v-model="store.state.onlyMatched">仅查看已关联单位</el-checkbox>
    </div></el-collapse-transition>
    <div class="builder-actions"><el-button link @click="store.moreExpanded = !store.moreExpanded">{{ store.moreExpanded ? '收起更多筛选' : '更多筛选' }}</el-button><span class="action-spacer" /><el-button @click="store.reset">重置</el-button><el-button type="primary" @click="$emit('search')">查询</el-button><el-button @click="$emit('save')">保存筛选条件</el-button></div>
  </section>
</template>
<script setup lang="ts">
import { useBidFilterStore } from '@/stores/bidFilter';
const store = useBidFilterStore();
defineEmits<{ (event: 'search'): void; (event: 'save'): void }>();
const provinces = ['北京','上海','重庆','四川','贵州','云南','西藏','陕西','甘肃','青海','新疆','广东','江苏','浙江'];
</script>
<style scoped>
.query-builder { padding: 20px; background: #fff; border: 1px solid #e6eaf0; border-radius: 8px; }
.quick-row, .builder-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.filter-label { color: #667085; font-size: 13px; min-width: 65px; }.form-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 18px; }.advanced-panel { margin-top: 16px; padding: 16px; background: #f8fafc; border-radius: 6px; }.keyword-title { display: flex; justify-content: space-between; margin-bottom: 10px; }.keyword-row { display: flex; gap: 8px; margin-bottom: 8px; }.keyword-row .el-input { flex: 1; }.keyword-where { width: 90px; text-align: center; color: #667085; padding-top: 8px; }.builder-actions { margin-top: 18px; }.action-spacer { flex: 1; }
@media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } .quick-row { align-items: flex-start; flex-direction: column; } }
</style>
