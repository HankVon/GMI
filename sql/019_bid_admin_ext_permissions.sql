-- ============================================================
-- 标讯后台管理扩展权限点 — 分类管理 / 订阅管理 / 统计 / 导入
-- 版本: v1.0.0
-- 说明: 在 013 基础上补齐 Phase2 模块权限(幂等); admin 角色自动关联。
-- ============================================================

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_category_mgt', '标讯分类管理', 'api', '/api/v1/admin/bids/*', NULL, 35
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_category_mgt');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_sub_mgt', '订阅管理', 'api', '/api/v1/admin/bids/subscriptions*', NULL, 36
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_sub_mgt');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_stats', '数据统计', 'api', '/api/v1/admin/bids/stats', NULL, 37
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_stats');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_import', '线索导入', 'api', '/api/v1/admin/bids/import-from-clues', NULL, 38
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_import');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_match', '实体匹配', 'api', '/api/v1/admin/bids/*match*', NULL, 39
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_match');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'bid_tag_manage', '标签管理', 'api', '/api/v1/admin/bid-tags/*', NULL, 40
  WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='bid_tag_manage');

-- admin 角色自动关联扩展权限(幂等)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p ON p.code IN ('bid_category_mgt','bid_sub_mgt','bid_stats','bid_import','bid_match','bid_tag_manage')
  AND p.is_deleted = 0
WHERE r.code = 'admin'
  AND NOT EXISTS (
      SELECT 1 FROM sys_role_permission rp
      WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
