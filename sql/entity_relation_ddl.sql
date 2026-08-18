-- ============================================================
-- SSM 知识抽取三元组表 (entity_relation) — 开放域关系落库
-- 存储 LLM 抽取的实体关系全量(含证据/置信度), Neo4j 不可用时降级查询
-- ============================================================

CREATE TABLE IF NOT EXISTS `entity_relation` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `source_type`   VARCHAR(32)     NOT NULL                 COMMENT '源实体类型 company/person/project/region',
    `source_name`   VARCHAR(512)    NOT NULL                 COMMENT '源实体名称',
    `source_id`     BIGINT          DEFAULT NULL             COMMENT '源实体id(映射到系统实体则填, 否则 null)',
    `target_type`   VARCHAR(32)     NOT NULL                 COMMENT '目标实体类型',
    `target_name`   VARCHAR(512)    NOT NULL                 COMMENT '目标实体名称',
    `target_id`     BIGINT          DEFAULT NULL             COMMENT '目标实体id',
    `relation`      VARCHAR(64)     NOT NULL                 COMMENT '关系标识(开放, 如 OWNS/CONTRACT_WITH)',
    `relation_zh`   VARCHAR(64)     DEFAULT NULL             COMMENT '关系中文名',
    `confidence`    DECIMAL(4,2)    NOT NULL DEFAULT 0.8     COMMENT '置信度 0-1',
    `evidence`      VARCHAR(1024)   DEFAULT NULL             COMMENT '证据(原文句子)',
    `source_text_id` BIGINT         DEFAULT NULL             COMMENT '来源文本id(如 web_clue.id)',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    KEY `idx_er_source` (`source_type`, `source_name`),
    KEY `idx_er_target` (`target_type`, `target_name`),
    KEY `idx_er_relation` (`relation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识抽取三元组(开放域关系)';
