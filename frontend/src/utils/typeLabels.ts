/**
 * 业务/项目类型枚举 → 中文 统一映射
 *
 * 后端各爬取/导入管道把项目分类存为英文枚举(如 geo_survey),
 * 前端展示与下拉框必须经此映射转中文, 禁止直接显示原始英文值。
 * 无法命中时透传原值(兼容库中直接存中文的情况)。
 */

export const TYPE_LABELS: Record<string, string> = {
  geo_hazard: "地质灾害治理",
  geo_survey: "地质勘察/监测",
  eco_restoration: "生态修复",
  mining_rights: "矿业权",
  policy: "规划评估",
  transport: "交通",
  energy: "能源",
  municipal: "市政",
  water: "水利",
  education: "教育",
  healthcare: "医疗",
  infrastructure: "基础设施",
  real_estate: "房地产",
  agriculture: "农业",
  forestry: "林业",
  land_survey: "土地调查",
  map_service: "测绘服务",
};

/** 枚举值/中文值 → 展示中文 */
export function typeLabel(v?: string | null): string {
  if (!v) return "未分类";
  return TYPE_LABELS[v] || v;
}

/** 用于 el-tag type 的类型配色 */
export function typeColor(t?: string | null): string {
  const m: Record<string, string> = {
    transport: "primary",
    geo_hazard: "danger",
    geo_survey: "warning",
    eco_restoration: "success",
    mining_rights: "info",
    energy: "primary",
    municipal: "warning",
    water: "primary",
    education: "info",
    healthcare: "danger",
  };
  return m[t || ""] || "info";
}
