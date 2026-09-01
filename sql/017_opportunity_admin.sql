-- 商机管理后台权限注册(幂等)
-- 页面: 商机管理 / 策展标签管理 / 商机订阅(共用 menu_intel_opportunities 菜单)
-- 写操作: api_opportunity_crud(商机CRUD/标签/同步), api_opportunity_subscription(订阅管理)
USE ssm;

-- 1. 菜单权限(挂到 menu_workspace 顶层下, 与 menu_intel_* 同级)
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_intel_opportunities', '商机管理', 'menu', '/workspace/opportunities', id, 11
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_intel_opportunities');

-- 2. API 权限
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'api_opportunity_crud', '商机CRUD', 'api', '/api/v1/opportunities/*', NULL, 20
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='api_opportunity_crud');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'api_opportunity_subscription', '商机订阅管理', 'api', '/api/v1/opportunities/subscriptions/*', NULL, 21
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='api_opportunity_subscription');

-- 3. 角色授权
-- admin 角色: 全量授权(含新权限)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r, sys_permission p
WHERE r.code = 'admin'
  AND p.code IN ('menu_intel_opportunities', 'api_opportunity_crud', 'api_opportunity_subscription')
  AND NOT EXISTS (
    SELECT 1 FROM sys_role_permission rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- viewer/project_mgr/member: 仅授菜单(只读浏览, 无写操作权限)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r, sys_permission p
WHERE r.code IN ('viewer', 'project_mgr', 'member')
  AND p.code = 'menu_intel_opportunities'
  AND NOT EXISTS (
    SELECT 1 FROM sys_role_permission rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
