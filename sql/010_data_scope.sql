-- ============================================================
-- 数据范围(Data Scope)扩展 — 「分发权限」的数据级授权
-- 版本: v1.0.0
-- 说明: 所有新增列默认 NULL, 存量用户/角色行为不变(未启用数据范围);
--       仅当管理员显式配置数据范围后才生效, 对现有状态零干扰。
-- ============================================================

-- 1. sys_role 增加角色级默认数据范围
ALTER TABLE `sys_role`
    ADD COLUMN `data_scope_rule` VARCHAR(16) DEFAULT NULL
        COMMENT '数据范围规则:ALL/DEPT_TREE/DEPT_ONLY/OWN/CUSTOM, NULL=未启用' AFTER `description`,
    ADD COLUMN `scope_dept_ids` JSON DEFAULT NULL
        COMMENT '部门范围ID列表(CUSTOM/DEPT_* 时)' AFTER `data_scope_rule`;

-- 2. sys_user 增加用户级覆盖数据范围
ALTER TABLE `sys_user`
    ADD COLUMN `data_scope_rule` VARCHAR(16) DEFAULT NULL
        COMMENT '用户级数据范围规则, NULL=继承角色' AFTER `person_id`,
    ADD COLUMN `scope_dept_ids` JSON DEFAULT NULL
        COMMENT '用户级部门范围ID列表' AFTER `data_scope_rule`;

-- 3. 对象级数据授权表(分发权限时把具体对象授权给用户, 并作为图谱授权边数据源)
CREATE TABLE IF NOT EXISTS `sys_data_grant` (
    `id`           BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `user_id`      BIGINT       NOT NULL                 COMMENT '被授权用户ID',
    `entity_type`  VARCHAR(32)  NOT NULL                 COMMENT '实体类型:project/company/bid',
    `entity_id`    BIGINT       NOT NULL                 COMMENT '实体ID',
    `grant_type`   VARCHAR(16)  NOT NULL DEFAULT 'view'  COMMENT '授权类型:view查看/own负责',
    `expire_at`    DATETIME     DEFAULT NULL             COMMENT '过期时间(NULL=永久)',
    `granted_by`   BIGINT       DEFAULT NULL             COMMENT '授权人用户ID',
    `created_at`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `is_deleted`   TINYINT(1)   NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_entity` (`user_id`, `entity_type`, `entity_id`, `grant_type`),
    KEY `idx_user` (`user_id`),
    KEY `idx_entity` (`entity_type`, `entity_id`),
    KEY `idx_expire` (`expire_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对象级数据授权表';
