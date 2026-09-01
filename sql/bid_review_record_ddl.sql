-- ============================================================
-- 标讯审核记录表 (bid_review_record) — DDL
-- 记录标讯生命周期内每次状态变更(提交/审核/发布/下线), 供审核追溯
-- ============================================================

CREATE TABLE IF NOT EXISTS `bid_review_record` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `bid_id`        BIGINT          NOT NULL                 COMMENT '关联标讯 bid_notice.id',
    `action`        VARCHAR(32)     NOT NULL                 COMMENT '操作: submit/approve/reject/publish/offline/revert',
    `reviewer_id`   BIGINT          DEFAULT NULL             COMMENT '操作人 user_id',
    `reviewer_name` VARCHAR(128)    DEFAULT NULL             COMMENT '操作人姓名快照',
    `comment`       TEXT            DEFAULT NULL             COMMENT '意见/说明',
    `from_status`   VARCHAR(32)     DEFAULT NULL             COMMENT '变更前状态',
    `to_status`     VARCHAR(32)     DEFAULT NULL             COMMENT '变更后状态',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    PRIMARY KEY (`id`),
    KEY `idx_brr_bid` (`bid_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标讯审核/发布记录';
