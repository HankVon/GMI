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

// 响应拦截：统一错误处理
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
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
    ElMessage.error(msg);
    if (err.response?.status === 401) {
      localStorage.removeItem("ssm_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;
