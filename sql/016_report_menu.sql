-- ============================================================
-- 报表中心菜单权限 — 自定义报表(维度统计+导出)
-- 版本: v1.0.0
-- 说明: 幂等补齐 menu 权限并关联到 admin 与存量业务角色
-- ============================================================

-- 1. 菜单权限(挂到 menu_workspace 顶层下)
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_workspace_reports', '报表中心', 'menu', '/workspace/reports', id, 11
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_workspace_reports');

-- 2. admin 角色全量关联
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p ON p.resource_type = 'menu' AND p.is_deleted = 0
WHERE r.code = 'admin' AND p.code = 'menu_workspace_reports'
  AND NOT EXISTS (
      SELECT 1 FROM sys_role_permission rp
      WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- 3. 存量业务角色默认可见(与 013 策略一致)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p ON p.resource_type = 'menu' AND p.is_deleted = 0
WHERE r.code IN ('viewer', 'project_mgr', 'member') AND p.code = 'menu_workspace_reports'
  AND NOT EXISTS (
      SELECT 1 FROM sys_role_permission rp
      WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
