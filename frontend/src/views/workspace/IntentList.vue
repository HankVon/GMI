<!--
  意向性项目信息页: 政务源(发改委/自然资源厅等)意向项目结构化列表
  + 中标活跃单位榜: 从海量招标中标公告挖掘经常中标的单位
-->
<template>
  <div class="intent-page">
    <el-tabs v-model="activeTab" class="intent-tabs">
      <!-- Tab1: 意向项目 -->
      <el-tab-pane label="意向项目" name="intents">
        <div class="page-head">
          <h2>意向性项目信息</h2>
          <div class="head-actions">
            <el-button v-if="!isPortal" type="primary" size="small" :loading="crawling" @click="runCrawl">
              <el-icon><Refresh /></el-icon>抓取意向源
            </el-button>
          </div>
        </div>

        <!-- 统计 -->
        <el-row :gutter="14" class="stat-row">
          <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ stats.total ?? 0 }}</div><div class="stat-label">意向总数</div></div></el-col>
          <el-col :span="6">
            <div class="stat-card"><div class="stat-num">{{ typeStats.length }}</div><div class="stat-label">项目类型</div></div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card"><div class="stat-num">{{ recentCount }}</div><div class="stat-label">近90天</div></div>
          </el-col>
          <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ crawlResult?.stored ?? '-' }}</div><div class="stat-label">最近抓取</div></div></el-col>
        </el-row>

        <!-- 筛选 -->
        <el-card class="filter-card" shadow="never">
          <div class="filters">
            <el-select v-model="filters.project_type" placeholder="项目类型" clearable size="small" style="width: 150px">
              <el-option v-for="(t, i) in typeStats" :key="i" :label="typeLabel(t.type)" :value="t.type" />
            </el-select>
            <RegionCascader v-model="regionVal" @change="onRegionChange" />
            <el-input v-model="filters.min_amount" placeholder="金额下限(万)" clearable size="small" style="width: 130px" type="number" />
            <el-select v-model="filters.days" size="small" style="width: 130px">
              <el-option label="近30天" :value="30" />
              <el-option label="近90天" :value="90" />
              <el-option label="近一年" :value="365" />
              <el-option label="全部" :value="0" />
            </el-select>
            <el-button type="primary" size="small" @click="loadList">查询</el-button>
          </div>
        </el-card>

        <!-- 列表 -->
        <el-card class="list-card" shadow="never">
          <el-table :data="items" size="small" v-loading="loading">
            <el-table-column prop="title" label="标题" min-width="360" show-overflow-tooltip>
              <template #default="{ row }">
                <el-link type="primary" :underline="false" @click="openDetail(row)">{{ row.title }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="typeColor(row.project_type)">{{ typeLabel(row.industry || row.project_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="dept" label="发布部门" width="160" show-overflow-tooltip />
            <el-table-column prop="region" label="地域" width="110" />
            <el-table-column label="金额(万)" width="100">
              <template #default="{ row }">{{ row.amount != null ? Number(row.amount).toLocaleString() : '-' }}</template>
            </el-table-column>
            <el-table-column prop="contact" label="联系方式" width="130" show-overflow-tooltip />
            <el-table-column label="意向依据" min-width="130">
              <template #default="{ row }">
                <el-popover v-if="(row.reason || []).length" placement="top" :width="360" trigger="hover">
                  <template #reference>
                    <span class="reason-more">+{{ row.reason.length }} 项理由</span>
                  </template>
                  <div class="reason-pop">
                    <div v-for="(r, ri) in row.reason" :key="ri" class="reason-pop-item" :class="{ 'is-main': ri === 0 }">
                      <span class="reason-pop-dot"></span>{{ r }}
                    </div>
                  </div>
                </el-popover>
                <span v-else class="reason-empty">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="published_at" label="抓取时间" width="100" />
            <el-table-column v-if="!isPortal" label="操作" width="80" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="page" v-model:page-size="pageSize"
            :total="total" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next"
            class="pager" @change="loadList"
          />
        </el-card>
      </el-tab-pane>

      <!-- Tab2: 中标活跃单位榜 -->
      <el-tab-pane label="中标活跃单位" name="winners">
        <div class="page-head">
          <h2>中标活跃单位榜</h2>
          <div class="head-actions tip-text">从海量招标中标公告挖掘经常中标/拿到项目的单位</div>
        </div>

        <div v-if="wSummary.missing_time" class="warn-tip">
          <el-icon><Warning /></el-icon>
          <span>有 {{ wSummary.missing_time }} 条中标公告未解析出发布时间，无法参与时间窗筛选，已计入「全部」统计</span>
        </div>

        <!-- 汇总统计 -->
        <el-row :gutter="14" class="stat-row">
          <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ wSummary.bid_total ?? 0 }}</div><div class="stat-label">中标公告</div></div></el-col>
          <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ wSummary.winner_total ?? 0 }}</div><div class="stat-label">上榜单位</div></div></el-col>
          <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ fmtWan(wSummary.total_amount_wan) }}</div><div class="stat-label">累计金额(万)</div></div></el-col>
          <el-col :span="6"><div class="stat-card"><div class="stat-num">{{ wItems.length }}</div><div class="stat-label">当前展示</div></div></el-col>
        </el-row>

        <!-- 筛选 -->
        <el-card class="filter-card" shadow="never">
          <div class="filters">
            <el-input v-model="wKeyword" placeholder="单位名关键字" clearable size="small" style="width: 160px" @keyup.enter="loadWinners" />
            <el-select v-model="wDays" size="small" style="width: 130px">
              <el-option label="近30天" :value="30" />
              <el-option label="近90天" :value="90" />
              <el-option label="近一年" :value="365" />
              <el-option label="全部" :value="0" />
            </el-select>
            <el-select v-model="wMinCount" size="small" style="width: 150px">
              <el-option label="全部中标(≥1次)" :value="1" />
              <el-option label="常客(≥2次)" :value="2" />
              <el-option label="熟客(≥3次)" :value="3" />
            </el-select>
            <el-select v-model="wSort" size="small" style="width: 130px">
              <el-option label="按中标次数" value="count" />
              <el-option label="按累计金额" value="amount" />
              <el-option label="按最近中标" value="last" />
            </el-select>
            <el-button type="primary" size="small" @click="loadWinners">查询</el-button>
          </div>
        </el-card>

        <!-- 榜单 -->
        <el-card class="list-card" shadow="never">
          <el-table :data="wItems" size="small" v-loading="wLoading">
            <el-table-column label="#" width="52" align="center">
              <template #default="{ $index }">
                <span class="rank-num" :class="{ 'rank-top': $index < 3 }">{{ $index + 1 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="单位名称" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="winner-name-cell">
                  <el-link v-if="row.company_id" type="primary" :underline="false" @click="openCompany(row.company_id)">{{ row.name }}</el-link>
                  <span v-else class="winner-raw-name">{{ row.name }}</span>
                  <el-tag v-for="t in row.tags" :key="t" size="small" effect="plain" class="winner-tag">{{ t }}</el-tag>
                </div>
                <div v-if="row.province || row.city" class="winner-loc">
                  <el-icon><Location /></el-icon>{{ row.province || '' }}{{ row.city || '' }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="中标次数" width="92" align="center">
              <template #default="{ row }">
                <span class="win-count">{{ row.win_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="累计金额(万)" width="120" align="right">
              <template #default="{ row }">{{ fmtWan(row.total_amount_wan) }}</template>
            </el-table-column>
            <el-table-column label="平均金额(万)" width="110" align="right">
              <template #default="{ row }">{{ fmtWan(row.avg_amount_wan) }}</template>
            </el-table-column>
            <el-table-column prop="last_win" label="最近中标" width="100" />
            <el-table-column label="活跃月份" width="84" align="center">
              <template #default="{ row }">{{ row.active_months ?? '-' }}个月</template>
            </el-table-column>
            <el-table-column label="采购人(业主)" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <template v-if="row.purchasers && row.purchasers.length">
                  <el-tag v-for="(p, i) in row.purchasers.slice(0, 3)" :key="i" size="small" type="info" class="winner-tag">{{ p }}</el-tag>
                  <span v-if="row.purchasers.length > 3" class="winner-more">等{{ row.purchasers.length }}家</span>
                </template>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="意向商机" width="88" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" :loading="oppLoadingName === row.name" @click="openOpportunities(row)">
                  意向
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!wLoading && !wItems.length" description="暂无中标单位数据，可先去「数据流水线」采集中标公告" :image-size="90" />
        </el-card>
      </el-tab-pane>

      <!-- Tab3: 高价值目标单位（机会侦察） -->
      <el-tab-pane label="目标单位" name="scout">
        <div class="page-head">
          <h2>高价值目标单位（机会侦察）</h2>
          <div class="head-actions">
            <span class="tip-text">从项目库/人脉/中标推导"该盯谁、查什么" → 反哺意向采集</span>
            <el-button v-if="!isPortal" type="primary" size="small" :loading="scoutLoading" @click="loadScout">
              <el-icon><Refresh /></el-icon>刷新侦察
            </el-button>
          </div>
        </div>
        <el-card class="list-card" shadow="never">
          <div v-if="!scoutTargets.length && !scoutLoading" class="empty-tip">暂无侦察目标 — 数据积累后自动推导</div>
          <div v-else class="scout-grid" v-loading="scoutLoading">
            <div v-for="t in scoutTargets" :key="t.unit" class="scout-card">
              <div class="scout-head">
                <div class="scout-name">{{ t.unit }}</div>
                <el-tag size="small" :type="t.score >= 10 ? 'danger' : t.score >= 6 ? 'warning' : 'info'" effect="dark">
                  {{ t.score }}分
                </el-tag>
              </div>
              <div class="scout-meta">
                <el-tag v-if="t.region_label" size="small" effect="plain">{{ t.region_label }}</el-tag>
                <el-tag v-for="s in t.sources" :key="s" size="small" type="success" effect="plain">{{ s }}</el-tag>
              </div>
              <div class="scout-reason">{{ t.reason }}</div>
              <div v-if="t.keywords?.length" class="scout-kw">
                <el-tag v-for="k in t.keywords.slice(0, 4)" :key="k" size="small" type="info" effect="plain" class="kw-tag">{{ k }}</el-tag>
                <span v-if="t.keywords.length > 4" class="kw-more">+{{ t.keywords.length - 4 }}</span>
              </div>
              <div v-if="t.last_activity" class="scout-last">最近活跃 {{ t.last_activity }}</div>
            </div>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 反向关联: 中标单位 → 意向商机 弹窗 -->
    <el-dialog v-model="oppVisible" :title="`「${oppUnit?.name || ''}」可能关注的意向项目`" width="860px" destroy-on-close append-to-body align-center>
      <!-- 证据链: 该单位真实做过的项目 -->
      <div v-if="oppProfile" class="opp-evidence">
        <div class="opp-evidence-head">
          <el-icon><Collection /></el-icon>
          <span>证据链：该单位在库中真实参与/中标的项目</span>
          <span class="opp-evidence-count">{{ oppProfile.projects?.length || 0 }} 个</span>
        </div>
        <div class="opp-evidence-body">
          <div v-if="oppProfile.projects?.length" class="opp-evidence-items">
            <div v-for="(pr, pi) in oppProfile.projects" :key="pi" class="opp-evidence-item">
              <span class="opp-evidence-tag" :class="pr.source === '中标项目' ? 'tag-won' : 'tag-join'">{{ pr.source }}</span>
              <span class="opp-evidence-name">{{ pr.name }}</span>
              <span class="opp-evidence-meta">
                <template v-if="pr.province">{{ pr.province }}</template><template v-if="pr.city">{{ pr.city }}</template><template v-if="pr.county">{{ pr.county }}</template>
                <el-tag v-if="pr.category" size="small" effect="plain" class="opp-evidence-cat">{{ catLabel(pr.category) }}</el-tag>
              </span>
            </div>
          </div>
          <div v-else class="opp-evidence-empty">
            未找到该单位在库中的项目参与/中标记录，无法建立证据链，不推荐意向项目。
          </div>
        </div>
      </div>
      <el-divider class="opp-divider" />
      <div class="opp-rule-tip">
        <el-icon><InfoFilled /></el-icon>
        <span>推荐规则：仅当意向项目与该单位做过项目「同地域 + 同业务」双证据成立时才推荐；弱证据一律不推。</span>
      </div>
      <div v-loading="oppLoading" class="opp-list">
        <template v-if="oppItems.length">
          <div v-for="it in oppItems" :key="it.intent_id" class="opp-item">
            <div class="opp-item-head">
              <el-link v-if="it.url" type="primary" :underline="false" @click="openUrl(it.url)" target="_blank" class="opp-item-title">{{ it.title }}</el-link>
              <span v-else class="opp-item-title">{{ it.title }}</span>
              <el-tag size="small" :type="it.kind === 'tender' ? 'success' : 'primary'" effect="plain">
                {{ it.kind === 'tender' ? '招标公告' : '意向批复' }}
              </el-tag>
              <el-tag v-if="it.kind !== 'tender' && (it.industry || it.project_type)" size="small" :type="typeColor(it.project_type)">{{ typeLabel(it.industry || it.project_type) }}</el-tag>
              <el-tag size="small" type="warning" effect="plain">双证据命中 {{ it.score }} 分</el-tag>
            </div>
            <div class="opp-item-meta">
              <span><el-icon><Location /></el-icon>{{ it.region || '-' }}</span>
              <span v-if="it.amount_wan != null">预算 {{ fmtWan(it.amount_wan) }} 万</span>
              <span v-if="it.published_at">发布于 {{ it.published_at }}</span>
            </div>
            <div v-if="it.reasons?.length" class="opp-item-reason">
              <el-icon><InfoFilled /></el-icon>
              <span v-for="(rs, ri) in it.reasons" :key="ri" class="reason-chip">{{ rs }}</span>
            </div>
          </div>
        </template>
        <el-empty v-else-if="!oppLoading" description="无满足「同地域+同业务」双证据的意向项目（弱证据不推）" :image-size="80" />
      </div>
    </el-dialog>

    <!-- 意向详情弹窗: 结构化字段 + 意向理由 + 原文 -->
    <el-dialog v-model="detailVisible" title="意向信息详情" width="780px" destroy-on-close append-to-body align-center>
      <div v-if="detailLoading" class="detail-loading" v-loading="true" style="min-height: 200px"></div>
      <template v-else-if="detail">
        <div class="detail-title">
          <el-link v-if="detail.url" type="primary" :underline="false" @click="openUrl(detail.url)" target="_blank">{{ detail.title }}</el-link>
          <span v-else>{{ detail.title }}</span>
        </div>

        <!-- 意向理由 -->
        <div class="detail-section">
          <div class="detail-section-head"><el-icon><InfoFilled /></el-icon>为什么这是一条意向信息</div>
          <div class="detail-reasons">
            <el-tag v-for="(r, ri) in detail.reason || []" :key="ri" size="small" effect="plain" class="detail-reason-tag">{{ r }}</el-tag>
          </div>
        </div>

        <!-- 结构化字段 -->
        <div class="detail-section">
          <div class="detail-section-head"><el-icon><Collection /></el-icon>结构化信息</div>
          <el-descriptions :column="3" border size="small" class="detail-desc">
            <el-descriptions-item label="项目类型">
              <el-tag size="small" :type="typeColor(detail.project_type)">{{ typeLabel(detail.industry || detail.project_type) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="地域">{{ detail.region || '-' }}</el-descriptions-item>
            <el-descriptions-item label="预算(万)">{{ detail.amount != null ? Number(detail.amount).toLocaleString() : '-' }}</el-descriptions-item>
            <el-descriptions-item label="发布部门">{{ detail.dept || '-' }}</el-descriptions-item>
            <el-descriptions-item label="来源">{{ detail.source_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发布时间">{{ detail.published_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="联系方式" :span="2">{{ detail.contact || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 项目单位匹配 -->
        <div v-if="detail.matched_entity" class="detail-section">
          <div class="detail-section-head"><el-icon><OfficeBuilding /></el-icon>关联单位</div>
          <div class="detail-unit">
            <el-tag size="small" :type="detail.matched_entity.matched ? 'success' : 'info'" effect="dark">
              {{ detail.matched_entity.matched ? '已匹配公司库' : '未匹配' }}
            </el-tag>
            <span class="detail-unit-name">{{ detail.matched_entity.unit }}</span>
            <span v-if="detail.matched_entity.company" class="detail-unit-company">→ {{ detail.matched_entity.company }}</span>
            <span v-if="detail.matched_entity.doc_no" class="detail-unit-doc">文号：{{ detail.matched_entity.doc_no }}</span>
          </div>
        </div>

        <!-- 人脉关联: 意向 × 人脉库匹配 -->
        <div v-if="detail.related_people?.length || detail.related_companies?.length" class="detail-section">
          <div class="detail-section-head"><el-icon><Avatar /></el-icon>人脉关联</div>
          <div v-if="detail.related_people?.length" class="detail-rel-group">
            <span class="rel-label">相关人员</span>
            <div v-for="(p, pi) in detail.related_people" :key="'p' + pi" class="rel-item">
              <el-tag size="small" type="warning" effect="dark">{{ p.entity_name }}</el-tag>
              <span class="rel-reason">{{ p.match_reason }}</span>
              <el-tag size="small" type="success" effect="plain" class="rel-score">{{ p.score }}</el-tag>
            </div>
          </div>
          <div v-if="detail.related_companies?.length" class="detail-rel-group">
            <span class="rel-label">相关单位</span>
            <div v-for="(c, ci) in detail.related_companies" :key="'c' + ci" class="rel-item">
              <el-tag size="small" type="primary" effect="dark">{{ c.entity_name }}</el-tag>
              <span class="rel-reason">{{ c.match_reason }}</span>
              <el-tag size="small" type="success" effect="plain" class="rel-score">{{ c.score }}</el-tag>
            </div>
          </div>
        </div>

        <!-- 人脉触达路径(真实图谱计算) -->
        <div v-if="reachPath.paths.length || reachPath.note" class="detail-section">
          <div class="detail-section-head"><el-icon><Connection /></el-icon>人脉触达路径</div>
          <p class="reach-note">{{ reachPath.note }}</p>
          <div v-for="(p, pi) in reachPath.paths.slice(0, 3)" :key="pi" class="reach-path">
            <div class="reach-target">
              <el-tag size="small" type="danger" effect="dark">{{ p.target_role }}</el-tag>
              <span class="reach-tname">{{ p.target }}</span>
            </div>
            <div class="reach-hops">
              <template v-for="(nd, ni) in (p.nodes as any[])" :key="ni">
                <span class="reach-node" :class="String(nd.type || '').toLowerCase()">{{ nd.name }}</span>
                <span v-if="ni < (p.nodes as any[]).length - 1" class="reach-arrow">→</span>
              </template>
            </div>
            <div class="reach-tip" v-if="p.kind === 'via_unit'">经关联单位内部人员触达</div>
            <div class="reach-tip weak" v-else-if="p.kind === 'weak_region'">同地域弱关联，建议线下建立业务联系</div>
          </div>
          <div v-if="reachPath.bridges.length" class="reach-bridges">
            <span class="bridge-label">可作桥接人：</span>
            <el-tag v-for="b in reachPath.bridges" :key="b.name" size="small" type="success" effect="plain" class="bridge-tag">{{ b.name }}</el-tag>
          </div>
        </div>

        <!-- 原文摘要 -->
        <div v-if="detail.raw_text" class="detail-section">
          <div class="detail-section-head"><el-icon><Document /></el-icon>原文摘要</div>
          <div class="detail-raw">{{ detail.raw_text }}</div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "IntentList" });
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useNavBase } from "@/utils/navBase";
import { usePortalMode } from "@/utils/portalMode";
import { ElMessage } from "element-plus";
import { Refresh, Location, Warning, InfoFilled, Collection, OfficeBuilding, Document, Avatar, Connection } from "@element-plus/icons-vue";
import api from "@/api";
import RegionCascader from "@/components/RegionCascader.vue";
import { typeLabel, typeColor as typeColorShared } from "@/utils/typeLabels";
const typeColor = typeColorShared;

const router = useRouter();
const { navTo } = useNavBase();
const { isPortal } = usePortalMode();
const activeTab = ref("intents");

/* ===== 意向项目 ===== */
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const crawling = ref(false);
const stats = ref<any>({});
const crawlResult = ref<any>(null);
const filters = ref<any>({ project_type: "", min_amount: "", days: 90 });
const regionVal = ref<string[]>([]);
function onRegionChange(v: { province: string; city: string; county: string }) {
  filters.value.province = v.province || undefined;
  filters.value.city = v.city || undefined;
  filters.value.county = v.county || undefined;
  loadList();
}

const typeStats = computed(() => stats.value.types || []);
const recentCount = computed(() => {
  const d = filters.value.days || 90;
  return items.value.filter((i) => {
    if (!i.published_at) return false;
    const t = new Date(i.published_at).getTime();
    return Date.now() - t < d * 86400000;
  }).length;
});

function openUrl(url: string) { window.open(url, "_blank", "noopener"); }

/* ===== 意向详情 ===== */
const detailVisible = ref(false);
const detail = ref<any>(null);
const detailLoading = ref(false);
const reachPath = ref<{ paths: any[]; bridges: any[]; note: string }>({ paths: [], bridges: [], note: "" });
async function openDetail(row: any) {
  detailVisible.value = true;
  detail.value = null;
  detailLoading.value = true;
  reachPath.value = { paths: [], bridges: [], note: "" };
  try {
    const res: any = await api.get(`/intent/intent-detail/${row.id}`);
    detail.value = res.data;
  } catch { detail.value = null; }
  finally { detailLoading.value = false; }
  // 加载真实人脉触达路径(后台账号已绑定人员时返回路径)
  try {
    const r: any = await api.get(`/intent/path/${row.id}`);
    if (r?.success) {
      reachPath.value = { paths: r.paths || [], bridges: r.bridges || [], note: r.note || "" };
    }
  } catch { /* 静默 */ }
}

/* ===== 高价值目标单位（机会侦察） ===== */
const scoutTargets = ref<any[]>([]);
const scoutLoading = ref(false);
async function loadScout() {
  scoutLoading.value = true;
  try {
    const r: any = await api.get("/intent/scout/targets?top_n=12");
    scoutTargets.value = r?.data || [];
  } catch { scoutTargets.value = []; }
  scoutLoading.value = false;
}
// 切到「目标单位」Tab 时自动加载
watch(activeTab, (v) => { if (v === "scout" && !scoutTargets.value.length) loadScout(); });

async function loadStats() {
  try { stats.value = (await api.get("/intent/stats")) || {}; } catch { stats.value = {}; }
}
async function loadList() {
  loading.value = true;
  try {
    const params: any = {
      page: page.value, page_size: pageSize.value, days: filters.value.days || undefined,
    };
    if (filters.value.project_type) params.project_type = filters.value.project_type;
    if (filters.value.province) params.province = filters.value.province;
    if (filters.value.city) params.city = filters.value.city;
    if (filters.value.county) params.county = filters.value.county;
    if (filters.value.min_amount) params.min_amount = filters.value.min_amount;
    const res: any = await api.get("/intent/list", { params });
    items.value = res.items || [];
    total.value = res.total || 0;
  } catch { items.value = []; }
  finally { loading.value = false; }
}
async function runCrawl() {
  crawling.value = true;
  try {
    const res: any = await api.post("/intent/crawl", {}, { timeout: 300000 });
    crawlResult.value = res.data || res;
    ElMessage.success(`抓取完成：${crawlResult.value.stored ?? 0} 条入库`);
    await loadStats();
    await loadList();
  } catch { /* 拦截器 */ }
  finally { crawling.value = false; }
}

/* ===== 中标活跃单位 ===== */
const wItems = ref<any[]>([]);
const wSummary = ref<any>({});
const wLoading = ref(false);
const wKeyword = ref("");
const wDays = ref(90);
const wMinCount = ref(2);
const wSort = ref("count");
let wLoaded = false;

function fmtWan(v: any): string {
  return v == null || v === "" ? "-" : Number(v).toLocaleString();
}
function catLabel(c: string): string {
  return typeLabel(c);
}
function openCompany(id: number) {
  router.push(navTo(`/companies/${id}`));
}
const oppVisible = ref(false);
const oppUnit = ref<any>(null);
const oppItems = ref<any[]>([]);
const oppProfile = ref<any>(null);
const oppLoading = ref(false);
const oppLoadingName = ref("");
async function openOpportunities(row: any) {
  oppUnit.value = row;
  oppVisible.value = true;
  oppItems.value = [];
  oppProfile.value = null;
  oppLoadingName.value = row.name;
  oppLoading.value = true;
  try {
    const res: any = await api.get("/intent/winner-opportunities", {
      params: { name: row.name, days: 0, limit: 30 },
    });
    oppItems.value = res.items || [];
    oppProfile.value = res.profile || null;
  } catch { oppItems.value = []; }
  finally {
    oppLoading.value = false;
    oppLoadingName.value = "";
  }
}
async function loadWinners() {
  wLoading.value = true;
  try {
    const params: any = {
      days: wDays.value, min_count: wMinCount.value, sort: wSort.value, limit: 100,
    };
    if (wKeyword.value) params.keyword = wKeyword.value;
    const res: any = await api.get("/intent/winners", { params });
    wItems.value = res.items || [];
    wSummary.value = res.summary || {};
    wLoaded = true;
  } catch { wItems.value = []; }
  finally { wLoading.value = false; }
}

watch(activeTab, (t) => {
  if (t === "winners" && !wLoaded) loadWinners();
});

onMounted(() => { loadStats(); loadList(); });
</script>

<style scoped>
.intent-page { max-width: 1400px; padding-bottom: 32px; }
.intent-tabs { background: transparent; }
.intent-tabs :deep(.el-tabs__header) { margin-bottom: 14px; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.page-head h2 { margin: 0; font-size: 20px; color: #1f2d3d; }
.tip-text { font-size: 12.5px; color: #909399; }
.warn-tip {
  display: flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: #b26a0a;
  background: #fdf6ec; border: 1px solid #f5dab1; border-radius: 6px;
  padding: 8px 14px; margin-bottom: 14px;
}
.stat-row { margin-bottom: 14px; }
.stat-card { background: #fff; border-radius: 8px; padding: 16px 20px; border: 1px solid #e9edf6; text-align: center; border-top: 3px solid #2979ff; }
.stat-num { font-size: 26px; font-weight: 700; color: #2979ff; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.filter-card { margin-bottom: 14px; border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.filters { display: flex; gap: 10px; flex-wrap: wrap; }
.list-card { border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.pager { margin-top: 14px; justify-content: flex-end; }

/* 榜单样式 */
.rank-num { font-weight: 600; color: #606266; }
.rank-num.rank-top { color: #fff; background: linear-gradient(135deg, #2979ff, #1d63e0); border-radius: 4px; padding: 1px 8px; display: inline-block; min-width: 22px; text-align: center; }
.winner-name-cell { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.winner-raw-name { color: #303133; font-weight: 500; }
.winner-loc { font-size: 12px; color: #909399; margin-top: 2px; display: flex; align-items: center; gap: 3px; }
.winner-tag { margin-left: 0; margin-right: 4px; }
.win-count { font-size: 15px; font-weight: 700; color: #2979ff; }
.winner-more { font-size: 12px; color: #909399; }

/* 反向关联弹窗 */
.opp-evidence { background: #f8fbff; border: 1px solid #dde7fa; border-radius: 8px; padding: 12px 14px; }
.opp-evidence-head { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: #303133; }
.opp-evidence-head .el-icon { color: #2979ff; }
.opp-evidence-count { margin-left: auto; color: #909399; font-weight: 400; }
.opp-evidence-body { margin-top: 10px; }
.opp-evidence-items { display: flex; flex-direction: column; gap: 6px; max-height: 220px; overflow-y: auto; }
.opp-evidence-item { display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
.opp-evidence-tag { flex-shrink: 0; font-size: 11px; border-radius: 3px; padding: 1px 6px; }
.tag-won { background: #fdf0e8; color: #d07a1f; }
.tag-join { background: #e8f4ff; color: #2979ff; }
.opp-evidence-name { color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.opp-evidence-meta { flex-shrink: 0; color: #909399; font-size: 12px; display: flex; align-items: center; gap: 4px; }
.opp-evidence-empty { color: #909399; font-size: 12.5px; }
.opp-rule-tip { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #909399; margin-bottom: 12px; }
.opp-rule-tip .el-icon { color: #e6a23c; }
.opp-divider { margin: 12px 0; }
.opp-list { min-height: 80px; }
.opp-item { border: 1px solid #e9edf6; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; background: #fafcff; }
.opp-item-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.opp-item-title { font-weight: 500; }
.opp-item-meta { display: flex; align-items: center; gap: 16px; font-size: 12.5px; color: #909399; margin-top: 6px; flex-wrap: wrap; }
.opp-item-meta .el-icon { vertical-align: -2px; margin-right: 2px; }
.opp-item-reason { display: flex; align-items: flex-start; gap: 4px; margin-top: 8px; font-size: 12px; color: #4b5264; flex-wrap: wrap; }
.reason-chip { background: #eef4ff; color: #2979ff; border-radius: 4px; padding: 2px 8px; }

/* 意向依据列 */
.reason-cell { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.reason-more { font-size: 12px; color: #2979ff; cursor: pointer; white-space: nowrap; }
.reason-empty { color: #c0c4cc; }
.reason-pop { max-height: 220px; overflow-y: auto; }
.reason-pop-item { display: flex; align-items: flex-start; gap: 6px; font-size: 12px; color: #4b5264; line-height: 1.6; padding: 3px 0; }
.reason-pop-item.is-main { color: #303133; font-weight: 500; }
.reason-pop-dot { width: 6px; height: 6px; border-radius: 50%; background: #2979ff; margin-top: 6px; flex-shrink: 0; }
.reason-pop-item.is-main .reason-pop-dot { background: #67c23a; }

/* 人脉关联 */
.detail-rel-group { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.rel-label { font-size: 12px; color: #909399; line-height: 24px; width: 60px; flex-shrink: 0; }
.rel-item { display: inline-flex; align-items: center; gap: 6px; background: #f8fafc; border: 1px solid #eef1f8; border-radius: 6px; padding: 3px 8px; }
.rel-reason { font-size: 12px; color: #4b5264; }
.rel-score { font-size: 11px; }

/* 高价值目标单位 */
.scout-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; padding: 4px 2px; }
.scout-card {
  border: 1px solid #eef1f8; border-radius: 10px; padding: 14px 16px;
  background: linear-gradient(180deg, #fafcff, #ffffff); transition: box-shadow .2s;
}
.scout-card:hover { box-shadow: 0 4px 14px rgba(77, 107, 254, 0.12); }
.scout-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.scout-name { font-weight: 600; color: #111827; font-size: 14px; line-height: 1.4; }
.scout-meta { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.scout-reason { color: #6b7280; font-size: 12px; line-height: 1.6; min-height: 36px; }
.scout-kw { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 8px; }
.kw-tag { max-width: 130px; }
.kw-more { font-size: 12px; color: #a3adc0; }
.scout-last { font-size: 11px; color: #a3adc0; margin-top: 6px; text-align: right; }

/* 详情弹窗 */
.detail-loading { display: flex; align-items: center; justify-content: center; }
.detail-title { font-size: 17px; font-weight: 600; color: #1f2d3d; line-height: 1.5; margin-bottom: 16px; }
.detail-section { margin-bottom: 16px; }
.detail-section-head { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: #303133; margin-bottom: 8px; }
.detail-section-head .el-icon { color: #2979ff; }
.detail-reasons { display: flex; flex-wrap: wrap; gap: 6px; }
.detail-reason-tag { max-width: 100%; }
.detail-desc :deep(.el-descriptions__label) { width: 90px; }
.detail-unit { display: flex; align-items: center; gap: 8px; font-size: 13px; flex-wrap: wrap; }
.detail-unit-name { font-weight: 500; color: #303133; }
.detail-unit-company { color: #2979ff; }
.detail-unit-doc { color: #909399; font-size: 12px; }
/* 人脉触达路径 */
.reach-note { margin: 0 0 8px; font-size: 12.5px; color: #7a8499; }
.reach-path { border: 1px solid #e9edf6; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; background: #fbfcff; }
.reach-target { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.reach-tname { font-size: 13.5px; font-weight: 600; color: #1f2d3d; }
.reach-hops { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; font-size: 12px; line-height: 1.7; }
.reach-node {
  background: #fff; border: 1px solid #e2e7f0; border-radius: 5px; padding: 2px 7px;
  color: #5b6478; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.reach-node.person { border-color: #bcd3ea; color: #3b6fb6; }
.reach-node.company { border-color: #e3b7c0; color: #a51c30; }
.reach-node.project { border-color: #e5d9bd; color: #b08d57; }
.reach-node.region { border-color: #d9d6d0; color: #8b93a7; }
.reach-arrow { color: #a3adc0; flex-shrink: 0; }
.reach-tip { margin-top: 5px; font-size: 11.5px; color: #2979ff; }
.reach-tip.weak { color: #b08d57; }
.reach-bridges { margin-top: 8px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; font-size: 12.5px; }
.bridge-label { color: #7a8499; }
.bridge-tag { margin-right: 0; }
.detail-raw {
  background: #f8fafc; border: 1px solid #e9edf6; border-radius: 8px; padding: 12px 14px;
  font-size: 13px; color: #4b5264; line-height: 1.7; max-height: 280px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all;
}
</style>
