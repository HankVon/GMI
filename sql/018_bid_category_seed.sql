-- ============================================================
-- 标讯分类选项集 seed — 供前台 FilterSidebar 标签云动态加载
-- 选项集: bid_industry(行业) / bid_purchase_way(采购方式)
--        bid_notice_type(公告类型) / bid_category(项目分类) / bid_price_type(询价方式)
-- 幂等: 选项集按 code 唯一, 选项项按 (option_set_id, value) 唯一
-- ============================================================

-- 1. 选项集主表(幂等)
INSERT INTO `option_set` (`code`, `name`, `description`)
SELECT 'bid_industry', '行业类型', '标讯行业分类(前台标签云)'
WHERE NOT EXISTS (SELECT 1 FROM `option_set` WHERE `code` = 'bid_industry');

INSERT INTO `option_set` (`code`, `name`, `description`)
SELECT 'bid_purchase_way', '采购方式', '公开招标/邀请招标/竞争性谈判/单一来源/询价/其他'
WHERE NOT EXISTS (SELECT 1 FROM `option_set` WHERE `code` = 'bid_purchase_way');

INSERT INTO `option_set` (`code`, `name`, `description`)
SELECT 'bid_notice_type', '公告类型', '招标/中标/成交/变更/终止/其他'
WHERE NOT EXISTS (SELECT 1 FROM `option_set` WHERE `code` = 'bid_notice_type');

INSERT INTO `option_set` (`code`, `name`, `description`)
SELECT 'bid_category', '项目分类', '工程/服务/货物'
WHERE NOT EXISTS (SELECT 1 FROM `option_set` WHERE `code` = 'bid_category');

INSERT INTO `option_set` (`code`, `name`, `description`)
SELECT 'bid_price_type', '询价方式', '单价/总价'
WHERE NOT EXISTS (SELECT 1 FROM `option_set` WHERE `code` = 'bid_price_type');

-- 2. 选项项 seed: 通过子查询反查 option_set_id, 按 (set_code, value) 幂等
INSERT INTO `option_item` (`option_set_id`, `value`, `label`, `sort_order`, `color`)
SELECT s.`id`, t.`value`, t.`label`, t.`sort_order`, t.`color`
FROM `option_set` s
JOIN (
    SELECT '工程' AS `value`, '工程' AS `label`, 1 AS `sort_order`, '#a51c30' AS `color`
    UNION ALL SELECT '服务', '服务', 2, '#a51c30'
    UNION ALL SELECT '货物', '货物', 3, '#a51c30'
) t
WHERE s.`code` = 'bid_category'
  AND NOT EXISTS (
      SELECT 1 FROM `option_item` oi
      WHERE oi.`option_set_id` = s.`id` AND oi.`value` = t.`value` AND oi.`is_deleted` = 0
  );

INSERT INTO `option_item` (`option_set_id`, `value`, `label`, `sort_order`, `color`)
SELECT s.`id`, t.`value`, t.`label`, t.`sort_order`, t.`color`
FROM `option_set` s
JOIN (
    SELECT '公开招标' AS `value`, '公开招标' AS `label`, 1 AS `sort_order`, NULL AS `color`
    UNION ALL SELECT '邀请招标', '邀请招标', 2, NULL
    UNION ALL SELECT '竞争性谈判', '竞争性谈判', 3, NULL
    UNION ALL SELECT '单一来源', '单一来源', 4, NULL
    UNION ALL SELECT '询价', '询价', 5, NULL
    UNION ALL SELECT '其他', '其他', 6, NULL
) t
WHERE s.`code` = 'bid_purchase_way'
  AND NOT EXISTS (
      SELECT 1 FROM `option_item` oi
      WHERE oi.`option_set_id` = s.`id` AND oi.`value` = t.`value` AND oi.`is_deleted` = 0
  );

INSERT INTO `option_item` (`option_set_id`, `value`, `label`, `sort_order`, `color`)
SELECT s.`id`, t.`value`, t.`label`, t.`sort_order`, t.`color`
FROM `option_set` s
JOIN (
    SELECT '招标' AS `value`, '招标' AS `label`, 1 AS `sort_order`, NULL AS `color`
    UNION ALL SELECT '中标', '中标', 2, NULL
    UNION ALL SELECT '成交', '成交', 3, NULL
    UNION ALL SELECT '变更', '变更', 4, NULL
    UNION ALL SELECT '终止', '终止', 5, NULL
    UNION ALL SELECT '其他', '其他', 6, NULL
) t
WHERE s.`code` = 'bid_notice_type'
  AND NOT EXISTS (
      SELECT 1 FROM `option_item` oi
      WHERE oi.`option_set_id` = s.`id` AND oi.`value` = t.`value` AND oi.`is_deleted` = 0
  );

INSERT INTO `option_item` (`option_set_id`, `value`, `label`, `sort_order`, `color`)
SELECT s.`id`, t.`value`, t.`label`, t.`sort_order`, t.`color`
FROM `option_set` s
JOIN (
    SELECT '单价' AS `value`, '单价' AS `label`, 1 AS `sort_order`, NULL AS `color`
    UNION ALL SELECT '总价', '总价', 2, NULL
) t
WHERE s.`code` = 'bid_price_type'
  AND NOT EXISTS (
      SELECT 1 FROM `option_item` oi
      WHERE oi.`option_set_id` = s.`id` AND oi.`value` = t.`value` AND oi.`is_deleted` = 0
  );

-- 行业类型(20项, 对标 GB/T 4754 大类)
INSERT INTO `option_item` (`option_set_id`, `value`, `label`, `sort_order`, `color`)
SELECT s.`id`, t.`value`, t.`label`, t.`sort_order`, t.`color`
FROM `option_set` s
JOIN (
    SELECT '农、林、牧、渔业' AS `value`, '农、林、牧、渔业' AS `label`, 1 AS `sort_order`, NULL AS `color`
    UNION ALL SELECT '采矿业', '采矿业', 2, NULL
    UNION ALL SELECT '制造业', '制造业', 3, NULL
    UNION ALL SELECT '电力、燃气及水的生产和供应业', '电力、燃气及水的生产和供应业', 4, NULL
    UNION ALL SELECT '建筑业', '建筑业', 5, NULL
    UNION ALL SELECT '交通运输、仓储和邮政业', '交通运输、仓储和邮政业', 6, NULL
    UNION ALL SELECT '信息传输、计算机服务和软件业', '信息传输、计算机服务和软件业', 7, NULL
    UNION ALL SELECT '批发和零售业', '批发和零售业', 8, NULL
    UNION ALL SELECT '住宿和餐饮业', '住宿和餐饮业', 9, NULL
    UNION ALL SELECT '金融业', '金融业', 10, NULL
    UNION ALL SELECT '房地产业', '房地产业', 11, NULL
    UNION ALL SELECT '租赁和商务服务业', '租赁和商务服务业', 12, NULL
    UNION ALL SELECT '科学研究、技术服务和地质勘查业', '科学研究、技术服务和地质勘查业', 13, NULL
    UNION ALL SELECT '水利、环境和公共设施管理业', '水利、环境和公共设施管理业', 14, NULL
    UNION ALL SELECT '居民服务和其他服务业', '居民服务和其他服务业', 15, NULL
    UNION ALL SELECT '教育', '教育', 16, NULL
    UNION ALL SELECT '卫生、社会保障和社会福利业', '卫生、社会保障和社会福利业', 17, NULL
    UNION ALL SELECT '文化、体育和娱乐业', '文化、体育和娱乐业', 18, NULL
    UNION ALL SELECT '公共管理和社会组织', '公共管理和社会组织', 19, NULL
    UNION ALL SELECT '国际组织', '国际组织', 20, NULL
) t
WHERE s.`code` = 'bid_industry'
  AND NOT EXISTS (
      SELECT 1 FROM `option_item` oi
      WHERE oi.`option_set_id` = s.`id` AND oi.`value` = t.`value` AND oi.`is_deleted` = 0
  );
