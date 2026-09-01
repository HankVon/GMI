-- ============================================================
-- 标讯后台管理权限点补齐 — 「指定哪些页面/接口能用」
-- 版本: v1.0.0
-- 说明: 标讯管理菜单 + API 权限点(幂等, 已存在则跳过);
--       admin 角色自动全量关联(保证超管全见)。
-- ============================================================

-- 1. 标讯管理菜单(挂到顶层菜单 menu_workspace 下)
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_bid_admin', '标讯管理', 'menu', '/workspace/bids-admin', id, 11
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_bid_admin');

-- 2. 标讯 API 权限点
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_view',    '标讯查看',   'api', '/api/v1/admin/bids/*', NULL, 30
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_view');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_create',  '标讯录入',   'api', '/api/v1/admin/bids/*', NULL, 31
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_create');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_edit',    '标讯编辑',   'api', '/api/v1/admin/bids/*', NULL, 32
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_edit');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_review',  '标讯审核',   'api', '/api/v1/admin/bids/*', NULL, 33
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_review');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_publish', '标讯发布',   'api', '/api/v1/admin/bids/*', NULL, 34
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_publish');

-- 3. admin 角色自动全量关联标讯菜单/API权限(幂等)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p ON p.code IN ('menu_bid_admin','bid_view','bid_create','bid_edit','bid_review','bid_publish')
  AND p.is_deleted = 0
WHERE r.code = 'admin'
  AND NOT EXISTS (
      SELECT 1 FROM sys_role_permission rp
      WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
