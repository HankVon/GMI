<template>
  <SiteLayout>
    <section class="page-hero">
      <div class="site-container">
        <span class="site-eyebrow">SOLUTIONS</span>
        <h1 class="page-title">解决方案</h1>
        <p class="page-sub">面向政府、国企与产业服务商的情报中台能力，覆盖从数据到决策的完整链路。</p>
      </div>
    </section>

    <!-- 解决方案卡片 -->
    <section class="section">
      <div class="site-container">
        <div class="sol-grid">
          <div class="sol-card site-card" v-for="(s, i) in solutions" :key="s.title">
            <div class="sol-no">0{{ i + 1 }}</div>
            <div class="sol-icon"><el-icon><component :is="s.icon" /></el-icon></div>
            <h3>{{ s.title }}</h3>
            <p>{{ s.desc }}</p>
            <ul class="sol-list">
              <li v-for="f in s.features" :key="f">{{ f }}</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- 应用场景 -->
    <section class="section alt">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">USE CASES</span>
          <h2 class="site-h2">典型应用场景</h2>
        </div>
        <div class="case-grid">
          <div class="case-card site-card" v-for="c in cases" :key="c.title">
            <div class="case-tag">{{ c.tag }}</div>
            <h4>{{ c.title }}</h4>
            <p>{{ c.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 流程 -->
    <section class="section">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">HOW IT WORKS</span>
          <h2 class="site-h2">交付流程</h2>
        </div>
        <div class="flow">
          <div class="flow-step" v-for="(f, i) in flow" :key="f.title">
            <div class="flow-dot">{{ i + 1 }}</div>
            <h4>{{ f.title }}</h4>
            <p>{{ f.desc }}</p>
            <div class="flow-line" v-if="i < flow.length - 1"></div>
          </div>
        </div>
      </div>
    </section>
  </SiteLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import SiteLayout from "@/components/site/SiteLayout.vue";
import {
  OfficeBuilding, Connection, Cpu, Search, DataAnalysis, Monitor,
} from "@element-plus/icons-vue";
import { fetchHomeConfig } from "@/api/siteApi";

const solutions = ref([
  { title: "单位全息画像", icon: OfficeBuilding, desc: "聚合工商、中标、人员、地域等多源数据，构建单位 360° 档案。", features: ["工商与经营信息", "中标与项目历史", "关键人员关系", "风险与异常预警"] },
  { title: "情报关系网络", icon: Connection, desc: "基于知识图谱挖掘业主、竞对、合作方与同地域关联脉络。", features: ["招投标关联", "人脉路径推演", "同地域线索", "可争取意向识别"] },
  { title: "AI 商情分析", icon: Cpu, desc: "大模型自动抽取开放关系、生成商情报告与公关路径建议。", features: ["智能报告生成", "公关路径规划", "意图公告匹配", "趋势研判"] },
  { title: "线索意图监测", icon: Search, desc: "定期扫描意向公告，精准匹配本单位业务与地域能力。", features: ["意向公告扫描", "能力匹配引擎", "实时提醒", "商机评分"] },
  { title: "态势可视化", icon: DataAnalysis, desc: "态势大屏与钻取分析，将海量数据转化为决策依据。", features: ["实时大屏", "多维钻取", "自定义看板", "移动端同步"] },
  { title: "数据采集治理", icon: Monitor, desc: "自动爬取公开数据源，结构化清洗入库，保障数据质量。", features: ["全网采集", "结构化清洗", "质量校验", "增量更新"] },
]);

const cases = ref([
  { tag: "政府", title: "自然资源部门招商研判", desc: "通过同地域采购线索与业主画像，辅助产业招商与项目谋划。" },
  { tag: "国企", title: "工程企业商机发现", desc: "实时匹配招标公告与自身资质，提升中标命中率。" },
  { tag: "服务商", title: "咨询机构情报服务", desc: "批量生成行业与单位商情报告，支撑咨询服务交付。" },
  { tag: "园区", title: "产业园区企业画像", desc: "构建入园企业全息档案，支撑精准招商与运营。" },
]);

const flow = ref([
  { title: "需求对齐", desc: "梳理业务场景与数据维度，明确情报目标。" },
  { title: "数据接入", desc: "配置爬虫与数据源，结构化入库治理。" },
  { title: "建模分析", desc: "构建知识图谱与 AI 分析模型。" },
  { title: "可视化交付", desc: "部署大屏与报告，培训使用。" },
  { title: "持续运营", desc: "定期更新与优化，闭环迭代。" },
]);

/** 后台「解决方案」配置驱动: solutions/cases/flow 区块 → 对应数据; 未配置时保持内置默认 */
async function loadSolutionsConfig() {
  const cfg = await fetchHomeConfig("solutions");
  if (!cfg || !cfg.blocks) return;
  const map = (key: string) => {
    const b = cfg.blocks[key];
    return b ? b.items.filter((it) => it.enabled === 1) : [];
  };
  const iconMap: Record<string, any> = {
    officebuilding: OfficeBuilding, connection: Connection, cpu: Cpu,
    search: Search, dataanalysis: DataAnalysis, monitor: Monitor,
  };

  const sol = map("solutions");
  if (sol.length) {
    solutions.value = sol.map((it) => ({
      title: it.title,
      icon: (it.icon && iconMap[it.icon.toLowerCase()]) || OfficeBuilding,
      desc: it.subtitle || "",
      features: Array.isArray(it.meta?.features) ? it.meta.features : [],
    }));
  }

  const cs = map("cases");
  if (cs.length) {
    cases.value = cs.map((it) => ({
      tag: (it.meta && it.meta.tag) || "场景",
      title: it.title,
      desc: it.subtitle || "",
    }));
  }

  const fl = map("flow");
  if (fl.length) {
    flow.value = fl.map((it) => ({ title: it.title, desc: it.subtitle || "" }));
  }
}

onMounted(() => {
  loadSolutionsConfig();
});
</script>

<style scoped>
.page-hero { padding: 96px 0 48px; background: linear-gradient(180deg, #fff, var(--site-bg)); border-bottom: 1px solid var(--site-hairline); }
.page-title { font-family: var(--site-font-display); font-size: var(--fs-h1); font-weight: var(--fw-display); line-height: var(--lh-display); letter-spacing: 0.01em; color: var(--site-text); margin: 12px 0; }
.page-sub { font-size: var(--fs-lead); line-height: var(--lh-body); color: var(--site-text-dim); max-width: 600px; }
.section { padding: 64px 0; }
.section.alt { background: #fff; }

.sol-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.sol-card { position: relative; padding-top: 28px; }
.sol-no { position: absolute; top: 18px; right: 20px; font-family: var(--site-font-display); font-size: 40px; font-weight: 600; color: rgba(200,16,46,0.10); }
.sol-icon { width: 50px; height: 50px; border-radius: 12px; background: var(--site-brand-soft); color: var(--site-brand); display: flex; align-items: center; justify-content: center; font-size: 24px; margin-bottom: 14px; }
.sol-card h3 { font-size: 19px; color: var(--site-text); margin: 0 0 10px; }
.sol-card p { font-size: 14px; line-height: 1.8; color: var(--site-text-dim); }
.sol-list { list-style: none; padding: 0; margin: 14px 0 0; }
.sol-list li { font-size: 13.5px; color: var(--site-text); padding: 6px 0 6px 22px; position: relative; }
.sol-list li::before { content: ""; position: absolute; left: 0; top: 12px; width: 8px; height: 8px; border-radius: 50%; background: var(--site-brand); }

.case-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; }
.case-card { padding: 24px; }
.case-tag { display: inline-block; font-size: 12px; color: var(--site-brand); border: 1px solid var(--site-panel-border); border-radius: 999px; padding: 3px 12px; margin-bottom: 12px; }
.case-card h4 { font-size: 17px; color: var(--site-text); margin: 0 0 8px; }
.case-card p { font-size: 14px; line-height: 1.8; color: var(--site-text-dim); }

.flow { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; }
.flow-step { position: relative; text-align: center; padding: 0 16px; }
.flow-dot { width: 46px; height: 46px; border-radius: 50%; background: var(--site-brand); color: #fff; font-weight: 700; font-size: 18px; display: flex; align-items: center; justify-content: center; margin: 0 auto 14px; box-shadow: 0 12px 22px -12px rgba(200,16,46,0.6); }
.flow-step h4 { font-size: 16px; color: var(--site-text); margin: 0 0 8px; }
.flow-step p { font-size: 13px; line-height: 1.7; color: var(--site-text-dim); }
.flow-line { position: absolute; top: 23px; left: 50%; width: 100%; height: 2px; background: linear-gradient(90deg, rgba(200,16,46,0.35), rgba(176,141,87,0.35)); z-index: -1; }

@media (max-width: 1024px) {
  .sol-grid { grid-template-columns: repeat(2, 1fr); }
  .flow { grid-template-columns: repeat(2, 1fr); gap: 24px; }
  .flow-line { display: none; }
}
@media (max-width: 768px) {
  .sol-grid, .case-grid { grid-template-columns: 1fr; }
  .flow { grid-template-columns: 1fr; }
}
</style>
