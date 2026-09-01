import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

/**
 * 业务页跳转前缀: 后台走 /workspace, 前台数据中心走 /site/data-center。
 * 供复用的后台组件在前台数据中心路由下保持站内跳转一致。
 */
export function useNavBase() {
  const route = useRoute();
  const router = useRouter();
  const base = computed(() => {
    return route.path.startsWith("/site/data-center") ? "/site/data-center" : "/workspace";
  });
  const navTo = (path: string) => `${base.value}${path}`;
  /**
   * 新标签页打开站内路由: 经 router.resolve 生成 href 后 window.open,
   * 保留 SPA 路由与路由守卫(鉴权基于 localStorage, 新标签自动生效)。
   */
  const navToNewTab = (path: string) => {
    const { href } = router.resolve(navTo(path));
    window.open(href, "_blank", "noopener");
  };
  return { base, navTo, navToNewTab };
}
