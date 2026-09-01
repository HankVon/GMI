// 项目商机后台管理 API(登录态, 自动附加 JWT)
import api from "@/api";
import type { OpportunityItem } from "@/api/opportunities";

export interface OpportunityDetail extends OpportunityItem {
  ownerScale?: string | null;
  unitRole?: string | null;
  unitName?: string | null;
  bodyExcerpt?: string | null;
  source?: string | null;
  publishedAt?: string | null;
  vipOnly?: {
    contactSummary?: string | null;
    followupLog?: string | null;
  };
}

export interface OpportunityVersionItem {
  id: number;
  version: string;
  changeSummary?: string | null;
  operator?: string | null;
  releasedAt?: string | null;
}

export interface OpportunityTagDefAdmin {
  id: number;
  code: string;
  label: string;
  kind: 'hot_field' | 'hot_project';
  isNew: boolean;
  sortOrder?: number;
}

export interface SubscriptionItem {
  id: number;
  name: string;
  condition: Record<string, unknown>;
  enabled: boolean;
  lastRunAt?: string | null;
  lastMatchCount?: number;
  updatedAt?: string | null;
}

export interface OpportunityAdminPayload {
  project_name: string;
  owner_name: string;
  owner_type?: string | null;
  owner_scale?: string | null;
  amount_wan?: number | null;
  stage?: string | null;
  region_province?: string | null;
  region_city?: string | null;
  project_type?: string | null;
  unit_role?: string | null;
  unit_name?: string | null;
  body_excerpt?: string | null;
  contact_summary?: string | null;
  followup_log?: string | null;
  dataset_type?: 'project' | 'proposed' | 'landtrade';
  tag_ids?: number[];
  change_summary?: string | null;
}

// ── 商机 CRUD ──
export function searchOpportunitiesAdmin(payload: Record<string, unknown>) {
  return api.post('/opportunities/search', payload);
}

export function fetchOpportunityDetail(id: number) {
  return api.get<{ success: boolean; data: OpportunityDetail }>(`/opportunities/${id}`);
}

export function createOpportunity(payload: OpportunityAdminPayload) {
  return api.post<{ success: boolean; data: { id: number } }>('/opportunities', payload);
}

export function updateOpportunity(id: number, payload: OpportunityAdminPayload) {
  return api.put<{ success: boolean; data: { id: number; currentVersion: string; changeSummary: string } }>(
    `/opportunities/${id}`,
    payload,
  );
}

export function deleteOpportunity(id: number) {
  return api.delete<{ success: boolean; data: { id: number } }>(`/opportunities/${id}`);
}

export function fetchOpportunityVersions(id: number) {
  return api.get<{ success: boolean; data: OpportunityVersionItem[] }>(`/opportunities/${id}/versions`);
}

export function syncOpportunitiesFromIntents() {
  return api.post<{ success: boolean; data: { scanned: number; created: number; skipped: number } }>(
    '/opportunities/sync-from-intents',
  );
}

export function exportOpportunities(params: Record<string, unknown>) {
  return api.get('/opportunities/export', { params, responseType: 'blob' });
}

// ── 标签字典管理 ──
export function listTagDefsAdmin() {
  return api.get<{ success: boolean; data: OpportunityTagDefAdmin[] }>('/opportunities/tags');
}

export function createTagDef(payload: { code: string; label: string; kind: string; is_new: boolean; sort_order?: number }) {
  return api.post('/opportunities/tags', payload);
}

export function updateTagDef(id: number, payload: { label?: string; kind?: string; is_new?: boolean; sort_order?: number }) {
  return api.put(`/opportunities/tags/${id}`, payload);
}

export function deleteTagDef(id: number) {
  return api.delete(`/opportunities/tags/${id}`);
}

// ── 订阅管理 ──
export function listOpportunitySubscriptions() {
  return api.get<{ success: boolean; data: SubscriptionItem[] }>('/opportunities/subscriptions');
}

export function createOpportunitySubscription(payload: { name: string; condition: Record<string, unknown> }) {
  return api.post<{ success: boolean; data: { id: number; name: string } }>('/opportunities/subscriptions', payload);
}

export function toggleOpportunitySubscription(id: number, enabled: boolean) {
  return api.put(`/opportunities/subscriptions/${id}`, { enabled });
}

export function deleteOpportunitySubscription(id: number) {
  return api.delete(`/opportunities/subscriptions/${id}`);
}
