<template>
  <el-drawer
    :model-value="visible"
    :size="480"
    direction="rtl"
    :with-header="false"
    :modal-class="'ac-mask'"
    :close-on-click-modal="true"
    class="ai-chat-drawer"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @closed="onClosed"
  >
    <!-- 头部（固定，不随内容滚动） -->
    <div class="ac-head">
      <div class="ac-avatar"><el-icon :size="20"><MagicStick /></el-icon></div>
      <div class="ac-head-info">
        <div class="ac-title">AI 人脉分析师</div>
        <div class="ac-sub" :title="isPath === false ? targetName : `${meName} → ${targetName}`">
          {{ isPath === false ? targetName : `${meName} → ${targetName}` }}
        </div>
      </div>
      <div class="ac-head-actions">
        <el-tooltip content="清空对话" placement="bottom">
          <el-button text circle :icon="Delete" :disabled="streaming || !messages.length" @click="clearChat" />
        </el-tooltip>
        <el-tooltip content="关闭" placement="bottom">
          <el-button text circle :icon="Close" @click="emit('update:modelValue', false)" />
        </el-tooltip>
      </div>
    </div>

    <!-- 模型状态条 -->
    <div class="ac-status">
      <el-tag v-if="aiReady" size="small" type="success" effect="plain" round>
        <el-icon style="margin-right: 4px"><Cpu /></el-icon>{{ modelLabel }}
      </el-tag>
      <el-tag v-else size="small" type="warning" effect="plain" round>
        <el-icon style="margin-right: 4px"><WarningFilled /></el-icon>未配置 AI 模型
      </el-tag>
      <span v-if="streaming" class="ac-streaming-hint">
        <span class="ac-cursor"></span>{{ aiReady ? '正在生成…' : '内置规则分析' }}
      </span>
    </div>

    <!-- 未配置 AI 提示 -->
    <div v-if="!aiReady" class="ac-config-hint">
      <el-icon><WarningFilled /></el-icon>
      <span>当前展示内置规则分析，无法 AI 追问。可在右上角头像 → AI 模型配置后获得对话能力。</span>
    </div>

    <!-- 消息区（仅此区域滚动，头部/输入区固定） -->
    <div ref="listEl" class="ac-body">
      <div v-for="(m, i) in messages" :key="i" class="ac-msg" :class="m.role">
        <div v-if="m.role === 'assistant'" class="ac-msg-avatar">
          <el-icon :size="15"><MagicStick /></el-icon>
        </div>
        <div class="ac-bubble" :class="m.role">
          <div v-if="m.done" class="ac-bubble-text" v-html="renderMd(m.content)"></div>
          <div v-else class="ac-bubble-text plain">
            {{ m.content }}<span v-if="isTyping(m)" class="ac-caret"></span>
          </div>
        </div>
      </div>
      <div v-if="streaming && !messages.length" class="ac-msg assistant">
        <div class="ac-msg-avatar"><el-icon :size="15"><MagicStick /></el-icon></div>
        <div class="ac-bubble assistant ac-typing">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
      </div>
    </div>

    <!-- 快捷追问（常驻占位, 不因生成状态出现/消失导致输入框跳动） -->
    <div class="ac-chips">
      <button
        v-for="c in QUICK_ASKS" :key="c"
        class="ac-chip" :class="{ 'is-disabled': streaming || !aiReady }"
        :disabled="streaming || !aiReady"
        @click="send(c)"
      >{{ c }}</button>
    </div>

    <!-- 输入区（原生 textarea，回车发送 / Shift+回车换行） -->
    <div class="ac-input">
      <textarea
        ref="taEl"
        v-model="draft"
        class="ac-ta"
        rows="1"
        :placeholder="aiReady ? '输入问题，Enter 发送，Shift+Enter 换行' : '配置 AI 模型后可对话追问…'"
        @keydown.enter.exact.prevent="onSend"
        @keydown.enter.shift.exact.prevent="insertNewline"
      ></textarea>
      <el-button
        v-if="!streaming"
        type="primary"
        class="ac-send-btn"
        :icon="Promotion"
        @click="onSend"
      >发送</el-button>
      <el-button v-else type="danger" :icon="CloseBold" @click="stopStream">停止</el-button>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from "vue";
import { ElMessage } from "element-plus";
import {
  MagicStick, Delete, Close, WarningFilled, Promotion, CloseBold, Cpu,
} from "@element-plus/icons-vue";

const props = defineProps<{
  modelValue: boolean;
  meName: string;
  targetName: string;
  steps: any[];
  fallbackResult?: any | null;
  /** 可选: 打开抽屉时的首轮分析问题(如"分析此公司的项目采购机会"); 缺省用默认人脉路径分析 */
  presetQuestion?: string;
  /** 数据是否为人脉路径(从我到目标, 首节点为我): true 走触达路径分节; false 为实体上下文分析 */
  isPath?: boolean;
}>();
const emit = defineEmits<{ (e: "update:modelValue", v: boolean): void }>();

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  /** true: 已完成(渲染 markdown)；false: 正在打字机输出(纯文本) */
  done: boolean;
  /** 打字机期间唯一一条进行中的消息 */
  typing?: boolean;
}

const visible = computed(() => props.modelValue);
const listEl = ref<HTMLElement | null>(null);
const taEl = ref<HTMLTextAreaElement | null>(null);
const messages = ref<ChatMsg[]>([]);
const draft = ref("");
const streaming = ref(false);
const aiReady = ref(false);
const aiCfg = ref<any>(null);
let abortCtrl: AbortController | null = null;
let initialized = false;
/** 记录上一次分析的目标名, 目标变化时强制重置会话(解决组件复用导致对话框停在旧目标) */
let lastTargetName = props.targetName;

// 目标切换: 重置会话并重新分析
watch(
  () => props.targetName,
  (nv) => {
    if (!nv || nv === lastTargetName) return;
    lastTargetName = nv;
    initialized = false;
    messages.value = [];
    sessionStorage.removeItem(SESSION_KEY());
    if (visible.value) {
      initialized = true;
      onOpen();
    }
  }
);

const STORAGE_KEY = "ssm_ai_config";
const SESSION_KEY = () => `ssm_ai_chat_${props.meName || "me"}_${props.targetName || "target"}`;

/** 首轮分析问题: 优先用调用方预设的问题(如"分析此公司的项目采购机会"), 否则按数据模式给出默认问题 */
function defaultQuestion(): string {
  if (props.presetQuestion) return props.presetQuestion;
  if (props.isPath === false) {
    return `请基于上方信息，从「${props.targetName || "该实体"}」的基本情况、关联单位与人员、参与项目、潜在合作机会等角度给出客观分析。`;
  }
  return `请分析从「${props.meName || "我"}」到「${props.targetName || "目标"}」的这条人脉路径，按触达路径解读 / 关键桥接人 / 相关单位 / 可切入的合作项目 / 公关建议 / 潜在合作机会 分节分析。`;
}

const QUICK_ASKS = [
  "如何让中间人愿意引荐？",
  "对方可能关注什么？",
  "怎么开场破冰？",
  "有什么合作风险？",
];

const modelLabel = computed(() => (aiCfg.value?.model ? `模型：${aiCfg.value.model}` : "AI 在线"));

function loadAiConfig(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const cfg = JSON.parse(raw);
      if (cfg?.base_url && cfg?.model) {
        aiCfg.value = cfg;
        aiReady.value = true;
        return true;
      }
    }
  } catch { /* ignore */ }
  aiCfg.value = null;
  aiReady.value = false;
  return false;
}

/** 是否接近消息区底部（用户上翻浏览历史时不打扰） */
function nearBottom(): boolean {
  const el = listEl.value;
  if (!el) return true;
  return el.scrollHeight - el.scrollTop - el.clientHeight < 90;
}

function scrollToBottom() {
  nextTick(() => {
    const el = listEl.value;
    if (el && nearBottom()) {
      el.scrollTop = el.scrollHeight;   // 只滚动消息区, 不影响外层布局
    }
  });
}

function isTyping(m: ChatMsg): boolean {
  return m.typing === true;
}

/** 内置规则回退结果 → 对话文本（按 markdown 分节，享受美化渲染） */
function formatFallback(r: any): string {
  if (!r) return "";
  const parts: string[] = [];
  if (r.summary) {
    parts.push(`## ${props.isPath === false ? "分析要点" : "触达路径解读"}\n${r.summary}`);
  }
  if (r.bridges?.length) {
    parts.push("## 关键桥接人");
    r.bridges.forEach((b: any) => {
      const who = b.company_name ? `${b.name}（${b.company_name}${b.position ? " · " + b.position : ""}）` : b.name;
      parts.push(`- **${who}**：${b.tip || ""}`);
    });
  }
  if (r.companies?.length) {
    parts.push("## 相关单位");
    r.companies.forEach((c: any) => parts.push(`- **${c.name}**：${c.tip || ""}`));
  }
  if (r.projects?.length) {
    parts.push("## 可切入的合作项目");
    r.projects.forEach((p: any) => parts.push(`- **${p.name}**：${p.tip || ""}`));
  }
  if (r.advice?.length) {
    parts.push("## 公关建议");
    r.advice.forEach((t: string, i: number) => parts.push(`${i + 1}. ${t}`));
  }
  if (r.opportunities?.length) {
    parts.push("## 潜在合作机会");
    r.opportunities.forEach((t: string) => parts.push(`- ${t}`));
  }
  parts.push("> 以上为内置规则分析，配置 AI 模型后可对话追问。");
  return parts.join("\n");
}

/* ============ 打字机：收到即入 buffer，定时逐字刷出 ============
 * 关键: 通过数组索引访问 messages.value[i]（Vue 响应式代理对象）,
 * 绝不能缓存原始对象引用再直接改属性, 否则绕过代理不触发视图更新。
 */
let typeBuf = "";
let typeTimer: number | null = null;
let typeDone = false;
let typeIdx = -1;

const TYPE_MS = 24;          // 每 tick 间隔
const TYPE_STEP = 2;         // 每 tick 固定刷出字数（匀速逐字，观感连续）

/** 获取当前正在打字的消息（走响应式数组，返回代理对象） */
function getTypeMsg(): ChatMsg | null {
  if (typeIdx < 0 || typeIdx >= messages.value.length) return null;
  return messages.value[typeIdx];
}

function typeTick() {
  if (!typeBuf) {
    if (typeDone) finishTyping();
    return;
  }
  const m = getTypeMsg();
  if (!m) { typeBuf = ""; return; }
  // 生成期间匀速逐字；流结束后按剩余量适度加速收尾（最多一次 6 字）
  const step = typeDone
    ? Math.max(TYPE_STEP, Math.min(6, Math.ceil(typeBuf.length / 200)))
    : TYPE_STEP;
  m.content += typeBuf.slice(0, step);
  typeBuf = typeBuf.slice(step);
  scrollToBottom();
}

function startTyping(idx: number) {
  typeIdx = idx;
  const m = messages.value[idx];
  if (m) {
    m.typing = true;
    m.done = false;
  }
  typeBuf = "";
  typeDone = false;
  if (typeTimer !== null) clearInterval(typeTimer);
  typeTimer = window.setInterval(typeTick, TYPE_MS);
}

function pushChunk(chunk: string) {
  typeBuf += chunk;
  // 已停止打字机但流未结束时重启
  if (typeTimer === null && typeIdx >= 0) {
    typeTimer = window.setInterval(typeTick, TYPE_MS);
  }
}

function finishTyping() {
  if (typeTimer !== null) {
    clearInterval(typeTimer);
    typeTimer = null;
  }
  const m = getTypeMsg();
  if (m) {
    m.typing = false;
    m.done = true;
  }
  typeIdx = -1;
  typeBuf = "";
  typeDone = false;
}

/** 立即输出剩余 buffer（停止生成时用） */
function flushTyping() {
  const m = getTypeMsg();
  if (m && typeBuf) {
    m.content += typeBuf;
    typeBuf = "";
  }
  finishTyping();
}

/* ============ 发送 ============ */
function onSend() {
  const q = draft.value.trim();
  if (!q) {
    ElMessage.warning("请输入想追问的内容");
    return;
  }
  if (streaming.value) return;
  if (!aiReady.value) {
    ElMessage.warning("请先配置 AI 模型（右上角头像 → AI 模型配置）后即可对话追问");
    return;
  }
  send(q);
  draft.value = "";
}

function insertNewline() {
  draft.value += "\n";
  nextTick(() => {
    if (taEl.value) taEl.value.scrollTop = taEl.value.scrollHeight;
  });
}

async function send(text?: string) {
  const q = (text ?? draft.value).trim();
  if (!q || streaming.value || !aiReady.value) return;
  if (!text) draft.value = "";

  messages.value.push({ role: "user", content: q, done: true });
  const aiIdx = messages.value.push({ role: "assistant", content: "", done: false, typing: true }) - 1;
  streaming.value = true;
  startTyping(aiIdx);
  scrollToBottom();

  const history = messages.value
    .map((m, i) => (i === aiIdx ? null : { role: m.role, content: m.content }))
    .filter(Boolean) as { role: string; content: string }[];

  abortCtrl = new AbortController();
  // 超时保护: 90s 无响应自动中断, 避免 AI 不可达时永久转圈
  let timedOut = false;
  const timeoutTimer = window.setTimeout(() => {
    timedOut = true;
    abortCtrl?.abort();
  }, 90000);
  try {
    const res = await fetch("/api/v1/ai/network/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("ssm_token") || ""}`,
      },
      body: JSON.stringify({
        base_url: aiCfg.value.base_url,
        model: aiCfg.value.model,
        me_name: props.meName || "",
        target_name: props.targetName || "",
        steps: props.steps || [],
        is_path: props.isPath !== false,
        messages: history,
      }),
      signal: abortCtrl.signal,
    });
    if (!res.ok || !res.body) {
      let detail = `请求失败 (HTTP ${res.status})`;
      try { detail = (await res.json())?.detail || detail; } catch { /* ignore */ }
      // 凭证失效: 与 axios 拦截器行为一致, 清除过期 token 并跳转登录
      if (res.status === 401) {
        localStorage.removeItem("ssm_token");
        sessionStorage.removeItem(SESSION_KEY());
        const m = messages.value[aiIdx];
        if (m) m.content = `登录已过期，请重新登录后再试。`;
        flushTyping();
        window.location.href = "/login";
        return;
      }
      const m = messages.value[aiIdx];
      if (m) m.content = `抱歉，AI 分析师暂时不可用：${detail}。`;
      flushTyping();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop() || "";
      for (const evt of events) {
        for (const line of evt.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data || data === "[DONE]") continue;
          try {
            const j = JSON.parse(data);
            if (j.error) {
              const m = messages.value[aiIdx];
              if (m) m.content += `\n\n> [连接中断] ${j.error}`;
            } else if (typeof j.content === "string") {
              pushChunk(j.content);
            }
          } catch { /* ignore malformed */ }
        }
      }
    }
  } catch (e: any) {
    const m = messages.value[aiIdx];
    if (m) {
      if (timedOut) {
        m.content = (m.content || "") + "\n\n> AI 响应超时（90 秒无输出），请检查右上角头像 → AI 模型配置，或稍后重试。";
      } else if (e?.name !== "AbortError") {
        m.content = m.content || `抱歉，AI 分析师暂时不可用：${e?.message || "网络错误"}。`;
      } else {
        m.content = m.content + "\n\n（已停止生成）";
      }
    }
  } finally {
    window.clearTimeout(timeoutTimer);
    typeDone = true;
    // 流已结束：剩余 buffer 由 typeTick 加速匀速刷完，typeTick 检测到
    // typeBuf 为空且 typeDone 后会自动 finishTyping，这里只做兜底
    const guard = window.setInterval(() => {
      if (!typeBuf) {
        clearInterval(guard);
        finishTyping();
      }
    }, 200);
    abortCtrl = null;
    streaming.value = false;
    persist();
    scrollToBottom();
  }
}

function stopStream() {
  abortCtrl?.abort();
  typeDone = true;
  // 立即输出剩余内容并结束打字机
  const m = getTypeMsg();
  if (m && typeBuf) {
    m.content += typeBuf;
    typeBuf = "";
  }
  finishTyping();
}

/* ============ 会话管理 ============ */
function clearChat() {
  if (streaming.value) return;
  messages.value = [];
  sessionStorage.removeItem(SESSION_KEY());
  if (aiReady.value) {
    void send(defaultQuestion());
  } else if (props.fallbackResult) {
    messages.value.push({ role: "assistant", content: formatFallback(props.fallbackResult), done: true });
  }
}

/** 会话持久化上限(条数): 超出丢弃最早消息, 防止 sessionStorage 持续膨胀 */
const MAX_SAVED_MSGS = 50;

function persist() {
  try {
    const done = messages.value.filter((m) => m.done);
    const kept = done.length > MAX_SAVED_MSGS ? done.slice(-MAX_SAVED_MSGS) : done;
    sessionStorage.setItem(SESSION_KEY(), JSON.stringify({
      messages: kept,
      aiReady: aiReady.value,
    }));
  } catch { /* ignore */ }
}

function restore() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY());
    if (!raw) return false;
    const saved = JSON.parse(raw);
    if (Array.isArray(saved.messages) && saved.messages.length) {
      const msgs = saved.messages.slice(-MAX_SAVED_MSGS);
      messages.value = msgs.map((m: any) => ({ role: m.role, content: m.content, done: true }));
      return true;
    }
  } catch { /* ignore */ }
  return false;
}

/** 打开抽屉：有历史则续接，无历史才首轮分析 */
function onOpen() {
  loadAiConfig();
  if (restore()) {
    scrollToBottom();
    return;
  }
  if (aiReady.value) {
    void send(defaultQuestion());
  } else if (props.fallbackResult) {
    messages.value.push({ role: "assistant", content: formatFallback(props.fallbackResult), done: true });
  }
}

function onClosed() {
  persist();
  // 关闭时中止仍在进行的生成
  if (streaming.value) stopStream();
}

watch(visible, (v) => {
  if (v && !initialized) {
    initialized = true;
    onOpen();
  }
  if (v) {
    nextTick(() => taEl.value?.focus());
  }
}, { immediate: true });

/* ============ Markdown 渲染（先转义防 XSS，再结构化美化） ============ */
const SEC_META: Record<string, { icon: string; cls: string }> = {
  "触达路径解读": { icon: "🧭", cls: "sec-route" },
  "关键桥接人": { icon: "🤝", cls: "sec-bridge" },
  "相关单位": { icon: "🏢", cls: "sec-company" },
  "可切入的合作项目": { icon: "🎯", cls: "sec-project" },
  "公关建议": { icon: "📋", cls: "sec-advice" },
  "潜在合作机会": { icon: "💡", cls: "sec-opp" },
};

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderMd(text: string): string {
  const esc = escapeHtml(text)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  const lines = esc.split("\n");
  let out = "";
  let list: "ul" | "ol" | null = null;
  let para = "";
  const closeList = () => {
    if (list) { out += `</${list}>`; list = null; }
  };
  const closePara = () => {
    if (para) { out += `<div class="md-para">${para}</div>`; para = ""; }
  };
  for (const rawLine of lines) {
    const t = rawLine.trim();
    let m: RegExpExecArray | null;
    if ((m = /^#{1,3}\s+(.*)$/.exec(t))) {
      closeList(); closePara();
      const title = m[1];
      const meta = SEC_META[title];
      if (meta) {
        out += `<div class="md-sec ${meta.cls}"><span class="md-sec-icon">${meta.icon}</span><span class="md-sec-title">${title}</span></div>`;
      } else {
        out += `<div class="md-h">${title}</div>`;
      }
    } else if ((m = /^> ?(.*)$/.exec(t))) {
      closeList(); closePara();
      out += `<div class="md-quote">${m[1]}</div>`;
    } else if ((m = /^[-*•]\s+(.*)$/.exec(t))) {
      closePara();
      if (list !== "ul") { closeList(); out += "<ul>"; list = "ul"; }
      out += `<li>${m[1]}</li>`;
    } else if ((m = /^\d+[.、)]\s*(.*)$/.exec(t))) {
      closePara();
      if (list !== "ol") { closeList(); out += "<ol>"; list = "ol"; }
      out += `<li>${m[1]}</li>`;
    } else if (!t) {
      closeList(); closePara();
    } else {
      closeList();
      para += (para ? "<br/>" : "") + rawLine;
    }
  }
  closeList(); closePara();
  return out;
}
</script>

<style scoped>
.ai-chat-drawer {
  height: 100%;
}
/* 注意: el-drawer 内容 teleport 到 body, :deep 依赖 scopeId 可能失效,
   故抽屉 body 的布局/滚动约束放在非 scoped 全局样式(见文件底部 <style>)。 */

/* 头部（固定） */
.ac-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #4f6ef7, #7c4dff 65%, #a855f7);
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(76, 91, 255, 0.25);
  position: relative;
  z-index: 2;
}
.ac-avatar {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  border: 1.5px solid rgba(255, 255, 255, 0.5);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  backdrop-filter: blur(4px);
}
.ac-head-info { flex: 1; min-width: 0; }
.ac-title { font-size: 15px; font-weight: 600; letter-spacing: 0.3px; }
.ac-sub {
  font-size: 12px; opacity: 0.88; margin-top: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ac-head-actions { display: flex; align-items: center; gap: 2px; }
.ac-head-actions :deep(.el-button) { color: #fff; }

/* 模型状态条 */
.ac-status {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.7);
  border-bottom: 1px solid #e8ecf3;
  backdrop-filter: blur(6px);
}
.ac-streaming-hint {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; color: #606266;
}
.ac-cursor {
  width: 8px; height: 14px; border-radius: 2px;
  background: #4f6ef7;
  display: inline-block;
  animation: ac-blink-cursor 0.9s infinite steps(1);
}
@keyframes ac-blink-cursor {
  0%, 100% { opacity: 1; } 50% { opacity: 0; }
}

/* 未配置提示 */
.ac-config-hint {
  display: flex; align-items: flex-start; gap: 8px;
  margin: 12px 16px 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  color: #b25e09;
  font-size: 12.5px;
  line-height: 1.6;
  flex-shrink: 0;
}
.ac-config-hint .el-icon { margin-top: 2px; flex-shrink: 0; }

/* 消息区（唯一滚动区） */
.ac-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ac-msg { display: flex; align-items: flex-start; gap: 8px; }
.ac-msg.user { justify-content: flex-end; }

.ac-msg-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f6ef7, #a855f7);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(79, 110, 247, 0.35);
}

.ac-bubble {
  max-width: 84%;
  padding: 10px 13px;
  border-radius: 12px;
  font-size: 13.5px;
  line-height: 1.75;
  word-break: break-word;
}
.ac-bubble.assistant {
  background: #fff;
  border: 1px solid #e6eaf2;
  border-top-left-radius: 4px;
  box-shadow: 0 2px 10px rgba(30, 41, 82, 0.06);
}
.ac-bubble.user {
  background: linear-gradient(135deg, #4f6ef7, #6d8dff);
  color: #fff;
  border-top-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(79, 110, 247, 0.3);
}
.ac-bubble-text.plain { white-space: pre-wrap; }

/* markdown 分节美化 */
.ac-bubble-text :deep(.md-sec) {
  display: flex; align-items: center; gap: 7px;
  font-size: 14px; font-weight: 700;
  margin: 8px 0 6px;
  padding: 6px 10px;
  border-radius: 8px;
  background: #f4f6ff;
  border-left: 3px solid #4f6ef7;
}
.ac-bubble-text :deep(.md-sec:first-child) { margin-top: 0; }
.ac-bubble-text :deep(.md-sec.sec-route) { background: #eff6ff; border-color: #2979ff; color: #1f5fb8; }
.ac-bubble-text :deep(.md-sec.sec-bridge) { background: #f5f3ff; border-color: #7c4dff; color: #6236c8; }
.ac-bubble-text :deep(.md-sec.sec-company) { background: #f0f9eb; border-color: #67c23a; color: #4d9123; }
.ac-bubble-text :deep(.md-sec.sec-project) { background: #fdf6ec; border-color: #e6a23c; color: #b26a0a; }
.ac-bubble-text :deep(.md-sec.sec-advice) { background: #fef0f0; border-color: #f56c6c; color: #c03636; }
.ac-bubble-text :deep(.md-sec.sec-opp) { background: #f0f9ff; border-color: #17a2b8; color: #0e7f92; }
.ac-bubble-text :deep(.md-sec-icon) { font-size: 15px; }
.ac-bubble-text :deep(.md-h) {
  font-weight: 700; color: #303133;
  font-size: 14px; margin: 8px 0 4px;
}
.ac-bubble-text :deep(.md-h:first-child) { margin-top: 0; }
.ac-bubble-text :deep(.md-para) { margin: 3px 0; }
.ac-bubble-text :deep(.md-quote) {
  margin: 6px 0; padding: 4px 10px;
  border-left: 3px solid #d5dbe8;
  background: #f7f8fc;
  color: #7c8495; border-radius: 4px; font-size: 12.5px;
}
.ac-bubble-text :deep(ul),
.ac-bubble-text :deep(ol) { margin: 4px 0; padding-left: 20px; }
.ac-bubble-text :deep(li) { margin: 3px 0; }
.ac-bubble-text :deep(code) {
  background: #f0f2f5; border-radius: 4px;
  padding: 1px 5px; font-size: 12.5px;
  color: #c7254e;
}
.ac-bubble-text :deep(strong) { font-weight: 700; color: #2b3245; }

/* 打字指示 */
.ac-typing { display: flex; align-items: center; gap: 4px; min-height: 22px; }
.ac-typing .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #a0b8ff;
  animation: ac-blink 1.2s infinite ease-in-out;
}
.ac-typing .dot:nth-child(2) { animation-delay: 0.2s; }
.ac-typing .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes ac-blink {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
.ac-caret {
  display: inline-block; width: 2px; height: 15px;
  background: #4f6ef7; margin-left: 2px; vertical-align: -2px;
  animation: ac-blink-cursor 0.8s infinite steps(1);
}

/* 快捷追问 */
.ac-chips {
  display: flex; gap: 6px; overflow-x: auto;
  padding: 8px 16px 0;
  flex-shrink: 0;
  scrollbar-width: none;
}
.ac-chips::-webkit-scrollbar { display: none; }
.ac-chip {
  flex-shrink: 0;
  border: 1px solid #d6e0ff;
  background: #fff;
  color: #4f6ef7;
  font-size: 12px;
  border-radius: 14px;
  padding: 4px 11px;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}
.ac-chip:hover:not(.is-disabled) { background: #4f6ef7; color: #fff; border-color: #4f6ef7; }
.ac-chip.is-disabled { opacity: 0.45; cursor: not-allowed; }

/* 输入区（固定） */
.ac-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 14px 14px;
  border-top: 1px solid #e6eaf2;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}
.ac-ta {
  flex: 1;
  height: 40px;          /* 固定高度, 不随内容变化 */
  min-height: 40px;
  max-height: 40px;
  overflow-y: auto;      /* 内容多时内部滚动 */
  resize: none;
  border: 1px solid #dce2ee;
  border-radius: 10px;
  padding: 9px 12px;
  font: inherit;
  font-size: 13.5px;
  line-height: 1.6;
  outline: none;
  background: #fbfcff;
  color: #303133;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.ac-ta:focus {
  border-color: #4f6ef7;
  box-shadow: 0 0 0 3px rgba(79, 110, 247, 0.12);
}
.ac-ta::placeholder { color: #a8b0c2; }
.ac-send-btn { margin-left: 0; }
.ac-send-btn :deep(span) { font-weight: 600; }
</style>

<style>
/* 淡遮罩：点击聊天框外可关闭，且不把背景压黑 */
.ac-mask {
  background-color: rgba(20, 28, 52, 0.16) !important;
  backdrop-filter: blur(1.5px);
}

/* ── 抽屉布局（非 scoped：el-drawer teleport 到 body，scoped+deep 会失效）──
 * 关键：body 限高 + overflow hidden，只有内部 .ac-body 滚动，
 * 输入区固定底部不随消息滚动。 */
.ai-chat-drawer {
  height: 100%;
}
.ai-chat-drawer .el-drawer__body {
  padding: 0 !important;
  height: 100% !important;
  min-height: 0 !important;
  overflow: hidden !important;
  display: flex !important;
  flex-direction: column !important;
  background: linear-gradient(180deg, #f5f7fb 0%, #eef1f7 100%);
}
</style>
