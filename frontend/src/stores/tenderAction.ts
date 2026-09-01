import { computed, reactive, ref } from "vue";
import { defineStore } from "pinia";
import api from "@/api";

export type TenderAction = "monitor" | "favorite";
export type TenderActionState = { isMonitored: boolean; isCollected: boolean };

export const useTenderActionStore = defineStore("tenderAction", () => {
  const states = reactive<Record<string, TenderActionState>>({});
  const pending = ref<Record<string, boolean>>({});
  const monitorCount = computed(() => Object.values(states).filter((item) => item.isMonitored).length);

  function key(id: number | string) { return String(id); }
  function setState(id: number | string, value: Partial<TenderActionState>) {
    const current = states[key(id)] || { isMonitored: false, isCollected: false };
    states[key(id)] = { ...current, ...value };
  }
  function getState(id: number | string): TenderActionState { return states[key(id)] || { isMonitored: false, isCollected: false }; }
  function isPending(id: number | string, action?: TenderAction) { return Boolean(pending.value[`${key(id)}:${action || "all"}`]); }

  async function load(id: number | string, initial?: Partial<TenderActionState>) {
    if (initial) setState(id, initial);
    try {
      const response: any = await api.get(`/tenders/${id}/actions`, { silent: true });
      if (response?.data) setState(id, response.data);
    } catch { /* 旧服务未提供状态查询时保留默认状态 */ }
    return getState(id);
  }

  async function toggle(id: number | string, action: TenderAction) {
    const state = getState(id);
    const field = action === "monitor" ? "isMonitored" : "isCollected";
    const before = Boolean(state[field]);
    const requestKey = `${key(id)}:${action}`;
    pending.value[requestKey] = true;
    setState(id, { [field]: !before });
    try {
      const response: any = await api.post(`/tenders/${id}/${action}`);
      const active = Boolean(response?.data?.active);
      setState(id, { [field]: active });
      return active;
    } catch (error) {
      setState(id, { [field]: before });
      throw error;
    } finally {
      delete pending.value[requestKey];
    }
  }

  async function refreshSummary() {
    const response: any = await api.get('/tenders/actions/summary');
    return response?.data || { monitoredCount: 0, collectedCount: 0 };
  }
  function clear(id?: number | string) {
    if (id === undefined) Object.keys(states).forEach((item) => delete states[item]);
    else delete states[key(id)];
  }

  return { states, pending, monitorCount, getState, isPending, load, toggle, refreshSummary, clear };
});
