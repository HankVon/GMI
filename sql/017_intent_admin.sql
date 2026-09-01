-- ============================================================
-- 情报中心后台管理 菜单 + 权限点 种子(幂等, 重复执行安全)
-- 版本: v1.0.0
-- 说明:
--   1) 新增菜单 menu_intel_admin 挂在 menu_workspace 下
--   2) 注册情报管理细粒度权限点(intel_intelligence_*)
--   3) admin 角色自动关联全部(超管全见)
-- 兼容: 后端写操作接口以 menu_intel_intents 作为保底权限,
--        即使未执行本脚本, 已拥有 menu_intel_intents 的角色仍可操作。
-- ============================================================

-- 1. 菜单: 情报管理(/workspace/intent-admin)
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_intel_admin', '情报管理', 'menu', '/workspace/intent-admin', id, 12
FROM sys_permission WHERE code='menu_workspace'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_intel_admin');

-- 2. 权限点(挂到 menu_intel_admin 下, resource_type='permission')
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_intelligence_view', '情报-查看', 'permission', '', id, 1
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_intelligence_view');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_intelligence_create', '情报-录入', 'permission', '', id, 2
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_intelligence_create');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_intelligence_edit', '情报-编辑/删除', 'permission', '', id, 3
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_intelligence_edit');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_intelligence_review', '情报-审核', 'permission', '', id, 4
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_intelligence_review');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_intelligence_publish', '情报-发布/下架', 'permission', '', id, 5
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_intelligence_publish');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_intelligence_ai', '情报-AI研判', 'permission', '', id, 6
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_intelligence_ai');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_category_manage', '情报-分类管理', 'permission', '', id, 7
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_category_manage');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_tag_manage', '情报-标签管理', 'permission', '', id, 8
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_tag_manage');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_source_manage', '情报-来源管理', 'permission', '', id, 9
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_source_manage');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_contact_view', '情报-真实联系人查看', 'permission', '', id, 10
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_contact_view');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'intel_export', '情报-导出', 'permission', '', id, 11
FROM sys_permission WHERE code='menu_intel_admin'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='intel_export');

-- 3. 拥有「意向信息」权限的角色(admin/viewer 等)自动关联菜单 + 全部新权限点(幂等)
--    理由: 意向信息页是情报管理的前身, 能访问意向信息的角色即视为情报相关角色。
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p
  ON (p.code IN (
      'menu_intel_admin',
      'intel_intelligence_view', 'intel_intelligence_create', 'intel_intelligence_edit',
      'intel_intelligence_review', 'intel_intelligence_publish', 'intel_intelligence_ai',
      'intel_category_manage', 'intel_tag_manage', 'intel_source_manage',
      'intel_contact_view', 'intel_export'
  ))
WHERE (
      r.code = 'admin'
      OR r.id IN (
          SELECT rp2.role_id
          FROM sys_role_permission rp2
          JOIN sys_permission p2 ON p2.id = rp2.permission_id
          WHERE p2.code = 'menu_intel_intents' AND p2.is_deleted = 0
      )
  )
  AND NOT EXISTS (
      SELECT 1 FROM sys_role_permission rp
      WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
