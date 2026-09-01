<template>
  <div class="gap-board">
    <div class="page-head">
      <div>
        <h2>附件缺口看板</h2>
        <p class="sub">
          采集 / 解析标讯时未能取到附件的来源汇总。
          <b>强信号 empty_fjxx</b> = 抓到详情页但附件区无链接 → 解析器需适配；
          <b>弱信号 no_detail</b> = 连详情页都没抓到 → 多为网络 / 反爬。
        </p>
      </div>
      <div class="head-actions">
        <el-button size="small" :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 概览卡片 -->
    <div class="stat-row" v-if="!loading">
      <div class="stat-card">
        <div class="stat-num">{{ data.total_events || 0 }}</div>
        <div class="stat-label">缺口事件（累计）</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ data.distinct_urls || 0 }}</div>
        <div class="stat-label">去重 URL 数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ (data.by_source || []).length }}</div>
        <div class="stat-label">涉及来源数</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-num">{{ strongTotal }}</div>
        <div class="stat-label">强信号 empty_fjxx</div>
      </div>
      <div class="stat-card warn">
        <div class="stat-num">{{ weakTotal }}</div>
        <div class="stat-label">弱信号 no_detail</div>
      </div>
    </div>

    <el-card shadow="never">
      <el-table
        :data="rows"
        size="small"
        v-loading="loading"
        row-key="source"
        empty-text="暂无缺口记录 — 所有采集来源的附件抓取均正常"
      >
        <el-table-column prop="source" label="来源" min-width="200" show-overflow-tooltip />
        <el-table-column label="强信号 empty_fjxx" width="160" sortable :sort-by="(r: any) => r.empty_fjxx">
          <template #default="{ row }">
            <el-tag size="small" :type="row.empty_fjxx > 0 ? 'danger' : 'info'" effect="light">
              {{ row.empty_fjxx }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="弱信号 no_detail" width="160" sortable :sort-by="(r: any) => r.no_detail">
          <template #default="{ row }">
            <el-tag size="small" :type="row.no_detail > 0 ? 'warning' : 'info'" effect="light">
              {{ row.no_detail }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="distinct_urls" label="去重 URL" width="110" sortable />
        <el-table-column label="样例链接" min-width="320">
          <template #default="{ row }">
            <div class="url-cell">
              <a
                v-for="u in row.urls"
                :key="u"
                :href="u"
                target="_blank"
                rel="noopener"
                class="url-link"
              >{{ shortUrl(u) }}</a>
              <span v-if="!row.urls || !row.urls.length" class="muted">—</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div class="foot" v-if="data.generated_at">统计生成时间：{{ data.generated_at }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import api from "@/api";

const loading = ref(false);
const data = ref<any>({ by_source: [] });

const rows = computed(() => data.value.by_source || []);
const strongTotal = computed(() =>
  rows.value.reduce((s: number, r: any) => s + (r.empty_fjxx || 0), 0),
);
const weakTotal = computed(() =>
  rows.value.reduce((s: number, r: any) => s + (r.no_detail || 0), 0),
);

function shortUrl(u: string): string {
  try {
    const p = new URL(u);
    return p.host + p.pathname.slice(0, 40);
  } catch {
    return u.slice(0, 60);
  }
}

async function load() {
  loading.value = true;
  try {
    const r: any = await api.get("/bids/attachment-gaps");
    if (r?.success) data.value = r.data || { by_source: [] };
    else data.value = { by_source: [] };
  } catch {
    data.value = { by_source: [] };
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.gap-board {
  padding: 4px 0 30px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-head h2 {
  margin: 0 0 4px;
  font-size: 16px;
  color: #1c2a3a;
}
.sub {
  margin: 0;
  font-size: 12px;
  color: #8a91a0;
  max-width: 760px;
  line-height: 1.6;
}
.head-actions {
  display: flex;
  gap: 8px;
}
.stat-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.stat-card {
  flex: 1;
  min-width: 130px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 16px;
}
.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #1c2a3a;
}
.stat-label {
  font-size: 12px;
  color: #8a91a0;
  margin-top: 4px;
}
.stat-card.danger .stat-num {
  color: #f56c6c;
}
.stat-card.warn .stat-num {
  color: #e6a23c;
}
.url-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.url-link {
  color: #409eff;
  text-decoration: none;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}
.url-link:hover {
  text-decoration: underline;
}
.muted {
  color: #b5b9c2;
}
.foot {
  margin-top: 12px;
  font-size: 12px;
  color: #b5b9c2;
}
</style>
