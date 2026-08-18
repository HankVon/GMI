-- ============================================================
-- SSM 中标公告模块 (bid_notice) — DDL
-- 从 web_clue 中标公告解析出的结构化数据, 用于人脉网络与关联分析
-- ============================================================

CREATE TABLE IF NOT EXISTS `bid_notice` (
    `id`                    BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `clue_id`               BIGINT          DEFAULT NULL             COMMENT '来源线索 web_clue.id',
    `title`                 VARCHAR(512)    NOT NULL                 COMMENT '公告标题',
    `url`                   VARCHAR(1024)   DEFAULT NULL             COMMENT '公告链接',
    `purchaser`             VARCHAR(512)    DEFAULT NULL             COMMENT '采购人/业主名称',
    `purchaser_company_id`  BIGINT          DEFAULT NULL             COMMENT '匹配的公司id',
    `region`                VARCHAR(128)    DEFAULT NULL             COMMENT '采购区域(省)',
    `meta`                  JSON            DEFAULT NULL             COMMENT '供应商明细[ {supplier, supplier_company_id, amount, address} ]',
    `notice_type`           VARCHAR(64)     DEFAULT NULL             COMMENT '公告类型(中标/成交)',
    `source_name`           VARCHAR(128)    DEFAULT NULL             COMMENT '来源名称',
    `published_at`          DATETIME        DEFAULT NULL             COMMENT '公告发布时间',
    `fetched_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '解析时间',
    `created_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`            TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    KEY `idx_bid_clue` (`clue_id`),
    KEY `idx_bid_purchaser` (`purchaser_company_id`),
    KEY `idx_bid_published` (`published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='中标公告(采购人→中标供应商 关系数据)';
