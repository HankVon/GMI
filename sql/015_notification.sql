-- ============================================================
-- 站内通知表 — 线索过期/项目进度变更/新中标等提醒
-- 版本: v1.0.0
-- 说明: 纯新增表, 不影响现有功能
-- ============================================================

CREATE TABLE IF NOT EXISTS `sys_notification` (
    `id`           BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`      BIGINT      NOT NULL                 COMMENT '接收用户ID',
    `type`         VARCHAR(32) NOT NULL DEFAULT 'system' COMMENT '类型:clue_expire/progress/bid_new/system',
    `title`        VARCHAR(255) NOT NULL                COMMENT '标题',
    `content`      TEXT                                 COMMENT '内容',
    `related_type` VARCHAR(32) DEFAULT NULL             COMMENT '关联实体类型',
    `related_id`   BIGINT      DEFAULT NULL             COMMENT '关联实体ID',
    `is_read`      TINYINT(1)  NOT NULL DEFAULT 0       COMMENT '已读:0-否,1-是',
    `status`       VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '处理状态:pending/processing/resolved/closed',
    `is_deleted`   TINYINT(1)  NOT NULL DEFAULT 0       COMMENT '软删除',
    `created_at`   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_read` (`user_id`, `is_read`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='站内通知表';
