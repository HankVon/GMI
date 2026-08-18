-- 项目跟踪线索关联表: 把意向/招标/中标/施工线索增量归整到项目, 支持自动监控各阶段
CREATE TABLE IF NOT EXISTS project_clue (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id BIGINT NOT NULL COMMENT '项目ID',
    clue_type VARCHAR(16) NOT NULL COMMENT '线索类型: intent/web_clue/bid',
    clue_id BIGINT NOT NULL COMMENT '线索表主键',
    stage VARCHAR(32) NOT NULL DEFAULT '' COMMENT '阶段: investment/bidding/awarded/construction',
    title VARCHAR(512) DEFAULT '' COMMENT '线索标题',
    url VARCHAR(1024) DEFAULT '' COMMENT '线索原文URL',
    source_name VARCHAR(128) DEFAULT '' COMMENT '来源名称',
    region VARCHAR(128) DEFAULT '' COMMENT '地域',
    purchaser VARCHAR(255) DEFAULT '' COMMENT '采购人/业主单位',
    published_at DATETIME DEFAULT NULL COMMENT '实际发布时间',
    fetched_at DATETIME DEFAULT NULL COMMENT '抓取时间',
    confidence DECIMAL(4,2) NOT NULL DEFAULT 0 COMMENT '关联置信度 0~1',
    match_reason VARCHAR(255) DEFAULT '' COMMENT '匹配依据(地域/类别/单位)',
    is_read TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已读(跟踪提示)',
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_project_clue (project_id, clue_type, clue_id),
    KEY idx_clue (clue_type, clue_id),
    KEY idx_project_stage (project_id, stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
