-- ============================================================
-- 意向联系人表 (intent_contact)
-- 后台录入的甲方/设计师/建造商/分包 分组联系人
-- 前台公开接口仅返回脱敏占位, 后台管理接口返回真实信息
-- ============================================================

CREATE TABLE IF NOT EXISTS `intent_contact` (
    `id`          BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `intent_id`   BIGINT          NOT NULL                 COMMENT '意向 id',
    `group`       VARCHAR(32)     NOT NULL DEFAULT '甲方'  COMMENT '分组: 甲方/设计师/建造商/分包',
    `name`        VARCHAR(128)    DEFAULT NULL             COMMENT '姓名',
    `role`        VARCHAR(128)    DEFAULT NULL             COMMENT '职务',
    `department`  VARCHAR(128)    DEFAULT NULL             COMMENT '部门',
    `position`    VARCHAR(128)    DEFAULT NULL             COMMENT '职位',
    `phone`       VARCHAR(64)     DEFAULT NULL             COMMENT '电话',
    `mobile`      VARCHAR(64)     DEFAULT NULL             COMMENT '手机',
    `address`     VARCHAR(512)    DEFAULT NULL             COMMENT '地址',
    `remark`      TEXT            DEFAULT NULL             COMMENT '备注',
    `sort_order`  BIGINT          NOT NULL DEFAULT 0       COMMENT '排序(升序)',
    `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`  TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_ic_intent_group` (`intent_id`, `group`),
    KEY `idx_ic_group` (`group`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意向联系人(甲方/设计师/建造商/分包分组)';
