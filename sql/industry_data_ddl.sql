-- ============================================================
-- SSM 行业数据标准库 (industry_data) — 对标建设通分项查询
--
-- 设计原则:
--   1. 所有公共渠道数据带 source + source_url + published_at 溯源
--   2. qualification/honor/credit_record/person_cert 支持 status 与
--      valid_to, 供"失效预警"运营功能使用
--   3. company_ic / company_legal_risk 为供应商工商/司法数据(JSON 结构化)
--   4. bid_open_record 在 bid_notice 之上扩展"按场次"的投标单位,
--      供同场竞标分析(COMPETES_WITH)使用
-- 对应文档: docs/gmi-renovation-guide.md B1
-- ============================================================

-- 单位资质台账(类别三段式: 类别_细分_等级)
CREATE TABLE IF NOT EXISTS `qualification` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `company_id`    BIGINT          NOT NULL                 COMMENT '单位id',
    `category`      VARCHAR(64)     NOT NULL                 COMMENT '资质大类(施工/勘察/设计/监理等)',
    `professional`  VARCHAR(128)    DEFAULT NULL             COMMENT '专业/细分',
    `level`         VARCHAR(32)     NOT NULL                 COMMENT '等级(甲/乙/丙/一级/二级/三级/不分等级)',
    `issue_org`     VARCHAR(128)    DEFAULT NULL             COMMENT '发证机关',
    `cert_no`       VARCHAR(128)    DEFAULT NULL             COMMENT '证书编号',
    `valid_from`    DATE            DEFAULT NULL             COMMENT '发证日期/有效期起',
    `valid_to`      DATE            DEFAULT NULL             COMMENT '有效期至',
    `status`        VARCHAR(16)     DEFAULT 'active'         COMMENT 'active/expiring/expired',
    `source`        VARCHAR(64)     DEFAULT 'manual'         COMMENT '来源 manual/import/sihku/...',
    `source_url`    VARCHAR(1024)   DEFAULT NULL             COMMENT '来源链接',
    `published_at`  DATETIME        DEFAULT NULL             COMMENT '采集/公示时间',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_qual_company` (`company_id`),
    KEY `idx_qual_category` (`category`),
    KEY `idx_qual_level` (`level`),
    KEY `idx_qual_valid_to` (`valid_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单位资质台账';

-- 单位荣誉台账
CREATE TABLE IF NOT EXISTS `honor` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `company_id`    BIGINT          NOT NULL                 COMMENT '单位id',
    `person_id`     BIGINT          DEFAULT NULL             COMMENT '关联人员id(荣誉可挂到人)',
    `title`         VARCHAR(512)    NOT NULL                 COMMENT '荣誉标题',
    `level`         VARCHAR(32)     DEFAULT NULL             COMMENT '等级(国家级/省/市/行业等)',
    `org`           VARCHAR(256)    DEFAULT NULL             COMMENT '授予机关/组织',
    `honored_at`    DATE            DEFAULT NULL             COMMENT '获奖日期',
    `source`        VARCHAR(64)     DEFAULT 'manual'         COMMENT '来源',
    `source_url`    VARCHAR(1024)   DEFAULT NULL             COMMENT '来源链接',
    `published_at`  DATETIME        DEFAULT NULL             COMMENT '采集/公示时间',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_honor_company` (`company_id`),
    KEY `idx_honor_person` (`person_id`),
    KEY `idx_honor_honored_at` (`honored_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单位荣誉台账';

-- 单位诚信/不良行为记录(双随机一公开等)
CREATE TABLE IF NOT EXISTS `credit_record` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `company_id`    BIGINT          NOT NULL                 COMMENT '单位id',
    `title`         VARCHAR(512)    NOT NULL                 COMMENT '记录标题/事由摘要',
    `reason`        TEXT            DEFAULT NULL             COMMENT '违规事由全文',
    `org`           VARCHAR(256)    DEFAULT NULL             COMMENT '公示机关',
    `published_at`  DATETIME        DEFAULT NULL             COMMENT '公示日期',
    `source`        VARCHAR(64)     DEFAULT 'manual'         COMMENT '来源',
    `source_url`    VARCHAR(1024)   DEFAULT NULL             COMMENT '来源链接',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_cr_company` (`company_id`),
    KEY `idx_cr_published_at` (`published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单位诚信/不良行为记录';

-- 人员证书
CREATE TABLE IF NOT EXISTS `person_cert` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `person_id`     BIGINT          NOT NULL                 COMMENT '人员id',
    `cert_type`     VARCHAR(64)     NOT NULL                 COMMENT '证书类型(建造师/监理/安全C证/职称/造价等)',
    `cert_no`       VARCHAR(128)    DEFAULT NULL             COMMENT '证书编号',
    `seal_no`       VARCHAR(128)    DEFAULT NULL             COMMENT '执业印章号',
    `major`         VARCHAR(128)    DEFAULT NULL             COMMENT '专业/注册类别',
    `valid_from`    DATE            DEFAULT NULL             COMMENT '有效期起',
    `valid_to`      DATE            DEFAULT NULL             COMMENT '有效期至',
    `status`        VARCHAR(16)     DEFAULT 'active'         COMMENT 'active/expiring/expired',
    `source`        VARCHAR(32)     DEFAULT 'manual'         COMMENT 'manual/import/external',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_pc_person` (`person_id`),
    KEY `idx_pc_type` (`cert_type`),
    KEY `idx_pc_valid_to` (`valid_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='人员证书';

-- 单位工商信息(供应商数据, JSON 结构化)
CREATE TABLE IF NOT EXISTS `company_ic` (
    `id`                BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `company_id`        BIGINT          NOT NULL                 COMMENT '单位id',
    `legal_rep`         VARCHAR(128)    DEFAULT NULL             COMMENT '法定代表人',
    `registered_capital` VARCHAR(64)    DEFAULT NULL             COMMENT '注册资本(原文, 含币种)',
    `est_date`          DATE            DEFAULT NULL             COMMENT '成立日期',
    `shareholders`      JSON            DEFAULT NULL             COMMENT '股东结构[{name,ratio,amount}]',
    `branches`          JSON            DEFAULT NULL             COMMENT '分支机构[{name,address}]',
    `investments`       JSON            DEFAULT NULL             COMMENT '对外投资[{name,ratio,amount}]',
    `changes`           JSON            DEFAULT NULL             COMMENT '变更记录[{date,item,from,to}]',
    `source`            VARCHAR(64)     DEFAULT 'manual'         COMMENT '来源 qcc/vendor/manual',
    `source_url`        VARCHAR(1024)   DEFAULT NULL             COMMENT '来源链接',
    `fetched_at`        DATETIME        DEFAULT NULL             COMMENT '抓取时间',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`        TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_ic_company` (`company_id`),
    KEY `idx_ic_legal_rep` (`legal_rep`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单位工商信息';

-- 单位司法与经营风险
CREATE TABLE IF NOT EXISTS `company_legal_risk` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `company_id`    BIGINT          NOT NULL                 COMMENT '单位id',
    `risk_type`     VARCHAR(32)     NOT NULL                 COMMENT '类型: lawsuit/judgment/executed/penalty/abnormal/pledge/...',
    `title`         VARCHAR(512)    NOT NULL                 COMMENT '风险标题',
    `court`         VARCHAR(256)    DEFAULT NULL             COMMENT '法院/机关',
    `amount`        DECIMAL(16,2)   DEFAULT NULL             COMMENT '涉案金额',
    `published_at`  DATETIME        DEFAULT NULL             COMMENT '发布日期',
    `source`        VARCHAR(64)     DEFAULT 'manual'         COMMENT '来源',
    `source_url`    VARCHAR(1024)   DEFAULT NULL             COMMENT '来源链接',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_clr_company` (`company_id`),
    KEY `idx_clr_type` (`risk_type`),
    KEY `idx_clr_published_at` (`published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单位司法与经营风险';

-- 开标记录(投标单位×场次, 同场竞标分析用)
CREATE TABLE IF NOT EXISTS `bid_open_record` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `bid_notice_id` BIGINT          NOT NULL                 COMMENT '关联 bid_notice.id(一场一公告)',
    `company_id`    BIGINT          NOT NULL                 COMMENT '投标单位id',
    `role`          VARCHAR(32)     DEFAULT 'bidder'         COMMENT '角色 bidder/winner(中标)',
    `amount`        DECIMAL(16,2)   DEFAULT NULL             COMMENT '投标报价',
    `discount_rate` DECIMAL(8,4)    DEFAULT NULL             COMMENT '下浮率(小数值, 如 0.05=5%)',
    `opened_at`     DATETIME        DEFAULT NULL             COMMENT '开标时间',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_bor_notice` (`bid_notice_id`),
    KEY `idx_bor_company` (`company_id`),
    KEY `idx_bor_opened_at` (`opened_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='开标记录(投标单位×场次)';
