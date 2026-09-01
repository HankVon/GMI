-- ============================================================
-- SSM 营销智能体 - GEO 监测模块 (geo)
--
-- 目标: 把「AI 引擎(豆包/DeepSeek/秘塔/百度AI搜索/腾讯元宝等)对
--       行业关键词的回答与引用」变成第 N 个数据源。
--   1. geo_engine   引擎配置(手动粘贴 / crawl4ai / OpenAI兼容API 三种适配器)
--   2. geo_keyword  监测关键词任务(行业词×公司词矩阵, 定时执行)
--   3. geo_mention  每次查询的回答快照 + 引用来源 + 提及实体 + 品牌可见性
--   4. mk_config    营销配置键值表(品牌词/行业词/风格等)
-- ============================================================

-- AI 引擎配置
CREATE TABLE IF NOT EXISTS `geo_engine` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `name`          VARCHAR(128)    NOT NULL                 COMMENT '引擎名称(豆包/DeepSeek/秘塔/百度AI搜索等)',
    `code`          VARCHAR(64)     NOT NULL                 COMMENT '引擎编码(doubao/deepseek/metaso/baiduai)',
    `url`           VARCHAR(1024)   DEFAULT NULL             COMMENT '网页访问地址',
    `adapter`       VARCHAR(32)     NOT NULL DEFAULT 'manual' COMMENT '采集适配器: manual手填/crawl4ai网页抓取/openai_api兼容API',
    `api_endpoint`  VARCHAR(1024)   DEFAULT NULL             COMMENT 'OpenAI兼容API端点(adapter=openai_api时)',
    `api_key`       VARCHAR(512)    DEFAULT NULL             COMMENT 'API密钥',
    `api_model`     VARCHAR(128)    DEFAULT NULL             COMMENT 'API模型名',
    `notes`         VARCHAR(512)    DEFAULT NULL             COMMENT '备注',
    `enabled`       TINYINT(1)      NOT NULL DEFAULT 1,
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_geo_engine_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='GEO监测-AI引擎配置';

-- 监测关键词任务
CREATE TABLE IF NOT EXISTS `geo_keyword` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `keyword`       VARCHAR(256)    NOT NULL                 COMMENT '监测关键词(问题)',
    `region`        VARCHAR(128)    DEFAULT NULL             COMMENT '地域限定(可选)',
    `category`      VARCHAR(128)    DEFAULT NULL             COMMENT '行业分类(可选)',
    `engines`       TEXT            DEFAULT NULL             COMMENT '绑定引擎JSON数组(空=全部启用引擎)',
    `priority`      INT             NOT NULL DEFAULT 5       COMMENT '优先级 1-10',
    `enabled`       TINYINT(1)      NOT NULL DEFAULT 1,
    `last_run_at`   DATETIME        DEFAULT NULL             COMMENT '上次执行时间',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_geo_kw_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='GEO监测-关键词任务';

-- 查询结果(回答快照 + 引用 + 实体 + 可见性)
CREATE TABLE IF NOT EXISTS `geo_mention` (
    `id`                BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `engine_id`         BIGINT          DEFAULT NULL             COMMENT '引擎id',
    `engine_name`       VARCHAR(128)    DEFAULT NULL             COMMENT '引擎名称快照',
    `keyword_id`        BIGINT          DEFAULT NULL             COMMENT '关键词任务id',
    `keyword`           VARCHAR(256)    NOT NULL                 COMMENT '查询词快照',
    `asked_at`          DATETIME        NOT NULL                 COMMENT '查询时间',
    `adapter`           VARCHAR(32)     DEFAULT 'manual'         COMMENT '采集方式',
    `answer_text`       LONGTEXT        DEFAULT NULL             COMMENT 'AI回答全文',
    `raw_text`          LONGTEXT        DEFAULT NULL             COMMENT '原始抓取文本(未解析)',
    `cited_sources`     JSON            DEFAULT NULL             COMMENT '被引用的来源列表 [{title,url,domain}]',
    `mentioned_entities` JSON           DEFAULT NULL             COMMENT '回答中提及的实体 [{name,type}] type=company/person/org',
    `brand_hits`        JSON            DEFAULT NULL             COMMENT '命中的品牌词列表',
    `self_visible`      TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '是否提及本公司',
    `self_rank`         INT             NOT NULL DEFAULT 0       COMMENT '本公司在回答中的提及位置(0=未提及)',
    `summary`           VARCHAR(1024)   DEFAULT NULL             COMMENT 'LLM总结(一句话)',
    `status`            VARCHAR(16)     NOT NULL DEFAULT 'pending' COMMENT '状态: pending待解析/parsed已解析/error失败',
    `error`             VARCHAR(1024)   DEFAULT NULL             COMMENT '错误信息',
    `elapsed_ms`        INT             DEFAULT NULL             COMMENT '耗时(毫秒)',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`        TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_geo_m_engine` (`engine_id`),
    KEY `idx_geo_m_kw` (`keyword_id`),
    KEY `idx_geo_m_asked` (`asked_at`),
    KEY `idx_geo_m_self` (`self_visible`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='GEO监测-查询结果';

-- 营销配置键值表(品牌词/行业词/风格等)
CREATE TABLE IF NOT EXISTS `mk_config` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `cfg_key`       VARCHAR(64)     NOT NULL                 COMMENT '配置键 brand_names/industry_keywords/content_style/geo_schedule',
    `cfg_value`     TEXT            DEFAULT NULL             COMMENT '配置值(JSON)',
    `description`   VARCHAR(256)   DEFAULT NULL             COMMENT '说明',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_mk_config_key` (`cfg_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='营销配置键值';
