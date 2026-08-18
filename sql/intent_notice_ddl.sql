-- ============================================================
-- SSM 意向性信息结构化表 (intent_notice)
-- 从政务源(发改委/交通厅/自然资源局等)抓取的意向性项目信息,
-- 结构化后供「提前获取招标信息」推荐
-- ============================================================

CREATE TABLE IF NOT EXISTS `intent_notice` (
    `id`             BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `clue_id`        BIGINT          DEFAULT NULL             COMMENT '来源线索 web_clue.id',
    `source_id`      BIGINT          DEFAULT NULL             COMMENT '来源 web_source.id',
    `title`          VARCHAR(512)    NOT NULL                 COMMENT '标题',
    `url`            VARCHAR(1024)   DEFAULT NULL             COMMENT '原文链接',
    `dept`           VARCHAR(256)    DEFAULT NULL             COMMENT '发布部门(如 四川省发改委基础设施发展处)',
    `project_type`   VARCHAR(128)    DEFAULT NULL             COMMENT '项目类型(地质勘察/地灾治理/生态修复等)',
    `industry`       VARCHAR(128)    DEFAULT NULL             COMMENT '行业(交通/能源/住建等)',
    `amount`         DECIMAL(16,2)   DEFAULT NULL             COMMENT '预算金额(万元)',
    `region`         VARCHAR(128)    DEFAULT NULL             COMMENT '地域',
    `province`       VARCHAR(64)     DEFAULT NULL,
    `city`           VARCHAR(64)     DEFAULT NULL,
    `county`         VARCHAR(64)     DEFAULT NULL,
    `contact`        VARCHAR(256)    DEFAULT NULL             COMMENT '联系人/电话',
    `start_date`     DATETIME        DEFAULT NULL             COMMENT '开工时间(拟)',
    `published_at`   DATETIME        DEFAULT NULL             COMMENT '发布时间',
    `status`         VARCHAR(32)     DEFAULT 'new'            COMMENT '状态: new/qualified/skip/expired',
    `keywords`       VARCHAR(512)    DEFAULT NULL             COMMENT '命中关键词',
    `matched_entity` VARCHAR(512)    DEFAULT NULL             COMMENT '匹配到的人脉实体(JSON: [{type,id,name}])',
    `raw_text`       TEXT            DEFAULT NULL             COMMENT '原文摘要(结构化来源)',
    `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`     TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_in_clue` (`clue_id`),
    KEY `idx_in_type` (`project_type`),
    KEY `idx_in_region` (`province`, `city`),
    KEY `idx_in_status` (`status`),
    KEY `idx_in_published` (`published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意向性项目信息(结构化, 提前获取招标)';
