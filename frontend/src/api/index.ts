import axios from "axios";
import { ElMessage } from "element-plus";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

// 请求拦截：自动附加 JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ssm_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 单个请求可携带 { silent: true } 关闭全局错误提示(用于后台轮询/静默回退)。
function isSilent(config?: any): boolean {
  return Boolean(config && config.silent);
}

// 响应拦截：统一响应解包层(治本"假成功")
//   后端统一信封 { success, data, msg }。success===false 视为业务失败,
//   一律拒绝并在非 silent 时弹错, 使任何调用方都不可能把失败当成功处理。
api.interceptors.response.use(
  (res) => {
    const body = res.data;
    if (body && typeof body === "object" && "success" in body) {
      if (body.success === false) {
        const msg = body.msg || body.detail || "请求失败，请稍后重试";
        if (!isSilent(res.config)) ElMessage.error(msg);
        return Promise.reject(new Error(msg));
      }
      return body; // 调用方通过 body.data 取数据
    }
    return body;
  },
  (err) => {
    // 401: 统一走登录流程。不弹错误(避免登录页刷屏), 已在登录页不再跳转
    // (防止「轮询 401 → 整页刷新到 /login → 轮询继续 401」的无限刷新循环)。
    if (err.response?.status === 401) {
      localStorage.removeItem("ssm_token");
      if (window.location.pathname !== "/login") {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search);
        // replace: 不留历史记录, 避免浏览器后退堆叠
        window.location.replace(`/login?redirect=${redirect}`);
      }
      return Promise.reject(err);
    }

    const detail = err.response?.data?.detail;
    let msg = "";
    if (typeof detail === "string") {
      msg = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI 422 校验错误: detail 是数组, 取第一条人可读信息
      const first = detail[0];
      const loc = first?.loc?.filter((p: string | number) => typeof p === "string").join(".");
      msg = loc ? `参数 ${loc} 无效: ${first?.msg ?? ""}` : (first?.msg ?? "请求参数校验失败");
    }
    // 兜底 axios 错误信息, 最后兜底通用中文提示
    if (!msg) {
      msg = err.message;
    }
    if (!msg) {
      msg = "请求失败，请稍后重试";
    }
    // 简化 axios 默认英文错误 ("Request failed with status code 500" → "请求失败 (HTTP 500)")
    const m = /^Request failed with status code (\d+)/i.exec(msg);
    if (m) {
      msg = `请求失败 (HTTP ${m[1]})`;
    }
    if (!isSilent(err.config)) ElMessage.error(msg);
    return Promise.reject(err);
  }
);

export default api;
