/**
 * 悬浮客服工具条 —— 全局配置开关(配置驱动, 禁止硬编码删除/保留)。
 *
 * 治理背景(架构报告): 同一客服能力在不同子产品呈现「挂载 / 冗余挂载 / 缺席」三种
 * 不一致状态。此处统一收敛为按子产品(product)声明的配置:
 *   - 页面通过 useRoute().meta.product 或 path 前缀取得当前子产品标识;
 *   - 组件只需按 floatToolsEnabledFor(product) 条件渲染, 切换配置即可统一开关,
 *     避免"某个子产品多挂一个悬浮工具条"的漂移问题。
 *
 * 覆盖优先级: 环境变量 VITE_SITE_FLOAT_TOOLS=true|false > 子产品配置 > 默认(开启)。
 */

export interface ProductFloatToolsConfig {
  /** 是否挂载悬浮客服工具条 */
  enabled: boolean;
}

const DEFAULT_CONFIG: ProductFloatToolsConfig = { enabled: true };

/** 按子产品标识声明的挂载配置(标识 = 路由 meta.product) */
const PRODUCT_FLOAT_TOOLS: Record<string, ProductFloatToolsConfig> = {
  // 官网主站(白色 Shell): 正常挂载
  default: { enabled: true },
  // 商机子产品(深蓝独立 Shell): 工具页去干扰, 默认缺席
  opportunity: { enabled: false },
};

export function floatToolsEnabledFor(product?: string): boolean {
  const env = (import.meta.env?.VITE_SITE_FLOAT_TOOLS as string | undefined)?.trim();
  if (env) return env === "true";
  const cfg = (product && PRODUCT_FLOAT_TOOLS[product]) || PRODUCT_FLOAT_TOOLS.default || DEFAULT_CONFIG;
  return cfg.enabled;
}
