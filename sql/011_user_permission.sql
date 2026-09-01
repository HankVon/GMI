-- ============================================================
-- 用户级功能直授 — 「分发权限」的例外授权(绕过角色, 直接给用户挂功能权限)
-- 版本: v1.0.0
-- 说明: 纯新增表, 不影响现有角色-权限体系; 未配置时不改变任何行为。
-- ============================================================

CREATE TABLE IF NOT EXISTS `sys_user_permission` (
    `id`            BIGINT      NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `user_id`       BIGINT      NOT NULL                 COMMENT '用户ID',
    `permission_id` BIGINT      NOT NULL                 COMMENT '权限ID',
    `granted_by`    BIGINT      DEFAULT NULL             COMMENT '授权人用户ID',
    `created_at`    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `is_deleted`    TINYINT(1)  NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_perm` (`user_id`, `permission_id`),
    KEY `idx_permission_id` (`permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户级直授权限表';
