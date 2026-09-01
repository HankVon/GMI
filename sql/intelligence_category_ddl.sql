-- ============================================================
-- 情报分类字典表 (intelligence_category)
-- 行业/项目类型/阶段/数据集 四类目录(录入表单下拉/筛选区/统计分组)
-- ============================================================

CREATE TABLE IF NOT EXISTS `intelligence_category` (
    `id`          BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `category`    VARCHAR(32)     NOT NULL                 COMMENT '分类维度: industry/project_type/stage/dataset',
    `code`        VARCHAR(64)     NOT NULL                 COMMENT '编码',
    `label`       VARCHAR(128)    NOT NULL                 COMMENT '显示名',
    `parent_id`   BIGINT          DEFAULT NULL             COMMENT '父分类id(树形)',
    `sort_order`  BIGINT          NOT NULL DEFAULT 0       COMMENT '排序',
    `enabled`     TINYINT(1)      NOT NULL DEFAULT 1       COMMENT '启用 1/0',
    `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`  TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_cat_code` (`category`, `code`),
    KEY `idx_cat_parent` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情报分类字典(行业/项目类型/阶段/数据集)';
