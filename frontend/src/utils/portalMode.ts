import { computed } from "vue";
import { useRoute } from "vue-router";

/**
 * 前台数据中心模式: 当前路由位于 /site/data-center 下时返回 true。
 * 复用后台组件在「前台数据中心」中展示时, 用该标记隐藏管理类操作按钮,
 * 调整弹窗/布局以适配前台展示场景。
 */
export function usePortalMode() {
  const route = useRoute();
  const isPortal = computed(() => route.path.startsWith("/site/data-center"));
  return { isPortal };
}
