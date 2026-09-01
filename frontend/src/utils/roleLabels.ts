/**
 * 角色中英文映射(统一, 供公司角色/成员角色展示复用)。
 *
 * 数据库 project_company.role / project_member.role 存英文枚举(owner/constructor/
 * partner/manager 等), 前端展示必须映射为中文, 否则界面出现英文。
 * 历史原因: 各页面曾各自定义映射表且键名不一致(如 construction vs constructor),
 * 导致部分页面缺键回退显示英文。此处统一并集中维护。
 */

/** 项目参与单位角色(project_company.role) → 中文 */
export const COMPANY_ROLE_LABEL: Record<string, string> = {
  // 数据库实际存值
  owner: "业主",
  constructor: "施工",
  partner: "合作伙伴",
  builder: "建设单位",
  // 兼容其他可能出现的取值
  design: "设计",
  designer: "设计",
  supervisor: "监理",
  construction: "施工",
  investor: "投资方",
  client: "业主",
  contractor: "施工",
  supplier: "供应商",
  other: "其他",
};

/** 项目成员角色(project_member.role) → 中文 */
export const MEMBER_ROLE_LABEL: Record<string, string> = {
  manager: "项目联系人",
  member: "成员",
  observer: "观察者",
  // 中文存值原样返回(兜底)
};

/** 单位角色展示: 未知值回退原样 */
export function companyRoleLabel(role?: string | null): string {
  if (!role) return "";
  return COMPANY_ROLE_LABEL[role] || role;
}

/** 成员角色展示: 未知值回退原样(兼容中文存值) */
export function roleLabel(role?: string | null): string {
  if (!role) return "";
  return MEMBER_ROLE_LABEL[role] || role;
}
