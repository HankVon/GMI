<template>
  <aside class="filter-sidebar">
    <!-- 顶部：操作按钮（订阅 / 导出） -->
    <div class="filter-actions">
      <el-button class="fsa-btn fsa-btn-primary" :icon="Bell" @click="$emit('subscribe')">
        订阅
      </el-button>
      <el-button class="fsa-btn fsa-btn-ghost" :icon="Download" :loading="exporting" @click="$emit('export')">
        导出
      </el-button>
    </div>

    <!-- 已选摘要 + 清空全部 + 折叠开关 P2/P10 -->
    <div class="filter-summary">
      <div class="fs-chips">
        <button v-for="chip in activeChips" :key="chip.field" class="fs-chip" @click="removeChip(chip.field)">
          {{ chip.label }}<el-icon :size="11"><Close /></el-icon>
        </button>
        <span v-if="!activeChips.length" class="fs-empty">未选择筛选条件</span>
      </div>
      <div class="fs-ops">
        <button v-if="activeChips.length" class="fs-clearall" @click="clearAll">清空全部</button>
        <button v-if="isMobile" class="fs-toggle" @click="expanded = !expanded">
          {{ expanded ? `收起筛选 ▴` : `展开筛选${activeChips.length ? `(${activeChips.length})` : ''} ▾` }}
        </button>
      </div>
    </div>

    <!-- 提示条（单行截断） P9 -->
    <div class="filter-tip">
      <el-icon :size="13"><InfoFilled /></el-icon>
      <span>点击标签即选中，可与上方输入条件叠加筛选</span>
    </div>

    <template v-if="panelVisible">
      <!-- 项目区域 P6 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">项目区域<em v-if="model.province" class="fg-count">1</em></span>
          <button v-if="model.province" class="fg-clear" @click="setField('province', '')">清空</button>
        </div>
        <div class="fg-tags fg-tags-grid">
          <button
            v-for="opt in groups.province"
            :key="opt"
            class="fg-tag"
            :class="{ active: model.province === opt }"
            @click="toggleField('province', opt)"
          >{{ opt }}</button>
        </div>
      </section>

      <!-- 项目分类 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">项目分类<em v-if="model.category" class="fg-count">1</em></span>
          <button v-if="model.category" class="fg-clear" @click="setField('category', '')">清空</button>
        </div>
        <div class="fg-tags">
          <button
            v-for="opt in groups.category"
            :key="opt.value"
            class="fg-tag"
            :class="{ active: model.category === opt.value }"
            @click="toggleField('category', opt.value)"
          >{{ opt.label }}</button>
        </div>
      </section>

      <!-- 行业类型 P5 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">行业类型<em v-if="model.industry" class="fg-count">1</em></span>
          <button v-if="model.industry" class="fg-clear" @click="setField('industry', '')">清空</button>
        </div>
        <div class="fg-tags fg-industry" :class="{ open: industryOpen }">
          <button
            v-for="opt in groups.industry"
            :key="opt"
            class="fg-tag"
            :class="{ active: model.industry === opt }"
            @click="toggleField('industry', opt)"
          >{{ opt }}</button>
        </div>
        <button v-if="groups.industry.length > 8" class="fg-more" @click="industryOpen = !industryOpen">
          {{ industryOpen ? "收起 ▴" : `更多行业（${groups.industry.length}）▾` }}
        </button>
      </section>

      <!-- 采购方式 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">采购方式<em v-if="model.purchaseWay" class="fg-count">1</em></span>
          <button v-if="model.purchaseWay" class="fg-clear" @click="setField('purchaseWay', '')">清空</button>
        </div>
        <div class="fg-tags">
          <button
            v-for="opt in groups.purchaseWay"
            :key="opt"
            class="fg-tag"
            :class="{ active: model.purchaseWay === opt }"
            @click="toggleField('purchaseWay', opt)"
          >{{ opt }}</button>
        </div>
      </section>

      <!-- 公告类型 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">公告类型<em v-if="model.noticeType" class="fg-count">1</em></span>
          <button v-if="model.noticeType" class="fg-clear" @click="setField('noticeType', '')">清空</button>
        </div>
        <div class="fg-tags">
          <button
            v-for="opt in groups.noticeType"
            :key="opt"
            class="fg-tag"
            :class="{ active: model.noticeType === opt }"
            @click="toggleField('noticeType', opt)"
          >{{ opt }}</button>
        </div>
      </section>

      <!-- 发布阶段 P3/P4 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">发布阶段<em v-if="model.stage || model.dateRange" class="fg-count">1</em></span>
          <button v-if="model.stage || model.dateRange" class="fg-clear" @click="clearStage">清空</button>
        </div>
        <div class="fg-tags">
          <button
            v-for="opt in groups.stage"
            :key="opt.value"
            class="fg-tag"
            :class="{ active: model.stage === opt.value }"
            @click="toggleStage(opt.value)"
          >{{ opt.label }}</button>
          <button
            class="fg-tag"
            :class="{ active: model.stage === 'custom' }"
            @click="toggleStage('custom')"
          >自定义</button>
        </div>
        <el-date-picker
          v-model="model.dateRange"
          type="daterange"
          range-separator="~"
          start-placeholder="开始"
          end-placeholder="结束"
          value-format="YYYY-MM-DD"
          size="default"
          :clearable="false"
          :disabled="model.stage !== 'custom' && !!model.stage"
          class="fg-datepicker"
          @change="onDateChange"
        />
      </section>

      <!-- 金额区间 P8 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">金额区间（万）<em v-if="model.amountMin || model.amountMax" class="fg-count">1</em></span>
          <button v-if="model.amountMin || model.amountMax" class="fg-clear" @click="clearAmount">清空</button>
        </div>
        <div class="fg-tags">
          <button
            v-for="opt in groups.amount"
            :key="opt.label"
            class="fg-tag"
            :class="{ active: isAmountActive(opt) }"
            @click="toggleAmount(opt)"
          >{{ opt.label }}</button>
        </div>
        <div class="fg-amount-row">
          <el-input-number v-model="amtMin" :min="0" :controls="false" placeholder="最低" class="fg-amt" @change="onAmountInput" />
          <span class="dash">~</span>
          <el-input-number v-model="amtMax" :min="0" :controls="false" placeholder="最高" class="fg-amt" @change="onAmountInput" />
          <span class="unit">万</span>
        </div>
      </section>

      <!-- 询价方式 P7 -->
      <section class="filter-group">
        <div class="fg-head">
          <span class="fg-title">询价方式<em v-if="model.priceType" class="fg-count">1</em></span>
          <button v-if="model.priceType" class="fg-clear" @click="setField('priceType', '')">清空</button>
        </div>
        <div class="fg-tags">
          <button
            v-for="opt in groups.priceType"
            :key="opt"
            class="fg-tag"
            :class="{ active: model.priceType === opt }"
            @click="toggleField('priceType', opt)"
          >{{ opt }}</button>
        </div>
      </section>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from "vue";
import { InfoFilled, Bell, Download, Close } from "@element-plus/icons-vue";
import api from "@/api";

interface AmountOpt { label: string; min: string; max: string }
export interface FilterModel {
  province: string;
  category: string;
  industry: string;
  purchaseWay: string;
  noticeType: string;
  dateRange: [string, string] | null;
  amountMin: string;
  amountMax: string;
  priceType: string;
  stage: string;
}

const props = defineProps<{
  model: FilterModel;
  exporting?: boolean;
}>();

const emit = defineEmits<{
  (e: "update", payload: FilterModel): void;
  (e: "subscribe"): void;
  (e: "export"): void;
}>();

/* ── 静态常量（地区/阶段/金额档不来自选项集）── */
const groups = reactive({
  province: ["北京", "天津", "上海", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "湖北", "广东", "广西", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "宁夏", "新疆"],
  category: [
    { value: "工程", label: "工程" },
    { value: "服务", label: "服务" },
    { value: "货物", label: "货物" },
  ],
  industry: [
    "农、林、牧、渔业", "采矿业", "制造业", "电力、燃气及水的生产和供应业",
    "建筑业", "交通运输、仓储和邮政业", "信息传输、计算机服务和软件业",
    "批发和零售业", "住宿和餐饮业", "金融业", "房地产业", "租赁和商务服务业",
    "科学研究、技术服务和地质勘查业", "水利、环境和公共设施管理业",
    "居民服务和其他服务业", "教育", "卫生、社会保障和社会福利业",
    "文化、体育和娱乐业", "公共管理和社会组织", "国际组织",
  ],
  purchaseWay: ["公开招标", "邀请招标", "竞争性谈判", "单一来源", "询价", "其他"],
  noticeType: ["招标", "中标", "成交", "变更", "终止", "其他"],
  stage: [
    { value: "today", label: "今日" },
    { value: "7d", label: "近7天" },
    { value: "1m", label: "近1个月" },
    { value: "3m", label: "近3个月" },
    { value: "1y", label: "近1年" },
  ],
  amount: [
    { label: "10万以下", min: "0", max: "10" },
    { label: "10~100万", min: "10", max: "100" },
    { label: "100~500万", min: "100", max: "500" },
    { label: "500~1000万", min: "500", max: "1000" },
    { label: "1000万以上", min: "1000", max: "" },
  ] as AmountOpt[],
  priceType: ["单价", "总价"],
});

/* 从 option-set 动态加载分类标签云(失败时保留硬编码 fallback) */
async function loadOptionSet(code: string, key: "category" | "industry" | "purchaseWay" | "noticeType" | "priceType") {
  try {
    const res: any = await api.get(`/option-sets/${code}/items`);
    const items = res?.items || [];
    if (!items.length) return;
    if (key === "industry" || key === "purchaseWay" || key === "noticeType" || key === "priceType") {
      groups[key] = items.map((i: any) => i.label || i.value);
    } else {
      groups[key] = items.map((i: any) => ({ value: i.value, label: i.label }));
    }
  } catch {
    /* 后台未配置选项集时使用内置常量 */
  }
}

onMounted(async () => {
  await Promise.all([
    loadOptionSet("bid_category", "category"),
    loadOptionSet("bid_industry", "industry"),
    loadOptionSet("bid_purchase_way", "purchaseWay"),
    loadOptionSet("bid_notice_type", "noticeType"),
    loadOptionSet("bid_price_type", "priceType"),
  ]);
});

/* ── P2 移动端折叠 ── */
const mq = window.matchMedia("(max-width: 768px)");
const isMobile = ref(mq.matches);
const expanded = ref(!mq.matches);
const panelVisible = computed(() => !isMobile.value || expanded.value);
function onMqChange(e: MediaQueryListEvent) {
  isMobile.value = e.matches;
  if (!e.matches) expanded.value = true;
}
onMounted(() => mq.addEventListener("change", onMqChange));
onUnmounted(() => mq.removeEventListener("change", onMqChange));

/* ── P5 行业展开/收起 ── */
const industryOpen = ref(false);

/* ── P10 已选摘要 chips ── */
const STAGE_LABELS: Record<string, string> = {
  today: "今日", "7d": "近7天", "1m": "近1个月", "3m": "近3个月", "1y": "近1年", custom: "自定义",
};
const activeChips = computed(() => {
  const m = props.model;
  const chips: Array<{ field: string; label: string }> = [];
  if (m.province) chips.push({ field: "province", label: m.province });
  if (m.category) chips.push({ field: "category", label: m.category });
  if (m.industry) chips.push({ field: "industry", label: m.industry });
  if (m.purchaseWay) chips.push({ field: "purchaseWay", label: m.purchaseWay });
  if (m.noticeType) chips.push({ field: "noticeType", label: m.noticeType });
  if (m.priceType) chips.push({ field: "priceType", label: m.priceType });
  if (m.stage === "custom" && m.dateRange) {
    chips.push({ field: "dateRange", label: `${m.dateRange[0]} ~ ${m.dateRange[1]}` });
  } else if (m.stage && m.stage !== "custom") {
    chips.push({ field: "stage", label: STAGE_LABELS[m.stage] || m.stage });
  } else if (!m.stage && m.dateRange) {
    chips.push({ field: "dateRange", label: `${m.dateRange[0]} ~ ${m.dateRange[1]}` });
  }
  if (m.amountMin || m.amountMax) {
    chips.push({ field: "amount", label: `${m.amountMin || 0} ~ ${m.amountMax || "∞"} 万` });
  }
  return chips;
});

function removeChip(field: string) {
  const next: any = { ...props.model };
  if (field === "stage" || field === "dateRange") {
    next.stage = "";
    next.dateRange = null;
  } else if (field === "amount") {
    next.amountMin = "";
    next.amountMax = "";
  } else {
    next[field] = "";
  }
  emit("update", next);
}

function clearAll() {
  emit("update", {
    province: "", category: "", industry: "", purchaseWay: "",
    noticeType: "", dateRange: null, amountMin: "", amountMax: "",
    priceType: "", stage: "",
  });
}

/* ── 通用字段切换 ── */
function setField(field: string, value: string) {
  emit("update", { ...props.model, [field]: value, stage: "" });
}

function toggleField(field: string, value: string) {
  setField(field, props.model[field as keyof typeof props.model] === value ? "" : value);
}

/* ── P3 发布阶段（快捷档回显范围 / 自定义可编辑）── */
function toggleStage(value: string) {
  if (value === "custom") {
    emit("update", { ...props.model, stage: "custom" });
    return;
  }
  if (props.model.stage === value) {
    emit("update", { ...props.model, stage: "", dateRange: null });
    return;
  }
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  let from = "";
  const to = fmt(today);
  switch (value) {
    case "today": from = to; break;
    case "7d": from = fmt(new Date(today.getTime() - 7 * 86400000)); break;
    case "1m": from = fmt(new Date(today.getTime() - 30 * 86400000)); break;
    case "3m": from = fmt(new Date(today.getTime() - 90 * 86400000)); break;
    case "1y": from = fmt(new Date(today.getTime() - 365 * 86400000)); break;
    default: from = "";
  }
  // 快捷档选中后同步回显实际范围到日期框
  emit("update", { ...props.model, stage: value, dateRange: from ? [from, to] : null });
}

function onDateChange() {
  // 自定义模式下改日期保持 custom；无档位时仅更新日期
  emit("update", { ...props.model, stage: props.model.stage === "custom" ? "custom" : "" });
}

function clearStage() {
  emit("update", { ...props.model, dateRange: null, stage: "" });
}

/* ── P8 金额标签 ↔ 输入框双向联动 ── */
const amtMin = ref<number | null>(null);
const amtMax = ref<number | null>(null);
watch(
  () => [props.model.amountMin, props.model.amountMax],
  ([mn, mx]) => {
    amtMin.value = mn === "" || mn == null ? null : Number(mn);
    amtMax.value = mx === "" || mx == null ? null : Number(mx);
  },
  { immediate: true }
);

function onAmountInput() {
  emit("update", {
    ...props.model,
    amountMin: amtMin.value == null ? "" : String(amtMin.value),
    amountMax: amtMax.value == null ? "" : String(amtMax.value),
  });
}

function isAmountActive(opt: AmountOpt) {
  const mn = props.model.amountMin;
  const mx = props.model.amountMax;
  if (!mn && !mx) return false;
  if (opt.max === "") {
    // 开区间档(1000万以上): 选中条件 = min 命中且无上限
    return mn !== "" && Number(mn) === Number(opt.min) && !mx;
  }
  return mn !== "" && mx !== "" && Number(mn) === Number(opt.min) && Number(mx) === Number(opt.max);
}

function toggleAmount(opt: AmountOpt) {
  const same = isAmountActive(opt);
  emit("update", {
    ...props.model,
    amountMin: same ? "" : opt.min,
    amountMax: same ? "" : opt.max,
  });
}

function clearAmount() {
  emit("update", { ...props.model, amountMin: "", amountMax: "" });
}
</script>

<style scoped>
.filter-sidebar {
  background: #fff;
  border: 1px solid var(--site-panel-border, #ece8e4);
  border-radius: 8px;
  padding: 0;
  overflow: hidden;
}

/* ── 顶部操作按钮区 (P1) ── */
.filter-actions {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #fbecee 0%, #fdf6f7 100%);
  border-bottom: 1px solid var(--site-panel-border, #ece8e4);
}
.fsa-btn {
  flex: 1;
  white-space: nowrap;
  height: 34px;
  font-weight: 600;
  border-radius: 6px;
  font-size: 13px;
}
.fsa-btn-primary {
  background: var(--site-brand, #a51c30);
  border-color: var(--site-brand, #a51c30);
  color: #fff;
}
.fsa-btn-primary:hover {
  background: var(--site-brand-dark, #851626);
  border-color: var(--site-brand-dark, #851626);
  color: #fff;
}
.fsa-btn-ghost {
  background: #fff;
  border-color: var(--site-panel-border, #ece8e4);
  color: var(--site-text, #1c1a1a);
}
.fsa-btn-ghost:hover {
  border-color: var(--site-brand, #a51c30);
  color: var(--site-brand, #a51c30);
}

/* ── 已选摘要条 (P2/P10) ── */
.filter-summary {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 14px;
  border-bottom: 1px solid var(--site-panel-border, #ece8e4);
}
.fs-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.fs-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: var(--site-brand-soft, #fbecee);
  color: var(--site-brand, #a51c30);
  border: 1px solid #f3d4d8;
  border-radius: 12px;
  font-size: 12px;
  padding: 2px 9px;
  cursor: pointer;
  transition: all 0.15s ease;
  line-height: 1.5;
}
.fs-chip:hover {
  background: var(--site-brand, #a51c30);
  border-color: var(--site-brand, #a51c30);
  color: #fff;
}
.fs-empty {
  font-size: 12px;
  color: var(--site-text-mute, #8c8784);
}
.fs-ops {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
  flex: none;
}
.fs-clearall {
  border: none;
  background: transparent;
  color: var(--site-text-mute, #8c8784);
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  padding: 2px 0;
}
.fs-clearall:hover {
  color: var(--site-brand, #a51c30);
}
.fs-toggle {
  border: none;
  background: transparent;
  color: var(--site-brand, #a51c30);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 2px 0;
  white-space: nowrap;
}

/* ── 提示条：单行截断 (P9) ── */
.filter-tip {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  font-size: 12px;
  color: var(--site-text-mute, #8c8784);
  background: #fafaf8;
  border-bottom: 1px dashed var(--site-panel-border, #ece8e4);
}
.filter-tip .el-icon {
  color: var(--site-brand, #a51c30);
  flex: none;
}
.filter-tip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 筛选组 (P11) ── */
.filter-group {
  padding: 12px 14px;
  border-bottom: 1px solid #f0ece8;
}
.fg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.fg-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--site-text, #1c1a1a);
  position: relative;
  padding-left: 8px;
}
.fg-title::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 12px;
  background: var(--site-brand, #a51c30);
  border-radius: 2px;
}
.fg-count {
  font-style: normal;
  font-size: 10.5px;
  font-weight: 600;
  background: var(--site-brand, #a51c30);
  color: #fff;
  border-radius: 8px;
  padding: 0 5px;
  margin-left: 5px;
  line-height: 15px;
  vertical-align: 1px;
}
.fg-clear {
  border: none;
  background: transparent;
  color: var(--site-text-mute, #8c8784);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}
.fg-clear:hover {
  color: var(--site-brand, #a51c30);
}

/* 标签云 */
.fg-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* P6 省份等宽栅格 */
.fg-tags-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}
.fg-tags-grid .fg-tag {
  width: 100%;
  text-align: center;
}

/* P5 行业折叠 + 渐隐遮罩 */
.fg-industry {
  position: relative;
  max-height: 64px;
  overflow: hidden;
}
.fg-industry::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 22px;
  background: linear-gradient(transparent, #fff);
  pointer-events: none;
}
.fg-industry.open {
  max-height: 220px;
  overflow-y: auto;
}
.fg-industry.open::after {
  display: none;
}
.fg-industry.open::-webkit-scrollbar {
  width: 6px;
}
.fg-industry.open::-webkit-scrollbar-thumb {
  background: #d8d2cc;
  border-radius: 3px;
}
.fg-more {
  margin-top: 8px;
  border: none;
  background: transparent;
  color: var(--site-brand, #a51c30);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.fg-more:hover {
  text-decoration: underline;
}

.fg-tag {
  border: 1px solid #e7e2dc;
  background: #fff;
  color: var(--site-text-dim, #4a4646);
  font-size: 12.5px;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.18s ease;
  line-height: 1.4;
}
.fg-tag:hover {
  border-color: var(--site-brand, #a51c30);
  color: var(--site-brand, #a51c30);
}
.fg-tag.active {
  background: var(--site-brand, #a51c30);
  border-color: var(--site-brand, #a51c30);
  color: #fff;
  box-shadow: 0 2px 5px rgba(165, 28, 48, 0.25);
}

/* ── P3/P4 日期选择器（快捷档只读回显 / 自定义可编辑；窄屏压缩）── */
.fg-datepicker {
  width: 100%;
  margin-top: 10px;
}
.fg-datepicker :deep(.el-range-input) {
  width: 40%;
  font-size: 12px;
}
.fg-datepicker :deep(.el-range-separator) {
  width: 18px;
  padding: 0;
  font-size: 12px;
}

/* ── P8 金额输入行 ── */
.fg-amount-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
}
.fg-amt {
  flex: 1;
}
.fg-amt :deep(.el-input__wrapper) {
  padding: 1px 8px;
}
.fg-amount-row .dash {
  color: var(--site-text-mute, #8c8784);
  font-size: 12px;
}
.fg-amount-row .unit {
  font-size: 12px;
  color: var(--site-text-mute, #8c8784);
  flex: none;
}

/* ── 响应式 (P2/P4) ── */
@media (max-width: 768px) {
  .filter-sidebar {
    border-radius: 6px;
  }
  .filter-group {
    padding: 12px 14px;
  }
}
@media (max-width: 480px) {
  .fg-tags-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
