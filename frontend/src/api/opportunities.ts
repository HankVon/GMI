// 商机数据公开接口(情报动态页公共访问, 无需登录)
import siteApi from '@/api/siteApi';
import type { PaginatedResponse } from '@/api/types';

export interface OpportunityTagDef {
  id: number;
  code: string;
  label: string;
  kind: 'hot_field' | 'hot_project';
  isNew: boolean;
}

export interface OpportunityItem {
  id: number;
  projectName: string;
  ownerName: string;
  ownerType?: string | null;
  ownerScale?: string | null;
  amountWan?: number | null;
  stage?: string | null;
  regionProvince?: string | null;
  regionCity?: string | null;
  projectType?: string | null;
  currentVersion?: string | null;
  datasetType: string;
  updatedAt?: string | null;
  tags: { label: string; code: string }[];
  intentId?: number | null;
}

export interface SearchPayload {
  tags?: number[];
  region_province?: string;
  region_city?: string;
  amount_min?: number;
  amount_max?: number;
  stage?: string;
  unit_role?: string;
  unit_name?: string;
  owner_type?: string;
  update_start?: string;
  update_end?: string;
  project_name?: string;
  project_type?: string;
  dataset_type: 'project' | 'proposed' | 'landtrade';
  page: number;
  page_size: number;
}

export function listOpportunityTags() {
  return siteApi.get<{ success: boolean; data: OpportunityTagDef[] }>('/public/opportunities/tags');
}

export function searchOpportunities(payload: SearchPayload) {
  return siteApi.post<PaginatedResponse<OpportunityItem>>('/public/opportunities/search', payload);
}