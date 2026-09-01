import api from "@/api";

/**
 * 静态只读配置接口的浏览器端缓存。
 *
 * 背景: 系统走 Cloudflare 免费隧道访问, 每个 API 请求有固定 ~1.2s 的链路 RTT。
 * 类别/阶段/动态表单等配置几乎不变, 但列表页/详情页反复请求, 造成大量重复的 1.2s 往返。
 * 这里对这些只读接口做 module 级缓存: 首次请求一次, 之后所有页面直接复用内存结果。
 */
const _cache = new Map<string, { ts: number; data: any }>();
// 缓存 TTL: 配置类数据 10 分钟
const TTL = 10 * 60 * 1000;

/**
 * 对只读配置接口做带 TTL 的缓存请求。
 * @param url 接口路径(如 /option-sets/project_category/items)
 */
export async function cachedConfig<T = any>(url: string): Promise<T> {
  const hit = _cache.get(url);
  if (hit && Date.now() - hit.ts < TTL) {
    return hit.data as T;
  }
  const res: any = await api.get(url);
  _cache.set(url, { ts: Date.now(), data: res });
  return res as T;
}

/** 主动失效某个缓存(配置变更后调用)。 */
export function invalidateConfig(url?: string) {
  if (url) {
    _cache.delete(url);
  } else {
    _cache.clear();
  }
}
