<!-- SearchResult.vue — 搜索结果页 -->
<template>
  <div class="search-page">
    <el-card>
      <el-input v-model="query" placeholder="搜索项目或人员..." @keyup.enter="doSearch" size="large" clearable>
        <template #prefix><el-icon><Search /></el-icon></template>
        <template #append><el-button @click="doSearch" :loading="loading">搜索</el-button></template>
      </el-input>
    </el-card>

    <div v-if="groups.length === 0 && !loading" style="margin-top:40px">
      <el-empty :description="query ? '未找到相关结果' : '请输入关键词搜索'" />
    </div>

    <div v-for="g in groups" :key="g.entity_type" style="margin:12px 0">
      <el-card>
        <template #header>
          <el-tag :type="g.entity_type==='project'?'primary':'success'">
            {{ g.entity_type === 'project' ? '项目' : '人员' }}
          </el-tag>
          <span class="group-count">共 {{ g.count }} 条</span>
        </template>
        <div v-for="item in g.items" :key="item.entity_id" class="result-item"
          @click="goTo(item.entity_type, item.entity_id)">
          <h4 class="result-title" v-html="highlightKeyword(item.title)"></h4>
          <p class="result-snippet" v-html="safeSnippet(item.snippet)"></p>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "@/api";

const route = useRoute();
const router = useRouter();
const query = ref((route.query.q as string) || "");
const loading = ref(false);
const groups = ref<any[]>([]);

async function doSearch() {
  if (!query.value.trim()) return;
  loading.value = true;
  try {
    const res: any = await api.get("/search", { params: { q: query.value } });
    groups.value = res.data?.groups || [];
  } catch { groups.value = []; }
  finally { loading.value = false; }
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function highlightKeyword(text: string): string {
  if (!text) return "";
  // 先转义原始文本防止 XSS, 再对高亮片段包裹 <em>
  const safe = escapeHtml(text);
  if (!query.value) return safe;
  const re = new RegExp(`(${query.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, "gi");
  return safe.replace(re, '<em style="color:#e6a23c">$1</em>');
}

function safeSnippet(snippet: string): string {
  // 摘要为后端返回的原始文本, 转义后渲染, 不执行任何 HTML
  return escapeHtml(snippet || "");
}

function goTo(type: string, id: number) {
  router.push(type === "person" ? `/workspace/persons/${id}` : `/workspace/projects/${id}`);
}

watch(() => route.query.q, (v) => { query.value = (v as string) || ""; if (v) doSearch(); });
onMounted(() => { if (route.query.q) doSearch(); });
</script>

<style scoped>
.search-page { max-width: 900px; margin: 0 auto; padding-top: 8px; }
.group-count { margin-left: 8px; color: #909399; font-size: 13px; }
.result-item { cursor: pointer; padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.result-item:hover { background: #f5f7fa; }
.result-title { margin: 0 0 4px; font-size: 15px; color: #303133; }
.result-snippet { margin: 0; font-size: 13px; color: #606266; }
</style>
