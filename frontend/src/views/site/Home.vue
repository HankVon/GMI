<template>
  <SiteLayout>
    <!-- 顶部引导：左侧面包屑，右侧用户信息行 -->
    <div class="top-guide">
      <div class="site-container top-guide-inner">
        <span class="top-guide-l">您好，欢迎来到地质与产业情报数据中台！</span>
        <span class="top-guide-r">
          <a href="/site/intelligence">信息动态</a>
          <a href="/site/data-center">数据中心</a>
          <a href="/site/solutions">解决方案</a>
          <a href="/site/contact">联系我们</a>
        </span>
      </div>
    </div>

    <!-- 顶部 banner 大搜索区 + 6 图标入口 -->
    <section class="hhb-banner">
      <div class="site-container hhb-inner">
        <div class="hhb-head">
          <div class="hhb-tabs">
            <span
              v-for="t in searchTabs"
              :key="t.key"
              :class="{ active: searchTab === t.key }"
              @click="setSearchTab(t.key)"
            >{{ t.label }}</span>
          </div>
          <div class="hhb-hot">
            热搜：
            <a v-for="(k, i) in hotKeys" :key="i" href="javascript:;" @click="setKeyword(k)">{{ k }}</a>
          </div>
        </div>

        <div class="hhb-search">
          <el-input
            v-model="keyword"
            class="hhb-input"
            :placeholder="searchPlaceholders[searchTab]"
            clearable
            size="large"
            @keyup.enter="goSearch"
          />
          <el-button class="hhb-btn" size="large" type="primary" @click="goSearch">
            <el-icon><Search /></el-icon>查 询
          </el-button>
        </div>

        <div class="hhb-icon-row">
          <a
            v-for="q in quickNavs"
            :key="q.title"
            :href="q.to"
            class="hhb-icon-card"
          >
            <div class="hhb-icon" :style="{ background: q.bg }">
              <el-icon><component :is="q.icon" /></el-icon>
            </div>
            <div class="hhb-icon-label">{{ q.title }}</div>
            <div class="hhb-icon-desc">{{ q.desc }}</div>
          </a>
        </div>
      </div>
    </section>

    <!-- 资质与认证 bar -->
    <section class="cert-bar">
      <div class="site-container cert-inner">
        <div class="cert-logo">
          <span class="cert-mark">地</span>
          <span>
            <strong>地矿智库</strong>
            <em>— 中国地质行业互联网综合服务门户</em>
          </span>
        </div>
        <div class="cert-list">
          <div class="cert-item" v-for="c in certs" :key="c.title">
            <div class="cert-icon" :style="{ color: c.color }">
              <el-icon><component :is="c.icon" /></el-icon>
            </div>
            <div>
              <strong>{{ c.title }}</strong>
              <span>{{ c.sub }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 主体三栏：左侧分类 / 中间地图与情报 / 右侧排行与图表 -->
    <section class="hhb-main">
      <div class="site-container main-grid">
        <!-- 左侧分类导航 -->
        <aside class="main-left">
          <div class="left-card">
            <div class="left-title">地质标讯 · 勘查 · 治理</div>
            <ul class="left-cat">
              <li v-for="c in leftCats" :key="c.label">
                <a :href="c.to">
                  <el-icon><component :is="c.icon" /></el-icon>
                  <span>{{ c.label }}</span>
                  <em class="hot">HOT</em>
                </a>
              </li>
            </ul>
          </div>
          <div class="left-card">
            <div class="left-title">地勘资质 · 人才</div>
            <ul class="left-cat">
              <li v-for="c in leftCats2" :key="c.label">
                <a :href="c.to">
                  <el-icon><component :is="c.icon" /></el-icon>
                  <span>{{ c.label }}</span>
                </a>
              </li>
            </ul>
          </div>
        </aside>

        <!-- 中央 -->
        <div class="main-center">
          <!-- 中国地图 + 概况统计 -->
          <div class="cn-map-card">
            <div class="cm-head">
              <span class="cm-title">全国地质业务分布热力</span>
              <a class="cm-more" href="/site/data-center/overview">查看更多区域 <el-icon><ArrowRight /></el-icon></a>
            </div>
            <div class="cm-body">
              <div class="cm-map">
                <EChart :option="mapOption" height="320px" />
              </div>
              <div class="cm-side">
                <div class="cm-stat" v-for="s in cnStats" :key="s.label">
                  <div class="cm-stat-num">{{ s.value }}</div>
                  <div class="cm-stat-label">{{ s.label }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 中部：三分类列表（勘探招标 / 矿产中标 / 治理项目） -->
          <div class="three-list">
            <div class="tl-tab" :class="{ on: tlTab === 'zb' }" @click="tlTab = 'zb'">勘探招标</div>
            <div class="tl-tab" :class="{ on: tlTab === 'zj' }" @click="tlTab = 'zj'">矿产中标</div>
            <div class="tl-tab" :class="{ on: tlTab === 'zj_nj' }" @click="tlTab = 'zj_nj'">治理项目</div>
            <ul class="tl-list">
              <li v-for="(item, i) in tlItems" :key="i">
                <span class="tl-date">{{ item.date }}</span>
                <a class="tl-title" :href="item.to">{{ item.title }}</a>
                <span class="tl-region">{{ item.region }}</span>
              </li>
              <li v-if="!tlItems.length" class="tl-empty">暂无该分类实时更新</li>
            </ul>
            <div class="tl-foot">
              <a href="javascript:;" @click="$router.push('/site/data-center/overview')">查看更多信息 +</a>
            </div>
          </div>
        </div>

        <!-- 右侧 -->
        <aside class="main-right">
          <!-- 排行榜列表 -->
          <div class="right-card">
            <div class="right-head">
              <span class="rh-title">本周访问排行</span>
              <a href="javascript:;" @click="$router.push('/site/data-center/companies')">更多</a>
            </div>
            <ul class="rank-list">
              <li v-for="(r, i) in viewRanking" :key="r.name">
                <i :class="{ top: i < 3 }">{{ i + 1 }}</i>
                <span class="rl-name">{{ r.name }}</span>
                <span class="rl-num">{{ r.value }}{{ r.unit }}</span>
              </li>
              <li v-if="!viewRanking.length" class="rl-empty">暂无数据</li>
            </ul>
          </div>
          <!-- 推荐地勘单位 -->
          <div class="right-card">
            <div class="right-head">
              <span class="rh-title">推荐地勘单位</span>
              <a href="javascript:;" @click="$router.push('/site/solutions')">更多</a>
            </div>
            <ul class="rcmd-list">
              <li v-for="(r, i) in recommendList" :key="i">
                <div class="rcmd-num">0{{ i + 1 }}</div>
                <div class="rcmd-body">
                  <div class="rcmd-name">{{ r.name }}</div>
                  <div class="rcmd-meta">{{ r.meta }}</div>
                </div>
              </li>
              <li v-if="!recommendList.length" class="rcmd-empty">暂无推荐</li>
            </ul>
          </div>
        </aside>
      </div>
    </section>

    <!-- 红色 CTA：地质大数据平台 -->
    <section class="cta-banner">
      <div class="site-container cta-inner">
        <span class="cta-l">地矿智库</span>
        <strong class="cta-m">地质大数据平台 4.0 上线：构建矿产资源全生命周期情报网络</strong>
        <a class="cta-r" href="/site/contact">立即咨询 →</a>
      </div>
    </section>

    <!-- 请选择地质服务领域  Tabs -->
    <section class="field-section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">GEOSCIENCE · 服务领域</span>
          <h2 class="site-h2">请选择地质服务领域</h2>
          <p class="site-sub">基础调查 · 矿产勘查 · 灾害防治 · 水文地质 · 工程地质全覆盖，科学支撑资源保障与防灾减灾。</p>
        </div>
        <div class="field-tabs">
          <span
            v-for="t in fieldTabs"
            :key="t.key"
            class="ft-tab"
            :class="{ on: fieldTab === t.key }"
            @click="fieldTab = t.key"
          >{{ t.label }}</span>
        </div>
        <div class="field-grid">
          <a
            v-for="(it, i) in fieldItems"
            :key="i"
            :href="it.to"
            class="fg-item"
          >
            <strong>{{ it.name }}</strong>
            <span class="fg-meta">{{ it.meta }}</span>
            <span class="fg-loc">{{ it.location }}</span>
          </a>
        </div>
      </div>
    </section>

    <!-- 三列数据情报流（情报动态 - 时间线 / 筛选 / 列表） -->
    <section class="intel-section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">INTELLIGENCE FEED</span>
          <h2 class="site-h2">地质行业情报动态</h2>
          <p class="site-sub">以勘探招标 / 矿产中标 / 治理项目三栏呈现，结合地域与时间筛选快速锁定地勘线索。</p>
        </div>

        <HomeNewsPanel
          :active-category="activeHomeCategory"
          :items="homeCategoryItems"
          @change-category="changeHomeCategory"
          @select="selectHomeItem"
          @more="openHomeCategory"
        />
      </div>
    </section>

    <!-- 国际地学数据合作（多机构 + 介绍） -->
    <section class="oversea-section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">GLOBAL GEOSCIENCE</span>
          <h2 class="site-h2">国际地学数据合作</h2>
          <p class="site-sub">链接全球地学机构数据库，与美、欧、日、俄及东盟等区域地质调查机构合作互通。</p>
        </div>
        <div class="oversea-grid">
          <div class="ovs-card" v-for="c in overseaCards" :key="c.title">
            <div class="ovs-flag" :style="{ background: c.bg }">{{ c.short }}</div>
            <div class="ovs-body">
              <strong>{{ c.title }}</strong>
              <span>{{ c.sub }}</span>
              <em>{{ c.members }} 家合作单位</em>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 地质技术与装备服务  4 卡片 -->
    <section class="prod-section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">TECH & EQUIPMENT</span>
          <h2 class="site-h2">地质技术与装备服务</h2>
          <p class="site-sub">钻探 · 物探 · 测试 · 监测四大方向甄选先进装备与技术服务商，赋能野外作业。</p>
        </div>
        <div class="prod-grid">
          <a v-for="p in prodItems" :key="p.title" class="prod-card" :href="p.to">
            <div class="prod-img" :style="{ background: p.bg }">
              <el-icon><component :is="p.icon" /></el-icon>
            </div>
            <div class="prod-body">
              <strong>{{ p.title }}</strong>
              <p>{{ p.desc }}</p>
              <span class="prod-cta">查看产品 ›</span>
            </div>
          </a>
        </div>
      </div>
    </section>

    <!-- 地质学术研讨  3 列 -->
    <section class="seminar-section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">ACADEMIC FORUM</span>
          <h2 class="site-h2">地质学术研讨</h2>
          <p class="site-sub">聚焦深地探测、灾害防治与水文地质前沿，联动科研院所与产业实践。</p>
        </div>
        <div class="seminar-grid">
          <article
            v-for="s in seminars"
            :key="s.title"
            class="seminar-card"
            :style="{ background: s.bg }"
            @click="$router.push('/site/solutions')"
          >
            <span class="sem-tag">{{ s.tag }}</span>
            <h3>{{ s.title }}</h3>
            <p>{{ s.desc }}</p>
            <span class="sem-date">{{ s.date }}</span>
          </article>
        </div>
      </div>
    </section>

    <!-- 权威资质认证 logo 阵列 -->
    <section class="credit-section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">QUALIFICATION · 资质认证</span>
          <h2 class="site-h2">权威资质认证体系</h2>
          <p class="site-sub">对接自然资源、地调系统等行业权威资质与信用认证单位。</p>
        </div>
        <div class="credit-tabs">
          <span
            v-for="t in creditTabs"
            :key="t"
            :class="{ on: creditTab === t }"
            @click="creditTab = t"
          >{{ t }}</span>
        </div>
        <div class="credit-grid">
          <div v-for="c in creditLogos" :key="c.name" class="cg-item">
            <div class="cg-mark" :style="{ color: c.color }">{{ c.short }}</div>
            <span>{{ c.name }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 指标墙与统计数据（保留原站点的统计展示） -->
    <section class="stat-section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">PLATFORM METRICS</span>
          <h2 class="site-h2">平台实时数据</h2>
          <p class="site-sub">数据更新于 {{ updatedAt }}。</p>
        </div>
        <div class="stat-grid">
          <div class="stat-card" v-for="k in kpis" :key="k.title">
            <div class="stat-icon" :style="{ background: k.bg, color: k.color }">
              <el-icon><component :is="k.icon" /></el-icon>
            </div>
            <div>
              <div class="stat-num">{{ k.value }}<small>{{ k.unit }}</small></div>
              <div class="stat-title">{{ k.title }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </SiteLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import SiteLayout from "@/components/site/SiteLayout.vue";
import EChart from "@/components/site/EChart.vue";
import HomeNewsPanel from "@/components/site/HomeNewsPanel.vue";
import { fetchOverview, fetchHomeConfig, type CmsBlock, default as siteApi } from "@/api/siteApi";
import {
  ArrowRight, DataBoard, OfficeBuilding, Cpu, User, Search,
  Tickets, Document, Medal, Trophy, DataAnalysis, Promotion,
  Connection, Monitor, Files, Histogram, Coin, Lock,
  Star, ChatLineRound, Compass, SetUp, Flag, Phone, ChatDotRound,
  Box, Sort, EditPen, Watermelon, TakeawayBox, Postcard,
} from "@element-plus/icons-vue";

const router = useRouter();

/* ────────── 顶部搜索 tabs ────────── */
type SearchTabKey = "company" | "person" | "project" | "bid";
const searchTabs: Array<{ key: SearchTabKey; label: string }> = [
  { key: "company", label: "查地勘单位" },
  { key: "person", label: "查地质人才" },
  { key: "project", label: "查勘查项目" },
  { key: "bid", label: "查地质标讯" },
];
const searchTab = ref<SearchTabKey>("company");
const searchPlaceholders: Record<string, string> = {
  company: "输入单位名称关键词（如「地质调查院」「矿冶集团」「勘测院」）",
  person: "输入人员姓名关键词（自动脱敏）",
  project: "输入项目名称关键词（如「地质勘探」「灾害治理」）",
  bid: "输入招标公告标题或编号关键词",
};
const hotKeys = ["地质勘查", "矿产普查", "地质灾害治理", "水文地质", "工程勘察", "地热资源"];
const keyword = ref("");
function setSearchTab(k: SearchTabKey) {
  searchTab.value = k;
}
function setKeyword(k: string) {
  keyword.value = k;
}
function goSearch() {
  const kw = keyword.value.trim();
  if (!kw) return;
  const map: Record<SearchTabKey, string> = {
    company: "/site/data-center/companies",
    person: "/site/data-center/persons",
    project: "/site/data-center/projects",
    bid: "/site/data-center/overview",
  };
  router.push({ path: map[searchTab.value], query: kw ? { keyword: kw } : {} });
}

/* ────────── 顶部 6 个图标入口（默认值, 后台 CMS 配置可覆盖） ────────── */
const quickNavs = ref([
  { title: "地质标讯", desc: "地勘招投标与中标动态", to: "/site/data-center/overview?tab=bid", icon: Tickets, bg: "linear-gradient(135deg, #e01a3c 0%, #c8102e 100%)" },
  { title: "地勘单位", desc: "地质单位 360° 多维画像", to: "/site/data-center/companies", icon: OfficeBuilding, bg: "linear-gradient(135deg, #ff6a6a 0%, #c8102e 100%)" },
  { title: "地质人才", desc: "专业人员任职与参与项目", to: "/site/data-center/persons", icon: User, bg: "linear-gradient(135deg, #4cc0a4 0%, #2f8f5b 100%)" },
  { title: "技术装备", desc: "钻探 · 物探 · 测试装备", to: "/site/solutions", icon: Box, bg: "linear-gradient(135deg, #b08d57 0%, #8a6a36 100%)" },
  { title: "资质认证", desc: "地勘资质与信用认证", to: "/site/about", icon: Medal, bg: "linear-gradient(135deg, #9c6bff 0%, #6633cc 100%)" },
  { title: "海外矿产", desc: "全球矿产资源数据库", to: "/site/intelligence", icon: Promotion, bg: "linear-gradient(135deg, #5b9bf6 0%, #2c4ec4 100%)" },
]);

/* ────────── 认证 bar（默认值, CMS 配置可覆盖） ────────── */
const certs = ref([
  { title: "地勘甲级资质", sub: "勘查资质等级核验", icon: Lock, color: "#c8102e" },
  { title: "安全生产许可", sub: "野外作业安全认证", icon: Star, color: "#c8102e" },
  { title: "CMA 计量认证", sub: "检测实验室资质", icon: Trophy, color: "#2f8f5b" },
  { title: "ISO 体系认证", sub: "国际标准体系", icon: Lock, color: "#b08d57" },
]);

/* ────────── 左侧分类 ────────── */
const leftCats = [
  { label: "地质勘探招标", icon: Document, to: "/site/data-center/overview?tab=bid" },
  { label: "矿产勘查中标", icon: Trophy, to: "/site/data-center/overview?tab=win" },
  { label: "灾害治理项目", icon: Histogram, to: "/site/data-center/projects" },
  { label: "水文地质公告", icon: Promotion, to: "/site/intelligence" },
  { label: "工程勘察预告", icon: EditPen, to: "/site/data-center/overview" },
  { label: "答疑补遗", icon: ChatLineRound, to: "/site/contact" },
];
const leftCats2 = [
  { label: "勘查资质等级", icon: Medal, to: "/site/data-center/companies" },
  { label: "注册地质师", icon: User, to: "/site/data-center/persons" },
  { label: "项目负责人", icon: DataAnalysis, to: "/site/data-center/persons" },
  { label: "单位业绩", icon: Connection, to: "/site/data-center/companies" },
  { label: "诚信记录", icon: Star, to: "/site/data-center/companies" },
  { label: "联系方式", icon: Phone, to: "/site/contact" },
];

/* ────────── 中央三分类列表 ────────── */
const overview = ref<any>(null);
type TL = "zb" | "zj" | "zj_nj";
const tlTab = ref<TL>("zb");
const tlItems = computed(() => {
  const d = homeData.value || {};
  if (tlTab.value === "zb") return (d.latest_tenders || []).slice(0, 8).map((x: any) => ({
    date: (x.published_at || x.updated_at || "").slice(5, 10),
    title: x.title || x.name || "—",
    region: x.province || x.region || "全国",
    to: x.id ? `/site/data-center/overview?tab=bid&id=${x.id}` : "/site/data-center/overview",
  }));
  if (tlTab.value === "zj") return (d.latest_bids || []).slice(0, 8).map((x: any) => ({
    date: (x.published_at || x.updated_at || "").slice(5, 10),
    title: x.title || x.name || "—",
    region: x.province || x.region || "全国",
    to: x.id ? `/site/data-center/overview?tab=win&id=${x.id}` : "/site/data-center/overview",
  }));
  return (d.latest_projects || []).slice(0, 8).map((x: any) => ({
    date: (x.published_at || x.updated_at || "").slice(5, 10),
    title: x.title || x.name || "—",
    region: x.province || x.region || "全国",
    to: x.id ? `/site/data-center/projects/${x.id}` : "/site/data-center/projects",
  }));
});

/* ────────── 中央地图 + 概况统计 ────────── */
const updatedAt = ref("—");
const cnStats = computed(() => {
  const t = overview.value?.totals || {};
  return [
    { value: (t.bid_notices ?? "—").toLocaleString("zh-CN"), label: "实时地质标讯" },
    { value: (t.companies ?? "—").toLocaleString("zh-CN"), label: "覆盖地勘单位" },
    { value: (t.web_clues ?? "—").toLocaleString("zh-CN"), label: "AI 情报线索" },
    { value: (t.persons ?? "—").toLocaleString("zh-CN"), label: "地质专业人才" },
  ];
});

const mapOption = computed(() => {
  const rows = (overview.value?.region_top ?? []).slice().reverse();
  return {
    tooltip: { trigger: "item" },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: "category", show: false, data: rows.map((r: any) => r.province) },
    yAxis: { type: "value", show: false },
    series: [{
      type: "bar",
      data: rows.map((r: any) => r.count),
      barWidth: 10,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,         colorStops: [
          { offset: 0, color: "#ff6a6a" },
          { offset: 1, color: "#c8102e" },
        ] },
      },
      label: { show: true, position: "top", color: "#4a4646", fontSize: 11 },
    }],
  };
});

/* ────────── 右侧排行与推荐 ────────── */
const viewRanking = computed<Array<{ name: string; value: any; unit: string }>>(() => {
  const t = (overview.value?.top_companies || []) as Array<any>;
  return t
    .slice(0, 10)
    .map((x: any) => ({
      name: x?.name || x?.company_name || "—",
      value: x?.visit_count ?? x?.score ?? "—",
      unit: "",
    }))
    .filter((x: { name: string }) => x.name && x.name !== "—");
});

const recommendList = ref([
  { name: "中国地质调查局", meta: "基础地质调查 · 北京" },
  { name: "中冶集团武汉勘察院", meta: "岩土工程勘察 · 武汉" },
  { name: "四川省地矿局", meta: "矿产勘查开发 · 成都" },
  { name: "中煤地质总局水文局", meta: "水文地质 · 邯郸" },
  { name: "中国有色金属矿产调查中心", meta: "矿产地质调查 · 北京" },
]);

/* ────────── 请选择地质服务领域 ────────── */
const fieldTabs = ref([
  { key: "survey", label: "基础地质调查" },
  { key: "ore", label: "矿产勘查开发" },
  { key: "hazard", label: "地质灾害防治" },
  { key: "hydro", label: "水文地质勘察" },
  { key: "eng", label: "工程地质勘察" },
  { key: "geo", label: "地热与新能源" },
  { key: "rock", label: "岩土工程治理" },
  { key: "monitor", label: "地质环境监测" },
]);
const fieldTab = ref("survey");
/** CMS 配置的领域条目(按 item_key 分组), 为空时使用内置默认数据 */
const fieldConfigItems = ref<Record<string, any[]>>({});
const fieldItems = computed(() => {
  const cfg = fieldConfigItems.value[fieldTab.value];
  if (cfg && cfg.length) return cfg;
  const samples: Record<string, any[]> = {
    survey: [
      { name: "南岭成矿带区域地质调查", meta: "1:25 万区调 · 构造专项", location: "湖南 · 郴州", to: "/site/data-center/projects" },
      { name: "青藏高原东缘基础地质调查", meta: "1:5 万填图 · 遥感解译", location: "四川 · 甘孜", to: "/site/data-center/projects" },
      { name: "华北陆块前寒武系专题调查", meta: "同位素年代学 · 岩相分析", location: "山西 · 五台", to: "/site/data-center/projects" },
      { name: "西秦岭造山带地质填图", meta: "岩石地层 · 构造解析", location: "甘肃 · 天水", to: "/site/data-center/projects" },
      { name: "扬子地块新元古代地层", meta: "沉积相 · 层序地层", location: "湖北 · 宜昌", to: "/site/data-center/projects" },
      { name: "天山造山带深部探测", meta: "大地电磁 · 深反射地震", location: "新疆 · 乌鲁木齐", to: "/site/data-center/projects" },
      { name: "大兴安岭成矿带调查", meta: "航空物探 · 化探异常查证", location: "内蒙古 · 呼伦贝尔", to: "/site/data-center/projects" },
      { name: "海岸带地质环境调查", meta: "第四纪地质 · 沉积演化", location: "广东 · 湛江", to: "/site/data-center/projects" },
    ],
    ore: [
      { name: "锂辉石矿详查项目", meta: "钻探 12000m · 选矿试验", location: "四川 · 马尔康", to: "/site/data-center/projects" },
      { name: "铜多金属矿普查", meta: "槽探 + 钻探 · 化探异常", location: "西藏 · 玉龙", to: "/site/data-center/projects" },
      { name: "稀土矿勘查评价", meta: "浅钻取样 · 储量估算", location: "江西 · 赣州", to: "/site/data-center/projects" },
      { name: "金矿深部找矿突破", meta: "坑道钻探 · 蚀变填图", location: "山东 · 胶东", to: "/site/data-center/projects" },
      { name: "铁矿资源储量核实", meta: "三维建模 · 资源量分割", location: "河北 · 迁安", to: "/site/data-center/projects" },
      { name: "萤石矿勘探", meta: "物探定靶 · 钻探验证", location: "浙江 · 常山", to: "/site/data-center/projects" },
      { name: "石墨矿勘查", meta: "样品测试 · 工业指标论证", location: "黑龙江 · 鸡西", to: "/site/data-center/projects" },
      { name: "地热温泉勘查评价", meta: "地温场测试 · 热储层分析", location: "广东 · 丰顺", to: "/site/data-center/projects" },
    ],
    hazard: [
      { name: "汶川震区滑坡治理工程", meta: "抗滑桩 + 锚索 · 监测预警", location: "四川 · 汶川", to: "/site/data-center/projects" },
      { name: "三峡库区塌岸防治", meta: "库岸再造 · 工程护坡", location: "重庆 · 巫山", to: "/site/data-center/projects" },
      { name: "黄土高原崩塌隐患治理", meta: "削坡减载 · 排水系统", location: "陕西 · 延安", to: "/site/data-center/projects" },
      { name: "泥石流沟谷综合防治", meta: "拦挡坝 · 排导槽", location: "云南 · 东川", to: "/site/data-center/projects" },
      { name: "地裂缝调查与监测", meta: "InSAR 监测 · 水准测量", location: "陕西 · 西安", to: "/site/data-center/projects" },
      { name: "岩溶塌陷勘查防治", meta: "物探探查 · 注浆加固", location: "广西 · 桂林", to: "/site/data-center/projects" },
      { name: "山洪地质灾害调查评价", meta: "1:5 万灾害调查 · 风险区划", location: "贵州 · 毕节", to: "/site/data-center/projects" },
      { name: "采空区塌陷综合治理", meta: "充填治理 · 稳定性评估", location: "山西 · 大同", to: "/site/data-center/projects" },
    ],
    hydro: [
      { name: "西北干旱区水资源勘查", meta: "水文测井 · 抽水试验", location: "甘肃 · 河西走廊", to: "/site/data-center/projects" },
      { name: "地下水污染风险调查", meta: "水质采样 · 数值模拟", location: "河北 · 沧州", to: "/site/data-center/projects" },
      { name: "矿泉水水源地评价", meta: "水化学分析 · 补给量计算", location: "吉林 · 长白山", to: "/site/data-center/projects" },
      { name: "岩溶大泉保护论证", meta: "示踪试验 · 泉域划分", location: "贵州 · 贵安", to: "/site/data-center/projects" },
      { name: "城市应急水源地勘查", meta: "物探定井 · 成井试验", location: "山东 · 济南", to: "/site/data-center/projects" },
      { name: "地热流体动态监测", meta: "水位水温自动监测", location: "西藏 · 羊八井", to: "/site/data-center/projects" },
      { name: "矿山疏干排水评估", meta: "涌水量预测 · 防治水设计", location: "河南 · 平顶山", to: "/site/data-center/projects" },
      { name: "沿海咸水入侵调查", meta: "水化学分层 · 电法探测", location: "广东 · 珠海", to: "/site/data-center/projects" },
    ],
  };
  return samples[fieldTab.value] || samples.survey;
});

/* ────────── 最新动态（情报动态 - 复刻原 HomeNewsPanel 行为） ────────── */
const activeHomeCategory = ref(localStorage.getItem("gmi_home_category") || "companies");
const homeData = ref<Record<string, any> | null>(null);
const homeCategoryItems = computed(() => {
  const d = homeData.value || {};
  const map: Record<string, any[]> = {
    companies: (d.latest_companies || []).map((x: any) => ({ ...x, type: x.company_type, capital: x.registered_capital, updated_at: x.latest_bid_at || x.updated_at })),
    bids: (d.latest_bids || []).map((x: any) => ({ ...x, name: x.title, type: x.notice_type, updated_at: x.published_at, amount: x.amount })),
    tenders: d.latest_tenders || [],
    projects: d.latest_projects || [],
    persons: d.latest_persons || [],
    managers: d.latest_managers || [],
    qualifications: d.latest_qualifications || [],
    honors: d.latest_honors || [],
    credit: d.latest_credit || [],
    intents: (d.latest_intents || []).map((x: any) => ({
      ...x, name: x.title, type: x.industry || x.project_type || "意向",
      updated_at: x.published_at, amount: x.amount_level,
    })),
  };
  return map[activeHomeCategory.value] || [];
});
function changeHomeCategory(key: string) {
  activeHomeCategory.value = key;
  localStorage.setItem("gmi_home_category", key);
  loadHomeCategory(key);
}
function openHomeCategory(key: string) {
  // 意向 → 前台「项目商机」列表页
  if (key === "intents") router.push("/site/intelligence");
  else if (key === "bids" || key === "tenders") router.push("/site/data-center/overview");
  else if (key === "persons" || key === "managers") router.push("/site/data-center/persons");
  else if (["companies", "qualifications", "honors", "credit"].includes(key)) router.push("/site/data-center/companies");
  else router.push("/site/data-center/projects");
}
function selectHomeItem(item: any) {
  if (!item?.id) return;
  // 意向 → 前台情报详情页(/site/intelligence/:id)
  if (activeHomeCategory.value === "intents") router.push(`/site/intelligence/${item.id}`);
  else if (["bids", "tenders"].includes(activeHomeCategory.value)) router.push(`/site/data-center/bids/${item.id}`);
  else if (["persons", "managers"].includes(activeHomeCategory.value)) router.push(`/site/data-center/persons/${item.id}`);
  else router.push(`/site/data-center/companies/${item.id}`);
}
async function fetchHome() {
  try {
    const res: any = await siteApi.get("/public/home");
    homeData.value = res?.data || null;
  } catch { /* ignore */ }
}
async function loadHomeCategory(key: string) {
  try {
    const res: any = await siteApi.get("/public/home/feed", { params: { category: key, page: 1, page_size: 12 } });
    const data = res?.data;
    if (data) homeData.value = { ...(homeData.value || {}), [`latest_${key}`]: data.items || [] };
  } catch { /* ignore */ }
}

/* ────────── 国际地学数据合作（默认值, CMS 可覆盖） ────────── */
const overseaCards = ref([
  { short: "US", title: "美国地质调查局", sub: "USGS · 全球矿产资源数据库", members: 320, bg: "linear-gradient(135deg, #4c79c4 0%, #1f3e85 100%)" },
  { short: "EU", title: "欧洲地质调查联盟", sub: "EuroGeoSurveys · 欧洲地学网络", members: 210, bg: "linear-gradient(135deg, #4c84c4 0%, #1f4a85 100%)" },
  { short: "AS", title: "中国—东盟地学中心", sub: "CAGS · 东南亚地质合作", members: 180, bg: "linear-gradient(135deg, #ffa157 0%, #c8102e 100%)" },
  { short: "JP", title: "日本地质调查所", sub: "AIST · 东亚灾害与矿产物探", members: 95, bg: "linear-gradient(135deg, #ff8293 0%, #c8314b 100%)" },
  { short: "RU", title: "俄罗斯地质调查所", sub: "VSEGEI · 独联体矿产数据库", members: 64, bg: "linear-gradient(135deg, #ce73ff 0%, #7c3aae 100%)" },
  { short: "AF", title: "非洲地学数据平台", sub: "Africa Geoscience Network", members: 48, bg: "linear-gradient(135deg, #f5c147 0%, #b88a1f 100%)" },
]);

/* ────────── 地质技术与装备服务（默认值, CMS 可覆盖） ────────── */
const prodItems = ref([
  { title: "钻探装备", desc: "岩芯钻机 · 绳索取芯 · 定向钻进 成套方案", icon: Box, bg: "linear-gradient(135deg, #ff6a6a 0%, #c8102e 100%)", to: "/site/solutions" },
  { title: "物探仪器", desc: "电法 · 地震 · 磁法 · 高精度测量设备", icon: Watermelon, bg: "linear-gradient(135deg, #4cc0a4 0%, #2f8f5b 100%)", to: "/site/solutions" },
  { title: "测试化验", desc: "岩矿测试 · 水质分析 · CMA 实验室服务", icon: Coin, bg: "linear-gradient(135deg, #ffaf63 0%, #d27825 100%)", to: "/site/solutions" },
  { title: "遥感监测", desc: "InSAR 地质灾害监测 · 无人机航测", icon: Promotion, bg: "linear-gradient(135deg, #b08dff 0%, #6633cc 100%)", to: "/site/solutions" },
]);

/* ────────── 地质学术研讨（默认值, CMS 可覆盖） ────────── */
const seminars = ref([
  { tag: "深地探测", title: "深地资源探测与智能勘查研讨会", desc: "聚焦深部找矿、智能钻探与三维地质建模的技术进展与应用。", date: "2026 · 09 · 成都", bg: "linear-gradient(135deg, #2c66b8 0%, #1a3a6e 100%)" },
  { tag: "灾害防治", title: "地质灾害防治与风险管控论坛", desc: "探讨滑坡、泥石流、岩溶塌陷的监测预警与工程防治体系。", date: "2026 · 10 · 重庆", bg: "linear-gradient(135deg, #1f8f5b 0%, #115f3b 100%)" },
  { tag: "水文地质", title: "水文地质与水资源可持续利用", desc: "面向地下水保护、水源地评价与地热开发的前沿对话。", date: "2026 · 11 · 武汉", bg: "linear-gradient(135deg, #c8761a 0%, #8a4d0c 100%)" },
]);

/* ────────── 资质认证体系（默认值, CMS 可覆盖） ────────── */
const creditTabs = ref(["勘查资质", "检测认证", "行业准入", "信用评级", "绿色勘查"]);
const creditTab = ref("勘查资质");
const creditLogos = ref([
  { name: "自然资源部", short: "资", color: "#c8102e" },
  { name: "中国地质调查局", short: "调", color: "#c8102e" },
  { name: "中国矿业联合会", short: "矿", color: "#2f8f5b" },
  { name: "全国地质资料馆", short: "馆", color: "#b08d57" },
  { name: "中国地震局", short: "震", color: "#9c6bff" },
  { name: "CMA 计量认证", short: "C", color: "#c8102e" },
  { name: "ISO 9001", short: "9", color: "#2f8f5b" },
  { name: "ISO 14001", short: "4", color: "#c8102e" },
  { name: "AAA 信用", short: "A", color: "#ff9800" },
  { name: "高新技术企业", short: "高", color: "#c8102e" },
  { name: "专精特新", short: "专", color: "#2f8f5b" },
  { name: "绿色勘查规范", short: "绿", color: "#b08d57" },
]);

/* ────────── KPI 指标墙 ────────── */
const kpis = computed(() => {
  const t = overview.value?.totals;
  return [
    { title: "地质标讯线索", value: t?.bid_notices ?? "—", unit: "条", icon: DataBoard, bg: "#fceef0", color: "#c8102e" },
    { title: "覆盖地勘单位", value: t?.companies ?? "—", unit: "家", icon: OfficeBuilding, bg: "#fceef0", color: "#c8102e" },
    { title: "AI 情报线索", value: t?.web_clues ?? "—", unit: "条", icon: Cpu, bg: "#e5f6f0", color: "#2f8f5b" },
    { title: "地质专业人才", value: t?.persons ?? "—", unit: "人", icon: User, bg: "#faf1e5", color: "#b08d57" },
  ];
});

/* ────────── 后台首页配置(CMS)驱动 ────────── */
/** 图标名 → Element Plus 图标组件的映射 */
const iconMap: Record<string, any> = {
  Tickets, Document, Medal, Trophy, User, OfficeBuilding, Box, Promotion,
  Lock, Star, DataBoard, Cpu, Histogram, Connection, EditPen, ChatLineRound,
  DataAnalysis, Phone, Watermelon, Coin, ArrowRight,
};

function resolveIcon(name: string | null | undefined, fallback: any) {
  if (name && iconMap[name]) return iconMap[name];
  return fallback;
}

/** 拉取并应用后台首页配置; 未配置/失败时保持内置默认值。 */
async function loadHomeConfig() {
  const cfg = await fetchHomeConfig();
  if (!cfg || !cfg.blocks) return;

  const map = (block: CmsBlock | undefined) => {
    if (!block || !block.items) return [];
    return block.items.filter((it) => it.enabled === 1);
  };

  // 图标入口
  const qlinks = map(cfg.blocks.quick_links);
  if (qlinks.length) {
    quickNavs.value = qlinks.map((it) => ({
      title: it.title,
      desc: it.subtitle || "",
      to: it.link || "/site/intelligence",
      icon: resolveIcon(it.icon, Tickets),
      bg: (it.meta && it.meta.bg) || "linear-gradient(135deg, #e01a3c 0%, #c8102e 100%)",
    }));
  }

  // 认证条
  const certItems = map(cfg.blocks.certs);
  if (certItems.length) {
    certs.value = certItems.map((it) => ({
      title: it.title,
      sub: it.subtitle || "",
      icon: resolveIcon(it.icon, Lock),
      color: (it.meta && it.meta.color) || "#c8102e",
    }));
  }

  // 推荐地勘单位
  const recItems = map(cfg.blocks.recommends);
  if (recItems.length) {
    recommendList.value = recItems.map((it) => ({ name: it.title, meta: it.subtitle || "" }));
  }

  // 国际地学合作
  const partnerItems = map(cfg.blocks.partners);
  if (partnerItems.length) {
    overseaCards.value = partnerItems.map((it) => ({
      short: (it.meta && it.meta.short) || "OC",
      title: it.title,
      sub: it.subtitle || "",
      members: (it.meta && it.meta.members) || 0,
      bg: (it.meta && it.meta.bg) || "linear-gradient(135deg, #4c79c4 0%, #1f3e85 100%)",
    }));
  }

  // 产品服务
  const prodItemsCfg = map(cfg.blocks.products);
  if (prodItemsCfg.length) {
    prodItems.value = prodItemsCfg.map((it) => ({
      title: it.title,
      desc: it.subtitle || "",
      icon: resolveIcon(it.icon, Box),
      bg: (it.meta && it.meta.bg) || "linear-gradient(135deg, #ff6a6a 0%, #c8102e 100%)",
      to: it.link || "/site/solutions",
    }));
  }

  // 学术研讨
  const actItems = map(cfg.blocks.activities);
  if (actItems.length) {
    seminars.value = actItems.map((it) => ({
      tag: (it.meta && it.meta.tag) || "研讨",
      title: it.title,
      desc: it.subtitle || "",
      date: (it.meta && it.meta.date) || "",
      bg: (it.meta && it.meta.bg) || "linear-gradient(135deg, #2c66b8 0%, #1a3a6e 100%)",
    }));
  }

  // 资质认证体系
  const creditItems = map(cfg.blocks.certifications);
  if (creditItems.length) {
    creditLogos.value = creditItems.map((it) => ({
      name: it.title,
      short: (it.meta && it.meta.short) || it.title.slice(0, 1),
      color: (it.meta && it.meta.color) || "#c8102e",
    }));
  }

  // 地质服务领域: 按 item_key 分组为各 tab 的示例项目
  const fieldItemsCfg = map(cfg.blocks.fields);
  if (fieldItemsCfg.length) {
    const groups: Record<string, any[]> = {};
    const tabs: { key: string; label: string }[] = [];
    for (const it of fieldItemsCfg) {
      const key = it.item_key || `f${it.id}`;
      if (!groups[key]) {
        groups[key] = [];
        tabs.push({ key, label: it.title });
      }
      groups[key].push({
        name: it.subtitle || it.title,
        meta: (it.meta && it.meta.meta) || "",
        location: (it.meta && it.meta.location) || "",
        to: it.link || "/site/data-center/projects",
      });
    }
    if (tabs.length) {
      fieldTabs.value = tabs;
      fieldConfigItems.value = groups;
      if (!groups[fieldTab.value]) fieldTab.value = tabs[0].key;
    }
  }
}

onMounted(async () => {
  try { overview.value = await fetchOverview(); updatedAt.value = overview.value?.updated_at || "—"; } catch {}
  loadHomeConfig();
  fetchHome();
  loadHomeCategory(activeHomeCategory.value);
});
</script>

<style scoped>
/* ── 顶部引导 ── */
.top-guide {
  background: #fafafa;
  border-bottom: 1px solid #e6ecf3;
  font-size: 12.5px;
  color: #6b7283;
}
.top-guide-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
}
.top-guide-r a {
  color: #6b7283;
  text-decoration: none;
  margin-left: 14px;
  transition: color 0.2s ease;
}
.top-guide-r a:hover {
  color: #c8102e;
}

/* ── HHB Banner 顶部搜索区 ── */
.hhb-banner {
  background: linear-gradient(135deg, #a40d26 0%, #c8102e 55%, #e01a3c 100%);
  padding: 24px 0 32px;
  position: relative;
  overflow: hidden;
}
.hhb-banner::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 18% 30%, rgba(255, 255, 255, 0.10) 0%, transparent 35%),
    radial-gradient(circle at 85% 70%, rgba(255, 220, 80, 0.10) 0%, transparent 38%);
}
.hhb-inner {
  position: relative;
  z-index: 1;
}
.hhb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 12px;
}
.hhb-tabs span {
  display: inline-block;
  padding: 4px 16px;
  margin-right: 6px;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.78);
  border-radius: 16px 16px 0 0;
  cursor: pointer;
  transition: all 0.2s;
}
.hhb-tabs span.active {
  background: #fff;
  color: #c8102e;
  font-weight: 700;
}
.hhb-hot {
  font-size: 12.5px;
  color: rgba(255, 255, 255, 0.78);
}
.hhb-hot a {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
  margin-left: 8px;
  transition: color 0.2s;
}
.hhb-hot a:hover {
  color: #ffe066;
}
.hhb-search {
  background: #fff;
  border-radius: 6px;
  padding: 5px;
  display: flex;
  align-items: stretch;
  gap: 4px;
  box-shadow: 0 8px 28px rgba(15, 32, 75, 0.18);
}
.hhb-input {
  flex: 1 1 auto;
  min-width: 0;
}
.hhb-input :deep(.el-input__wrapper) {
  border-radius: 4px;
  box-shadow: none !important;
  padding: 6px 12px;
}
.hhb-input :deep(.el-input__inner) {
  font-size: 15px;
  height: 40px;
}
.hhb-btn {
  font-size: 15px !important;
  padding: 0 32px !important;
  border-radius: 4px !important;
  background: linear-gradient(135deg, #ff8a3d 0%, #c8102e 100%) !important;
  border-color: transparent !important;
  height: 40px !important;
}
.hhb-icon-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
  margin-top: 22px;
}
.hhb-icon-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  background: rgba(255, 255, 255, 0.10);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  text-decoration: none;
  color: #fff;
  transition: all 0.25s ease;
}
.hhb-icon-card:hover {
  background: rgba(255, 255, 255, 0.20);
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(15, 32, 75, 0.18);
}
.hhb-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
}
.hhb-icon-label {
  font-size: 15px;
  font-weight: var(--fw-semibold);
  font-family: var(--site-font-display);
  letter-spacing: 0.03em;
  margin-bottom: 2px;
}
.hhb-icon-desc {
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.78);
}

/* ── 认证 bar ── */
.cert-bar {
  background: #fff;
  border-bottom: 1px solid #e6ecf3;
  padding: 14px 0;
}
.cert-inner {
  display: flex;
  align-items: center;
  gap: 32px;
  flex-wrap: wrap;
}
.cert-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-right: 28px;
  border-right: 1px solid #e6ecf3;
}
.cert-mark {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e01a3c 0%, #c8102e 100%);
  color: #fff;
  font-weight: 900;
  font-size: 20px;
  display: grid;
  place-items: center;
}
.cert-logo strong {
  display: block;
  font-size: 18px;
  color: #141414;
  letter-spacing: 1px;
}
.cert-logo em {
  font-size: 11.5px;
  color: #6b7283;
  font-style: normal;
}
.cert-list {
  display: flex;
  gap: 28px;
  flex: 1;
}
.cert-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cert-item .cert-icon {
  font-size: 22px;
}
.cert-item strong {
  display: block;
  font-size: 13.5px;
  color: #141414;
}
.cert-item span {
  font-size: 11.5px;
  color: #6b7283;
}

/* ── 主体三栏 ── */
.hhb-main {
  background: #f6f8fb;
  padding: 20px 0 28px;
}
.main-grid {
  display: grid;
  grid-template-columns: 200px 1fr 240px;
  gap: 16px;
}
.main-left {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.left-card {
  background: #fff;
  border: 1px solid #e6ecf3;
  border-radius: 6px;
  padding: 14px 12px;
}
.left-title {
  font-size: 15px;
  font-weight: 700;
  color: #141414;
  margin-bottom: 10px;
  border-left: 3px solid #c8102e;
  padding-left: 8px;
}
.left-cat li {
  list-style: none;
}
.left-cat a {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 6px;
  font-size: 13px;
  color: #4a5568;
  text-decoration: none;
  border-radius: 4px;
  transition: all 0.2s ease;
}
.left-cat a:hover {
  background: #fceef0;
  color: #c8102e;
}
.left-cat a .el-icon {
  font-size: 14px;
  color: #c8102e;
}
.left-cat em.hot {
  margin-left: auto;
  font-style: normal;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 8px;
  background: linear-gradient(135deg, #e01a3c 0%, #c8102e 100%);
  color: #fff;
  font-weight: 700;
}

.main-center {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 中央地图卡 */
.cn-map-card {
  background: #fff;
  border: 1px solid #e6ecf3;
  border-radius: 6px;
  padding: 16px 18px 12px;
}
.cm-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px dashed #e6ecf3;
  padding-bottom: 10px;
}
.cm-title {
  font-size: 16px;
  font-weight: var(--fw-semibold);
  color: var(--site-text);
  font-family: var(--site-font-display);
  letter-spacing: 0.01em;
}
.cm-more {
  font-size: 12px;
  color: #6b7283;
  text-decoration: none;
}
.cm-more:hover {
  color: #c8102e;
}
.cm-body {
  display: grid;
  grid-template-columns: 1fr 160px;
  gap: 8px;
  align-items: center;
}
.cm-map {
  height: 320px;
  position: relative;
  overflow: hidden;
  border-radius: 4px;
}
.cm-side {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.cm-stat {
  background: linear-gradient(135deg, #fceef0 0%, #fff 100%);
  border: 1px solid #e6ecf3;
  border-radius: 6px;
  padding: 14px 10px;
  text-align: center;
}
.cm-stat-num {
  font-family: var(--site-font-display);
  font-size: 22px;
  font-weight: 800;
  color: #c8102e;
}
.cm-stat-label {
  font-size: 11.5px;
  color: #6b7283;
  margin-top: 4px;
}

/* 三分类列表 */
.three-list {
  background: #fff;
  border: 1px solid #e6ecf3;
  border-radius: 6px;
  padding: 12px 18px 14px;
}
.tl-tab {
  display: inline-block;
  font-size: 14px;
  font-weight: 700;
  padding: 6px 16px;
  border: 1px solid #e6ecf3;
  background: #f6f8fb;
  color: #4a5568;
  cursor: pointer;
  margin-right: 4px;
  border-radius: 4px 4px 0 0;
  transition: all 0.2s ease;
}
.tl-tab.on {
  background: #c8102e;
  border-color: #c8102e;
  color: #fff;
}
.tl-list {
  list-style: none;
  border-top: 2px solid #c8102e;
  padding-top: 10px;
}
.tl-list li {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 9px 4px;
  border-bottom: 1px dashed #e6ecf3;
}
.tl-date {
  font-size: 12.5px;
  font-weight: 700;
  color: #c8102e;
  width: 56px;
  flex-shrink: 0;
}
.tl-title {
  flex: 1;
  color: #141414;
  text-decoration: none;
  font-size: 13.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tl-title:hover {
  color: #c8102e;
}
.tl-region {
  font-size: 12px;
  color: #6b7283;
  flex-shrink: 0;
}
.tl-empty,
.rl-empty,
.rcmd-empty {
  padding: 24px 0;
  text-align: center;
  color: #6b7283;
  font-size: 12.5px;
}
.tl-foot {
  text-align: center;
  padding-top: 8px;
  font-size: 12.5px;
}
.tl-foot a {
  color: #c8102e;
  text-decoration: none;
}

/* 右侧 */
.main-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.right-card {
  background: #fff;
  border: 1px solid #e6ecf3;
  border-radius: 6px;
  padding: 14px 14px 8px;
}
.right-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e6ecf3;
  padding-bottom: 8px;
  margin-bottom: 10px;
}
.rh-title {
  font-size: 15px;
  font-weight: var(--fw-semibold);
  color: var(--site-text);
  font-family: var(--site-font-display);
  letter-spacing: 0.02em;
}
.right-head a {
  font-size: 12px;
  color: #6b7283;
  text-decoration: none;
}
.right-head a:hover {
  color: #c8102e;
}
.rank-list {
  list-style: none;
}
.rank-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  border-bottom: 1px dashed #e6ecf3;
  font-size: 13px;
}
.rank-list li:last-child {
  border-bottom: none;
}
.rank-list i {
  font-style: normal;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  background: #f0f3f7;
  color: #6b7283;
  font-size: 11px;
  font-weight: 700;
  border-radius: 4px;
  flex-shrink: 0;
}
.rank-list i.top {
  background: linear-gradient(135deg, #e01a3c 0%, #c8102e 100%);
  color: #fff;
}
.rl-name {
  flex: 1;
  color: #141414;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rl-num {
  font-size: 12px;
  color: #c8102e;
  font-weight: 700;
}
.rcmd-list {
  list-style: none;
}
.rcmd-list li {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px dashed #e6ecf3;
}
.rcmd-list li:last-child {
  border-bottom: none;
}
.rcmd-num {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #c8102e 0%, #e01a3c 100%);
  color: #fff;
  font-weight: 800;
  font-size: 12.5px;
  border-radius: 4px;
  flex-shrink: 0;
}
.rcmd-name {
  font-size: 13.5px;
  color: #141414;
  font-weight: 600;
  margin-bottom: 2px;
}
.rcmd-meta {
  font-size: 11.5px;
  color: #6b7283;
}

/* ── 红色 CTA banner ── */
.cta-banner {
  background: linear-gradient(135deg, #ff8a3d 0%, #c8102e 55%, #c43c0f 100%);
  padding: 18px 0;
  position: relative;
  overflow: hidden;
}
.cta-banner::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 12% 50%, rgba(255, 255, 255, 0.16) 0%, transparent 38%),
    radial-gradient(circle at 88% 50%, rgba(255, 220, 80, 0.18) 0%, transparent 40%);
}
.cta-inner {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 24px;
  color: #fff;
}
.cta-l {
  font-size: 22px;
  font-weight: 900;
  letter-spacing: 1.5px;
  background: rgba(255, 255, 255, 0.18);
  padding: 6px 18px;
  border-radius: 4px;
}
.cta-m {
  flex: 1;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.cta-r {
  background: #fff;
  color: #c8102e;
  padding: 8px 24px;
  border-radius: 22px;
  font-weight: 700;
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s ease;
}
.cta-r:hover {
  background: #ffe066;
  color: #c43c0f;
}

/* ── Section 通用 ── */
.site-eyebrow {
  display: inline-block;
  font-size: 12px;
  font-weight: var(--fw-bold);
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--site-eyebrow);
  margin-bottom: 14px;
}
.site-eyebrow::before {
  content: "";
  display: inline-block;
  width: 24px;
  height: 2px;
  background: var(--site-brand);
  vertical-align: middle;
  margin-right: 10px;
}
.site-h2 {
  font-family: var(--site-font-display);
  font-size: var(--fs-h2);
  font-weight: var(--fw-display);
  line-height: var(--lh-heading);
  color: var(--site-text);
  margin: 0 0 14px;
  letter-spacing: 0.01em;
}
.site-sub {
  font-size: var(--fs-lead);
  line-height: var(--lh-body);
  color: var(--site-text-dim);
  max-width: 720px;
}
.section-head {
  text-align: center;
  margin-bottom: 32px;
}

/* ── 地质服务领域 ── */
.field-section {
  background: #fff;
  padding: 56px 0;
}
.field-tabs {
  text-align: center;
  border-bottom: 1px solid #e6ecf3;
  padding-bottom: 10px;
  margin-bottom: 22px;
}
.ft-tab {
  display: inline-block;
  padding: 6px 18px;
  font-size: 14px;
  font-weight: 600;
  color: #4a5568;
  cursor: pointer;
  margin: 0 4px;
  border-radius: 4px 4px 0 0;
  transition: all 0.2s ease;
}
.ft-tab.on {
  background: #c8102e;
  color: #fff;
}
.ft-tab:hover:not(.on) {
  color: #c8102e;
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.fg-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border: 1px solid #e6ecf3;
  border-left: 3px solid #c8102e;
  border-radius: 4px;
  background: #fff;
  text-decoration: none;
  transition: all 0.25s ease;
}
.fg-item:hover {
  border-left-color: #c8102e;
  border-color: #c8102e;
  transform: translateY(-3px);
  box-shadow: 0 10px 22px rgba(233, 78, 27, 0.10);
}
.fg-item strong {
  font-size: 15px;
  color: var(--site-text);
  font-weight: var(--fw-semibold);
  font-family: var(--site-font-display);
  letter-spacing: 0.01em;
}
.fg-meta {
  font-size: 12px;
  color: #6b7283;
}
.fg-loc {
  font-size: 11.5px;
  color: #c8102e;
  font-weight: 600;
  margin-top: 2px;
}

/* ── 情报动态 ── */
.intel-section {
  background: #f6f8fb;
  padding: 56px 0;
}

/* ── 国际地学合作 ── */
.oversea-section {
  background: linear-gradient(180deg, #fff 0%, #f6f8fb 100%);
  padding: 56px 0;
}
.oversea-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.ovs-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1px solid #e6ecf3;
  border-radius: 8px;
  padding: 16px 20px;
  transition: all 0.25s ease;
}
.ovs-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 22px rgba(31, 109, 184, 0.10);
  border-color: #c8102e;
}
.ovs-flag {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 18px;
  font-weight: 900;
  letter-spacing: 1px;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.10);
}
.ovs-body strong {
  display: block;
  font-size: 16px;
  font-weight: var(--fw-semibold);
  color: var(--site-text);
  font-family: var(--site-font-display);
  letter-spacing: 0.01em;
  margin-bottom: 4px;
}
.ovs-body span {
  display: block;
  font-size: 12.5px;
  color: #6b7283;
  margin-bottom: 4px;
}
.ovs-body em {
  display: inline-block;
  font-style: normal;
  font-size: 11px;
  color: #c8102e;
  background: #eaf3ff;
  padding: 2px 8px;
  border-radius: 8px;
  font-weight: 600;
}

/* ── 新产品 ── */
.prod-section {
  background: #fff;
  padding: 56px 0;
}
.prod-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.prod-card {
  display: flex;
  flex-direction: column;
  text-decoration: none;
  background: #f6f8fb;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e6ecf3;
  transition: all 0.25s ease;
}
.prod-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(31, 109, 184, 0.12);
  border-color: #c8102e;
}
.prod-img {
  height: 130px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 44px;
}
.prod-body {
  padding: 14px 16px 18px;
}
.prod-body strong {
  display: block;
  font-size: 18px;
  font-weight: var(--fw-semibold);
  color: var(--site-text);
  font-family: var(--site-font-display);
  letter-spacing: 0.01em;
  margin-bottom: 6px;
  word-break: break-word;
  overflow-wrap: break-word;
}
.prod-body p {
  font-size: 12.5px;
  color: #6b7283;
  margin: 0 0 10px;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.prod-cta {
  display: inline-block;
  font-size: 12.5px;
  color: #c8102e;
  font-weight: 600;
}
@media (max-width: 1100px) { .prod-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) { .prod-grid { grid-template-columns: 1fr; } }

/* ── 校企研讨会 ── */
.seminar-section {
  background: #f6f8fb;
  padding: 56px 0;
}
.seminar-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}
.seminar-card {
  border-radius: 10px;
  padding: 24px 24px 22px;
  color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
  min-height: 220px;
}
.seminar-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 90% 10%, rgba(255, 255, 255, 0.18), transparent 40%);
}
.seminar-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 16px 30px rgba(15, 32, 75, 0.20);
}
.sem-tag {
  display: inline-block;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.20);
  padding: 3px 10px;
  border-radius: 12px;
  margin-bottom: 14px;
}
.seminar-card h3 {
  font-size: 23px;
  font-weight: var(--fw-semibold);
  font-family: var(--site-font-display);
  letter-spacing: 0.01em;
  line-height: var(--lh-heading);
  margin: 0 0 12px;
  position: relative;
  word-break: break-word;
  overflow-wrap: break-word;
}
.seminar-card p {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.8;
  margin: 0 0 18px;
  position: relative;
}
@media (max-width: 1100px) { .seminar-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) { .seminar-grid { grid-template-columns: 1fr; } }
.sem-date {
  font-size: 12.5px;
  background: rgba(255, 255, 255, 0.92);
  color: #141414;
  padding: 5px 12px;
  border-radius: 16px;
  font-weight: 700;
}

/* ── 信用中国 ── */
.credit-section {
  background: #fff;
  padding: 56px 0;
}
.credit-tabs {
  text-align: center;
  border-bottom: 1px solid #e6ecf3;
  margin-bottom: 22px;
}
.credit-tabs span {
  display: inline-block;
  padding: 8px 22px;
  font-size: 14px;
  font-weight: 600;
  color: #4a5568;
  cursor: pointer;
  margin: 0 4px;
  transition: all 0.2s ease;
  position: relative;
}
.credit-tabs span.on {
  color: #c8102e;
}
.credit-tabs span.on::after {
  content: "";
  position: absolute;
  left: 18%;
  right: 18%;
  bottom: -1px;
  height: 2px;
  background: #c8102e;
}
.credit-tabs span:hover:not(.on) {
  color: #c8102e;
}
.credit-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
}
.cg-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 18px 6px;
  border: 1px solid #e6ecf3;
  border-radius: 6px;
  background: #f6f8fb;
  transition: all 0.25s ease;
  cursor: pointer;
}
.cg-item:hover {
  transform: translateY(-3px);
  border-color: #c8102e;
  box-shadow: 0 8px 16px rgba(31, 109, 184, 0.10);
}
.cg-mark {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 18px;
  font-weight: 800;
  background: #fff;
  border: 2px solid currentColor;
}
.cg-item span {
  font-size: 12.5px;
  color: #4a5568;
  text-align: center;
}

/* ── 指标墙 ── */
.stat-section {
  background: #f6f8fb;
  padding: 50px 0;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e6ecf3;
  border-radius: 8px;
  padding: 22px 18px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.25s ease;
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 22px rgba(31, 109, 184, 0.08);
  border-color: #c8102e;
}
.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 22px;
  flex-shrink: 0;
}
.stat-num {
  font-family: var(--site-font-display);
  font-size: 26px;
  font-weight: 800;
  color: #141414;
}
.stat-num small {
  font-size: 13px;
  color: #6b7283;
  margin-left: 2px;
  font-weight: 600;
}
.stat-title {
  font-size: 12.5px;
  color: #6b7283;
  margin-top: 4px;
}

/* ====================================================
   响应式
   ==================================================== */
@media (max-width: 1024px) {
  .main-grid { grid-template-columns: 1fr; }
  .main-left { flex-direction: row; flex-wrap: wrap; }
  .left-card { flex: 1 1 calc(50% - 6px); }
  .cm-body { grid-template-columns: 1fr; }
  .field-grid { grid-template-columns: repeat(2, 1fr); }
  .oversea-grid { grid-template-columns: repeat(2, 1fr); }
  .prod-grid { grid-template-columns: repeat(2, 1fr); }
  .seminar-grid { grid-template-columns: 1fr; }
  .credit-grid { grid-template-columns: repeat(4, 1fr); }
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .hhb-icon-row { grid-template-columns: repeat(3, 1fr); }
  .cert-list { gap: 16px; }
}
@media (max-width: 768px) {
  .top-guide-r a { margin-left: 8px; }
  .hhb-icon-row { grid-template-columns: repeat(2, 1fr); }
  .hhb-search { flex-wrap: wrap; }
  .hhb-btn { width: 100%; padding: 12px !important; margin-top: 8px; }
  .cert-inner { flex-direction: column; align-items: flex-start; gap: 12px; }
  .cert-logo { padding-right: 0; border: none; padding-bottom: 10px; border-bottom: 1px solid #e6ecf3; width: 100%; }
  .cert-list { flex-wrap: wrap; gap: 12px; }
  .cta-inner { flex-direction: column; text-align: center; gap: 12px; }
  .field-grid,
  .oversea-grid,
  .prod-grid,
  .credit-grid {
    grid-template-columns: 1fr 1fr;
  }
  .stat-grid { grid-template-columns: 1fr; }
  .main-left { flex-direction: column; }
  .left-card { flex: 1; }
  .field-tabs,
  .credit-tabs { display: flex; overflow-x: auto; white-space: nowrap; padding-bottom: 8px; }
  .ft-tab,
  .credit-tabs span { flex-shrink: 0; }
  .credit-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
