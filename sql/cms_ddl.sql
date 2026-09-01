-- ============================================================
-- 前台首页内容配置 CMS 表 + 默认种子 + 菜单/权限种子
-- 版本: v1.0.0
-- 说明: 全部 IF NOT EXISTS / NOT EXISTS 幂等, 重复执行安全。
--       前台 /public/home-config 拉取 enabled=1 的区块; 未配置时
--       前端 Home.vue 回退到内置静态数据, 后台配置后即接管展示。
-- ============================================================

-- 1. 区块主表
CREATE TABLE IF NOT EXISTS cms_block (
  id BIGINT NOT NULL AUTO_INCREMENT,
  page_key VARCHAR(32) NOT NULL DEFAULT 'home' COMMENT '所属前台页面',
  block_key VARCHAR(64) NOT NULL COMMENT '区块标识',
  title VARCHAR(256) NOT NULL COMMENT '区块标题',
  description VARCHAR(512) DEFAULT NULL COMMENT '区块说明',
  enabled TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  sort_order INT DEFAULT 0 COMMENT '区块排序',
  extra JSON DEFAULT NULL COMMENT '区块级扩展配置',
  is_deleted TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_page_block (page_key, block_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前台页面配置区块';

-- 2. 区块条目表
CREATE TABLE IF NOT EXISTS cms_block_item (
  id BIGINT NOT NULL AUTO_INCREMENT,
  block_id BIGINT NOT NULL COMMENT '所属区块id',
  item_key VARCHAR(128) DEFAULT NULL COMMENT '条目标识',
  title VARCHAR(256) NOT NULL COMMENT '标题/名称',
  subtitle VARCHAR(512) DEFAULT NULL COMMENT '副标题/描述',
  icon VARCHAR(128) DEFAULT NULL COMMENT '图标名',
  link VARCHAR(512) DEFAULT NULL COMMENT '跳转地址',
  meta JSON DEFAULT NULL COMMENT '差异化字段',
  enabled TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  sort_order INT DEFAULT 0 COMMENT '展示排序',
  is_deleted TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_block (block_id, enabled, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='首页配置区块条目';

-- 3. 默认区块种子(与前台 Home.vue 内置内容一致, 保证首启展示)
INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'top_guide', '顶部引导条', '首页顶部欢迎语与导航链接', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='top_guide');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'quick_links', '图标入口', 'Banner 下方 6 个快捷功能入口', 1, 2
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='quick_links');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'certs', '资质认证条', '首页资质与认证展示条', 1, 3
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='certs');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'cta', 'CTA Banner', '红色号召横幅(标题/副文案/链接)', 1, 4
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='cta');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'fields', '地质服务领域', '领域 Tabs + 示例项目', 1, 5
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='fields');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'partners', '国际地学合作', '全球地学机构合作卡片', 1, 6
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='partners');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'products', '地质技术与装备', '钻探/物探/测试/监测产品卡', 1, 7
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='products');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'activities', '地质学术研讨', '研讨活动卡片', 1, 8
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='activities');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'certifications', '资质认证体系', '认证分类与机构 Logo 阵列', 1, 9
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='certifications');

INSERT INTO cms_block (block_key, title, description, enabled, sort_order)
SELECT 'recommends', '推荐地勘单位', '首页右栏推荐单位', 1, 10
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE block_key='recommends');

-- 4. 顶部引导条默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'welcome', '您好，欢迎来到地质与产业情报数据中台！', NULL, NULL, NULL, NULL, 1, 1
FROM cms_block b WHERE b.block_key='top_guide'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='welcome');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'nav_intel', '信息动态', NULL, NULL, '/site/intelligence', NULL, 1, 2
FROM cms_block b WHERE b.block_key='top_guide'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='nav_intel');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'nav_data', '数据中心', NULL, NULL, '/site/data-center', NULL, 1, 3
FROM cms_block b WHERE b.block_key='top_guide'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='nav_data');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'nav_sol', '解决方案', NULL, NULL, '/site/solutions', NULL, 1, 4
FROM cms_block b WHERE b.block_key='top_guide'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='nav_sol');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'nav_contact', '联系我们', NULL, NULL, '/site/contact', NULL, 1, 5
FROM cms_block b WHERE b.block_key='top_guide'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='nav_contact');

-- 5. 图标入口默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'bid', '地质标讯', '地勘招投标与中标动态', 'Tickets', '/site/data-center/overview?tab=bid', JSON_OBJECT('bg', 'linear-gradient(135deg, #e01a3c 0%, #c8102e 100%)'), 1, 1
FROM cms_block b WHERE b.block_key='quick_links'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='bid');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'company', '地勘单位', '地质单位 360° 多维画像', 'OfficeBuilding', '/site/data-center/companies', JSON_OBJECT('bg', 'linear-gradient(135deg, #ff6a6a 0%, #c8102e 100%)'), 1, 2
FROM cms_block b WHERE b.block_key='quick_links'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='company');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'person', '地质人才', '专业人员任职与参与项目', 'User', '/site/data-center/persons', JSON_OBJECT('bg', 'linear-gradient(135deg, #4cc0a4 0%, #2f8f5b 100%)'), 1, 3
FROM cms_block b WHERE b.block_key='quick_links'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='person');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'equip', '技术装备', '钻探 · 物探 · 测试装备', 'Box', '/site/solutions', JSON_OBJECT('bg', 'linear-gradient(135deg, #b08d57 0%, #8a6a36 100%)'), 1, 4
FROM cms_block b WHERE b.block_key='quick_links'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='equip');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'cert', '资质认证', '地勘资质与信用认证', 'Medal', '/site/about', JSON_OBJECT('bg', 'linear-gradient(135deg, #9c6bff 0%, #6633cc 100%)'), 1, 5
FROM cms_block b WHERE b.block_key='quick_links'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='cert');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'oversea', '海外矿产', '全球矿产资源数据库', 'Promotion', '/site/intelligence', JSON_OBJECT('bg', 'linear-gradient(135deg, #5b9bf6 0%, #2c4ec4 100%)'), 1, 6
FROM cms_block b WHERE b.block_key='quick_links'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='oversea');

-- 6. 资质认证条默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'grade', '地勘甲级资质', '勘查资质等级核验', 'Lock', NULL, JSON_OBJECT('color', '#c8102e'), 1, 1
FROM cms_block b WHERE b.block_key='certs'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='grade');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'safe', '安全生产许可', '野外作业安全认证', 'Star', NULL, JSON_OBJECT('color', '#c8102e'), 1, 2
FROM cms_block b WHERE b.block_key='certs'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='safe');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'cma', 'CMA 计量认证', '检测实验室资质', 'Trophy', NULL, JSON_OBJECT('color', '#2f8f5b'), 1, 3
FROM cms_block b WHERE b.block_key='certs'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='cma');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'iso', 'ISO 体系认证', '国际标准体系', 'Lock', NULL, JSON_OBJECT('color', '#b08d57'), 1, 4
FROM cms_block b WHERE b.block_key='certs'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='iso');

-- 7. CTA Banner 默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'main', '地矿智库', '地质大数据平台 4.0 上线：构建矿产资源全生命周期情报网络', NULL, '/site/contact', NULL, 1, 1
FROM cms_block b WHERE b.block_key='cta'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='main');

-- 8. 地质服务领域默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'survey', '基础地质调查', '1:25 万区调 · 构造专项', NULL, '/site/data-center/projects', JSON_OBJECT('location', '湖南 · 郴州'), 1, 1
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='survey');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'ore', '矿产勘查开发', '钻探 12000m · 选矿试验', NULL, '/site/data-center/projects', JSON_OBJECT('location', '四川 · 马尔康'), 1, 2
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='ore');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'hazard', '地质灾害防治', '抗滑桩 + 锚索 · 监测预警', NULL, '/site/data-center/projects', JSON_OBJECT('location', '四川 · 汶川'), 1, 3
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='hazard');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'hydro', '水文地质勘察', '水文测井 · 抽水试验', NULL, '/site/data-center/projects', JSON_OBJECT('location', '甘肃 · 河西走廊'), 1, 4
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='hydro');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'eng', '工程地质勘察', '岩土测试 · 桩基勘察', NULL, '/site/data-center/projects', JSON_OBJECT('location', '北京'), 1, 5
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='eng');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'geothermal', '地热与新能源', '地温场测试 · 热储层分析', NULL, '/site/data-center/projects', JSON_OBJECT('location', '广东 · 丰顺'), 1, 6
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='geothermal');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'rock', '岩土工程治理', '边坡加固 · 基坑支护', NULL, '/site/data-center/projects', JSON_OBJECT('location', '重庆'), 1, 7
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='rock');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'monitor', '地质环境监测', 'InSAR 监测 · 地下水监测', NULL, '/site/data-center/projects', JSON_OBJECT('location', '陕西 · 西安'), 1, 8
FROM cms_block b WHERE b.block_key='fields'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='monitor');

-- 9. 国际地学合作默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'usgs', '美国地质调查局', 'USGS · 全球矿产资源数据库', NULL, '/site/intelligence', JSON_OBJECT('short', 'US', 'members', 320, 'bg', 'linear-gradient(135deg, #4c79c4 0%, #1f3e85 100%)'), 1, 1
FROM cms_block b WHERE b.block_key='partners'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='usgs');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'eu', '欧洲地质调查联盟', 'EuroGeoSurveys · 欧洲地学网络', NULL, '/site/intelligence', JSON_OBJECT('short', 'EU', 'members', 210, 'bg', 'linear-gradient(135deg, #4c84c4 0%, #1f4a85 100%)'), 1, 2
FROM cms_block b WHERE b.block_key='partners'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='eu');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'asean', '中国—东盟地学中心', 'CAGS · 东南亚地质合作', NULL, '/site/intelligence', JSON_OBJECT('short', 'AS', 'members', 180, 'bg', 'linear-gradient(135deg, #ffa157 0%, #c8102e 100%)'), 1, 3
FROM cms_block b WHERE b.block_key='partners'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='asean');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'jp', '日本地质调查所', 'AIST · 东亚灾害与矿产物探', NULL, '/site/intelligence', JSON_OBJECT('short', 'JP', 'members', 95, 'bg', 'linear-gradient(135deg, #ff8293 0%, #c8314b 100%)'), 1, 4
FROM cms_block b WHERE b.block_key='partners'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='jp');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'ru', '俄罗斯地质调查所', 'VSEGEI · 独联体矿产数据库', NULL, '/site/intelligence', JSON_OBJECT('short', 'RU', 'members', 64, 'bg', 'linear-gradient(135deg, #ce73ff 0%, #7c3aae 100%)'), 1, 5
FROM cms_block b WHERE b.block_key='partners'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='ru');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'af', '非洲地学数据平台', 'Africa Geoscience Network', NULL, '/site/intelligence', JSON_OBJECT('short', 'AF', 'members', 48, 'bg', 'linear-gradient(135deg, #f5c147 0%, #b88a1f 100%)'), 1, 6
FROM cms_block b WHERE b.block_key='partners'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='af');

-- 10. 地质技术与装备默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'drill', '钻探装备', '岩芯钻机 · 绳索取芯 · 定向钻进 成套方案', 'Box', '/site/solutions', JSON_OBJECT('bg', 'linear-gradient(135deg, #ff6a6a 0%, #c8102e 100%)'), 1, 1
FROM cms_block b WHERE b.block_key='products'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='drill');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'geo', '物探仪器', '电法 · 地震 · 磁法 · 高精度测量设备', 'Watermelon', '/site/solutions', JSON_OBJECT('bg', 'linear-gradient(135deg, #4cc0a4 0%, #2f8f5b 100%)'), 1, 2
FROM cms_block b WHERE b.block_key='products'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='geo');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'lab', '测试化验', '岩矿测试 · 水质分析 · CMA 实验室服务', 'Coin', '/site/solutions', JSON_OBJECT('bg', 'linear-gradient(135deg, #ffaf63 0%, #d27825 100%)'), 1, 3
FROM cms_block b WHERE b.block_key='products'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='lab');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'remote', '遥感监测', 'InSAR 地质灾害监测 · 无人机航测', 'Promotion', '/site/solutions', JSON_OBJECT('bg', 'linear-gradient(135deg, #b08dff 0%, #6633cc 100%)'), 1, 4
FROM cms_block b WHERE b.block_key='products'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='remote');

-- 11. 地质学术研讨默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'deep', '深地资源探测与智能勘查研讨会', '聚焦深部找矿、智能钻探与三维地质建模的技术进展与应用。', NULL, '/site/solutions', JSON_OBJECT('tag', '深地探测', 'date', '2026 · 09 · 成都', 'bg', 'linear-gradient(135deg, #2c66b8 0%, #1a3a6e 100%)'), 1, 1
FROM cms_block b WHERE b.block_key='activities'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='deep');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'hazard_forum', '地质灾害防治与风险管控论坛', '探讨滑坡、泥石流、岩溶塌陷的监测预警与工程防治体系。', NULL, '/site/solutions', JSON_OBJECT('tag', '灾害防治', 'date', '2026 · 10 · 重庆', 'bg', 'linear-gradient(135deg, #1f8f5b 0%, #115f3b 100%)'), 1, 2
FROM cms_block b WHERE b.block_key='activities'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='hazard_forum');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'hydro_forum', '水文地质与水资源可持续利用', '面向地下水保护、水源地评价与地热开发的前沿对话。', NULL, '/site/solutions', JSON_OBJECT('tag', '水文地质', 'date', '2026 · 11 · 武汉', 'bg', 'linear-gradient(135deg, #c8761a 0%, #8a4d0c 100%)'), 1, 3
FROM cms_block b WHERE b.block_key='activities'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='hydro_forum');

-- 12. 资质认证体系默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'mgt', '自然资源部', NULL, NULL, '/site/about', JSON_OBJECT('short', '资', 'color', '#c8102e'), 1, 1
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='mgt');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'cgs', '中国地质调查局', NULL, NULL, '/site/about', JSON_OBJECT('short', '调', 'color', '#c8102e'), 1, 2
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='cgs');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'cma2', 'CMA 计量认证', NULL, NULL, '/site/about', JSON_OBJECT('short', 'C', 'color', '#c8102e'), 1, 3
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='cma2');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'iso9001', 'ISO 9001', NULL, NULL, '/site/about', JSON_OBJECT('short', '9', 'color', '#2f8f5b'), 1, 4
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='iso9001');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'iso14001', 'ISO 14001', NULL, NULL, '/site/about', JSON_OBJECT('short', '4', 'color', '#c8102e'), 1, 5
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='iso14001');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'aaa', 'AAA 信用', NULL, NULL, '/site/about', JSON_OBJECT('short', 'A', 'color', '#ff9800'), 1, 6
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='aaa');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'high_tech', '高新技术企业', NULL, NULL, '/site/about', JSON_OBJECT('short', '高', 'color', '#c8102e'), 1, 7
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='high_tech');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'special', '专精特新', NULL, NULL, '/site/about', JSON_OBJECT('short', '专', 'color', '#2f8f5b'), 1, 8
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='special');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'green', '绿色勘查规范', NULL, NULL, '/site/about', JSON_OBJECT('short', '绿', 'color', '#b08d57'), 1, 9
FROM cms_block b WHERE b.block_key='certifications'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='green');

-- 13. 推荐地勘单位默认条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'cgs_rec', '中国地质调查局', '基础地质调查 · 北京', NULL, '/site/data-center/companies', NULL, 1, 1
FROM cms_block b WHERE b.block_key='recommends'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='cgs_rec');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'wsy_rec', '中冶集团武汉勘察院', '岩土工程勘察 · 武汉', NULL, '/site/data-center/companies', NULL, 1, 2
FROM cms_block b WHERE b.block_key='recommends'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='wsy_rec');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'sc_rec', '四川省地矿局', '矿产勘查开发 · 成都', NULL, '/site/data-center/companies', NULL, 1, 3
FROM cms_block b WHERE b.block_key='recommends'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='sc_rec');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'coal_rec', '中煤地质总局水文局', '水文地质 · 邯郸', NULL, '/site/data-center/companies', NULL, 1, 4
FROM cms_block b WHERE b.block_key='recommends'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='coal_rec');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'metal_rec', '中国有色金属矿产调查中心', '矿产地质调查 · 北京', NULL, '/site/data-center/companies', NULL, 1, 5
FROM cms_block b WHERE b.block_key='recommends'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='metal_rec');

-- ============================================================
-- 菜单 + 权限码种子: 管理后台「首页配置」
-- ============================================================
-- 1. 菜单: 首页配置(/admin/cms)
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'menu_cms_home', '首页配置', 'menu', '/admin/cms',
       (SELECT id FROM sys_permission WHERE code='menu_admin' LIMIT 1), 10
WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='menu_cms_home');

-- 2. 权限点(挂到 menu_cms_home 下)
INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'cms_home_view', '首页配置-查看', 'permission', '',
       (SELECT id FROM sys_permission WHERE code='menu_cms_home' LIMIT 1), 1
WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='cms_home_view');

INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order)
SELECT 'cms_home_edit', '首页配置-编辑', 'permission', '',
       (SELECT id FROM sys_permission WHERE code='menu_cms_home' LIMIT 1), 2
WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='cms_home_edit');

-- 3. admin 角色全量关联(超管全见, 幂等)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r
JOIN sys_permission p
  ON p.code IN ('menu_cms_home','cms_home_view','cms_home_edit')
WHERE r.code = 'admin'
  AND NOT EXISTS (
    SELECT 1 FROM sys_role_permission x WHERE x.role_id=r.id AND x.permission_id=p.id
  );

-- 4. 拥有 menu_rbac 权限的角色(即管理后台可见者)同步关联(幂等)
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT DISTINCT rp.role_id, p.id
FROM sys_role_permission rp
JOIN sys_permission rp_code ON rp_code.id = rp.permission_id AND rp_code.code = 'menu_rbac'
JOIN sys_permission p ON p.code IN ('menu_cms_home','cms_home_view','cms_home_edit')
WHERE NOT EXISTS (
  SELECT 1 FROM sys_role_permission x WHERE x.role_id=rp.role_id AND x.permission_id=p.id
);

-- ============================================================
-- 关于我们(about) 默认种子
-- ============================================================
INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'about', 'highlights', '简介数据', '关于我们-简介高亮数据', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='about' AND block_key='highlights');

INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'about', 'values', '核心价值观', '关于我们-价值观卡片', 1, 2
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='about' AND block_key='values');

INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'about', 'timeline', '发展历程', '关于我们-时间线', 1, 3
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='about' AND block_key='timeline');

INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'about', 'team_stats', '团队统计', '关于我们-底部数据统计', 1, 4
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='about' AND block_key='team_stats');

-- 简介数据条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'found', '成立时间', '2023 年', NULL, NULL, NULL, 1, 1
FROM cms_block b WHERE b.page_key='about' AND b.block_key='highlights'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='found');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'clients', '服务客户', '60+ 政企单位', NULL, NULL, NULL, 1, 2
FROM cms_block b WHERE b.page_key='about' AND b.block_key='highlights'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='clients');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'data', '数据规模', '70+ 万条', NULL, NULL, NULL, 1, 3
FROM cms_block b WHERE b.page_key='about' AND b.block_key='highlights'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='data');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'region', '覆盖地域', '全国 90+ 省级区', NULL, NULL, NULL, 1, 4
FROM cms_block b WHERE b.page_key='about' AND b.block_key='highlights'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='region');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'freq', '更新频率', '7×24 小时', NULL, NULL, NULL, 1, 5
FROM cms_block b WHERE b.page_key='about' AND b.block_key='highlights'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='freq');

-- 价值观条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'data_driven', '数据驱动', '以真实、可验证的公开数据为基础，拒绝主观臆测。', 'Aim', NULL, NULL, 1, 1
FROM cms_block b WHERE b.page_key='about' AND b.block_key='values'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='data_driven');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'safe', '安全合规', '仅采集公开数据源，严格数据治理与权限管控。', 'Lock', NULL, NULL, 1, 2
FROM cms_block b WHERE b.page_key='about' AND b.block_key='values'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='safe');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'ai', 'AI 赋能', '用大模型与图谱技术放大人脑研判效率。', 'Cpu', NULL, NULL, 1, 3
FROM cms_block b WHERE b.page_key='about' AND b.block_key='values'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='ai');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'service', '专业服务', '行业专家 + 工程团队，持续陪跑运营。', 'Service', NULL, NULL, 1, 4
FROM cms_block b WHERE b.page_key='about' AND b.block_key='values'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='service');

-- 发展历程条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, '2023', '平台立项', '面向地质产业情报的首版数据采集与画像系统上线。', NULL, NULL, JSON_OBJECT('year', '2023'), 1, 1
FROM cms_block b WHERE b.page_key='about' AND b.block_key='timeline'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='2023');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, '2024', '图谱升级', '引入知识图谱与关系抽取，构建招投标关联网络。', NULL, NULL, JSON_OBJECT('year', '2024'), 1, 2
FROM cms_block b WHERE b.page_key='about' AND b.block_key='timeline'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='2024');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, '2025', 'AI 报告', '接入大模型，实现商情报告与公关路径自动生成。', NULL, NULL, JSON_OBJECT('year', '2025'), 1, 3
FROM cms_block b WHERE b.page_key='about' AND b.block_key='timeline'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='2025');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, '2026', '规模运营', '服务 60+ 政企单位，数据规模突破 70 万条。', NULL, NULL, JSON_OBJECT('year', '2026'), 1, 4
FROM cms_block b WHERE b.page_key='about' AND b.block_key='timeline'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='2026');

-- 团队统计条目
INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'unit', '60+', '服务单位', NULL, NULL, NULL, 1, 1
FROM cms_block b WHERE b.page_key='about' AND b.block_key='team_stats'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='unit');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'rows', '70万+', '数据条目', NULL, NULL, NULL, 1, 2
FROM cms_block b WHERE b.page_key='about' AND b.block_key='team_stats'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='rows');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'regions', '90+', '覆盖省级区', NULL, NULL, NULL, 1, 3
FROM cms_block b WHERE b.page_key='about' AND b.block_key='team_stats'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='regions');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'cycle', '24h', '更新周期', NULL, NULL, NULL, 1, 4
FROM cms_block b WHERE b.page_key='about' AND b.block_key='team_stats'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='cycle');

-- ============================================================
-- 联系我们(contact) 默认种子
-- ============================================================
INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'contact', 'contact_info', '联系信息卡片', '联系我们-邮箱/电话/地址/服务时间', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='contact' AND block_key='contact_info');

INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'contact', 'contact_note', '隐私说明', '联系我们-底部隐私承诺', 1, 2
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='contact' AND block_key='contact_note');

INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'contact', 'map_address', '来访地址', '联系我们-地图占位地址', 1, 3
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='contact' AND block_key='map_address');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'email', '邮箱', 'contact@gmi.example', 'Message', NULL, NULL, 1, 1
FROM cms_block b WHERE b.page_key='contact' AND b.block_key='contact_info'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='email');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'phone', '电话', '400-000-0000', 'Phone', NULL, NULL, 1, 2
FROM cms_block b WHERE b.page_key='contact' AND b.block_key='contact_info'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='phone');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'address', '地址', '成都市 · 高新区', 'Location', NULL, NULL, 1, 3
FROM cms_block b WHERE b.page_key='contact' AND b.block_key='contact_info'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='address');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'hours', '服务时间', '工作日 9:00 - 18:00', 'Clock', NULL, NULL, 1, 4
FROM cms_block b WHERE b.page_key='contact' AND b.block_key='contact_info'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='hours');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'note', '我们承诺：仅将您的信息用于本次咨询对接，绝不外泄。如需了解数据合规详情，请邮件联系合规团队。', NULL, NULL, NULL, NULL, 1, 1
FROM cms_block b WHERE b.page_key='contact' AND b.block_key='contact_note'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='note');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'addr', '成都 · 高新区 · 天府软件园', '（示意地图，可接入高德 / 百度地图组件）', NULL, NULL, NULL, 1, 1
FROM cms_block b WHERE b.page_key='contact' AND b.block_key='map_address'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='addr');

-- ============================================================
-- 解决方案(solutions) 默认种子
-- ============================================================
INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'solutions', 'solutions', '解决方案卡片', '解决方案-六大能力卡片', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='solutions' AND block_key='solutions');

INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'solutions', 'cases', '应用场景', '解决方案-典型应用场景', 1, 2
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='solutions' AND block_key='cases');

INSERT INTO cms_block (page_key, block_key, title, description, enabled, sort_order)
SELECT 'solutions', 'flow', '交付流程', '解决方案-交付流程步骤', 1, 3
WHERE NOT EXISTS (SELECT 1 FROM cms_block WHERE page_key='solutions' AND block_key='flow');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'portrait', '单位全息画像', '聚合工商、中标、人员、地域等多源数据，构建单位 360° 档案。', 'OfficeBuilding', NULL, JSON_OBJECT('features', JSON_ARRAY('工商与经营信息','中标与项目历史','关键人员关系','风险与异常预警')), 1, 1
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='solutions'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='portrait');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'network', '情报关系网络', '基于知识图谱挖掘业主、竞对、合作方与同地域关联脉络。', 'Connection', NULL, JSON_OBJECT('features', JSON_ARRAY('招投标关联','人脉路径推演','同地域线索','可争取意向识别')), 1, 2
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='solutions'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='network');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'ai_report', 'AI 商情分析', '大模型自动抽取开放关系、生成商情报告与公关路径建议。', 'Cpu', NULL, JSON_OBJECT('features', JSON_ARRAY('智能报告生成','公关路径规划','意图公告匹配','趋势研判')), 1, 3
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='solutions'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='ai_report');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'intent', '线索意图监测', '定期扫描意向公告，精准匹配本单位业务与地域能力。', 'Search', NULL, JSON_OBJECT('features', JSON_ARRAY('意向公告扫描','能力匹配引擎','实时提醒','商机评分')), 1, 4
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='solutions'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='intent');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'visual', '态势可视化', '态势大屏与钻取分析，将海量数据转化为决策依据。', 'DataAnalysis', NULL, JSON_OBJECT('features', JSON_ARRAY('实时大屏','多维钻取','自定义看板','移动端同步')), 1, 5
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='solutions'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='visual');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'harvest', '数据采集治理', '自动爬取公开数据源，结构化清洗入库，保障数据质量。', 'Monitor', NULL, JSON_OBJECT('features', JSON_ARRAY('全网采集','结构化清洗','质量校验','增量更新')), 1, 6
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='solutions'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='harvest');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'gov', '自然资源部门招商研判', '通过同地域采购线索与业主画像，辅助产业招商与项目谋划。', NULL, NULL, JSON_OBJECT('tag', '政府'), 1, 1
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='cases'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='gov');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'soe', '工程企业商机发现', '实时匹配招标公告与自身资质，提升中标命中率。', NULL, NULL, JSON_OBJECT('tag', '国企'), 1, 2
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='cases'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='soe');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'agency', '咨询机构情报服务', '批量生成行业与单位商情报告，支撑咨询服务交付。', NULL, NULL, JSON_OBJECT('tag', '服务商'), 1, 3
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='cases'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='agency');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'park', '产业园区企业画像', '构建入园企业全息档案，支撑精准招商与运营。', NULL, NULL, JSON_OBJECT('tag', '园区'), 1, 4
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='cases'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='park');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'req', '需求对齐', '梳理业务场景与数据维度，明确情报目标。', NULL, NULL, NULL, 1, 1
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='flow'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='req');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'ingest', '数据接入', '配置爬虫与数据源，结构化入库治理。', NULL, NULL, NULL, 1, 2
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='flow'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='ingest');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'model', '建模分析', '构建知识图谱与 AI 分析模型。', NULL, NULL, NULL, 1, 3
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='flow'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='model');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'deliver', '可视化交付', '部署大屏与报告，培训使用。', NULL, NULL, NULL, 1, 4
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='flow'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='deliver');

INSERT INTO cms_block_item (block_id, item_key, title, subtitle, icon, link, meta, enabled, sort_order)
SELECT b.id, 'ops', '持续运营', '定期更新与优化，闭环迭代。', NULL, NULL, NULL, 1, 5
FROM cms_block b WHERE b.page_key='solutions' AND b.block_key='flow'
  AND NOT EXISTS (SELECT 1 FROM cms_block_item i WHERE i.block_id=b.id AND i.item_key='ops');
