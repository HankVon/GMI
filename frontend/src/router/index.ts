    import { createRouter, createWebHistory } from "vue-router";
import { useUserStore } from "@/stores/user";

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: (_to, _from, savedPosition) => {
    // 返回(back/forward)时恢复滚动位置, 新开页面则回顶部
    if (savedPosition) return savedPosition;
    return { top: 0 };
  },
  routes: [
    {
      path: "/login",
      name: "Login",
      component: () => import("@/views/Login.vue"),
      // site: 走前台裸渲染分支(无后台侧边栏), 登录页全屏展示; 守卫对 /login 特殊放行
      meta: { title: "登录", site: true },
    },
    // 域名根路径直接进入前台(前台需登录, 未登录会跳登录页)
    {
      path: "/",
      redirect: "/site",
    },
    // 业务管理(默认落地页 → 项目管理)
    {
      path: "/workspace",
      redirect: "/workspace/projects",
      meta: { title: "项目管理" },
    },
    {
      path: "/workspace/network/:id",
      name: "NetworkPath",
      component: () => import("@/views/workspace/NetworkPath.vue"),
      meta: { title: "人脉路径", permission: "menu_workspace_persons" },
    },
    {
      path: "/workspace/web-clues",
      name: "WebClue",
      component: () => import("@/views/workspace/WebClue.vue"),
      meta: { title: "网页线索", permission: "menu_workspace_web_clues" },
    },
    {
      path: "/workspace/web-clues/:id",
      name: "WebClueDetail",
      component: () => import("@/views/workspace/WebClueDetail.vue"),
      meta: { title: "线索详情", permission: "menu_workspace_web_clues" },
    },
    {
      path: "/workspace/data-sources",
      name: "DataSourceCenter",
      component: () => import("@/views/workspace/DataSourceCenter.vue"),
      meta: { title: "统一数据源管理中心", permission: "menu_workspace_web_clues" },
    },
    {
      path: "/workspace/intelligence",
      name: "Intelligence",
      component: () => import("@/views/workspace/IntelligenceHub.vue"),
      meta: { title: "行业情报", permission: "menu_intel_intelligence" },
    },
    // 组合查询 → 行业情报(高级检索) 宿主页
    {
      path: "/workspace/combined-query",
      name: "CombinedQueryLegacy",
      redirect: "/workspace/intelligence?tab=advanced",
    },
    {
      path: "/workspace/pipeline",
      name: "DataPipeline",
      component: () => import("@/views/workspace/DataPipeline.vue"),
      meta: { title: "数据流水线", permission: "menu_intel_pipeline" },
    },
    {
      path: "/workspace/intents",
      name: "IntentList",
      component: () => import("@/views/workspace/IntentList.vue"),
      meta: { title: "意向信息", permission: "menu_intel_intents" },
    },
    {
      path: "/workspace/bids-admin",
      name: "BidAdmin",
      component: () => import("@/views/workspace/BidManagement.vue"),
      meta: { title: "标讯管理", permission: "menu_bid_admin" },
    },
    {
      path: "/workspace/attachment-gaps",
      name: "AttachmentGapBoard",
      component: () => import("@/views/workspace/AttachmentGapBoard.vue"),
      meta: { title: "附件缺口看板", permission: "menu_bid_admin" },
    },
    // 情报中心 · 情报管理(录入/编辑/审核/发布, 兼容老角色以 menu_intel_intents 访问)
    {
      path: "/workspace/intent-admin",
      name: "IntentAdmin",
      component: () => import("@/views/workspace/IntentAdmin.vue"),
      meta: { title: "情报管理", permission: "menu_intel_intents" },
    },
    {
      path: "/workspace/intent-admin/edit",
      name: "IntentAdminCreate",
      component: () => import("@/views/workspace/IntentAdminEdit.vue"),
      meta: { title: "录入情报", permission: "menu_intel_intents" },
    },
    {
      path: "/workspace/intent-admin/edit/:id",
      name: "IntentAdminEdit",
      component: () => import("@/views/workspace/IntentAdminEdit.vue"),
      meta: { title: "编辑情报", permission: "menu_intel_intents" },
    },
    {
      path: "/workspace/intent-dashboard",
      name: "IntentDashboardLegacy",
      redirect: "/dashboard?tab=intent",
    },
    {
      path: "/workspace/opportunities",
      name: "OpportunityList",
      component: () => import("@/views/workspace/OpportunityList.vue"),
      meta: { title: "商机管理", permission: "menu_intel_opportunities" },
    },
    {
      path: "/workspace/opportunity-tags",
      name: "OpportunityTagManage",
      component: () => import("@/views/workspace/OpportunityTagManage.vue"),
      meta: { title: "策展标签管理", permission: "menu_intel_opportunities" },
    },
    // 营销智能体(合并宿主页: 总览/内容工厂/GEO 监测)
    {
      path: "/workspace/marketing",
      name: "Marketing",
      component: () => import("@/views/workspace/MarketingHub.vue"),
      meta: { title: "营销智能体", permission: "menu_mk_marketing" },
    },
    {
      path: "/workspace/geo",
      name: "GeoMonitorLegacy",
      redirect: "/workspace/marketing?tab=geo",
    },
    {
      path: "/workspace/content",
      name: "ContentFactoryLegacy",
      redirect: "/workspace/marketing?tab=content",
    },
    {
      path: "/me",
      name: "MeProfile",
      component: () => import("@/views/MeProfile.vue"),
      meta: { title: "我的信息" },
    },
    {
      path: "/workspace/projects",
      name: "ProjectList",
      component: () => import("@/views/workspace/ProjectList.vue"),
      meta: { title: "项目管理", permission: "menu_workspace_projects" },
    },
    {
      path: "/workspace/projects/:id",
      name: "ProjectDetail",
      component: () => import("@/views/workspace/ProjectDetail.vue"),
      meta: { title: "项目360°", permission: "menu_workspace_projects" },
    },
    {
      path: "/workspace/persons",
      name: "PersonList",
      component: () => import("@/views/workspace/PersonList.vue"),
      meta: { title: "人员管理", permission: "menu_workspace_persons" },
    },
    {
      path: "/workspace/persons/:id",
      name: "PersonProfile",
      component: () => import("@/views/workspace/PersonProfile.vue"),
      meta: { title: "人员主页", permission: "menu_workspace_persons" },
    },
    {
      path: "/workspace/companies",
      name: "CompanyList",
      component: () => import("@/views/workspace/CompanyList.vue"),
      meta: { title: "单位管理", permission: "menu_workspace_companies" },
    },
    {
      path: "/workspace/companies/:id",
      name: "CompanyDetail",
      component: () => import("@/views/workspace/CompanyDetail.vue"),
      meta: { title: "单位360°", permission: "menu_workspace_companies" },
    },
    // 标讯中心 → 标讯管理(浏览检索) 宿主页
    {
      path: "/workspace/bid-center",
      name: "BidCenterLegacy",
      redirect: "/workspace/bids-admin?tab=center",
    },
    // 管理后台
    {
      path: "/admin/cms",
      name: "CmsManager",
      component: () => import("@/views/admin/CmsManager.vue"),
      meta: { title: "首页配置", permission: "menu_cms_home" },
    },
    {
      path: "/admin/fields",
      name: "MetadataManager",
      component: () => import("@/views/admin/MetadataManager.vue"),
      meta: { title: "元数据配置", permission: "menu_field_mgt" },
    },
    {
      path: "/admin/options",
      name: "OptionManagerLegacy",
      redirect: "/admin/fields?tab=options",
    },
    {
      path: "/admin/rbac",
      name: "RbacManager",
      component: () => import("@/views/admin/RbacManager.vue"),
      meta: { title: "角色权限", permission: "menu_rbac" },
    },
    {
      path: "/admin/audit",
      name: "AuditLog",
      component: () => import("@/views/admin/AuditLog.vue"),
      meta: { title: "审计日志", permission: "menu_audit" },
    },
    // 统计中心(经营看板 + 情报看板)
    {
      path: "/dashboard",
      name: "Dashboard",
      component: () => import("@/views/workspace/StatisticsHub.vue"),
      meta: { title: "统计中心", permission: "menu_dashboard" },
    },
    // 报表中心(多维度聚合统计, 后端仅需登录)
    {
      path: "/workspace/reports",
      name: "ReportsCenter",
      component: () => import("@/views/workspace/ReportsCenter.vue"),
      meta: { title: "报表中心", permission: "menu_dashboard" },
    },
    // 无权限提示页
    {
      path: "/403",
      name: "Forbidden",
      component: () => import("@/views/Forbidden.vue"),
      meta: { title: "无访问权限" },
    },
    // 404 兜底
    {
      path: "/:pathMatch(.*)*",
      name: "NotFound",
      component: () => import("@/views/NotFound.vue"),
      meta: { title: "页面不存在" },
    },
    // ===== 前台官网(全部需登录, 走前台 SiteLayout 框架) =====
    {
      path: "/site",
      name: "SiteHome",
      component: () => import("@/views/site/Home.vue"),
      meta: { title: "GMI 数据平台", site: true },
    },
    {
      path: "/site/solutions",
      name: "SiteSolutions",
      component: () => import("@/views/site/Solutions.vue"),
      meta: { title: "解决方案", site: true },
    },
    {
      path: "/site/about",
      name: "SiteAbout",
      component: () => import("@/views/site/About.vue"),
      meta: { title: "关于我们", site: true },
    },
    {
      path: "/site/contact",
      name: "SiteContact",
      component: () => import("@/views/site/Contact.vue"),
      meta: { title: "联系咨询", site: true },
    },
    {
      path: "/site/intelligence",
      name: "SiteIntelligence",
      component: () => import("@/views/site/Intelligence.vue"),
      meta: { title: "情报动态", site: true },
    },
    {
      path: "/site/content/:id",
      name: "SiteContentDetail",
      component: () => import("@/views/site/ContentDetail.vue"),
      meta: { title: "内容详情", site: true },
    },
    {
      path: "/site/intelligence/:id",
      name: "SiteIntelligenceDetail",
      component: () => import("@/views/site/IntelligenceDetail.vue"),
      meta: { title: "意向详情", site: true },
    },
    // ===== 前台数据中心(替换原「数据展示」页: 五合一 tabs + 详情子页) =====
    // (首页已整合公开检索能力, 单独的 /site/public-search 已下线)
    /* legacy route removed: /site/public-search → PublicSearch.vue (integrated into Home.vue) */
    {
      path: "/site/data-center",
      component: () => import("@/components/site/PortalLayout.vue"),
      meta: { title: "数据中心", site: true },
      children: [
        {
          path: "",
          redirect: "/site/data-center/overview",
        },
        {
          path: "overview",
          name: "DataCenter",
          component: () => import("@/views/site/DataCenter.vue"),
          meta: { title: "标讯中心", site: true },
        },
        {
          path: "companies",
          name: "SiteSubQuery",
          component: () => import("@/views/site/DataCenter.vue"),
          meta: { title: "分项查询", site: true },
        },
        {
          path: "persons",
          name: "SitePersonList",
          component: () => import("@/views/site/DataCenter.vue"),
          meta: { title: "人员信息", site: true },
        },
        {
          path: "projects",
          name: "SiteProjectList",
          component: () => import("@/views/site/DataCenter.vue"),
          meta: { title: "项目库", site: true },
        },
        {
          path: "bids/:id",
          name: "DataCenterBidDetail",
          component: () => import("@/views/site/BidDetail.vue"),
          meta: { title: "标讯详情", site: true },
        },
        {
          path: "companies/:id",
          name: "DataCenterCompanyDetail",
          component: () => import("@/views/workspace/CompanyDetail.vue"),
          meta: { title: "单位360°", site: true },
        },
        {
          path: "persons/:id",
          name: "DataCenterPersonProfile",
          component: () => import("@/views/workspace/PersonProfile.vue"),
          meta: { title: "人员主页", site: true },
        },
        {
          path: "projects/:id",
          name: "DataCenterProjectDetail",
          component: () => import("@/views/workspace/ProjectDetail.vue"),
          meta: { title: "项目360°", site: true },
        },
        {
          path: "network/:id",
          name: "DataCenterNetworkPath",
          component: () => import("@/views/workspace/NetworkPath.vue"),
          meta: { title: "人脉路径", site: true },
        },
      ],
    },
    {
      path: "/site/account",
      component: () => import("@/components/site/AccountCenterLayout.vue"),
      meta: { title: "个人中心", site: true },
      children: [
        { path: "", name: "AccountHome", component: () => import("@/views/site/account/Index.vue"), meta: { title: "个人首页", site: true } },
        { path: "subscriptions", name: "AccountSubscriptions", component: () => import("@/views/site/account/Subscriptions.vue"), meta: { title: "我的订阅", site: true } },
        { path: "collection", name: "AccountCollection", component: () => import("@/views/site/account/AccountCollection.vue"), meta: { title: "我的收藏", site: true } },
        { path: "monitor", name: "AccountMonitor", component: () => import("@/views/site/account/AccountMonitor.vue"), meta: { title: "我的监控", site: true } },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/site",
    },
  ],
});

// 路由守卫：全站需登录(除登录页本身), 未登录带 redirect 跳登录页, 登录后回跳;
// 页面级权限: 路由带 meta.permission 时校验当前用户权限, 无权则跳 403。
router.beforeEach(async (to, _from, next) => {
  if (to.path === "/login") return next();
  // 匿名公开页(如公开检索)无需登录
  if (to.meta && (to.meta as Record<string, unknown>).public) return next();

  const token = localStorage.getItem("ssm_token");
  if (!token) {
    return next({ path: "/login", query: { redirect: to.fullPath } });
  }

  // 在路由层访问 pinia setup store: 顶层无实例时 TS 类型退化, 用 any 桥接
  const userStore = useUserStore() as any;
  // 刷新后 store 无权限数据 → 从 /auth/me 恢复一次
  if (!userStore.permissions.length) {
    try {
      await userStore.loadMe();
    } catch {
      userStore.logout();
      return next({ path: "/login", query: { redirect: to.fullPath } });
    }
  }

  // 后台布局区域(/workspace、/admin、/dashboard): 必须具备任一后台菜单权限,
  // 防止前台客户账号手输 URL 直接进入后台(页面级 permission 只是更细一层)。
  const isAdminArea = ["/workspace", "/admin", "/dashboard"].some((p) => to.path.startsWith(p));
  if (isAdminArea && !userStore.permissions.some((p: string) => p.startsWith("menu_"))) {
    return next({ path: "/403", replace: true });
  }

  const perm = (to.meta as any)?.permission as string | undefined;
  if (perm && !userStore.hasPermission(perm)) {
    return next({ path: "/403", replace: true });
  }
  next();
});

export default router;
