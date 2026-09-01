-- ============================================================
-- SSM 营销智能体 - 数据内容工厂 (content)
--
-- 目标: 把中台数据(招标/中标/意向/业绩统计)自动生成「被AI引擎
--       引用的内容资产」, 走 草稿→审核→发布 流程。
--   1. content_channel  发布渠道(官网/公众号/知乎/百家号等)
--   2. content_asset    内容资产(报告/FAQ/公司档案/文章)
-- ============================================================

-- 发布渠道
CREATE TABLE IF NOT EXISTS `content_channel` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `name`          VARCHAR(128)    NOT NULL                 COMMENT '渠道名称(官网/公众号/知乎/百家号)',
    `code`          VARCHAR(64)     NOT NULL                 COMMENT '渠道编码 official_site/wechat/zhihu/baijiahao',
    `url_prefix`    VARCHAR(1024)   DEFAULT NULL             COMMENT '发布URL前缀',
    `enabled`       TINYINT(1)      NOT NULL DEFAULT 1,
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_content_channel_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='内容发布渠道';

-- 内容资产(营销智能体的执行产物)
CREATE TABLE IF NOT EXISTS `content_asset` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `title`         VARCHAR(512)    NOT NULL                 COMMENT '内容标题',
    `kind`          VARCHAR(32)     NOT NULL DEFAULT 'article' COMMENT '类型: industry_report行业报告/faq问答/company_profile公司档案/article文章',
    `channel`       VARCHAR(64)     DEFAULT NULL             COMMENT '目标渠道编码',
    `channel_name`  VARCHAR(128)    DEFAULT NULL             COMMENT '渠道名称快照',
    `summary`       VARCHAR(1024)   DEFAULT NULL             COMMENT '摘要(用于分发)',
    `content`       LONGTEXT        DEFAULT NULL             COMMENT '正文(Markdown)',
    `source_data`   JSON            DEFAULT NULL             COMMENT '生成依据的数据统计JSON(可溯源)',
    `status`        VARCHAR(16)     NOT NULL DEFAULT 'draft' COMMENT '状态: draft草稿/review待审核/published已发布/rejected已驳回',
    `review_comment` VARCHAR(512)   DEFAULT NULL             COMMENT '审核意见',
    `published_url` VARCHAR(1024)   DEFAULT NULL             COMMENT '发布URL(模拟)',
    `created_by`    BIGINT          DEFAULT NULL             COMMENT '创建人id(智能体=0)',
    `created_by_name` VARCHAR(128)  DEFAULT NULL             COMMENT '创建人名称',
    `geo_feedback`  JSON            DEFAULT NULL             COMMENT 'GEO反馈(发布后被引用情况, 回链geo_mention)',
    `published_at`  DATETIME        DEFAULT NULL             COMMENT '发布时间',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_content_kind` (`kind`),
    KEY `idx_content_status` (`status`),
    KEY `idx_content_channel` (`channel`),
    KEY `idx_content_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='内容资产(营销智能体执行产物)';
