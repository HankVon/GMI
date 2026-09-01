import axios from "axios";

// 对外官网专用实例: 不附加 token, 不在 401 时强制跳转登录页
// public 接口本身无需鉴权, 此实例仅用于官网展示真实聚合数据
const siteApi = axios.create({
  baseURL: "/api/v1",
  timeout: 15000,
});

siteApi.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err),
);

export interface OverviewData {
  totals: {
    bid_notices: number;
    companies: number;
    intents: number;
    web_clues: number;
    persons: number;
    projects: number;
  };
  region_top: { province: string; count: number }[];
  type_dist: { name: string; value: number }[];
  monthly_trend: { month: string; count: number }[];
  province_count: number;
  updated_at: string;
}

export interface IntentItem {
  id: number;
  title: string;
  dept: string | null;
  region: string | null;
  province: string | null;
  project_type: string | null;
  industry: string | null;
  amount_level: string;
  published_at: string | null;
  status: string | null;
  keywords: string[];
  contact?: string | null;
  body_excerpt?: string | null;
  url?: string | null;
  opp_id?: number | null;
  opp_version?: string | null;
  ai: { heat: number; coop_prob: number; advice: string };
}

export interface IntentAttachment {
  id: number;
  file_name: string;
  remote_url: string | null;
  file_size: number;
  download_url: string;
  preview_url: string;
}

// 拉取某意向的公告附件列表
export async function fetchIntentAttachments(intentId: number): Promise<IntentAttachment[]> {
  try {
    const res: any = await siteApi.get(`/public/intent/${intentId}/attachments`);
    return res?.data ?? [];
  } catch (e) {
    return [];
  }
}

export interface AttachmentTable {
  file_name: string;
  headers: string[];
  rows: string[][];
}

// 解析公告附件中的 Excel -> 表头 + 数据行(后端原样解析, 不推断补全, 无值即空串)
export async function fetchIntentAttachmentTable(
  intentId: number,
  attachmentId: number,
): Promise<AttachmentTable | null> {
  try {
    const res: any = await siteApi.get(`/public/intent/${intentId}/attachments/${attachmentId}/table`);
    return res?.data ?? null;
  } catch (e) {
    return null;
  }
}

export interface GraphNode { id: string; name: string; type: string; degree: number; }
export interface GraphLink { source: string; target: string; rel: string; weight: number; }
export interface IntelligenceData {
  intents: IntentItem[];
  graph: { nodes: GraphNode[]; links: GraphLink[] };
  edge_total: number;
  note: string;
  updated_at: string;
}

// 拉取平台脱敏概览(真实数据)
export async function fetchOverview(): Promise<OverviewData | null> {
  try {
    const res: any = await siteApi.get("/public/overview");
    return res?.data ?? null;
  } catch (e) {
    return null;
  }
}

export interface CmsBlockItem {
  id: number;
  item_key: string | null;
  title: string;
  subtitle: string | null;
  icon: string | null;
  link: string | null;
  meta: Record<string, any>;
  enabled: number;
  sort_order: number;
}

export interface CmsBlock {
  id: number;
  block_key: string;
  title: string;
  description: string | null;
  enabled: number;
  sort_order: number;
  extra: Record<string, any>;
  items: CmsBlockItem[];
}

export interface HomeConfigData {
  page: string;
  blocks: Record<string, CmsBlock>;
  order: string[];
}

// 拉取前台页面内容配置(后台「内容配置中心」按页面维护; 未配置时前端回退内置静态内容)
export async function fetchHomeConfig(page = "home"): Promise<HomeConfigData | null> {
  try {
    const res: any = await siteApi.get("/public/home-config", { params: { page } });
    return res?.data ?? null;
  } catch (e) {
    return null;
  }
}

// 拉取情报动态(真实数据骨架 + 脱敏图谱 + 规则化 AI 摘要)
export async function fetchIntelligence(limit = 50): Promise<IntelligenceData | null> {
  try {
    const res: any = await siteApi.get("/public/intelligence", { params: { limit } });
    return res?.data ?? null;
  } catch (e) {
    return null;
  }
}

// 按 id 直取单条已发布情报(详情页首选)。
// 早期详情页依赖列表(limit 上限 50)再按 id 查找, 发布时间较早的情报会漏掉而显示"不存在"。
// 此接口按 id 直取, 未发布/已删除/不存在均返回 404, 由调用方回退到列表或显示空态。
export async function fetchPublicIntent(intentId: number): Promise<IntentItem | null> {
  try {
    const res: any = await siteApi.get(`/public/intent/${intentId}`);
    return res?.data ?? null;
  } catch (e) {
    return null;
  }
}

export interface IntentAiResult {
  status: string;
  data: {
    source: "llm" | "rule";
    model?: string;
    analysis: {
      summary: string;
      heat: number;
      coop_prob: number;
      orgs: string[];
      persons_hint: string;
      network_path: string;
      advice: string[];
      opportunities: string[];
    };
    note: string;
  } | null;
  error?: string;
}

// 提交单条意向的 LLM 深度研判任务(后端异步生成, 弱算力下较慢)
export async function submitIntentAi(intentId: number): Promise<string | null> {
  try {
    const res: any = await siteApi.post("/public/intent-ai", { intent_id: intentId });
    return res?.task_id ?? null;
  } catch (e) {
    return null;
  }
}

// 轮询研判结果
export async function pollIntentAi(taskId: string): Promise<IntentAiResult | null> {
  try {
    const res: any = await siteApi.get(`/public/intent-ai/${taskId}`);
    return res as IntentAiResult;
  } catch (e) {
    return null;
  }
}

export interface CachedIntentAi {
  found: boolean;
  data?: {
    source: "llm" | "rule";
    model?: string;
    analysis: IntentAiResult["data"]["analysis"];
    note: string;
    updated_at: string | null;
  };
}

// 读取该意向已缓存的分析结果(优先展示, 避免重复生成)
export async function fetchCachedIntentAi(intentId: number): Promise<CachedIntentAi | null> {
  try {
    const res: any = await siteApi.get(`/public/intent-ai/cached/${intentId}`);
    return res as CachedIntentAi;
  } catch (e) {
    return null;
  }
}

export default siteApi;
