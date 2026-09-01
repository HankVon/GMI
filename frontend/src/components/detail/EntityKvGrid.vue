<script setup lang="ts">
/**
 * 通用实体详情 KV 网格。
 *
 * 直接消费后端 DetailKvItem 契约({ label, field:{value,displayText,isGated}, entity, wide }),
 * 标讯 / 公司 / 人员 / 项目 / 情报等详情页共用同一份渲染与样式。
 *
 * 新增展示字段只需后端在 kv 里加一项, 前端零改动。
 */
export interface KvField {
  value?: unknown;
  displayText?: string;
  isGated?: boolean;
}
export interface KvEntity {
  entityId?: number | null;
  entityType?: string;
  name?: string;
  href?: string | null;
  matched?: boolean;
}
export interface KvItem {
  label: string;
  field?: KvField;
  entity?: KvEntity | null;
  /** 空值原因说明(如工商字段"不可探查"及建议), 有值时在值下方显示提示行 */
  note?: { reason?: string; suggest?: string } | null;
  wide?: boolean;
}

const props = withDefaults(
  defineProps<{
    items?: KvItem[];
    /** 列数(桌面端); 移动端自动降为 2 / 1 列 */
    columns?: number;
    /** grid=带边框标签列(基本信息) | plain=浅底色块(关键时间等) */
    variant?: 'grid' | 'plain';
    /** 无值时的兜底文案 */
    fallback?: string;
    /** 强制占满整行的标签 */
    wideLabels?: string[];
    /** 空数据提示 */
    emptyText?: string;
  }>(),
  {
    items: () => [],
    columns: 3,
    variant: 'grid',
    fallback: '未披露',
    wideLabels: () => ['建设规模', '招标范围', '项目内容', '建设内容', '备注', '其他'],
    emptyText: '',
  },
);

import { InfoFilled } from '@element-plus/icons-vue';

const emit = defineEmits<{ (e: 'entity-click', entity: KvEntity): void }>();

function isWide(item: KvItem): boolean {
  return Boolean(item.wide) || props.wideLabels.includes(item.label);
}
function displayText(item: KvItem): string {
  return item.field?.displayText || props.fallback;
}
function isGated(item: KvItem): boolean {
  return Boolean(item.field?.isGated);
}
function isLink(item: KvItem): boolean {
  return Boolean(item.entity?.matched && item.entity?.entityId);
}
function onClickEntity(item: KvItem) {
  if (item.entity) emit('entity-click', item.entity);
}
</script>

<template>
  <div
    v-if="items.length"
    class="entity-kv-grid"
    :class="[`variant-${variant}`, `cols-${columns}`]"
  >
    <div
      v-for="(item, idx) in items"
      :key="`${item.label}-${idx}`"
      :class="['entity-kv-item', { wide: isWide(item) }]"
    >
      <span class="entity-kv-label">{{ item.label }}</span>
      <div class="entity-kv-value">
        <a
          v-if="isLink(item)"
          class="entity-link"
          @click.prevent="onClickEntity(item)"
        >{{ item.entity?.name || displayText(item) }}</a>
        <b v-else :class="{ 'is-gated': isGated(item) }">{{ displayText(item) }}</b>
        <div
          v-if="item.note?.reason"
          class="entity-kv-note"
          :title="`原因：${item.note.reason}${item.note.suggest ? `\n建议：${item.note.suggest}` : ''}`"
        >
          <el-icon><InfoFilled /></el-icon>
          <span>不可探查：{{ item.note.reason }}</span>
        </div>
      </div>
    </div>
  </div>
  <div v-else-if="emptyText" class="entity-kv-empty">{{ emptyText }}</div>
</template>

<style scoped>
.entity-kv-grid {
  display: grid;
  border-top: 1px solid #e3eaf3;
  border-left: 1px solid #e3eaf3;
  border-radius: 4px;
  overflow: hidden;
}
.entity-kv-grid.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.entity-kv-grid.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.entity-kv-grid.cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

/* ---------- variant: grid ---------- */
.variant-grid .entity-kv-item {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
  min-height: 44px;
  border-right: 1px solid #e3eaf3;
  border-bottom: 1px solid #e3eaf3;
  font-size: 13px;
}
.variant-grid .entity-kv-item.wide {
  grid-column: 1 / -1;
}
.variant-grid .entity-kv-item.wide .entity-kv-value {
  min-height: 44px;
  padding: 10px 14px;
  align-items: flex-start;
  line-height: 1.75;
}
.variant-grid .entity-kv-label {
  display: flex;
  align-items: center;
  padding: 0 12px;
  color: #3b6fb6;
  background: #eef6ff;
  border-right: 1px solid #d6e5f3;
}

/* ---------- variant: plain ---------- */
.variant-plain {
  border: 1px solid #e3eaf3;
}
.variant-plain .entity-kv-item {
  padding: 10px 14px;
  border-right: 1px solid #e3eaf3;
  border-bottom: 1px solid #e3eaf3;
  background: #fafcff;
  min-height: 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}
.variant-plain .entity-kv-item.wide { grid-column: 1 / -1; }
.variant-plain .entity-kv-label {
  font-size: 12px;
  color: #909399;
}
.variant-plain .entity-kv-value b {
  font-size: 13px;
  color: #1f2d3d;
}

/* ---------- 共用 ---------- */
.entity-kv-value {
  display: flex;
  align-items: center;
  padding: 0 14px;
  color: var(--site-text);
  font-weight: 500;
  word-break: break-word;
  min-width: 0;
}
.entity-kv-value b {
  font-weight: 500;
  word-break: break-word;
  font-size: 13px;
}
.entity-kv-value .is-gated { color: #c45656; }
.entity-link {
  color: #3b6fb6;
  cursor: pointer;
  text-decoration: none;
  font-weight: 500;
}
.entity-link:hover { text-decoration: underline; }
.entity-kv-note {
  flex-basis: 100%;
  display: inline-flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 12px;
  color: #c45656;
  line-height: 1.4;
  cursor: help;
}
.entity-kv-note :deep(.el-icon) { font-size: 13px; margin-top: 1px; flex-shrink: 0; }
.entity-kv-empty {
  padding: 14px;
  color: var(--site-text-mute, #909399);
  font-size: 13px;
  text-align: center;
  background: #fafcff;
  border: 1px solid #e3eaf3;
  border-radius: 4px;
}

/* ---------- 响应式 ---------- */
@media (max-width: 900px) {
  .entity-kv-grid.cols-3,
  .entity-kv-grid.cols-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .entity-kv-grid.cols-2,
  .entity-kv-grid.cols-3,
  .entity-kv-grid.cols-4 { grid-template-columns: minmax(0, 1fr); }
  .variant-grid .entity-kv-item { grid-template-columns: 86px minmax(0, 1fr); }
}
</style>
