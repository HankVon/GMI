-- 商机子产品 DDL + 种子数据(执行一次, 全部 IF NOT EXISTS 幂等)
USE ssm;

-- 1. subscription_task.product_type 扩展(已有表加列)
SET @col_exists := (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA='ssm' AND TABLE_NAME='subscription_task' AND COLUMN_NAME='product_type');
SET @ddl := IF(@col_exists=0,
  'ALTER TABLE subscription_task ADD COLUMN product_type VARCHAR(32) DEFAULT ''tender'' COMMENT ''tender/opportunity'' AFTER last_match_count',
  'SELECT ''subscription_task.product_type 已存在'' AS msg');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. 商机主表
CREATE TABLE IF NOT EXISTS opportunity (
  id BIGINT NOT NULL AUTO_INCREMENT,
  project_name VARCHAR(255) NOT NULL COMMENT '项目名称',
  owner_name VARCHAR(255) NOT NULL COMMENT '业主名称',
  owner_type VARCHAR(64) DEFAULT NULL COMMENT '业主类型',
  owner_scale VARCHAR(64) DEFAULT NULL COMMENT '业主规模',
  amount_wan BIGINT DEFAULT NULL COMMENT '投资金额(万元)',
  stage VARCHAR(64) DEFAULT NULL COMMENT '项目阶段',
  region_province VARCHAR(64) DEFAULT NULL COMMENT '省',
  region_city VARCHAR(64) DEFAULT NULL COMMENT '市',
  project_type VARCHAR(64) DEFAULT NULL COMMENT '项目类型',
  unit_role VARCHAR(64) DEFAULT NULL,
  unit_name VARCHAR(128) DEFAULT NULL,
  contact_summary TEXT COMMENT '关键联系人(VIP)',
  followup_log TEXT COMMENT '跟进记录(VIP)',
  body_excerpt TEXT,
  current_version VARCHAR(32) DEFAULT NULL COMMENT '当前版本号',
  dataset_type VARCHAR(32) DEFAULT 'project' COMMENT 'project/proposed/landTrade',
  source VARCHAR(128) DEFAULT NULL,
  is_deleted TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  published_at DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_dataset_updated (dataset_type, updated_at),
  KEY idx_owner_name (owner_name),
  KEY idx_amount (amount_wan)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目商机主表';

-- 3. 版本记录
CREATE TABLE IF NOT EXISTS opportunity_version (
  id BIGINT NOT NULL AUTO_INCREMENT,
  opportunity_id BIGINT NOT NULL,
  version VARCHAR(32) NOT NULL,
  change_summary TEXT,
  operator VARCHAR(64) DEFAULT NULL,
  released_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted TINYINT(1) DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_opp (opportunity_id, released_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商机版本历史';

-- 4. 标签字典
CREATE TABLE IF NOT EXISTS opportunity_tag_def (
  id BIGINT NOT NULL AUTO_INCREMENT,
  code VARCHAR(64) NOT NULL,
  label VARCHAR(64) NOT NULL,
  kind VARCHAR(32) DEFAULT 'hot_project',
  is_new TINYINT(1) DEFAULT 1,
  sort_order BIGINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted TINYINT(1) DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策展标签字典';

-- 5. 标签关联
CREATE TABLE IF NOT EXISTS opportunity_tag (
  id BIGINT NOT NULL AUTO_INCREMENT,
  opportunity_id BIGINT NOT NULL,
  tag_id BIGINT NOT NULL,
  tag_kind VARCHAR(32) DEFAULT 'hot_project',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted TINYINT(1) DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_opp_tag (opportunity_id, tag_id),
  KEY idx_tag (tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商机-标签关联';

-- 6. 业主主表
CREATE TABLE IF NOT EXISTS owner (
  id BIGINT NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  owner_type VARCHAR(64) DEFAULT NULL,
  owner_scale VARCHAR(64) DEFAULT NULL,
  province VARCHAR(64) DEFAULT NULL,
  city VARCHAR(64) DEFAULT NULL,
  industry VARCHAR(64) DEFAULT NULL,
  opportunity_count BIGINT DEFAULT 0,
  total_amount_wan BIGINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted TINYINT(1) DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='业主主表';

-- 7. 标签字典种子(幂等 INSERT IGNORE)
INSERT IGNORE INTO opportunity_tag_def (code, label, kind, is_new, sort_order) VALUES
 ('hot_field_urban',     '城市更新',     'hot_field',   1, 10),
 ('hot_field_lowalt',    '低空经济',     'hot_field',   1, 20),
 ('hot_field_ne',        '新能源',       'hot_field',   1, 30),
 ('hot_proj_private',    '大型民企项目', 'hot_project', 1, 10),
 ('hot_proj_foreign',    '外资项目',     'hot_project', 1, 20),
 ('hot_proj_land',       '土拍项目',     'hot_project', 1, 30),
 ('hot_proj_industrial', '产业园区',     'hot_project', 1, 40),
 ('hot_proj_warehouse',  '厂房仓储',     'hot_project', 1, 50),
 ('hot_proj_science',    '科创中心',     'hot_project', 1, 60),
 ('hot_proj_digital',    '数智中心',     'hot_project', 1, 70),
 ('hot_proj_water',      '水利水电',     'hot_project', 1, 80),
 ('hot_proj_farmland',   '高标准农田',   'hot_project', 1, 90);

-- 8. 业主种子
INSERT IGNORE INTO owner (id, name, owner_type, owner_scale, province, city, industry, opportunity_count, total_amount_wan) VALUES
 (1, '深圳市城市建设投资集团有限公司', '国央企',   '大型', '广东省', '深圳市', '城市基建', 3, 85000),
 (2, '比亚迪汽车工业有限公司',         '民企',     '大型', '广东省', '深圳市', '新能源汽车', 2, 32000),
 (3, '深圳市交通运输局',               '机关单位', '大型', '广东省', '深圳市', '交通基建', 2, 48000),
 (4, '中山大学深圳校区管理委员会',     '事业单位', '大型', '广东省', '深圳市', '高等教育', 1, 25000),
 (5, '广州南沙经济技术开发区管委会',   '机关单位', '中型', '广东省', '广州市', '产业园区', 1, 18000);

-- 9. 商机种子(覆盖三个 dataset)
INSERT IGNORE INTO opportunity (id, project_name, owner_name, owner_type, owner_scale, amount_wan, stage, region_province, region_city, project_type, unit_role, unit_name, current_version, dataset_type, source, body_excerpt, contact_summary, followup_log, published_at) VALUES
 (1, '深圳前海城市更新单元规划项目',     '深圳市城市建设投资集团有限公司', '国央企', '大型', 36000, '立项阶段', '广东省', '深圳市', '房建',     '施工总承包', '中铁某局',   'V2.0',   'project', '人工调研',   '前海合作区低空经济与城市更新融合示范项目, 总建筑面积约 80 万平方米, 包含甲级写字楼/科创孵化园/人才公寓。', '王经理 138****8888', '7/15 首次对接, 8/2 提供方案初稿', '2026-08-01 10:00:00'),
 (2, '比亚迪深圳总部数智中心二期',       '比亚迪汽车工业有限公司',         '民企',   '大型', 12000, '设计阶段', '广东省', '深圳市', '房建',     '设计联合体', '深圳设计总院','V2.0.3', 'project', '人工调研',   '比亚迪总部园区数智化升级二期, 含数据中心/智能办公区/屋顶光伏。', '李工 139****6666', '8/10 业主确认初设方向',          '2026-08-05 14:00:00'),
 (3, '深圳地铁 16 号线南延工程',         '深圳市交通运输局',               '机关单位', '大型', 28000, '可研阶段', '广东省', '深圳市', '市政交通', '勘察设计', '广州地铁院', 'V2.2.3', 'project', '人工调研',   '深圳地铁 16 号线南延, 全长约 12 公里, 设站 8 座, 投资估算 28 亿元。', '陈主任 135****5555', '7/22 报送可研报告',                '2026-07-15 09:00:00'),
 (4, '中山大学深圳校区海洋实验室',       '中山大学深圳校区管理委员会',     '事业单位', '大型', 25000, '筹备阶段', '广东省', '深圳市', '科研',     'EPC 总承包', '中建某局',   'V3.2.3', 'project', '人工调研',   '深圳校区海洋科学楼与实验水池, 总建筑面积 6.5 万平方米, 含 P3 实验室。', '吴主任 137****3333', '8/8 完成 EPC 招标策划',           '2026-08-08 11:00:00'),
 (5, '广州南沙智能网联汽车产业园',       '广州南沙经济技术开发区管委会',   '机关单位', '中型', 18000, '立项阶段', '广东省', '广州市', '产业园区', 'EPC 总承包', '中建某局',   'V2.0',   'proposed','人工调研',   '南沙区智能网联汽车产业园一期, 含整车工厂/研发中心/测试场。', '黄局 138****2222', '8/12 立项批复中',                  '2026-08-12 15:00:00'),
 (6, '广州天河低空经济产业基地',         '广州南沙经济技术开发区管委会',   '机关单位', '中型',  9500, '筹备阶段', '广东省', '广州市', '产业园区', '施工总承包', '中铁某局',   'V2.0',   'proposed','人工调研',   '天河区低空经济产业园(无人机/eVTOL 制造基地), 总建筑面积 12 万平方米。', '黄局 138****2222', '7/30 完成概念方案',                '2026-07-30 10:00:00'),
 (7, '深圳龙岗土拍地块综合开发',         '深圳市城市建设投资集团有限公司', '国央企', '大型', 16000, '筹备阶段', '广东省', '深圳市', '房建',     '投资合作', '深圳城投',   'V2.0',   'landtrade','人工调研',  '龙岗中心城土拍地块, 占地 4.2 万平米, 容积率 4.5, 拟建商业综合体。', '王经理 138****8888', '8/1 完成拿地方案',                 '2026-08-01 16:00:00');

-- 10. 商机版本历史(每个商机 1~3 条)
INSERT IGNORE INTO opportunity_version (id, opportunity_id, version, change_summary, operator, released_at) VALUES
 (1, 1, 'V1.0', '首版立项信息录入',          '调研员A', '2026-07-15 10:00:00'),
 (2, 1, 'V2.0', '补充甲级写字楼/科创园子项', '调研员A', '2026-08-01 10:00:00'),
 (3, 2, 'V1.0', '首版立项信息录入',          '调研员B', '2026-07-20 11:00:00'),
 (4, 2, 'V2.0', '新增数据中心模块',          '调研员B', '2026-07-30 14:00:00'),
 (5, 2, 'V2.0.3', '细化屋顶光伏容量 5MW',    '调研员B', '2026-08-05 14:00:00'),
 (6, 3, 'V1.0', '首版立项信息录入',          '调研员A', '2026-06-30 09:00:00'),
 (7, 3, 'V2.0', '明确 8 座站点选址',        '调研员A', '2026-07-10 09:00:00'),
 (8, 3, 'V2.2.3', '投资估算从 25 亿调至 28 亿', '调研员A', '2026-07-15 09:00:00'),
 (9, 4, 'V1.0', '首版立项信息录入',          '调研员C', '2026-07-25 11:00:00'),
 (10, 4, 'V2.0', '明确实验水池规模',         '调研员C', '2026-08-01 11:00:00'),
 (11, 4, 'V3.0', '新增 P3 实验室需求',       '调研员C', '2026-08-05 11:00:00'),
 (12, 4, 'V3.2.3', 'EPC 招标策划定稿',       '调研员C', '2026-08-08 11:00:00');

-- 11. 商机-标签关联
INSERT IGNORE INTO opportunity_tag (opportunity_id, tag_id, tag_kind) VALUES
 (1, (SELECT id FROM opportunity_tag_def WHERE code='hot_field_urban'),  'hot_field'),
 (1, (SELECT id FROM opportunity_tag_def WHERE code='hot_field_lowalt'), 'hot_field'),
 (1, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_science'),  'hot_project'),
 (2, (SELECT id FROM opportunity_tag_def WHERE code='hot_field_ne'),      'hot_field'),
 (2, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_private'), 'hot_project'),
 (2, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_digital'),  'hot_project'),
 (3, (SELECT id FROM opportunity_tag_def WHERE code='hot_field_lowalt'), 'hot_field'),
 (3, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_foreign'), 'hot_project'),
 (4, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_science'),  'hot_project'),
 (4, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_water'),    'hot_project'),
 (5, (SELECT id FROM opportunity_tag_def WHERE code='hot_field_ne'),      'hot_field'),
 (5, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_industrial'),'hot_project'),
 (6, (SELECT id FROM opportunity_tag_def WHERE code='hot_field_lowalt'), 'hot_field'),
 (6, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_industrial'),'hot_project'),
 (7, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_land'),     'hot_project'),
 (7, (SELECT id FROM opportunity_tag_def WHERE code='hot_proj_warehouse'),'hot_project');