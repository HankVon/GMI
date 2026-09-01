<template>
  <div class="bid-detail-page">
    <div v-if="loading" v-loading="loading" class="loading-box"></div>
    <template v-else-if="bid">
      <!-- 顶部:面包屑 + 返回 -->
      <div class="detail-breadcrumb">
        <el-breadcrumb separator=">">
          <el-breadcrumb-item @click="goBack">全部标讯</el-breadcrumb-item>
          <el-breadcrumb-item>{{ bid.notice_type || '标讯详情' }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ bid.title }}</el-breadcrumb-item>
        </el-breadcrumb>
      </div>

      <!-- 顶部标题 + 操作卡 -->
      <section class="detail-header">
        <div class="detail-header-left">
          <h1 class="detail-title">
            <span class="title-text">{{ bid.title }}</span>
            <span v-if="bid.project_code" class="title-code">[{{ bid.project_code }}]</span>
          </h1>
          <div class="detail-tags">
            <span v-for="(tag, idx) in detailTags" :key="idx" :class="['title-tag', `tag-${tag.kind}`]">
              {{ tag.label }}
            </span>
          </div>
          <div class="detail-publish">
            <el-icon><Clock /></el-icon>
            <span>发布时间：{{ bid.published_at || '-' }}</span>
          </div>
        </div>
        <div class="detail-header-right">
          <div class="platform-links" v-if="bid.source_name || bid.platform_links?.length">
            <a
              v-for="(p, i) in platformLinks"
              :key="i"
              class="platform-link"
              :href="p.url || bid.url || '#'"
              target="_blank"
              rel="noopener"
            >{{ p.name }}</a>
          </div>
          <div class="detail-actions">
            <a v-if="bid.url" class="action-link" @click.prevent="openOriginal">
              <el-icon><Link /></el-icon>
              <span>查看来源</span>
            </a>
            <a v-if="bid.attachment_url || bid.url" class="action-link" @click.prevent="downloadFiles">
              <el-icon><Download /></el-icon>
              <span>下载招标文件</span>
            </a>
            <a class="action-link" @click.prevent="toggleMonitor">
              <el-icon><Monitor /></el-icon>
              <span>{{ isMonitored ? '已监控' : '监控' }}</span>
            </a>
            <a class="action-link" @click.prevent="toggleFavorite">
              <el-icon><component :is="isCollected ? StarFilled : Star" /></el-icon>
              <span>{{ isCollected ? '已收藏' : '收藏' }}</span>
            </a>
          </div>
        </div>
      </section>

      <!-- 标签页 -->
      <nav class="detail-tabs">
        <button
          v-for="tab in detailTabs"
          :key="tab"
          :class="{ active: activeDetailTab === tab }"
          @click="selectDetailTab(tab)"
        >{{ tab }}</button>
      </nav>

      <!-- 基本信息 -->
      <div v-if="activeDetailTab === '基本信息'" class="content-grid">
        <main class="content-main">
          <section class="info-section kv-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>基本信息</h2>
              <span class="heading-note">结构化实体档案</span>
            </div>
            <entity-kv-grid
              :items="detailKv"
              :columns="3"
              variant="grid"
              @entity-click="(entity) => entity.entityId && goCompany(entity.entityId)"
            />
          </section>

          <section class="info-section timeinfo-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>关键时间信息</h2>
            </div>
            <entity-kv-grid
              :items="detailTimeMatrix"
              :columns="4"
              variant="plain"
              empty-text="暂无公开时间节点"
            />
          </section>

          <!-- 更正内容(更正公告专属, 无更正项时不渲染) -->
          <section v-if="corrections.length" class="info-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>更正内容</h2>
              <span class="heading-note">按公告原表整理</span>
            </div>
            <el-table :data="corrections" border size="small" class="correction-table">
              <el-table-column prop="no" label="序号" width="60" align="center" />
              <el-table-column prop="item" label="更正项" min-width="150" show-overflow-tooltip />
              <el-table-column label="更正前内容" min-width="180">
                <template #default="{ row }">
                  <span v-if="row.before">{{ row.before }}</span>
                  <span v-else class="cell-raw" :title="row.raw">{{ row.raw }}</span>
                </template>
              </el-table-column>
              <el-table-column label="更正后内容" min-width="180">
                <template #default="{ row }">
                  <span v-if="row.after">{{ row.after }}</span>
                  <span v-else class="cell-muted">公告原文为连排文本, 无法可靠拆分, 详见正文</span>
                </template>
              </el-table-column>
            </el-table>
          </section>

          <!-- 公告附件(此前完全未渲染) -->
          <section v-if="hasAttachments" class="info-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>公告附件</h2>
              <span class="heading-note">共 {{ attachmentList.length }} 个文件</span>
            </div>
            <ul class="attachment-list">
              <li v-for="(att, index) in attachmentList" :key="index" class="attachment-item">
                <el-icon><Document /></el-icon>
                <a
                  v-if="att.url"
                  class="attachment-name"
                  :href="att.url"
                  target="_blank"
                  rel="noopener"
                >{{ att.name }}</a>
                <span v-else class="attachment-name is-plain">{{ att.name }}</span>
                <span v-if="att.size" class="attachment-size">{{ att.size }}</span>
                <a
                  v-if="att.url"
                  class="attachment-download"
                  :href="att.url"
                  target="_blank"
                  rel="noopener"
                >下载</a>
                <span v-else class="attachment-tip">采集器未抓到下载链接, 请前往来源站获取</span>
              </li>
            </ul>
          </section>

          <!-- 正文补抽信息: 只展示抽到值的项 -->
          <section v-if="hasEnriched" class="info-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>补充信息</h2>
              <span class="heading-note">从公告正文提取</span>
            </div>
            <div class="compact-grid">
              <div v-for="row in enrichedRows" :key="row.label" class="compact-item">
                <span>{{ row.label }}</span>
                <b>{{ row.value }}</b>
              </div>
              <div v-if="expertList.length" class="compact-item">
                <span>评审专家</span>
                <b>{{ expertList.join('、') }}</b>
              </div>
            </div>
          </section>

          <section v-if="bid.budget || bid.suppliers?.length" class="info-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>资金与中标信息</h2>
            </div>
            <div class="money-row">
              <div class="money-box">
                <span>预算 / 成交金额</span>
                <strong>{{ bid.budget || totalAmount || '未披露' }}</strong>
              </div>
              <div class="money-box">
                <span>中标供应商</span>
                <strong>{{ bid.suppliers?.length || 0 }} 家</strong>
              </div>
            </div>
            <div v-if="bid.suppliers?.length" class="supplier-list">
              <div v-for="(s, index) in bid.suppliers" :key="index" class="supplier-item">
                <span class="rank">{{ s.rank || index + 1 }}</span>
                <a v-if="s.companyId" @click="goCompany(s.companyId)">{{ s.name || '未披露' }}</a>
                <b v-else>{{ s.name || '未披露' }}</b>
                <span v-if="s.amount != null" class="supplier-amount">¥{{ formatAmount(Number(s.amount)) }}</span>
                <span v-if="s.score != null" class="supplier-score">得分 {{ s.score }}</span>
              </div>
              <div
                v-for="(s, index) in bid.suppliers"
                :key="`addr-${index}`"
                v-show="s.address"
                class="supplier-address"
              >{{ s.name }}：{{ s.address }}</div>
            </div>
          </section>

          <section class="info-section announcement-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>公告正文</h2>
              <span class="heading-note">原始公告全文(已去除源站样式噪声)</span>
            </div>
            <div v-if="bodyText" class="announcement-body" :class="{ 'is-collapsed': bodyCollapsed }">
              {{ bodyText }}
            </div>
            <el-empty v-else description="暂无公告正文，请查看原文" :image-size="70" />
            <button v-if="bodyText.length > 600" class="body-toggle" @click="bodyCollapsed = !bodyCollapsed">
              {{ bodyCollapsed ? '展开全文' : '收起' }}
            </button>
          </section>
        </main>

        <aside class="content-aside">
          <section class="info-section progress-panel">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>招标进度</h2>
              <span class="heading-note">最新在上</span>
            </div>
            <div v-if="detailTimeline.length" class="vertical-timeline">
              <div
                v-for="(event, index) in detailTimeline"
                :key="`${event.name}-${index}`"
                :class="['timeline-event', { 'is-latest': index === 0 }]"
              >
                <i class="timeline-dot"></i>
                <div class="timeline-body">
                  <div class="timeline-row">
                    <b class="timeline-name">{{ event.name }}</b>
                    <span class="timeline-date">{{ event.date || '日期未披露' }}</span>
                    <span v-if="index === 0" class="timeline-badge">最新</span>
                  </div>
                  <div class="timeline-stars">*****</div>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无进度事件" :image-size="60" />
          </section>

          <section class="info-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>关联单位</h2>
            </div>
            <div v-if="bid.purchaser_company" class="company-entry" @click="goCompany(bid.purchaser_company.id)">
              <el-icon><OfficeBuilding /></el-icon>
              <div>
                <span>采购人</span>
                <b>{{ bid.purchaser_company.name }}</b>
              </div>
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div v-for="c in bid.related_companies || []" :key="c.id" class="company-entry" @click="goCompany(c.id)">
              <el-icon><Connection /></el-icon>
              <div>
                <span>中标供应商</span>
                <b>{{ c.name }}</b>
              </div>
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div v-if="!bid.purchaser_company && !(bid.related_companies || []).length" class="side-empty">
              暂无已匹配单位
            </div>
          </section>

          <section class="info-section">
            <div class="section-heading">
              <span class="heading-mark"></span>
              <h2>关键词</h2>
            </div>
            <div class="keyword-list">
              <el-tag v-for="k in bid.keywords || []" :key="k" size="small">{{ k }}</el-tag>
              <span v-if="!(bid.keywords || []).length" class="side-empty">暂无关键词</span>
            </div>
          </section>
        </aside>
      </div>

      <!-- 公告正文 -->
      <section
        v-else-if="activeDetailTab === '公告正文'"
        class="info-section announcement-section standalone-announcement"
      >
        <div class="section-heading">
          <span class="heading-mark"></span>
          <h2>公告正文</h2>
        </div>
        <div v-if="bodyText" class="announcement-body" :class="{ 'is-collapsed': bodyCollapsed }">{{ bodyText }}</div>
        <el-empty v-else description="暂无公告正文，请查看原文" :image-size="70" />
        <button v-if="bodyText.length > 600" class="body-toggle" @click="bodyCollapsed = !bodyCollapsed">
          {{ bodyCollapsed ? '展开全文' : '收起' }}
        </button>
      </section>

      <!-- 招标单位 -->
      <section v-else-if="activeDetailTab === '招标单位'" class="info-section structured-section">
        <div class="section-heading">
          <span class="heading-mark"></span>
          <h2>招标单位</h2>
        </div>
        <div v-if="bid.purchaser_company" class="company-entry big" @click="goCompany(bid.purchaser_company.id)">
          <el-icon><OfficeBuilding /></el-icon>
          <div>
            <span>采购人</span>
            <b>{{ bid.purchaser_company.name }}</b>
          </div>
          <el-icon><ArrowRight /></el-icon>
        </div>
        <div v-else class="side-empty">暂无已匹配单位</div>
      </section>

      <!-- 相似推荐 -->
      <section v-else-if="activeDetailTab === '相似推荐'" class="info-section structured-section">
        <div class="section-heading">
          <span class="heading-mark"></span>
          <h2>相似推荐</h2>
          <span class="heading-note">同类型或同地区标讯</span>
        </div>
        <div v-loading="similarLoading" class="similar-list">
          <button
            v-for="item in similarItems"
            :key="item.id"
            class="similar-card"
            @click="openSimilar(item.id)"
          >
            <div class="similar-tags">
              <span v-for="(t, ti) in similarTags(item)" :key="ti" :class="['similar-tag', `tag-${t.kind}`]">
                {{ t.displayText || t.label }}
              </span>
            </div>
            <strong>{{ item.title }}</strong>
            <span>{{ item.region || '地区未披露' }} · {{ item.purchaser || '招标单位未披露' }} · {{ item.published_at || '日期未披露' }}</span>
          </button>
          <el-empty
            v-if="!similarLoading && !similarItems.length"
            description="暂无相似标讯推荐"
            :image-size="70"
          />
        </div>
      </section>

      <!-- 人脉匹配: 这条标讯我认识谁(招标线索 × 人脉库) -->
      <section v-else-if="activeDetailTab === '人脉匹配'" class="info-section structured-section">
        <div class="section-heading">
          <span class="heading-mark"></span>
          <h2>人脉匹配</h2>
          <span class="heading-note">这条标讯我认识谁（招标线索 × 人脉库）</span>
          <el-button size="small" :loading="matchLoading" @click="rerunMatch" style="margin-left:auto">重新匹配</el-button>
        </div>
        <div v-loading="matchLoading" class="match-list">
          <div v-for="m in matchList" :key="m.id" class="match-card">
            <div class="match-head">
              <el-tag size="small" :type="m.entity_type === 'person' ? 'warning' : 'info'">
                {{ m.entity_type === 'person' ? '人员' : '单位' }}
              </el-tag>
              <strong class="match-name" @click="m.entity_type === 'company' && goCompany(m.entity_id)">
                {{ m.entity_name }}
              </strong>
              <span class="match-score">匹配度 {{ (m.score || 0).toFixed(2) }}</span>
            </div>
            <div class="match-reason">{{ m.match_reason }}</div>
            <div class="match-meta" v-if="m.region || m.amount">
              {{ m.region || '' }}<template v-if="m.region && m.amount"> · </template>{{ m.amount || '' }}
            </div>
          </div>
          <el-empty v-if="!matchLoading && !matchList.length" description="暂无匹配人脉，可点「重新匹配」生成" :image-size="70" />
        </div>
      </section>

      <!-- 人脉网络(全 tab 通用置底) -->
      <section v-if="bid.purchaser_company_id" class="info-section network-section">
        <div class="section-heading">
          <span class="heading-mark"></span>
          <h2>人脉网络</h2>
          <span class="heading-note">采购人、供应商、人员与项目协作关系</span>
        </div>
        <CompanyGraph
          v-if="bid.purchaser_company_id"
          :company-id="Number(bid.purchaser_company_id)"
          :company-name="bid.purchaser || '采购人'"
        />
      </section>

      <!-- 悬浮操作按钮 -->
      <div class="floating-detail-actions" :class="{ visible: showFloatingActions }">
        <el-button v-if="bid.url" circle title="查看来源" @click="openOriginal">
          <el-icon><Link /></el-icon>
        </el-button>
        <el-button
          circle
          :type="isMonitored ? 'success' : 'default'"
          title="监控"
          @click="toggleMonitor"
        >
          <el-icon><Monitor /></el-icon>
        </el-button>
        <el-button
          circle
          :type="isCollected ? 'warning' : 'default'"
          title="收藏"
          @click="toggleFavorite"
        >
          <el-icon><component :is="isCollected ? StarFilled : Star" /></el-icon>
        </el-button>
      </div>
    </template>
    <el-empty v-else description="标讯不存在或已删除" :image-size="100" />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'BidDetail' });
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from "@/api";
import { ElMessage } from 'element-plus';
import {
  ArrowRight,
  Clock,
  Document,
  Link,
  Download,
  OfficeBuilding,
  Connection,
  Monitor,
  Star,
  StarFilled,
} from '@element-plus/icons-vue';
import { useNavBase } from '@/utils/navBase';
import CompanyGraph from '@/components/CompanyGraph.vue';
import EntityKvGrid from '@/components/detail/EntityKvGrid.vue';
import { useTenderActionStore } from '@/stores/tenderAction';

const route = useRoute();
const router = useRouter();
const { navToNewTab } = useNavBase();
const loading = ref(true);
const bid = ref<any>(null);
const id = Number(route.params.id);
const actionStore = useTenderActionStore();
const isMonitored = computed(() => actionStore.getState(id).isMonitored);
const isCollected = computed(() => actionStore.getState(id).isCollected);
const detailTabs = ['基本信息', '公告正文', '招标单位', '相似推荐', '人脉匹配'];

// 标签按种类映射样式(对齐图片:白色/蓝色/红色等)
const detailTags = computed(() => {
  return (bid.value?.tags || []).map((tag: any) => {
    const label = tag.displayText || tag.label;
    let kind: 'status' | 'category' | 'warning' | 'danger' | 'plain' = 'status';
    if (tag.kind === 'warning') kind = 'warning';
    else if (tag.kind === 'category') kind = 'category';
    else if (tag.kind === 'danger') kind = 'danger';
    else if (tag.kind === 'plain') kind = 'plain';
    // 关键字推断:含"截止"标红,含类型词(港航/工程/设计)标蓝
    if (label.includes('截止')) kind = 'danger';
    else if (/港航|工程|设计|施工|服务|采购|物资/.test(label)) kind = 'category';
    return { label, kind };
  });
});
const activeDetailTab = ref('基本信息');
const similarItems = ref<any[]>([]);
const similarLoading = ref(false);
const showFloatingActions = ref(false);

function selectDetailTab(tab: string) {
  activeDetailTab.value = tab;
  if (tab === '相似推荐') loadSimilar();
  if (tab === '人脉匹配') loadMatches();
  if (tab !== '基本信息') window.scrollTo({ top: 0, behavior: 'smooth' });
}
async function loadSimilar() {
  if (similarLoading.value || similarItems.value.length) return;
  similarLoading.value = true;
  try {
    const res: any = await api.get(`/tenders/${id}/similar`);
    similarItems.value = res?.data || [];
  } finally {
    similarLoading.value = false;
  }
}
function similarTags(item: any) {
  return (item.tags || []).map((tag: any) => ({
    ...tag,
    displayText: tag.displayText || tag.label,
    kind: tag.kind || 'status',
  }));
}
function openSimilar(itemId: number) {
  navToNewTab(`/bids/${itemId}`);
}
function onScroll() {
  showFloatingActions.value = window.scrollY > 280;
}

// 平台链接(右上角展示)
const platformLinks = computed(() => {
  if (Array.isArray(bid.value?.platform_links) && bid.value.platform_links.length) {
    return bid.value.platform_links;
  }
  const name = bid.value?.source_name;
  return name ? [{ name, url: bid.value?.url }] : [];
});

const detailKv = computed(() => bid.value?.detailKv || bid.value?.kv || []);
const detailTimeMatrix = computed(() => bid.value?.timeMatrix || []);
const detailTimeline = computed(() => bid.value?.timeline || []);

// 正文默认折叠, 点击展开(替代此前的 slice(0, 2000) 硬截断)
const bodyCollapsed = ref(true);
const bodyText = computed(() => bid.value?.body_excerpt || bid.value?.body || bid.value?.summary || '');

const totalAmount = computed(() => {
  const amounts = (bid.value?.suppliers || [])
    .map((s: any) => Number(s.amount))
    .filter((n: number) => Number.isFinite(n));
  return amounts.length ? `¥${formatAmount(amounts.reduce((a: number, b: number) => a + b, 0))}` : '';
});

/** 正文补抽得到的补充信息。只展示**有值**的项, 避免"未披露"刷屏。 */
const enrichedRows = computed(() => {
  const e = bid.value?.enriched || {};
  const scalars = [
    ['公告时间', e.announced_at],
    ['行政区域', e.admin_region],
    ['项目名称', e.project_name],
    ['总中标金额', e.total_amount_text],
    ['代理机构地址', e.agency_address],
    ['代理机构联系方式', e.agency_phone],
    ['采购单位地址', e.purchaser_address],
    ['采购单位联系方式', e.purchaser_phone],
    ['项目联系人', e.project_person],
    ['项目联系电话', e.project_phone],
    ['原投标截止', e.prev_bid_deadline],
  ];
  return scalars
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([label, value]) => ({ label: label as string, value: String(value) }));
});
const hasEnriched = computed(() => enrichedRows.value.length > 0);

/** 评审专家名单 */
const expertList = computed(() => (bid.value?.enriched?.expert_list || []) as string[]);

/** 更正内容(更正公告) */
const corrections = computed(() => (bid.value?.enriched?.corrections || []) as any[]);

/** 公告附件: 采集到链接的可下载, 仅正文线索的提示去来源站获取 */
const attachmentList = computed(() => (bid.value?.attachments || []) as any[]);
const hasAttachments = computed(() => attachmentList.value.length > 0);

function formatAmount(value: number): string {
  return value >= 10000 ? `${(value / 10000).toFixed(2)}万` : value.toLocaleString();
}
function goCompany(companyId: number) {
  navToNewTab(`/companies/${companyId}`);
}

// ── 人脉匹配(标讯 × 人脉库, 回答"这条标讯我认识谁") ──
const matchList = ref<any[]>([]);
const matchLoading = ref(false);
async function loadMatches() {
  if (matchLoading.value) return;
  const clueId = bid.value?.clue_id;
  if (!clueId) { matchList.value = []; return; }
  matchLoading.value = true;
  try {
    const res: any = await api.get("/biz-network/tenders/matches", {
      params: { clue_id: clueId, valid: "valid", limit: 50 },
    });
    matchList.value = (res?.data?.items || res?.items || []) as any[];
  } catch {
    matchList.value = [];
  } finally {
    matchLoading.value = false;
  }
}
async function rerunMatch() {
  const clueId = bid.value?.clue_id;
  if (!clueId) return;
  matchLoading.value = true;
  try {
    await api.post("/biz-network/tenders/match", { clue_id: clueId });
    ElMessage.success("已重新匹配人脉");
    await loadMatches();
  } catch {
    // 拦截器已提示(如无 api_company_crud 权限)
  } finally {
    matchLoading.value = false;
  }
}
function goBack() {
  if (window.history.length > 1) router.back();
  else router.push('/site/data-center/overview');
}
function openOriginal() {
  if (bid.value?.url) window.open(bid.value.url, '_blank', 'noopener');
}
function downloadFiles() {
  // 优先下载采集到的公告附件,否则回退到来源链接
  const atts: any[] = bid.value?.attachments || [];
  const target = atts[0]?.url || bid.value?.attachment_url || bid.value?.url;
  if (target) {
    window.open(target, '_blank', 'noopener');
  } else {
    ElMessage.info('暂未提供招标文件下载');
  }
}
async function toggleAction(action: 'monitor' | 'favorite') {
  try {
    const active = await actionStore.toggle(id, action);
    ElMessage.success(
      active
        ? action === 'monitor'
          ? '已加入监控'
          : '已收藏'
        : action === 'monitor'
          ? '已取消监控'
          : '已取消收藏',
    );
  } catch {
    ElMessage.error('操作失败，请确认已登录');
  }
}
function toggleMonitor() {
  toggleAction('monitor');
}
function toggleFavorite() {
  toggleAction('favorite');
}
async function copyTitle() {
  try {
    await navigator.clipboard.writeText(bid.value?.title || '');
    ElMessage.success('标题已复制');
  } catch {
    ElMessage.warning('复制失败，请手动复制');
  }
}

/** 旧接口 /bids/{id} 的供应商字段名与聚合契约不同, 统一成 SupplierItem */
function normalizeSuppliers(list: any[]): any[] {
  return (list || []).map((s: any, index: number) => ({
    rank: s.rank ?? index + 1,
    name: s.name ?? s.supplier ?? '',
    address: s.address ?? null,
    amount: s.amount != null && s.amount !== '' ? Number(s.amount) : null,
    score: s.score ?? null,
    companyId: s.companyId ?? s.supplier_company_id ?? s.supplierCompanyId ?? null,
  }));
}

function normalizeDetail(data: any) {
  // 旧接口契约(降级路径): 只做字段归一化, 保证模板两条路径都能渲染
  if (!data?.header) {
    return {
      ...data,
      suppliers: normalizeSuppliers(data.suppliers),
      body_excerpt: data.body_excerpt || data.body || '',
      attachments: data.attachments || [],
      enriched: data.enriched || {},
    };
  }
  const purchaser = data.entities?.purchaser;
  const agency = data.entities?.agency;
  const fields = Object.fromEntries(
    (data.kv || []).map((row: any) => [row.label, row.field?.displayText || '未披露']),
  );
  return {
    ...data,
    id: data.header.id,
    title: data.header.title,
    url: data.header.sourceUrl,
    source_name: data.header.sourceName,
    published_at: data.header.publishedAt,
    project_code: data.header.projectCode || data.header.code,
    notice_type: fields['公告类型'],
    region: fields['项目地区'],
    purchaser: purchaser?.name || fields['招标单位'],
    agency: agency?.name || fields['招标代理'],
    purchaser_company_id: purchaser?.entityId,
    purchaser_company: purchaser?.matched ? { id: purchaser.entityId, name: purchaser.name } : null,
    // 修复: 此前用 `item.entityId !== purchaser?.entityId` 过滤, 当两者都为 null 时会把自己过滤掉,
    // 导致"关联单位"在未匹配实体时恒为空。改为只保留已匹配且非采购人的单位。
    related_companies: (data.relatedCompanies || [])
      .filter((item: any) => item?.entityId && item.entityId !== purchaser?.entityId)
      .map((item: any) => ({ id: item.entityId, name: item.name })),
    // 修复: 正文由后端清洗后全量下发, 前端不再 slice(0, 2000) 截断(383 实测被切掉 386 字)
    summary: (data.body || '').slice(0, 500),
    body_excerpt: data.body || '',
    // 修复: 此前硬编码为空数组, 导致中标公告丢失中标供应商与成交金额
    keywords: data.keywords || [],
    suppliers: normalizeSuppliers(data.suppliers),
    enriched: data.enriched || {},
    timeline: (data.timeline || []).map((row: any) => ({
      label: row.name,
      value: row.date,
      summary: row.summary?.displayText,
    })),
  };
}


async function loadBidDetail() {
  try {
    const aggregated: any = await api.get(`/tenders/${id}/detail`, { silent: true });
    return aggregated?.data || null;
  } catch (error: any) {
    const status = error?.response?.status;
    if (status === 401 || status === 403) throw error;
    const legacy: any = await api.get(`/bids/${id}`, { silent: true });
    return legacy?.data || null;
  }
}

onMounted(async () => {
  window.addEventListener('scroll', onScroll, { passive: true });
  try {
    bid.value = normalizeDetail(await loadBidDetail());
    if (bid.value) {
      await actionStore.load(id, {
        isMonitored: Boolean(bid.value?.actions?.isMonitored),
        isCollected: Boolean(bid.value?.actions?.isCollected),
      });
    }
  } finally {
    loading.value = false;
  }
});
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll));
</script>

<style scoped>
/* ==============================================================
   标讯详情页 · 整体布局(对齐截图样式)
   - 顶部:标题 + 内联标签 + 发布时间 | 平台链接 + 操作按钮
   - 标签页:基本信息 / 公告正文 / 招标单位 / 相似推荐
   - 二栏:左侧基本信息 KV 网格 + 关键时间 + 公告正文;
          右侧招标进度时间线 + 关联单位 + 关键词
   ============================================================== */
.bid-detail-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 16px 16px 60px;
  color: var(--site-text);
}
.loading-box { height: 520px; }

/* 面包屑 */
.detail-breadcrumb { margin-bottom: 10px; }
.detail-breadcrumb :deep(.el-breadcrumb__inner) { cursor: pointer; }

/* ============ 顶部头部卡 ============ */
.detail-header {
  background: #fff;
  border: 1px solid #e3eaf3;
  border-radius: 8px;
  padding: 18px 22px;
  display: flex;
  gap: 24px;
  margin-bottom: 0;
  position: relative;
}
.detail-header::before {
  content: '';
  position: absolute;
  left: 0; right: 0; top: 0;
  height: 2px;
  background: linear-gradient(90deg, #3b6fb6 0%, #6ea3d8 100%);
  border-radius: 8px 8px 0 0;
}
.detail-header-left { flex: 1; min-width: 0; }
.detail-header-right {
  flex: 0 0 280px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-end;
}

/* 标题 */
.detail-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2d3d;
  margin: 0 0 12px;
  line-height: 1.45;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}
.title-text { word-break: break-word; }
.title-code {
  font-size: 14px;
  color: #7a8597;
  font-weight: 500;
  font-family: 'Consolas', 'Monaco', monospace;
}

/* 标签 */
.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.title-tag {
  display: inline-block;
  padding: 2px 10px;
  font-size: 12px;
  border-radius: 3px;
  line-height: 1.6;
  font-weight: 500;
  border: 1px solid transparent;
}
.title-tag.tag-status {
  background: #f5f7fa;
  color: #5a6678;
  border-color: #e3e6ec;
}
.title-tag.tag-category {
  background: #e8f1fb;
  color: #3b6fb6;
  border-color: #c5dcf2;
}
.title-tag.tag-warning {
  background: #fff8e6;
  color: #c98a16;
  border-color: #fce5b0;
}
.title-tag.tag-danger {
  background: #fdf0ef;
  color: #c0392b;
  border-color: #f3cdc8;
}
.title-tag.tag-plain {
  background: #fff;
  color: #5a6678;
  border-color: #d8dde5;
}

/* 发布时间 */
.detail-publish {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: #909399;
}
.detail-publish .el-icon { font-size: 13px; }

/* 平台链接 */
.platform-links {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.platform-link {
  font-size: 12.5px;
  color: #3b6fb6;
  text-decoration: none;
  line-height: 1.6;
  transition: color 0.15s ease;
}
.platform-link:hover { color: #1f5fc4; text-decoration: underline; }

/* 操作按钮 */
.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  justify-content: flex-end;
}
.action-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12.5px;
  color: #3b6fb6;
  cursor: pointer;
  text-decoration: none;
  line-height: 1.6;
  padding: 2px 0;
  transition: color 0.15s ease;
}
.action-link:hover { color: #1f5fc4; }
.action-link .el-icon { font-size: 13px; }

/* ============ 标签页 ============ */
.detail-tabs {
  display: flex;
  gap: 0;
  background: #fff;
  border: 1px solid #e3eaf3;
  border-top: 0;
  border-radius: 0 0 8px 8px;
  padding: 0 22px;
  margin-bottom: 14px;
}
.detail-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 14px 18px;
  color: #5a6678;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.detail-tabs button:hover { color: #3b6fb6; }
.detail-tabs button.active {
  color: #3b6fb6;
  border-bottom-color: #3b6fb6;
  font-weight: 600;
}

/* ============ 主体两栏 ============ */
.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
  align-items: start;
}
.content-main,
.content-aside {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

/* ============ 通用信息块 ============ */
.info-section {
  background: #fff;
  border: 1px solid #e3eaf3;
  border-radius: 8px;
  padding: 18px 20px;
}
.section-heading {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 14px;
}
.heading-mark {
  width: 3px;
  height: 16px;
  border-radius: 2px;
  background: #3b6fb6;
}
.section-heading h2 {
  font-size: 16px;
  margin: 0;
  color: #1f2d3d;
  font-weight: 600;
}
.heading-note {
  font-size: 12px;
  color: #909399;
  margin-left: 4px;
}

/* ============ KV 网格 ============
   样式已下沉到公共组件 components/detail/EntityKvGrid.vue,
   标讯 / 公司 / 人员等详情页共用, 此处只保留区块外间距。 */
.kv-section { padding-bottom: 8px; }
.timeinfo-section { padding-bottom: 14px; }

/* ============ 补充信息(正文补抽, 只展示有值项) ============ */
.compact-grid {
  border-top: 1px solid var(--site-hairline);
}
.compact-item {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px;
  min-height: 38px;
  align-items: center;
  border-bottom: 1px dashed var(--site-hairline);
  font-size: 12.5px;
  padding: 6px 0;
}
.compact-item span { color: var(--site-text-mute); }
.compact-item b { color: var(--site-text-dim); font-weight: 500; word-break: break-word; }

/* ============ 资金与中标 ============ */
.money-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 14px;
}
.money-box {
  padding: 14px 16px;
  background: var(--site-bg);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.money-box span { color: var(--site-text-mute); font-size: 12px; }
.money-box strong { color: #3b6fb6; font-size: 18px; font-weight: 600; }
.supplier-list { border-top: 1px solid var(--site-hairline); }
.supplier-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 4px;
  border-bottom: 1px dashed var(--site-hairline);
  font-size: 13px;
}
.supplier-item .rank {
  width: 22px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  background: #eef6ff;
  color: #3b6fb6;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 500;
}
.supplier-item b,
.supplier-item a { flex: 1; color: #1f2d3d; }
.supplier-item a { color: #3b6fb6; cursor: pointer; }
.supplier-amount { color: #3b6fb6; font-weight: 600; }
.supplier-score {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 10px;
  background: #eef6ff;
  color: #3b6fb6;
  font-size: 12px;
}
.supplier-address {
  padding: 4px 4px 10px 32px;
  font-size: 12px;
  color: var(--site-text-mute);
  word-break: break-word;
}

/* ============ 公告正文 ============ */
.announcement-body {
  white-space: pre-wrap;
  line-height: 2;
  color: #4a5566;
  font-size: 13.5px;
  background: #fafcff;
  padding: 16px 18px;
  border-radius: 6px;
  border: 1px solid #e8eef7;
  word-break: break-word;
}
/* 折叠态: 替代此前的 slice(0, 2000) 硬截断, 内容不再丢失 */
.announcement-body.is-collapsed {
  max-height: 320px;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(180deg, #000 72%, transparent 100%);
  mask-image: linear-gradient(180deg, #000 72%, transparent 100%);
}
.body-toggle {
  margin-top: 10px;
  padding: 5px 14px;
  font-size: 12.5px;
  color: #3b6fb6;
  background: #fff;
  border: 1px solid #cfe0f3;
  border-radius: 14px;
  cursor: pointer;
}
.body-toggle:hover { background: #eef6ff; }
.standalone-announcement { min-height: 300px; }

/* ============ 公告附件 ============ */
.attachment-list { list-style: none; margin: 0; padding: 0; }
.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 4px;
  border-bottom: 1px dashed var(--site-hairline);
  font-size: 13px;
}
.attachment-item .el-icon { color: #3b6fb6; flex-shrink: 0; }
.attachment-name {
  flex: 1;
  min-width: 0;
  color: #3b6fb6;
  text-decoration: none;
  word-break: break-all;
}
.attachment-name:hover { text-decoration: underline; }
.attachment-name.is-plain { color: var(--site-text-dim); }
.attachment-size { flex-shrink: 0; color: var(--site-text-mute); font-size: 12px; }
.attachment-download { flex-shrink: 0; color: #3b6fb6; font-size: 12.5px; }
.attachment-tip { flex-shrink: 0; color: #b0b5bd; font-size: 12px; }

/* ============ 更正内容 ============ */
.correction-table { width: 100%; }
.cell-raw { color: var(--site-text-dim); cursor: help; }
.cell-muted { color: #b0b5bd; font-size: 12px; }
@media (max-width: 640px) {
  .attachment-item { flex-wrap: wrap; }
  .attachment-name { flex-basis: 100%; }
}

/* ============ 招标进度时间线(右侧栏) ============ */
.progress-panel { padding-bottom: 8px; }
.vertical-timeline { padding: 4px 0 4px 4px; }
.timeline-event {
  position: relative;
  display: flex;
  gap: 12px;
  padding: 0 0 18px 0;
}
.timeline-event::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 12px;
  bottom: 0;
  width: 1px;
  background: #b9dfc7;
}
.timeline-event:last-child { padding-bottom: 4px; }
.timeline-event:last-child::before { display: none; }
.timeline-dot {
  position: relative;
  z-index: 1;
  flex: 0 0 11px;
  width: 11px;
  height: 11px;
  margin-top: 4px;
  border-radius: 50%;
  background: #20a04b;
  box-shadow: 0 0 0 3px #e1f5e7;
}
.timeline-event.is-latest .timeline-dot {
  background: #20a04b;
  box-shadow: 0 0 0 3px #cdebd8;
}
.timeline-body { flex: 1; min-width: 0; }
.timeline-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.timeline-name {
  color: #1f2d3d;
  font-size: 13.5px;
  font-weight: 500;
}
.timeline-date {
  color: #5a6678;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
}
.timeline-badge {
  display: inline-block;
  font-size: 11px;
  color: #fff;
  background: linear-gradient(90deg, #ff7a45, #ff5a2a);
  padding: 0 6px;
  border-radius: 3px;
  font-weight: 500;
  line-height: 18px;
}
.timeline-stars {
  font-size: 11px;
  color: #c45656;
  letter-spacing: 1px;
  line-height: 1.4;
}

/* ============ 关联单位 + 关键词 ============ */
.company-entry {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 4px;
  border-bottom: 1px dashed var(--site-hairline);
  cursor: pointer;
  transition: background 0.15s ease;
}
.company-entry:hover { background: #fafcff; }
.company-entry:last-of-type { border-bottom: 0; }
.company-entry.big { padding: 14px 8px; }
.company-entry > div { flex: 1; min-width: 0; }
.company-entry span {
  display: block;
  color: var(--site-text-mute);
  font-size: 11px;
  margin-bottom: 3px;
}
.company-entry b {
  display: block;
  color: #3b6fb6;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}
.company-entry > .el-icon:last-child { color: var(--site-text-mute); font-size: 12px; }
.keyword-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.side-empty {
  color: var(--site-text-mute);
  font-size: 12.5px;
  padding: 8px 0;
}

/* ============ 招标单位(独立 tab) ============ */
.structured-section { padding: 20px 22px; }

/* ============ 相似推荐 ============ */
.similar-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.similar-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid #e3eaf3;
  background: #fff;
  border-radius: 6px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}
.similar-card:hover {
  border-color: #3b6fb6;
  box-shadow: 0 4px 14px rgba(59, 111, 182, 0.12);
}
.similar-card strong { color: #1f2d3d; line-height: 1.6; font-size: 14px; font-weight: 600; }
.similar-card span { color: #909399; font-size: 12px; }
.similar-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.similar-tag {
  display: inline-block;
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 3px;
  background: #eef6ff;
  color: #3b6fb6;
  border: 1px solid #d6e5f3;
}

/* ============ 人脉网络 ============ */
.network-section { padding: 18px 20px; }

/* ============ 悬浮操作按钮 ============ */
.floating-detail-actions {
  position: fixed;
  right: 24px;
  bottom: 90px;
  z-index: 80;
  display: flex;
  flex-direction: column;
  gap: 8px;
  opacity: 0;
  pointer-events: none;
  transform: translateY(10px);
  transition: 0.2s;
}
.floating-detail-actions.visible {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

/* ==============================================================
   响应式
   ============================================================== */
@media (max-width: 1024px) {
  .detail-header-right { flex: 0 0 240px; }
  .content-grid { grid-template-columns: minmax(0, 1fr) 260px; }
}
@media (max-width: 820px) {
  .detail-header { flex-direction: column; }
  .detail-header-right { flex: 1 1 auto; align-items: flex-start; }
  .platform-links { align-items: flex-start; }
  .detail-actions { justify-content: flex-start; }
  .content-grid { grid-template-columns: 1fr; }
  .similar-list { grid-template-columns: 1fr; }
  .floating-detail-actions { right: 12px; bottom: 70px; }
}
@media (max-width: 560px) {
  .bid-detail-page { padding: 12px 10px 50px; }
  .detail-title { font-size: 17px; }
  .title-code { font-size: 12px; }
  .detail-tabs { padding: 0 12px; overflow-x: auto; }
  .detail-tabs button { padding: 12px 12px; font-size: 13px; white-space: nowrap; }
  .info-section { padding: 14px 14px; }
  .money-row { grid-template-columns: 1fr; }
  .announcement-body { padding: 12px; }
}
</style>
