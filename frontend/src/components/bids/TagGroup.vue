<template>
  <span class="tag-group">
    <el-tag v-for="tag in tags" :key="`${tag.kind}-${tag.label}`" size="small" :type="tagType(tag.kind)" effect="light" :class="{ 'tag-gated': tag.isGated }" :title="tag.isGated ? '当前字段受权限限制' : undefined">
      <el-icon v-if="tag.icon"><component :is="tag.icon" /></el-icon>{{ tag.displayText || tag.label }}
    </el-tag>
  </span>
</template>
<script setup lang="ts">
type Tag = { label: string; displayText?: string; kind: "status" | "category" | "warning"; icon?: any; isGated?: boolean };
const props = defineProps<{ tags: Tag[] }>();
function tagType(kind: Tag["kind"]): "info" | "primary" | "danger" { return kind === "warning" ? "danger" : kind === "category" ? "primary" : "info"; }
</script>
<style scoped>
.tag-group { display: inline-flex; flex-wrap: wrap; gap: 5px; }
.el-icon { margin-right: 3px; vertical-align: -2px; }
.tag-gated { color: #c45656; }
</style>
