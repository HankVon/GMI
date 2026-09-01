-- ============================================================
-- 修复 012 脚本因客户端字符集造成的菜单名称双重编码乱码
-- 保留权限 ID 不变, 不影响已有角色-权限关联
-- ============================================================

UPDATE sys_permission SET name = '项目管理' WHERE code = 'menu_workspace_projects';
UPDATE sys_permission SET name = '人员管理' WHERE code = 'menu_workspace_persons';
UPDATE sys_permission SET name = '单位管理' WHERE code = 'menu_workspace_companies';
UPDATE sys_permission SET name = '网页线索' WHERE code = 'menu_workspace_web_clues';
UPDATE sys_permission SET name = '行业情报' WHERE code = 'menu_intel_intelligence';
UPDATE sys_permission SET name = '数据流水线' WHERE code = 'menu_intel_pipeline';
UPDATE sys_permission SET name = '意向信息' WHERE code = 'menu_intel_intents';
UPDATE sys_permission SET name = 'GEO 监测' WHERE code = 'menu_mk_geo';
UPDATE sys_permission SET name = '内容工厂' WHERE code = 'menu_mk_content';
UPDATE sys_permission SET name = '智能体总览' WHERE code = 'menu_mk_marketing';