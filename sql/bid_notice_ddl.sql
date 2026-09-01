-- ============================================================
-- SSM 中标公告模块 (bid_notice) — DDL
-- 从 web_clue 中标公告解析出的结构化数据, 用于人脉网络与关联分析
-- 含标讯后台管理字段(生命周期状态/分类维度/审核发布留痕)
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
    `notice_type`           VARCHAR(64)     DEFAULT NULL             COMMENT '公告类型(中标/成交/招标)',
    `agency`                VARCHAR(512)    DEFAULT NULL             COMMENT '采购代理机构名称',
    `source_id`             BIGINT          DEFAULT NULL             COMMENT '来源站点 id(web_source)',
    `source_name`           VARCHAR(128)    DEFAULT NULL             COMMENT '来源名称',
    `published_at`          DATETIME        DEFAULT NULL             COMMENT '公告发布时间(原始采集时间)',
    `fetched_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '解析时间',
    -- 生命周期状态(前台仅可见 published)
    `status`                VARCHAR(32)     NOT NULL DEFAULT 'published' COMMENT '生命周期状态:draft/pending/approved/rejected/published/offline',
    -- 分类/筛选维度(前台标签云数据源)
    `category`              VARCHAR(64)     DEFAULT NULL             COMMENT '项目分类(工程/服务/货物)',
    `industry`              VARCHAR(128)    DEFAULT NULL             COMMENT '行业类型(option_set:bid_industry)',
    `purchase_way`          VARCHAR(64)     DEFAULT NULL             COMMENT '采购方式(公开招标/邀请招标/竞争性谈判/单一来源/询价/其他)',
    `price_type`            VARCHAR(32)     DEFAULT NULL             COMMENT '询价方式(单价/总价)',
    `budget_min`            FLOAT           DEFAULT NULL             COMMENT '预算金额下限(万元)',
    `budget_max`            FLOAT           DEFAULT NULL             COMMENT '预算金额上限(万元)',
    -- 审核 / 发布留痕
    `submitted_by`          BIGINT          DEFAULT NULL             COMMENT '提交审核人 user_id',
    `submitted_at`          DATETIME        DEFAULT NULL             COMMENT '提交审核时间',
    `reviewed_by`           BIGINT          DEFAULT NULL             COMMENT '审核人 user_id',
    `reviewed_at`           DATETIME        DEFAULT NULL             COMMENT '审核时间',
    `review_comment`        TEXT            DEFAULT NULL             COMMENT '审核意见',
    `publish_at`            DATETIME        DEFAULT NULL             COMMENT '后台实际发布时间',
    `publish_by`            BIGINT          DEFAULT NULL             COMMENT '发布人 user_id',
    -- 创建/编辑留痕
    `created_by`            BIGINT          DEFAULT NULL             COMMENT '创建人 user_id(后台录入)',
    `updated_by`            BIGINT          DEFAULT NULL             COMMENT '最后编辑人 user_id',
    `created_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`            TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    KEY `idx_bid_clue` (`clue_id`),
    KEY `idx_bid_purchaser` (`purchaser_company_id`),
    KEY `idx_bid_published` (`published_at`),
    KEY `idx_bid_status` (`status`, `published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='中标公告(采购人→中标供应商 关系数据)';
