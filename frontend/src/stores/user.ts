import { defineStore } from "pinia";
import { ref } from "vue";
import api from "@/api";

/**
 * User Store — 认证状态 + 权限信息
 */
export const useUserStore = defineStore("user", () => {
  const token = ref(localStorage.getItem("ssm_token") || "");
  const username = ref("");
  const displayName = ref("");
  const roles = ref<string[]>([]);
  const permissions = ref<string[]>([]);
  const departmentId = ref<number | null>(null);

  async function login(user: string, pass: string) {
    const res: any = await api.post("/auth/login", { username: user, password: pass });
    token.value = res.access_token;
    localStorage.setItem("ssm_token", res.access_token);
    username.value = res.user.username;
    displayName.value = res.user.display_name;
    roles.value = res.user.roles || [];
    permissions.value = res.user.permissions || [];
    departmentId.value = res.user.department_id;
    return res;
  }

  function logout() {
    token.value = "";
    username.value = "";
    roles.value = [];
    permissions.value = [];
    localStorage.removeItem("ssm_token");
  }

  function hasPermission(code: string): boolean {
    return permissions.value.includes(code);
  }

  function hasAnyRole(...roleCodes: string[]): boolean {
    return roleCodes.some((r) => roles.value.includes(r));
  }

  /** 刷新页面后从 /auth/me 恢复权限(路由守卫/菜单渲染依赖) */
  async function loadMe() {
    const res: any = await api.get("/auth/me");
    username.value = res.username || "";
    displayName.value = res.display_name || "";
    roles.value = res.roles || [];
    permissions.value = res.permissions || [];
    departmentId.value = res.department_id ?? null;
    return res;
  }

  return { token, username, displayName, roles, permissions, departmentId, login, logout, loadMe, hasPermission, hasAnyRole };
});
