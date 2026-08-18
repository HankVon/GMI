<template>
  <el-dialog
    :model-value="modelValue" title="AI 模型配置" width="520px" top="18vh"
    @update:model-value="(v) => emit('update:modelValue', v)"
    :close-on-click-modal="false"
  >
    <el-alert
      type="info" show-icon :closable="false" style="margin-bottom: 16px"
      title="配置后，「人脉分析」将调用本地 Ollama 的 qwen 大模型生成智能分析；未配置时自动使用内置规则分析。"
    />

    <el-form label-width="110px">
      <el-form-item label="Ollama 地址">
        <el-input v-model="form.base_url" placeholder="http://localhost:11434" clearable>
          <template #prefix><el-icon><Monitor /></el-icon></template>
        </el-input>
        <div class="base-url-tip">仅支持本机回环地址（localhost/127.0.0.1），出于安全考虑服务端不接受远程地址。</div>
      </el-form-item>

      <el-form-item label="模型">
        <div class="model-row">
          <el-select
            v-model="form.model" filterable allow-create default-first-option
            placeholder="选择或输入模型名" style="flex: 1"
          >
            <el-option
              v-for="m in modelOptions" :key="m" :label="m" :value="m"
            />
          </el-select>
          <el-button :loading="loadingModels" @click="loadModels">
            {{ modelOptions.length ? '刷新模型' : '加载模型' }}
          </el-button>
        </div>
        <div v-if="modelsMsg" class="models-msg" :class="modelsOk ? 'is-ok' : 'is-err'">
          {{ modelsMsg }}
        </div>
      </el-form-item>

      <el-form-item label="测试连接">
        <el-button :loading="testing" :type="tested ? (testOk ? 'success' : 'danger') : 'default'" @click="testConnect">
          {{ tested ? (testOk ? '连接成功' : '连接失败') : '测试' }}
        </el-button>
        <span v-if="tested && testOk" class="test-detail">{{ testDetail }}</span>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <span v-if="saved" class="saved-tip"><el-icon><CircleCheck /></el-icon>已保存：{{ savedModel }}</span>
        <el-button @click="emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" @click="save">保存配置</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Monitor, CircleCheck } from "@element-plus/icons-vue";
import api from "@/api";

const props = defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{ (e: "update:modelValue", v: boolean): void }>();

const STORAGE_KEY = "ssm_ai_config";

const form = ref({ base_url: "http://localhost:11434", model: "" });
const modelOptions = ref<string[]>([]);
const loadingModels = ref(false);
const modelsMsg = ref("");
const modelsOk = ref(false);
const testing = ref(false);
const tested = ref(false);
const testOk = ref(false);
const testDetail = ref("");
const saved = ref(false);
const savedModel = ref("");

function loadSaved() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const cfg = JSON.parse(raw);
      if (cfg.base_url) form.value.base_url = cfg.base_url;
      if (cfg.model) form.value.model = cfg.model;
      saved.value = true;
      savedModel.value = cfg.model || "";
    }
  } catch { /* ignore */ }
}

async function loadModels() {
  loadingModels.value = true;
  modelsMsg.value = "";
  try {
    const res: any = await api.get("/ai/ollama/models", { params: { base_url: form.value.base_url } });
    if (res.ok) {
      modelOptions.value = res.models || [];
      modelsOk.value = true;
      modelsMsg.value = `连接成功，发现 ${modelOptions.value.length} 个模型`;
      if (!form.value.model && modelOptions.value.length) {
        const pick = modelOptions.value.find((m: string) => /qwen/i.test(m)) || modelOptions.value[0];
        form.value.model = pick;
      }
    } else {
      modelsOk.value = false;
      modelsMsg.value = `连接失败：${res.detail || "无法访问 Ollama"}`;
    }
  } catch (e: any) {
    modelsOk.value = false;
    modelsMsg.value = `连接失败：${e?.message || "无法访问 Ollama"}`;
  } finally {
    loadingModels.value = false;
  }
}

async function testConnect() {
  if (testing.value) return;
  testing.value = true;
  tested.value = false;
  try {
    const res: any = await api.get("/ai/ollama/models", { params: { base_url: form.value.base_url } });
    if (res.ok) {
      testOk.value = true;
      testDetail.value = form.value.model
        ? `模型「${form.value.model}」已就绪`
        : `Ollama 已连接（${res.models?.length || 0} 个模型）`;
    } else {
      testOk.value = false;
      testDetail.value = res.detail || "连接失败";
    }
  } catch (e: any) {
    testOk.value = false;
    testDetail.value = e?.message || "连接失败";
  } finally {
    tested.value = true;
    testing.value = false;
  }
}

function save() {
  const cfg = {
    base_url: (form.value.base_url || "http://localhost:11434").trim(),
    model: form.value.model.trim(),
  };
  if (!cfg.model) {
    ElMessage.warning("请选择或输入模型名");
    return;
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
  saved.value = true;
  savedModel.value = cfg.model;
  ElMessage.success(`已保存 AI 配置：${cfg.model}`);
  emit("update:modelValue", false);
}

watch(
  () => props.modelValue,
  (v) => { if (v) loadSaved(); },
  { immediate: true }
);
</script>

<style scoped>
.model-row { display: flex; gap: 8px; width: 100%; }
.base-url-tip { font-size: 12px; color: #909399; margin-top: 4px; }
.models-msg { font-size: 12.5px; margin-top: 6px; }
.models-msg.is-ok { color: #67c23a; }
.models-msg.is-err { color: #f56c6c; }
.test-detail { margin-left: 10px; font-size: 12.5px; color: #909399; }
.dialog-footer { display: flex; align-items: center; justify-content: space-between; }
.saved-tip { display: inline-flex; align-items: center; gap: 4px; color: #67c23a; font-size: 12.5px; }
</style>
