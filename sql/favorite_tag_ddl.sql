-- 收藏与标签表(A4 / B1) — 对标建设通收藏/竞争跟踪
-- 由 services/migrate.py 在启动时以 CREATE TABLE IF NOT EXISTS 幂等执行

CREATE TABLE IF NOT EXISTS `favorite` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`     BIGINT       NOT NULL COMMENT '用户ID',
  `entity_type` VARCHAR(32)  NOT NULL COMMENT '实体类型: company/project/person',
  `entity_id`   BIGINT       NOT NULL COMMENT '实体ID',
  `created_at`  DATETIME     DEFAULT NULL COMMENT 'create time',
  `updated_at`  DATETIME     DEFAULT NULL COMMENT 'update time',
  `is_deleted`  TINYINT(1)   DEFAULT 0 COMMENT 'soft delete flag',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_favorite_user_entity` (`user_id`, `entity_type`, `entity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户收藏(对标建设通收藏/竞争跟踪)';

CREATE TABLE IF NOT EXISTS `tag` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`     BIGINT       NOT NULL COMMENT '用户ID',
  `entity_type` VARCHAR(32)  NOT NULL COMMENT '实体类型',
  `entity_id`   BIGINT       NOT NULL COMMENT '实体ID',
  `tag`         VARCHAR(64)  NOT NULL COMMENT '标签文本',
  `created_at`  DATETIME     DEFAULT NULL COMMENT 'create time',
  `updated_at`  DATETIME     DEFAULT NULL COMMENT 'update time',
  `is_deleted`  TINYINT(1)   DEFAULT 0 COMMENT 'soft delete flag',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tag_user_entity` (`user_id`, `entity_type`, `entity_id`, `tag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户个人标签';
