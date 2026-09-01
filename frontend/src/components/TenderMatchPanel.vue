<!--
  标讯人脉匹配面板（P1-5 阶段一）
  复用后端 /biz-network/tenders/match（生成）+ /biz-network/tenders/matches（读取）
  + /biz-network/tenders/matches/{id}/status（标记），回答"这条标讯我认识谁"。
  仅消费既有图谱/人脉数据，不新增孤儿节点。
-->
<template>
  <el-card class="section-card match-card" shadow="never">
    <template #header>
      <div class="section-header">
        <span class="section-title">
          <el-icon><Connection /></el-icon> 人脉匹配（这条标讯我认识谁）
        </span>
        <el-button size="small" :loading="matching" @click="generate">重新匹配</el-button>
      </div>
    </template>

    <div v-loading="loading">
      <div v-if="!loading && !items.length" class="match-empty">
        暂无匹配到的人脉实体。点击右上「重新匹配」基于当前线索生成推荐。
      </div>

      <div v-else class="match-list">
        <div v-for="m in items" :key="m.id" class="match-item">
          <div class="mi-head">
            <span class="mi-name" @click="goEntity(m)">{{ m.entity_name || "未知实体" }}</span>
            <el-tag size="small" :type="statusType(m.status)">{{ statusLabel(m.status) }}</el-tag>
          </div>

          <div v-if="m.match_reason" class="mi-reason">{{ m.match_reason }}</div>

          <div class="mi-meta">
            <el-tag size="small" effect="plain" type="warning">{{ matchTypeLabel(m.match_type) }}</el-tag>
            <span v-if="m.region">区域：{{ m.region }}</span>
            <span v-if="m.amount">金额：{{ m.amount }}</span>
            <span>相关度：{{ scoreText(m.score) }}</span>
            <span v-if="m.is_expired" class="mi-exp">已过期</span>
          </div>

          <div class="mi-foot">
            <el-select
              :model-value="m.status"
              size="small"
              style="width: 130px"
              @change="(v: string) => setStatus(m, v)"
            >
              <el-option label="新建" value="new" />
              <el-option label="已联系" value="contacted" />
              <el-option label="跟进中" value="followed" />
              <el-option label="忽略" value="ignored" />
            </el-select>
            <span v-if="m.valid_until" class="mi-valid">有效至 {{ formatTime(m.valid_until) }}</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { Connection } from "@element-plus/icons-vue";
import api from "@/api";

const props = defineProps<{ clueId: number }>();
const router = useRouter();

const loading = ref(false);
const matching = ref(false);
const items = ref<any[]>([]);

async function loadMatches() {
  loading.value = true;
  try {
    const res: any = await api.get(`/biz-network/tenders/matches?clue_id=${props.clueId}`);
    items.value = Array.isArray(res?.items) ? res.items : [];
  } catch {
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function generate() {
  matching.value = true;
  try {
    await api.post("/biz-network/tenders/match", { clue_id: props.clueId });
    await loadMatches();
  } catch {
    /* 拦截器已提示（如缺 api_company_crud 权限） */
  } finally {
    matching.value = false;
  }
}

async function setStatus(m: any, v: string) {
  try {
    await api.put(`/biz-network/tenders/matches/${m.id}/status`, { status: v });
    m.status = v;
  } catch {
    /* 拦截器已提示 */
  }
}

function goEntity(m: any) {
  const routes: Record<string, string> = {
    company: `/workspace/companies/${m.entity_id}`,
    person: `/workspace/persons/${m.entity_id}`,
    project: `/workspace/projects/${m.entity_id}`,
  };
  const p = routes[m.entity_type];
  if (p) router.push(p);
}

const STATUS_MAP: Record<string, { label: string; type: "" | "success" | "warning" | "info" | "danger" }> = {
  new: { label: "新建", type: "info" },
  contacted: { label: "已联系", type: "warning" },
  followed: { label: "跟进中", type: "success" },
  ignored: { label: "忽略", type: "info" },
};
function statusLabel(s?: string) {
  return (STATUS_MAP[s || ""] || STATUS_MAP.new).label;
}
function statusType(s?: string) {
  return (STATUS_MAP[s || ""] || STATUS_MAP.new).type;
}

const MATCH_TYPE_LABELS: Record<string, string> = {
  skill: "专长匹配",
  category: "类别匹配",
  region: "区域匹配",
  company: "单位匹配",
  intent_unit: "意向单位匹配",
};
function matchTypeLabel(t?: string) {
  return MATCH_TYPE_LABELS[t || ""] || t || "匹配";
}

function scoreText(s?: number) {
  const n = Number(s || 0);
  return n.toFixed(2);
}

function formatTime(t?: string) {
  if (!t) return "-";
  return String(t).replace("T", " ").slice(0, 19);
}

onMounted(loadMatches);
</script>

<style scoped>
.match-card { border-radius: 10px; border-top: 3px solid #722ed1; }
.match-empty {
  font-size: 13px; color: #8a94a6; background: #f7f9fc;
  border-radius: 6px; padding: 14px 16px; line-height: 1.8;
}
.match-list { display: flex; flex-direction: column; gap: 10px; }
.match-item {
  background: #f7f9fc; border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 14px;
}
.match-item:hover { border-color: #b37feb; background: #faf5ff; }
.mi-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.mi-name {
  font-size: 14px; font-weight: 600; color: #1f2733; cursor: pointer;
}
.mi-name:hover { color: #722ed1; text-decoration: underline; }
.mi-reason { font-size: 12px; color: #5b6675; margin-top: 6px; line-height: 1.7; }
.mi-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  font-size: 12px; color: #8a94a6; margin-top: 8px;
}
.mi-exp { color: #e6a23c; font-weight: 600; }
.mi-foot { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
.mi-valid { font-size: 12px; color: #a0a8b5; }
</style>
