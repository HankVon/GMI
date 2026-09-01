-- 标讯附件表
CREATE TABLE IF NOT EXISTS `bid_attachment` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `bid_id`      BIGINT NOT NULL COMMENT '标讯 id',
  `file_name`   VARCHAR(255) NOT NULL COMMENT '附件名',
  `local_path`  VARCHAR(512) DEFAULT NULL COMMENT 'uploads/ 相对路径',
  `remote_url`  VARCHAR(1024) DEFAULT NULL COMMENT '远程抓取 URL',
  `file_size`   BIGINT DEFAULT 0 COMMENT '文件大小(字节)',
  `file_type`   VARCHAR(32) DEFAULT NULL COMMENT '文件类型 pdf/docx/xlsx/zip',
  `remark`      VARCHAR(255) DEFAULT NULL COMMENT '备注',
  `uploaded_by` BIGINT DEFAULT NULL COMMENT '上传人 user_id',
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted`  TINYINT(1) DEFAULT 0,
  KEY `idx_bid_id` (`bid_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标讯附件';

-- 标讯标签定义表
CREATE TABLE IF NOT EXISTS `bid_tag_def` (
  `id`           BIGINT AUTO_INCREMENT PRIMARY KEY,
  `label`        VARCHAR(64) NOT NULL COMMENT '标签文本',
  `kind`         VARCHAR(16) DEFAULT 'category' COMMENT '展示样式: status/category/warning/danger/plain',
  `rule_keyword` VARCHAR(512) DEFAULT NULL COMMENT '自动打标关键字(逗号分隔)',
  `sort_order`   INT DEFAULT 0,
  `enabled`      TINYINT(1) DEFAULT 1,
  `created_at`   DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at`   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted`   TINYINT(1) DEFAULT 0,
  UNIQUE KEY `uk_label` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标讯标签定义';

-- 标讯-标签关联表
CREATE TABLE IF NOT EXISTS `bid_notice_tag` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `bid_id`      BIGINT NOT NULL COMMENT '标讯 id',
  `tag_id`      BIGINT NOT NULL COMMENT '标签 id',
  `created_by`  BIGINT DEFAULT NULL COMMENT '打标人 user_id',
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_bid_tag` (`bid_id`, `tag_id`),
  KEY `idx_tag_id` (`tag_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标讯-标签关联';
