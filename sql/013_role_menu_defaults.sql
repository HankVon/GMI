-- ============================================================
-- 存量业务角色默认页面权限 — 平滑过渡, 避免部署后非超管被全部锁死
-- 版本: v1.0.0
-- 说明: viewer/project_mgr/member 默认可见全部业务页(workspace/intel/mk),
--       管理后台(/admin/*)仍只归 admin 角色。管理员可在「配置权限」里按需收紧。
-- ============================================================

INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p ON p.resource_type = 'menu' AND p.is_deleted = 0
WHERE r.code IN ('viewer', 'project_mgr', 'member')
  AND (p.code LIKE 'menu_workspace_%' OR p.code LIKE 'menu_intel_%' OR p.code LIKE 'menu_mk_%')
  AND NOT EXISTS (
      SELECT 1 FROM sys_role_permission rp
      WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
