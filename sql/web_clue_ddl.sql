-- ============================================================
-- SSM 网页线索/情报模块 (firecrawl 爬取) — DDL
-- ============================================================

-- 来源站点配置
CREATE TABLE IF NOT EXISTS `web_source` (
    `id`                BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `name`              VARCHAR(128)    NOT NULL                 COMMENT '来源名称(如:四川省公共资源交易中心)',
    `url`               VARCHAR(1024)   NOT NULL                 COMMENT '来源URL(列表页/种子页)',
    `description`       VARCHAR(512)    DEFAULT NULL             COMMENT '来源说明',
    `allow_domains`     TEXT            DEFAULT NULL             COMMENT '域名白名单(逗号分隔, 空=不限制域名)',
    `keywords`          TEXT            DEFAULT NULL             COMMENT '命中关键词(逗号分隔)',
    `exclude_keywords`  TEXT            DEFAULT NULL             COMMENT '排除关键词(逗号分隔)',
    `regions`           TEXT            DEFAULT NULL             COMMENT '地域限定(逗号分隔, 空=不限)',
    `scrape_mode`       VARCHAR(32)     NOT NULL DEFAULT 'crawl' COMMENT '抓取模式: scrape单页 / crawl整站',
    `max_depth`         BIGINT          NOT NULL DEFAULT 1       COMMENT 'crawl 最大深度',
    `max_pages`         BIGINT          NOT NULL DEFAULT 50      COMMENT 'crawl 最多页数',
    `include_urls`      TEXT            DEFAULT NULL             COMMENT '仅抓取匹配的URL模式(可选)',
    `query_config`      TEXT            DEFAULT NULL             COMMENT '查询式抓取配置JSON(OCR验证码/接口关键字等)',
    `llm_enhance`       VARCHAR(32)     NOT NULL DEFAULT 'filter' COMMENT 'LLM增强模式: filter/extract/summary/all/空=关闭',
    `enabled`           TINYINT(1)      NOT NULL DEFAULT 1       COMMENT '是否启用',
    `last_run_at`       DATETIME        DEFAULT NULL             COMMENT '上次抓取时间',
    `last_run_result`   VARCHAR(512)    DEFAULT NULL             COMMENT '上次抓取结果摘要',
    `last_error`        VARCHAR(1024)   DEFAULT NULL             COMMENT '上次抓取错误',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`        TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    KEY `idx_web_source_enabled` (`enabled`),
    KEY `idx_web_source_url` (`url`(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='网页线索来源站点配置';

-- 网页线索(仅通过筛选的网页入库)
CREATE TABLE IF NOT EXISTS `web_clue` (
    `id`                BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `url`               VARCHAR(1024)   NOT NULL                 COMMENT '网页URL(唯一)',
    `title`             VARCHAR(512)    NOT NULL                 COMMENT '网页标题',
    `summary`           TEXT            DEFAULT NULL             COMMENT '摘要',
    `content`           MEDIUMTEXT      DEFAULT NULL             COMMENT '正文(Markdown)',
    `source_id`         BIGINT          DEFAULT NULL             COMMENT '来源站点ID(web_source)',
    `source_name`       VARCHAR(128)    DEFAULT NULL             COMMENT '来源名称快照',
    `hit_keywords`      VARCHAR(512)    DEFAULT NULL             COMMENT '命中的关键词(逗号分隔)',
    `region`            VARCHAR(128)    DEFAULT NULL             COMMENT '命中的地域',
    `category`          VARCHAR(128)    DEFAULT NULL             COMMENT '分类(如:矿业/基建/项目)',
    `status`            VARCHAR(32)     NOT NULL DEFAULT 'accepted' COMMENT '线索状态: pending待入库/accepted已通过/rejected已拒绝/imported已转实体',
    `published_at`      DATETIME        DEFAULT NULL             COMMENT '网页发布时间',
    `fetched_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '抓取时间',
    `meta`              JSON            DEFAULT NULL             COMMENT '扩展信息(提取结果)',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`        TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_web_clue_url` (`url`(512)),
    KEY `idx_web_clue_status` (`status`),
    KEY `idx_web_clue_source` (`source_id`),
    KEY `idx_web_clue_region` (`region`),
    KEY `idx_web_clue_fetched` (`fetched_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='网页线索(仅通过筛选入库)';
