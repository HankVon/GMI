<template>
  <SiteLayout>
    <section class="page-hero">
      <div class="site-container">
        <span class="site-eyebrow">CONTACT</span>
        <h1 class="page-title">联系咨询</h1>
        <p class="page-sub">留下你的需求，我们的专家将在 1 个工作日内与你联系。</p>
      </div>
    </section>

    <section class="section">
      <div class="site-container contact-grid">
        <!-- 表单 -->
        <div class="contact-form site-card reveal">
          <h3>预约演示 / 咨询</h3>
          <el-form :model="form" label-position="top" @submit.prevent="submit">
            <el-form-item label="称呼">
              <el-input v-model="form.name" placeholder="您的姓名 / 职务" />
            </el-form-item>
            <el-form-item label="单位名称">
              <el-input v-model="form.org" placeholder="所在公司 / 机构" />
            </el-form-item>
            <el-form-item label="联系方式">
              <el-input v-model="form.contact" placeholder="手机 / 邮箱 / 微信" />
            </el-form-item>
            <el-form-item label="需求类型">
              <el-select v-model="form.type" placeholder="请选择" style="width:100%">
                <el-option label="单位画像与情报" value="unit" />
                <el-option label="招投标线索" value="bid" />
                <el-option label="AI 商情报告" value="ai" />
                <el-option label="私有化部署" value="deploy" />
                <el-option label="其他咨询" value="other" />
              </el-select>
            </el-form-item>
            <el-form-item label="需求描述">
              <el-input v-model="form.desc" type="textarea" :rows="4" placeholder="简要描述您的业务场景与目标" />
            </el-form-item>
            <el-button type="primary" class="submit-btn" @click="submit">提交咨询</el-button>
            <p v-if="sent" class="sent-tip">✓ 已收到，我们会尽快与您联系。</p>
          </el-form>
        </div>

        <!-- 信息 -->
        <div class="contact-info reveal">
          <div class="ci-card site-card" v-for="c in contactInfo" :key="c.k">
            <div class="ci-icon"><el-icon><component :is="c.icon" /></el-icon></div>
            <div>
              <div class="ci-k">{{ c.k }}</div>
              <div class="ci-v">{{ c.v }}</div>
            </div>
          </div>
          <div class="ci-note">
            <p>{{ contactNote }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 地图占位 -->
    <section class="section alt">
      <div class="site-container">
        <div class="section-head">
          <span class="site-eyebrow">FIND US</span>
          <h2 class="site-h2">来访路线</h2>
        </div>
        <div class="map-placeholder">
          <el-icon class="map-icon"><LocationFilled /></el-icon>
          <p>{{ mapAddress }}</p>
          <span>{{ mapHint }}</span>
        </div>
      </div>
    </section>
  </SiteLayout>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import SiteLayout from "@/components/site/SiteLayout.vue";
import { Message, Phone, Location, Clock, LocationFilled } from "@element-plus/icons-vue";
import api from "@/api";
import { fetchHomeConfig } from "@/api/siteApi";

const form = reactive({ name: "", org: "", contact: "", type: "", desc: "" });
const sent = ref(false);

/** 联系信息(默认值, 后台「联系我们」配置可覆盖) */
const contactInfo = ref([
  { k: "邮箱", v: "contact@gmi.example", icon: Message },
  { k: "电话", v: "400-000-0000", icon: Phone },
  { k: "地址", v: "成都市 · 高新区", icon: Location },
  { k: "服务时间", v: "工作日 9:00 - 18:00", icon: Clock },
]);
const contactNote = ref("我们承诺：仅将您的信息用于本次咨询对接，绝不外泄。如需了解数据合规详情，请邮件联系合规团队。");
const mapAddress = ref("成都 · 高新区 · 天府软件园");
const mapHint = ref("（示意地图，可接入高德 / 百度地图组件）");

/** 后台「联系我们」配置驱动: contact_info 区块 → 联系卡片; 未配置时保持内置默认 */
async function loadContactConfig() {
  const cfg = await fetchHomeConfig("contact");
  if (!cfg || !cfg.blocks) return;
  const map = (key: string) => {
    const b = cfg.blocks[key];
    return b ? b.items.filter((it) => it.enabled === 1) : [];
  };
  const info = map("contact_info");
  if (info.length) {
    const iconMap: Record<string, any> = { message: Message, phone: Phone, location: Location, clock: Clock };
    contactInfo.value = info.map((it) => ({
      k: it.title,
      v: it.subtitle || "",
      icon: (it.icon && iconMap[it.icon.toLowerCase()]) || Message,
    }));
  }
  const note = map("contact_note");
  if (note.length) contactNote.value = note[0].title;
  const addr = map("map_address");
  if (addr.length) {
    mapAddress.value = addr[0].title;
    mapHint.value = addr[0].subtitle || mapHint.value;
  }
}

async function submit() {
  if (!form.contact) { ElMessage.warning("请填写联系方式"); return; }
  try {
    await api.post("/public/contact", { name: form.name, org: form.org, contact: form.contact, type: form.type, description: form.desc });
    sent.value = true;
    ElMessage.success("提交成功，我们会尽快联系您");
  } catch { ElMessage.error("提交失败，请稍后重试"); }
}

onMounted(() => {
  const queryType = new URLSearchParams(window.location.search).get("type");
  if (queryType === "feedback") form.type = "other";
  loadContactConfig();
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

.contact-grid { display: grid; grid-template-columns: 1.3fr 1fr; gap: 32px; align-items: start; }
.contact-form h3 { font-size: 20px; color: var(--site-text); margin: 0 0 20px; }
.contact-form :deep(.el-form-item__label) { color: var(--site-text-dim); }
.submit-btn { width: 100%; background: var(--site-brand); border: none; height: 46px; font-size: 15px; font-weight: 600; border-radius: 999px; box-shadow: 0 12px 24px -12px rgba(200,16,46,0.6); }
.submit-btn:hover { background: var(--site-brand-dark); }
.sent-tip { color: #2bb673; font-size: 14px; margin-top: 12px; }

.contact-info { display: flex; flex-direction: column; gap: 14px; }
.ci-card { display: flex; align-items: center; gap: 16px; padding: 18px 20px; }
.ci-icon { width: 44px; height: 44px; border-radius: 11px; background: var(--site-brand-soft); color: var(--site-brand); display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.ci-k { font-size: 13px; color: var(--site-text-mute); }
.ci-v { font-size: 15px; color: var(--site-text); font-weight: 600; margin-top: 2px; }
.ci-note { font-size: 13px; line-height: 1.8; color: var(--site-text-mute); padding: 4px 8px; }

.map-placeholder {
  height: 320px; border-radius: 16px; border: 1px dashed var(--site-panel-border);
  background: var(--site-bg); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
}
.map-icon { font-size: 48px; color: var(--site-brand); }
.map-placeholder p { font-size: 18px; color: var(--site-text); margin: 0; }
.map-placeholder span { font-size: 13px; color: var(--site-text-mute); }

@media (max-width: 1024px) {
  .contact-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
}
</style>
