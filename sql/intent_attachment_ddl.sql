CREATE TABLE IF NOT EXISTS `intent_attachment` (
    `id`             BIGINT          NOT NULL AUTO_INCREMENT COMMENT '主键',
    `intent_id`      BIGINT          NOT NULL COMMENT '意向 id intent_notice.id',
    `file_name`      VARCHAR(255)    NOT NULL COMMENT '文件名',
    `local_path`     VARCHAR(512)    DEFAULT NULL COMMENT '相对存储路径 uploads/...',
    `remote_url`     VARCHAR(1024)   DEFAULT NULL COMMENT '原网页附件地址',
    `file_size`      BIGINT          NOT NULL DEFAULT 0 COMMENT '文件大小(字节)',
    `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`     TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'soft delete flag',
    PRIMARY KEY (`id`),
    KEY `idx_att_intent` (`intent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意向公告附件';
