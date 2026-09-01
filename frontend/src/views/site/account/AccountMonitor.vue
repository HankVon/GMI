<template>
  <div class="ac-page">
    <el-card shadow="never">
      <template #header>
        <div class="ac-header">
          <span class="ac-title">我的监控</span>
          <span class="ac-count">共 {{ total }} 条</span>
        </div>
      </template>

      <el-table :data="items" v-loading="loading" stripe empty-text="暂无监控的标讯">
        <el-table-column label="标题" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <router-link class="ac-link" :to="{ name: 'DataCenterBidDetail', params: { id: row.bid_id } }">
              {{ row.title || '（标题缺失）' }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="region" label="地区" width="120" />
        <el-table-column prop="purchaser" label="采购人" min-width="160" show-overflow-tooltip />
        <el-table-column prop="notice_type" label="类型" width="100" />
        <el-table-column label="发布时间" width="170">
          <template #default="{ row }">{{ fmt(row.published_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" text @click="removeOne(row)">取消监控</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="ac-pager" v-if="total > page_size">
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="page_size"
          :current-page="page" @current-change="handlePage" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "@/api";

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const page = ref(1);
const page_size = 20;

async function load() {
  loading.value = true;
  try {
    const res: any = await api.get("/tenders/actions", {
      params: { type: "monitored", page: page.value, page_size },
    });
    items.value = (res?.data?.items || []).map((it: any) => ({
      ...it,
      collected: it.collected ? 1 : 0,
      monitored: it.monitored ? 1 : 0,
    }));
    total.value = res?.data?.total || 0;
  } catch { /* 拦截器统一处理 */ }
  finally { loading.value = false; }
}

function handlePage(p: number) { page.value = p; load(); }

async function removeOne(row: any) {
  try {
    await ElMessageBox.confirm(`确认取消监控「${row.title || "该标讯"}」?`, "提示", { type: "warning" });
    // ★ P0-4: 复用标讯监控开关接口(toggle), 再次调用即取消监控
    await api.post(`/tenders/${row.bid_id}/monitor`);
    ElMessage.success("已取消监控");
    load();
  } catch { /* 取消或拦截器处理 */ }
}

function fmt(v?: string) {
  if (!v) return "—";
  return v.replace("T", " ").slice(0, 19);
}

onMounted(load);
</script>

<style scoped>
.ac-page { max-width: 1080px; }
.ac-header { display: flex; align-items: center; gap: 12px; }
.ac-title { font-weight: 600; font-size: 16px; }
.ac-count { color: #8a94a6; font-size: 13px; }
.ac-link { color: var(--ssm-primary, #a51c30); text-decoration: none; }
.ac-link:hover { text-decoration: underline; }
.ac-pager { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
