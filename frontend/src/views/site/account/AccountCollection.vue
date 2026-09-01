<template>
  <div class="ac-page">
    <el-card shadow="never">
      <template #header>
        <div class="ac-header">
          <span class="ac-title">我的收藏</span>
          <span class="ac-count">企业 {{ counts.company }} · 项目 {{ counts.project + counts.opportunity }} · 人员 {{ counts.person }} · 标讯 {{ counts.tender }}</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="onTab">
        <el-tab-pane label="企业" name="company" />
        <el-tab-pane label="项目" name="project" />
        <el-tab-pane label="人员" name="person" />
        <el-tab-pane label="标讯" name="tender" />
      </el-tabs>

      <!-- 企业/项目/人员: 通用收藏 -->
      <template v-if="activeTab !== 'tender'">
        <el-table :data="items" v-loading="loading" stripe empty-text="暂无收藏">
          <el-table-column label="名称" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <router-link class="ac-link" :to="detailTo(row)">{{ row.name || '（已删除）' }}</router-link>
            </template>
          </el-table-column>
          <el-table-column label="标签" min-width="200">
            <template #default="{ row }">
              <el-tag v-for="t in (row.tags || [])" :key="t" size="small" type="primary" effect="plain" class="ac-tag">{{ t }}</el-tag>
              <span v-if="!row.tags || !row.tags.length" class="ac-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="收藏时间" width="180">
            <template #default="{ row }">{{ fmt(row.favorited_at) }}</template>
          </el-table-column>
          <el-table-column label="更新" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.is_new" type="danger" size="small" effect="dark">新</el-tag>
              <span v-else class="ac-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" text @click="removeOne(row)">取消收藏</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- 标讯: 复用既有标讯收藏 -->
      <template v-else>
        <el-table :data="tenders" v-loading="tenderLoading" stripe empty-text="暂无收藏的标讯">
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
              <el-button size="small" type="danger" text @click="removeTender(row)">取消收藏</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <div class="ac-pager" v-if="total > page_size">
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="page_size"
          :current-page="page" @current-change="handlePage" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "@/api";

const activeTab = ref("company");
const items = ref<any[]>([]);
const tenders = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const tenderLoading = ref(false);
const page = ref(1);
const page_size = 20;
const counts = reactive({ company: 0, project: 0, person: 0, opportunity: 0, tender: 0 });

const ROUTE: Record<string, string> = {
  company: "CompanyDetail",
  project: "ProjectDetail",
  person: "PersonProfile",
  opportunity: "OpportunityList",
};

function detailTo(row: any) {
  if (row.entity_type === "opportunity") return { name: "OpportunityList" };
  return { name: ROUTE[row.entity_type], params: { id: row.entity_id } };
}

async function loadSummary() {
  try {
    const s: any = await api.get("/favorites/summary", { silent: true });
    const g = s?.data || {};
    counts.company = g.company?.count || 0;
    counts.project = g.project?.count || 0;
    counts.person = g.person?.count || 0;
    counts.opportunity = g.opportunity?.count || 0;
  } catch { /* ignore */ }
}

async function loadFavs() {
  loading.value = true;
  try {
    // 「项目」tab = 工程项目(project) + 项目商机(opportunity) 合并展示
    if (activeTab.value === "project") {
      const [pr, op] = await Promise.allSettled([
        api.get("/favorites", { params: { entity_type: "project", page: 1, page_size: 100 }, silent: true } as any),
        api.get("/favorites", { params: { entity_type: "opportunity", page: 1, page_size: 100 }, silent: true } as any),
      ]);
      const prItems = pr.status === "fulfilled" ? pr.value?.data?.items || [] : [];
      const opItems = op.status === "fulfilled" ? op.value?.data?.items || [] : [];
      const merged = [...prItems, ...opItems].sort(
        (a: any, b: any) => (b.favorited_at || "").localeCompare(a.favorited_at || "")
      );
      items.value = merged;
      total.value = merged.length;
      return;
    }
    const res: any = await api.get("/favorites", {
      params: { entity_type: activeTab.value, page: page.value, page_size },
    });
    items.value = res?.data?.items || [];
    total.value = res?.data?.total || 0;
  } catch {
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

async function loadTenders() {
  tenderLoading.value = true;
  try {
    const res: any = await api.get("/tenders/actions", {
      params: { type: "collected", page: page.value, page_size },
    });
    tenders.value = (res?.data?.items || []).map((it: any) => ({
      ...it,
      collected: it.collected ? 1 : 0,
      monitored: it.monitored ? 1 : 0,
    }));
    total.value = res?.data?.total || 0;
    counts.tender = res?.data?.total || 0;
  } catch {
    tenders.value = [];
    total.value = 0;
  } finally {
    tenderLoading.value = false;
  }
}

async function loadTenderCount() {
  tenderLoading.value = true;
  try {
    const res: any = await api.get("/tenders/actions", {
      params: { type: "collected", page: 1, page_size: 1 },
      silent: true,
    } as any);
    counts.tender = res?.data?.total || 0;
  } catch {
    counts.tender = 0;
  } finally {
    tenderLoading.value = false;
  }
}

function onTab() {
  page.value = 1;
  if (activeTab.value === "tender") loadTenders();
  else loadFavs();
}

function handlePage(p: number) {
  page.value = p;
  if (activeTab.value === "tender") loadTenders();
  else loadFavs();
}

async function removeOne(row: any) {
  try {
    await ElMessageBox.confirm(`确认取消收藏「${row.name || "该实体"}」?`, "提示", { type: "warning" });
    await api.post("/favorites/toggle", { entity_type: row.entity_type, entity_id: row.entity_id });
    ElMessage.success("已取消收藏");
    loadFavs();
    loadSummary();
  } catch { /* 取消或拦截器处理 */ }
}

async function removeTender(row: any) {
  try {
    await ElMessageBox.confirm(`确认取消收藏「${row.title || "该标讯"}」?`, "提示", { type: "warning" });
    await api.post(`/tenders/${row.bid_id}/favorite`);
    ElMessage.success("已取消收藏");
    loadTenders();
  } catch { /* 取消或拦截器处理 */ }
}

function fmt(v?: string) {
  if (!v) return "—";
  return v.replace("T", " ").slice(0, 19);
}

onMounted(() => {
  loadSummary();
  loadFavs();
  loadTenderCount();
});
</script>

<style scoped>
.ac-page { max-width: 1080px; }
.ac-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ac-title { font-weight: 600; font-size: 16px; }
.ac-count { color: #8a94a6; font-size: 13px; }
.ac-link { color: var(--ssm-primary, #a51c30); text-decoration: none; }
.ac-link:hover { text-decoration: underline; }
.ac-tag { margin-right: 6px; }
.ac-muted { color: #c0c4cc; }
.ac-pager { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
