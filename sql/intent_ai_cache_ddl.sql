CREATE TABLE IF NOT EXISTS `intent_ai_cache` (
    `id`             BIGINT          NOT NULL AUTO_INCREMENT COMMENT '主键',
    `intent_id`      BIGINT          NOT NULL COMMENT '意向 id intent_notice.id',
    `source`         VARCHAR(16)     NOT NULL DEFAULT 'llm' COMMENT '来源: llm/rule',
    `model`          VARCHAR(128)    DEFAULT NULL COMMENT '生成模型名',
    `analysis`       TEXT            DEFAULT NULL COMMENT '分析结果 JSON',
    `note`           VARCHAR(512)    DEFAULT NULL COMMENT '说明',
    `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`     TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'soft delete flag',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_ai_cache_intent` (`intent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意向AI研判结果缓存(按意向唯一, 用于复用已生成的分析)';
