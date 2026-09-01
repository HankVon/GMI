<template>
  <SiteLayout>
    <section class="page-hero">
      <div class="site-container">
        <span class="site-eyebrow">ABOUT US</span>
        <h1 class="page-title">关于我们</h1>
        <p class="page-sub">我们致力于用数据与智能，重构产业情报的生产方式。</p>
      </div>
    </section>

    <!-- 简介 -->
    <section class="section">
      <div class="site-container about-grid">
        <div class="about-text reveal">
          <h2 class="site-h2">让公开数据产生决策价值</h2>
          <p>GMI 数据平台专注于地质与产业情报领域，将分散在政府公开采购、招投标、工商与行业资讯中的海量数据，通过自动采集、知识图谱与 AI 分析，转化为可供政企单位直接使用的情报资产。</p>
          <p>我们相信，数据本身不产生价值，<strong>结构化的洞察</strong>才会。平台以"单位画像—关系网络—智能报告"为核心，帮助用户从信息洪流中快速锁定机会、识别风险、规划路径。</p>
          <div class="about-tags">
            <span>数据驱动</span><span>AI 赋能</span><span>专业可信</span><span>持续运营</span>
          </div>
        </div>
        <div class="about-visual site-card reveal">
          <div class="av-row" v-for="a in highlights" :key="a.k">
            <span class="av-k">{{ a.k }}</span>
            <span class="av-v">{{ a.v }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 价值观 -->
    <section class="section alt">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">OUR VALUES</span>
          <h2 class="site-h2">我们坚持的事</h2>
        </div>
        <div class="value-grid">
          <div class="value-card site-card" v-for="v in values" :key="v.title">
            <div class="value-icon"><el-icon><component :is="v.icon" /></el-icon></div>
            <h3>{{ v.title }}</h3>
            <p>{{ v.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 历程 -->
    <section class="section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">MILESTONES</span>
          <h2 class="site-h2">发展历程</h2>
        </div>
        <div class="timeline">
          <div class="tl-item" v-for="t in timeline" :key="t.year">
            <div class="tl-year">{{ t.year }}</div>
            <div class="tl-body">
              <h4>{{ t.title }}</h4>
              <p>{{ t.desc }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 团队/数据 -->
    <section class="section alt">
      <div class="site-container team-stats">
        <div class="ts" v-for="t in teamStats" :key="t.label">
          <div class="ts-num">{{ t.value }}</div>
          <div class="ts-label">{{ t.label }}</div>
        </div>
      </div>
    </section>
  </SiteLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import SiteLayout from "@/components/site/SiteLayout.vue";
import { Aim, Lock, Cpu, Service } from "@element-plus/icons-vue";
import { fetchHomeConfig } from "@/api/siteApi";

const highlights = ref([
  { k: "成立时间", v: "2023 年" },
  { k: "服务客户", v: "60+ 政企单位" },
  { k: "数据规模", v: "70+ 万条" },
  { k: "覆盖地域", v: "全国 90+ 省级区" },
  { k: "更新频率", v: "7×24 小时" },
]);

const values = ref([
  { title: "数据驱动", desc: "以真实、可验证的公开数据为基础，拒绝主观臆测。", icon: Aim },
  { title: "安全合规", desc: "仅采集公开数据源，严格数据治理与权限管控。", icon: Lock },
  { title: "AI 赋能", desc: "用大模型与图谱技术放大人脑研判效率。", icon: Cpu },
  { title: "专业服务", desc: "行业专家 + 工程团队，持续陪跑运营。", icon: Service },
]);

const timeline = ref([
  { year: "2023", title: "平台立项", desc: "面向地质产业情报的首版数据采集与画像系统上线。" },
  { year: "2024", title: "图谱升级", desc: "引入知识图谱与关系抽取，构建招投标关联网络。" },
  { year: "2025", title: "AI 报告", desc: "接入大模型，实现商情报告与公关路径自动生成。" },
  { year: "2026", title: "规模运营", desc: "服务 60+ 政企单位，数据规模突破 70 万条。" },
]);

const teamStats = ref([
  { value: "60+", label: "服务单位" },
  { value: "70万+", label: "数据条目" },
  { value: "90+", label: "覆盖省级区" },
  { value: "24h", label: "更新周期" },
]);

/** 后台「关于我们」配置驱动: 按 block_key 覆盖对应数据, 未配置时保持内置默认 */
async function loadAboutConfig() {
  const cfg = await fetchHomeConfig("about");
  if (!cfg || !cfg.blocks) return;
  const map = (key: string) => {
    const b = cfg.blocks[key];
    return b ? b.items.filter((it) => it.enabled === 1) : [];
  };

  const hl = map("highlights");
  if (hl.length) highlights.value = hl.map((it) => ({ k: it.title, v: it.subtitle || "" }));

  const vals = map("values");
  if (vals.length) {
    const iconByKey: Record<string, any> = { aim: Aim, lock: Lock, cpu: Cpu, service: Service };
    values.value = vals.map((it) => ({
      title: it.title,
      desc: it.subtitle || "",
      icon: (it.icon && iconByKey[it.icon.toLowerCase()]) || Aim,
    }));
  }

  const tl = map("timeline");
  if (tl.length) timeline.value = tl.map((it) => ({
    year: (it.meta && it.meta.year) || "",
    title: it.title,
    desc: it.subtitle || "",
  }));

  const ts = map("team_stats");
  if (ts.length) teamStats.value = ts.map((it) => ({ value: it.title, label: it.subtitle || "" }));
}

onMounted(async () => {
  loadAboutConfig();
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
  }, { threshold: 0.15 });
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
});
</script>

<style scoped>
.page-hero { padding: 96px 0 48px; background: linear-gradient(180deg, #fff, var(--site-bg)); border-bottom: 1px solid var(--site-hairline); }
.page-title { font-family: var(--site-font-display); font-size: var(--fs-h1); font-weight: var(--fw-display); line-height: var(--lh-display); letter-spacing: 0.01em; color: var(--site-text); margin: 12px 0; }
.page-sub { font-size: var(--fs-lead); line-height: var(--lh-body); color: var(--site-text-dim); max-width: 600px; }
.section { padding: 64px 0; }
.section.alt { background: #fff; }

.about-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 40px; align-items: center; }
.about-text p { font-size: 15px; line-height: 1.9; color: var(--site-text-dim); margin: 0 0 16px; }
.about-text strong { color: var(--site-brand); }
.about-tags { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
.about-tags span { font-size: 13px; color: var(--site-text); border: 1px solid var(--site-panel-border); border-radius: 999px; padding: 6px 16px; background: #fff; }
.about-visual { padding: 26px; }
.av-row { display: flex; justify-content: space-between; padding: 14px 0; border-bottom: 1px dashed var(--site-hairline); }
.av-row:last-child { border-bottom: none; }
.av-k { font-size: 14px; color: var(--site-text-dim); }
.av-v { font-size: 14px; color: var(--site-brand); font-weight: 600; }

.value-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.value-card h3 { font-size: 17px; color: var(--site-text); margin: 12px 0 8px; }
.value-card p { font-size: 13.5px; line-height: 1.8; color: var(--site-text-dim); }
.value-icon { width: 48px; height: 48px; border-radius: 12px; background: var(--site-brand-soft); color: var(--site-brand); display: flex; align-items: center; justify-content: center; font-size: 22px; }

.timeline { position: relative; padding-left: 30px; }
.timeline::before { content: ""; position: absolute; left: 7px; top: 6px; bottom: 6px; width: 2px; background: linear-gradient(180deg, var(--site-brand), var(--site-brand-bright)); }
.tl-item { position: relative; margin-bottom: 28px; }
.tl-item::before { content: ""; position: absolute; left: -30px; top: 4px; width: 16px; height: 16px; border-radius: 50%; background: var(--site-brand); box-shadow: 0 0 0 4px rgba(200,16,46,0.15); }
.tl-year { font-family: var(--site-font-display); font-size: 20px; font-weight: 700; color: var(--site-brand); }
.tl-body h4 { font-size: 16px; color: var(--site-text); margin: 4px 0 6px; }
.tl-body p { font-size: 14px; line-height: 1.7; color: var(--site-text-dim); }

.team-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; text-align: center; }
.ts-num { font-family: var(--site-font-display); font-size: 40px; font-weight: 700; color: var(--site-brand); }
.ts-label { margin-top: 8px; font-size: 14px; color: var(--site-text-mute); }

@media (max-width: 1024px) {
  .about-grid { grid-template-columns: 1fr; }
  .value-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .value-grid, .team-stats { grid-template-columns: 1fr 1fr; }
}
</style>
