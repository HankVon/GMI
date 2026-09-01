<template>
  <span class="fav-wrap">
    <el-button
      :type="active ? 'warning' : 'default'"
      size="small"
      :icon="Star"
      @click="toggle"
    >{{ active ? '已收藏' : '收藏' }}</el-button>

    <el-popover placement="bottom" :width="280" trigger="click">
      <template #reference>
        <el-button size="small" :icon="CollectionTag">标签</el-button>
      </template>
      <div class="fav-tags">
        <div v-if="tags.length" class="fav-tag-list">
          <el-tag
            v-for="t in tags"
            :key="t"
            closable
            size="small"
            type="primary"
            effect="plain"
            @close="delTag(t)"
          >{{ t }}</el-tag>
        </div>
        <div v-else class="fav-tag-empty">暂无标签</div>
        <el-input
          v-model="newTag"
          size="small"
          placeholder="输入标签后回车"
          maxlength="20"
          show-word-limit
          style="margin-top: 8px"
          @keyup.enter="addTag"
        />
      </div>
    </el-popover>
  </span>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Star, CollectionTag } from "@element-plus/icons-vue";
import api from "@/api";

const props = defineProps<{ entityType: string; entityId: number }>();

const active = ref(false);
const tags = ref<string[]>([]);
const newTag = ref("");

async function load() {
  try {
    const res: any = await api.get("/favorites/state", {
      params: { entity_type: props.entityType, entity_id: props.entityId },
      silent: true,
    });
    active.value = !!res?.data?.active;
    tags.value = res?.data?.tags || [];
  } catch {
    /* 静默: 未登录/异常都不影响详情页 */
  }
}

async function toggle() {
  const res: any = await api.post("/favorites/toggle", {
    entity_type: props.entityType,
    entity_id: props.entityId,
  });
  active.value = !!res?.data?.active;
  ElMessage.success(active.value ? "已收藏" : "已取消收藏");
}

async function addTag() {
  const t = newTag.value.trim();
  if (!t) return;
  const res: any = await api.post("/favorites/tags", {
    entity_type: props.entityType,
    entity_id: props.entityId,
    tag: t,
  });
  tags.value = res?.data?.tags || [];
  newTag.value = "";
}

async function delTag(t: string) {
  const res: any = await api.delete("/favorites/tags", {
    data: { entity_type: props.entityType, entity_id: props.entityId, tag: t },
  });
  tags.value = res?.data?.tags || [];
}

onMounted(load);
</script>

<style scoped>
.fav-wrap { display: inline-flex; gap: 8px; align-items: center; }
.fav-tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.fav-tag-empty { color: #909399; font-size: 12px; }
</style>
