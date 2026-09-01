-- ============================================================
-- 页面级权限(菜单权限)补齐 — 「指定哪些页面能看/不能看」
-- 版本: v1.0.0
-- 说明: 为每个后台业务页面补齐 menu 类型权限码(幂等, 已存在则跳过);
--       admin 角色自动全量关联全部菜单权限(保证超管可见所有页面)。
-- ============================================================

-- 1. 业务管理页(挂到顶层菜单 menu_workspace 下)
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_workspace_projects', '项目管理', 'menu', '/workspace/projects', id, 1
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_workspace_projects');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_workspace_persons', '人员管理', 'menu', '/workspace/persons', id, 2
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_workspace_persons');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_workspace_companies', '单位管理', 'menu', '/workspace/companies', id, 3
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_workspace_companies');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_workspace_web_clues', '网页线索', 'menu', '/workspace/web-clues', id, 4
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_workspace_web_clues');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_intel_intelligence', '行业情报', 'menu', '/workspace/intelligence', id, 5
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_intel_intelligence');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_intel_pipeline', '数据流水线', 'menu', '/workspace/pipeline', id, 6
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_intel_pipeline');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_intel_intents', '意向信息', 'menu', '/workspace/intents', id, 7
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_intel_intents');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_mk_geo', 'GEO 监测', 'menu', '/workspace/geo', id, 8
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_mk_geo');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_mk_content', '内容工厂', 'menu', '/workspace/content', id, 9
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_mk_content');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_mk_marketing', '智能体总览', 'menu', '/workspace/marketing', id, 10
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_mk_marketing');

-- 2. admin 角色自动全量关联所有菜单权限(幂等, 超管全见)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p ON p.resource_type = 'menu' AND p.is_deleted = 0
WHERE r.code = 'admin'
  AND NOT EXISTS (
      SELECT 1 FROM sys_role_permission rp
      WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
