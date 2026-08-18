    import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "Login",
      component: () => import("@/views/Login.vue"),
      meta: { title: "登录" },
    },
    // 商业信息
    {
      path: "/workspace",
      redirect: "/workspace/business",
      meta: { title: "商业信息" },
    },
    {
      path: "/workspace/business",
      name: "BusinessInfoList",
      component: () => import("@/views/workspace/BusinessInfoList.vue"),
      meta: { title: "商业信息" },
    },
    {
      path: "/workspace/business/:id",
      name: "BusinessInfoDetail",
      component: () => import("@/views/workspace/BusinessInfoDetail.vue"),
      meta: { title: "商业信息详情" },
    },
    {
      path: "/workspace/network/:id",
      name: "NetworkPath",
      component: () => import("@/views/workspace/NetworkPath.vue"),
      meta: { title: "人脉路径" },
    },
    {
      path: "/workspace/web-clues",
      name: "WebClue",
      component: () => import("@/views/workspace/WebClue.vue"),
      meta: { title: "网页线索" },
    },
    {
      path: "/workspace/web-clues/:id",
      name: "WebClueDetail",
      component: () => import("@/views/workspace/WebClueDetail.vue"),
      meta: { title: "线索详情" },
    },
    {
      path: "/workspace/intelligence",
      name: "Intelligence",
      component: () => import("@/views/workspace/Intelligence.vue"),
      meta: { title: "行业情报" },
    },
    {
      path: "/workspace/pipeline",
      name: "DataPipeline",
      component: () => import("@/views/workspace/DataPipeline.vue"),
      meta: { title: "数据流水线" },
    },
    {
      path: "/workspace/intents",
      name: "IntentList",
      component: () => import("@/views/workspace/IntentList.vue"),
      meta: { title: "意向信息" },
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
      meta: { title: "项目管理" },
    },
    {
      path: "/workspace/projects/:id",
      name: "ProjectDetail",
      component: () => import("@/views/workspace/ProjectDetail.vue"),
      meta: { title: "项目360°" },
    },
    {
      path: "/workspace/persons",
      name: "PersonList",
      component: () => import("@/views/workspace/PersonList.vue"),
      meta: { title: "人员管理" },
    },
    {
      path: "/workspace/persons/:id",
      name: "PersonProfile",
      component: () => import("@/views/workspace/PersonProfile.vue"),
      meta: { title: "人员主页" },
    },
    {
      path: "/workspace/companies",
      name: "CompanyList",
      component: () => import("@/views/workspace/CompanyList.vue"),
      meta: { title: "单位管理" },
    },
    {
      path: "/workspace/companies/:id",
      name: "CompanyDetail",
      component: () => import("@/views/workspace/CompanyDetail.vue"),
      meta: { title: "单位360°" },
    },
    // 管理后台
    {
      path: "/admin/fields",
      name: "FieldManager",
      component: () => import("@/views/admin/FieldManager.vue"),
      meta: { title: "字段管理" },
    },
    {
      path: "/admin/options",
      name: "OptionManager",
      component: () => import("@/views/admin/OptionManager.vue"),
      meta: { title: "选项集管理" },
    },
    {
      path: "/admin/rbac",
      name: "RbacManager",
      component: () => import("@/views/admin/RbacManager.vue"),
      meta: { title: "角色权限" },
    },
    {
      path: "/admin/audit",
      name: "AuditLog",
      component: () => import("@/views/admin/AuditLog.vue"),
      meta: { title: "审计日志" },
    },
    // 数据看板（二期）
    {
      path: "/dashboard",
      name: "Dashboard",
      component: () => import("@/views/dashboard/Dashboard.vue"),
      meta: { title: "数据看板" },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/workspace/business",
    },
  ],
});

// 路由守卫：未登录跳转登录页
router.beforeEach(async (to, _from, next) => {
  if (to.path === "/login") return next();

  const token = localStorage.getItem("ssm_token");
  if (!token) {
    return next("/login");
  }
  next();
});

export default router;
