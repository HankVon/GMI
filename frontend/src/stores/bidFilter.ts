import { defineStore } from "pinia";
import { computed, ref } from "vue";

export type KeywordCondition = { value: string; operator: "AND" | "OR" };
export type BidFilterSnapshot = {
  keyword: string;
  province: string;
  noticeType: string;
  amountMin: string;
  amountMax: string;
  purchaserKeyword: string;
  supplierKeyword: string;
  onlyMatched: boolean;
  keywords: KeywordCondition[];
};

const defaultSnapshot = (): BidFilterSnapshot => ({ keyword: "", province: "", noticeType: "", amountMin: "", amountMax: "", purchaserKeyword: "", supplierKeyword: "", onlyMatched: false, keywords: [{ value: "", operator: "AND" }] });
const STORAGE_KEY = "gmi_bid_filter_snapshot";

export const useBidFilterStore = defineStore("bidFilter", () => {
  const state = ref<BidFilterSnapshot>(defaultSnapshot());
  const moreExpanded = ref(false);
  const savedName = ref("");
  const serialized = computed(() => JSON.stringify(state.value));

  function reset() { state.value = defaultSnapshot(); moreExpanded.value = false; }
  function addKeyword() { state.value.keywords.push({ value: "", operator: "AND" }); }
  function removeKeyword(index: number) { if (state.value.keywords.length > 1) state.value.keywords.splice(index, 1); }
  function setKeywordOperator(index: number, operator: "AND" | "OR") { if (state.value.keywords[index]) state.value.keywords[index].operator = operator; }
  function saveLocal(name = "默认筛选") { savedName.value = name; localStorage.setItem(`${STORAGE_KEY}:${name}`, serialized.value); localStorage.setItem(STORAGE_KEY, serialized.value); }
  function restoreLocal(name?: string) {
    try { const raw = localStorage.getItem(name ? `${STORAGE_KEY}:${name}` : STORAGE_KEY); if (raw) state.value = { ...defaultSnapshot(), ...JSON.parse(raw) }; } catch { reset(); }
  }
  function snapshot(): BidFilterSnapshot { return JSON.parse(serialized.value); }
  return { state, moreExpanded, savedName, serialized, reset, addKeyword, removeKeyword, setKeywordOperator, saveLocal, restoreLocal, snapshot };
});
