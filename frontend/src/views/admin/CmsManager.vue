<template>
  <div class="cms-manager">
    <!-- 页面切换 -->
    <el-card class="cms-page-nav" shadow="never">
      <div class="page-nav-head">
        <span class="page-nav-label">选择要配置的前台页面</span>
        <div class="page-nav-tabs">
          <div
            v-for="p in pageDefs"
            :key="p.key"
            class="page-nav-tab"
            :class="{ on: currentPage === p.key }"
            @click="switchPage(p.key)"
          >
            {{ p.label }}
          </div>
        </div>
      </div>
    </el-card>

    <!-- 顶部说明 -->
    <el-card class="cms-intro" shadow="never">
      <div class="cms-intro-body">
        <div>
          <div class="cms-intro-title">{{ currentPageDef?.label || '内容配置' }}</div>
          <div class="cms-intro-sub">{{ currentPageDef?.desc || '维护前台页面内容区块，保存后前台立即生效。' }}</div>
        </div>
        <div class="cms-intro-actions">
          <el-button type="primary" @click="router.push(currentPageDef?.preview || '/site')" :icon="View">查看前台</el-button>
          <el-button @click="loadBlocks" :loading="loading" :icon="Refresh">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- 区块列表 -->
    <el-card v-loading="loading" shadow="never">
      <template #header>
        <div class="card-hd">
          <span>内容区块（{{ blocks.length }}）</span>
          <el-button v-if="canEdit" type="primary" size="small" @click="openCreateBlock">新建区块</el-button>
        </div>
      </template>

      <el-empty v-if="!blocks.length && !loading" description="暂无区块配置" />

      <el-collapse v-model="activeBlocks" accordion>
        <el-collapse-item v-for="b in blocks" :key="b.block_key" :name="b.block_key">
          <template #title>
            <div class="block-title">
              <span class="block-key-tag">{{ b.block_key }}</span>
              <span class="block-name">{{ b.title }}</span>
              <el-tag :type="b.enabled === 1 ? 'success' : 'info'" size="small" effect="light">
                {{ b.enabled === 1 ? '已启用' : '已停用' }}
              </el-tag>
              <span class="block-desc">{{ b.description }}</span>
            </div>
          </template>

          <!-- 区块操作 -->
          <div class="block-toolbar">
            <el-button v-if="canEdit" size="small" @click="toggleBlock(b)">{{ b.enabled === 1 ? '停用' : '启用' }}</el-button>
            <el-button v-if="canEdit" size="small" @click="openEditBlock(b)">编辑</el-button>
            <el-button v-if="canEdit" size="small" type="danger" text @click="removeBlock(b)">删除区块</el-button>
          </div>

          <!-- 条目表格 -->
          <el-table :data="b.items" size="small" stripe>
            <el-table-column prop="sort_order" label="排序" width="70" />
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column prop="subtitle" label="副标题/描述" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="cell-sub">{{ row.subtitle || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="link" label="跳转" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="cell-link">{{ row.link || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled === 1 ? 'success' : 'info'" size="small">{{ row.enabled === 1 ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="170" align="center">
              <template #default="{ row }">
                <template v-if="canEdit">
                  <el-button size="small" @click="toggleItem(b, row)">{{ row.enabled === 1 ? '停用' : '启用' }}</el-button>
                  <el-button size="small" @click="openEditItem(b, row)">编辑</el-button>
                  <el-button size="small" type="danger" text @click="removeItem(b, row)">删除</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>

          <div class="block-item-add" v-if="canEdit">
            <el-button type="primary" plain size="small" @click="openCreateItem(b)">＋ 添加条目</el-button>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 新建区块 -->
    <el-dialog v-model="createBlockVisible" title="新建区块" width="480px">
      <el-form ref="blockFormRef" :model="blockForm" :rules="blockRules" label-width="90px">
        <el-form-item label="区块标识" prop="block_key"><el-input v-model="blockForm.block_key" placeholder="如 quick_links / certs" /></el-form-item>
        <el-form-item label="区块标题" prop="title"><el-input v-model="blockForm.title" /></el-form-item>
        <el-form-item label="区块说明"><el-input v-model="blockForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="blockForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="blockForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createBlockVisible = false">取消</el-button>
        <el-button type="primary" @click="saveBlock">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑区块 -->
    <el-dialog v-model="editBlockVisible" title="编辑区块" width="480px">
      <el-form :model="editBlockForm" label-width="90px">
        <el-form-item label="区块标识"><el-input :model-value="editBlockForm.block_key" disabled /></el-form-item>
        <el-form-item label="区块标题"><el-input v-model="editBlockForm.title" /></el-form-item>
        <el-form-item label="区块说明"><el-input v-model="editBlockForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="editBlockForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="editBlockForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editBlockVisible = false">取消</el-button>
        <el-button type="primary" @click="saveBlock">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑条目 -->
    <el-dialog v-model="itemDialogVisible" :title="itemForm.id ? '编辑条目' : '添加条目'" width="560px">
      <el-form :model="itemForm" :rules="itemRules" label-width="90px">
        <el-form-item label="标题" prop="title"><el-input v-model="itemForm.title" placeholder="标题/名称（必填）" /></el-form-item>
        <el-form-item label="副标题"><el-input v-model="itemForm.subtitle" placeholder="副标题/描述/子文案" /></el-form-item>
        <el-form-item label="图标">
          <el-select v-model="itemForm.icon" clearable filterable placeholder="选择图标（选填）">
            <el-option v-for="(nm, key) in iconOptions" :key="key" :label="nm" :value="key">
              <span class="opt-label"><el-icon><component :is="iconMap[key]" /></el-icon>&nbsp;{{ nm }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="跳转地址"><el-input v-model="itemForm.link" placeholder="/site/data-center/companies" /></el-form-item>
        <el-form-item label="条目标识"><el-input v-model="itemForm.item_key" placeholder="可选，英文唯一标识" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="itemForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="itemForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
        <el-form-item label="扩展参数">
          <el-input v-model="itemForm.metaText" type="textarea" :rows="3" placeholder='JSON 对象，如 {"color":"#c8102e","bg":"linear-gradient(...)","short":"US","members":320}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  View, Refresh, Tickets, Document, Medal, Trophy, User, OfficeBuilding,
  Box, Promotion, Lock, Star, DataBoard, Cpu, Histogram, Connection, EditPen,
  ChatLineRound, DataAnalysis, Phone, Watermelon, Coin, ArrowRight,
} from "@element-plus/icons-vue";
import api from "@/api";
import type { CmsBlock, CmsBlockItem } from "@/api/siteApi";
import { useUserStore } from "@/stores/user";

const router = useRouter();
const userStore = useUserStore();

const loading = ref(false);
const blocks = ref<CmsBlock[]>([]);
const activeBlocks = ref<string[]>([]);

// ── 前台页面维度定义 ──
const pageDefs = [
  { key: "home", label: "首页", desc: "维护前台首页各内容区块（引导条/图标入口/认证/CTA/领域/合作/产品/研讨/认证体系/推荐单位）。", preview: "/site" },
  { key: "about", label: "关于我们", desc: "维护「关于我们」页面内容（简介数据/价值观/发展历程/团队统计）。", preview: "/site/about" },
  { key: "contact", label: "联系我们", desc: "维护「联系我们」页面信息（联系方式卡片/服务时间/地址/隐私说明）。", preview: "/site/contact" },
  { key: "solutions", label: "解决方案", desc: "维护「解决方案」页面内容（方案卡片/案例/流程步骤）。", preview: "/site/solutions" },
  { key: "intelligence", label: "情报动态", desc: "维护「情报动态/项目商机」页面信息（筛选标签/介绍/横幅）。", preview: "/site/intelligence" },
  { key: "datacenter", label: "数据中心", desc: "维护「数据中心」页面信息（标讯/单位/人员/项目各子页介绍）。", preview: "/site/data-center" },
];

const currentPage = ref("home");
const currentPageDef = computed(() => pageDefs.find((p) => p.key === currentPage.value) || pageDefs[0]);

function switchPage(key: string) {
  currentPage.value = key;
  router.replace({ query: { ...router.currentRoute.value.query, page: key } });
  loadBlocks();
}

// 权限: 查看需 cms_home_view, 编辑需 cms_home_edit
const canView = computed(() => userStore.hasPermission("cms_home_view") || userStore.hasPermission("cms_home_edit"));
const canEdit = computed(() => userStore.hasPermission("cms_home_edit"));

const iconOptions: Record<string, string> = {
  Tickets: "标讯", Document: "文档", Medal: "资质", Trophy: "奖杯", User: "人员",
  OfficeBuilding: "单位", Box: "装备", Promotion: "推广", Lock: "安全", Star: "星级",
  DataBoard: "看板", Cpu: "AI", Histogram: "图表", Connection: "关系", EditPen: "编辑",
  ChatLineRound: "咨询", DataAnalysis: "分析", Phone: "电话", Watermelon: "物探", Coin: "测试",
};

const iconMap: Record<string, any> = {
  Tickets, Document, Medal, Trophy, User, OfficeBuilding, Box, Promotion,
  Lock, Star, DataBoard, Cpu, Histogram, Connection, EditPen, ChatLineRound,
  DataAnalysis, Phone, Watermelon, Coin, ArrowRight,
};

// ── 区块表单 ──
const createBlockVisible = ref(false);
const editBlockVisible = ref(false);
const blockForm = reactive({ block_key: "", title: "", description: "", enabled: 1, sort_order: 0 });
const editBlockForm = reactive({ id: 0, block_key: "", title: "", description: "", enabled: 1, sort_order: 0 });
const blockRules = {
  block_key: [{ required: true, message: "请输入区块标识", trigger: "blur" }],
  title: [{ required: true, message: "请输入区块标题", trigger: "blur" }],
};

// ── 条目表单 ──
const itemDialogVisible = ref(false);
const itemBlockKey = ref("");
const itemForm = reactive<CmsBlockItem & { metaText: string }>({
  id: 0, item_key: null, title: "", subtitle: null, icon: null, link: null,
  meta: {}, enabled: 1, sort_order: 0, metaText: "",
});
const itemRules = {
  title: [{ required: true, message: "请输入标题", trigger: "blur" }],
};

async function loadBlocks() {
  loading.value = true;
  try {
    const res: any = await api.get("/cms/blocks", { params: { page: currentPage.value } });
    blocks.value = res?.data ?? [];
    if (blocks.value.length) activeBlocks.value = [blocks.value[0].block_key];
  } catch (e) {
    // api 拦截器已弹错
  } finally {
    loading.value = false;
  }
}

function openCreateBlock() {
  Object.assign(blockForm, { block_key: "", title: "", description: "", enabled: 1, sort_order: 0 });
  createBlockVisible.value = true;
}

function openEditBlock(b: CmsBlock) {
  Object.assign(editBlockForm, {
    id: b.id, block_key: b.block_key, title: b.title,
    description: b.description || "", enabled: b.enabled, sort_order: b.sort_order,
  });
  editBlockVisible.value = true;
}

async function saveBlock() {
  if (createBlockVisible.value) {
    if (!blockForm.block_key || !blockForm.title) {
      ElMessage.warning("区块标识与标题必填");
      return;
    }
    try {
      await api.post("/cms/blocks", { ...blockForm, page_key: currentPage.value });
      ElMessage.success("区块已创建");
      createBlockVisible.value = false;
      await loadBlocks();
    } catch (e) { /* 拦截器已弹错 */ }
  } else if (editBlockVisible.value) {
    try {
      await api.put(`/cms/blocks/${currentPage.value}/${editBlockForm.block_key}`, {
        title: editBlockForm.title,
        description: editBlockForm.description,
        enabled: editBlockForm.enabled,
        sort_order: editBlockForm.sort_order,
      });
      ElMessage.success("区块已更新");
      editBlockVisible.value = false;
      await loadBlocks();
    } catch (e) { /* 拦截器已弹错 */ }
  }
}

async function toggleBlock(b: CmsBlock) {
  try {
    await api.put(`/cms/blocks/${currentPage.value}/${b.block_key}`, { enabled: b.enabled === 1 ? 0 : 1 });
    await loadBlocks();
    ElMessage.success(b.enabled === 1 ? "区块已停用" : "区块已启用");
  } catch (e) { /* 拦截器已弹错 */ }
}

async function removeBlock(b: CmsBlock) {
  await ElMessageBox.confirm(`确定删除区块「${b.title}」及其全部条目？`, "删除确认", { type: "warning" });
  try {
    await api.delete(`/cms/blocks/${currentPage.value}/${b.block_key}`);
    ElMessage.success("区块已删除");
    await loadBlocks();
  } catch (e) { /* 拦截器已弹错 */ }
}

function openCreateItem(b: CmsBlock) {
  itemBlockKey.value = b.block_key;
  Object.assign(itemForm, {
    id: 0, item_key: null, title: "", subtitle: null, icon: null, link: null,
    meta: {}, enabled: 1, sort_order: b.items.length, metaText: "",
  });
  itemDialogVisible.value = true;
}

function openEditItem(b: CmsBlock, row: CmsBlockItem) {
  itemBlockKey.value = b.block_key;
  Object.assign(itemForm, {
    id: row.id, item_key: row.item_key, title: row.title, subtitle: row.subtitle,
    icon: row.icon, link: row.link, meta: { ...row.meta }, enabled: row.enabled,
    sort_order: row.sort_order, metaText: row.meta ? JSON.stringify(row.meta, null, 2) : "",
  });
  itemDialogVisible.value = true;
}

function parseMetaText() {
  if (!itemForm.metaText.trim()) {
    itemForm.meta = {};
    return true;
  }
  try {
    itemForm.meta = JSON.parse(itemForm.metaText);
    return true;
  } catch (e) {
    ElMessage.error("扩展参数不是合法 JSON");
    return false;
  }
}

async function saveItem() {
  if (!itemForm.title) {
    ElMessage.warning("标题必填");
    return;
  }
  if (!parseMetaText()) return;
  const payload: Record<string, any> = {
    title: itemForm.title,
    subtitle: itemForm.subtitle || null,
    icon: itemForm.icon || null,
    link: itemForm.link || null,
    item_key: itemForm.item_key || null,
    meta: itemForm.meta,
    enabled: itemForm.enabled,
    sort_order: itemForm.sort_order,
  };
  try {
    if (itemForm.id) {
      await api.put(`/cms/blocks/${currentPage.value}/${itemBlockKey.value}/items/${itemForm.id}`, payload);
    } else {
      await api.post(`/cms/blocks/${currentPage.value}/${itemBlockKey.value}/items`, payload);
    }
    ElMessage.success("条目已保存");
    itemDialogVisible.value = false;
    await loadBlocks();
  } catch (e) { /* 拦截器已弹错 */ }
}

async function toggleItem(b: CmsBlock, row: CmsBlockItem) {
  try {
    await api.put(`/cms/blocks/${currentPage.value}/${b.block_key}/items/${row.id}`, { enabled: row.enabled === 1 ? 0 : 1 });
    await loadBlocks();
  } catch (e) { /* 拦截器已弹错 */ }
}

async function removeItem(b: CmsBlock, row: CmsBlockItem) {
  await ElMessageBox.confirm(`确定删除条目「${row.title}」？`, "删除确认", { type: "warning" });
  try {
    await api.delete(`/cms/blocks/${currentPage.value}/${b.block_key}/items/${row.id}`);
    ElMessage.success("条目已删除");
    await loadBlocks();
  } catch (e) { /* 拦截器已弹错 */ }
}

onMounted(() => {
  const qPage = router.currentRoute.value.query.page as string | undefined;
  if (qPage && pageDefs.some((p) => p.key === qPage)) {
    currentPage.value = qPage;
  }
  loadBlocks();
});
</script>

<style scoped>
.cms-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.cms-intro {
  border-radius: 12px;
}
.cms-intro-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.cms-intro-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--site-text, #141414);
  margin-bottom: 6px;
}
.cms-intro-sub {
  font-size: 13px;
  color: var(--site-text-dim, #525252);
  max-width: 560px;
  line-height: 1.7;
}
.card-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.block-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.block-key-tag {
  font-family: var(--site-font-mono, Consolas, monospace);
  font-size: 11px;
  background: var(--site-brand-soft, #fceef0);
  color: var(--site-brand, #c8102e);
  border: 1px solid #f0cdd2;
  padding: 1px 8px;
  border-radius: 4px;
  white-space: nowrap;
}
.block-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--site-text, #141414);
  white-space: nowrap;
}
.block-desc {
  font-size: 12px;
  color: var(--site-text-mute, #9ca3af);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.block-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}
.block-item-add {
  margin-top: 12px;
}
.cell-sub,
.cell-link {
  font-size: 12.5px;
  color: var(--site-text-dim, #525252);
}
.opt-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
/* ── 页面切换导航 ── */
.cms-page-nav {
  border-radius: 12px;
  background: linear-gradient(120deg, #fff 0%, #fdf6f7 100%);
}
.page-nav-head {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.page-nav-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--site-text-dim, #525252);
  white-space: nowrap;
}
.page-nav-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.page-nav-tab {
  padding: 6px 16px;
  border-radius: 999px;
  border: 1px solid var(--site-panel-border, #e5e7eb);
  background: #fff;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--site-text-dim, #525252);
  cursor: pointer;
  transition: all 0.2s ease;
}
.page-nav-tab:hover {
  border-color: var(--site-brand, #c8102e);
  color: var(--site-brand, #c8102e);
}
.page-nav-tab.on {
  background: var(--site-brand, #c8102e);
  border-color: var(--site-brand, #c8102e);
  color: #fff;
  font-weight: 600;
}
@media (max-width: 768px) {
  .page-nav-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}
</style>
